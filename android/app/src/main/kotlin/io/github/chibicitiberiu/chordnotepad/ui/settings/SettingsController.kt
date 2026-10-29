package io.github.chibicitiberiu.chordnotepad.ui.settings

import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.bridge.SettingsState
import io.github.chibicitiberiu.chordnotepad.bridge.VoicingEditorState
import io.github.chibicitiberiu.chordnotepad.bridge.VoicingPreset
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/** Where the Settings screen is in its life. */
enum class SettingsPhase {
    /** Not started: [SettingsController.start] sends `begin_settings_edit`. */
    NEW,

    /** `begin_settings_edit` sent, waiting for an active `VoicingEditorState`. */
    OPENING,

    /** Editing. */
    EDITING,

    /** `save_settings` sent: the edit ends (closed) or comes back with an error. */
    SAVING,

    /** Saved or cancelled: the screen goes away. */
    CLOSED,
}

/** The screen's pages (help/settings.rst: General, Playback, and the Voicings editor). */
enum class SettingsPage { GENERAL, PLAYBACK, VOICINGS }

/**
 * Which page is open. On phones [page] null is the list of pages; on tablets
 * (two panes) the list is always there and null shows General.
 * [voicingDetail] is the voicing form on phones (list → form).
 */
@Serializable
data class SettingsNav(val page: SettingsPage? = null, val voicingDetail: Boolean = false) {
    /** The page the content pane shows. */
    fun shown(twoPane: Boolean): SettingsPage? = page ?: if (twoPane) SettingsPage.GENERAL else null

    /**
     * Back: from the voicing form to the list (unless both show, [split]),
     * from a page to the list of pages (phones), else null: leave the screen.
     */
    fun back(twoPane: Boolean, split: Boolean): SettingsNav? = when {
        page == SettingsPage.VOICINGS && voicingDetail && !split -> copy(voicingDetail = false)
        page != null && !twoPane -> SettingsNav()
        else -> null
    }
}

/** A dialog the Settings screen shows over itself. */
@Serializable
sealed interface SettingsDialog {
    /** Leave without saving? */
    @Serializable
    data object Discard : SettingsDialog

    /** Remove voicing [name]? (`remove_confirm`) */
    @Serializable
    data class RemoveVoicing(val name: String) : SettingsDialog

    /** Rename voicing [name]. */
    @Serializable
    data class Rename(val name: String) : SettingsDialog

    /** Switch to [model], dropping the edits? (`model_confirm`) */
    @Serializable
    data class ChangeModel(val model: String) : SettingsDialog

    /** Replace the parameters with a preset? (`load_confirm`) */
    @Serializable
    data class LoadPreset(val label: String, val group: String) : SettingsDialog
}

/**
 * What the Settings screen shows, apart from the voicings editor state.
 *
 * @property initial The values the screen opened with ([changed] compares).
 * @property invalidNumbers Number fields whose text isn't a value in range (Save is off).
 * @property voicingsTouched A voicing command other than select was sent.
 * @property saveRevision The editor revision when Save was sent (a newer active state = refused).
 */
@Serializable
data class SettingsUi(
    val phase: SettingsPhase = SettingsPhase.NEW,
    val nav: SettingsNav = SettingsNav(),
    val draft: SettingsDraft? = null,
    val initial: SettingsDraft? = null,
    val invalidNumbers: Set<NumberSetting> = emptySet(),
    val voicingsTouched: Boolean = false,
    val dialog: SettingsDialog? = null,
    val saveRevision: Int = -1,
) {
    /** Whether leaving now would lose something. */
    val changed: Boolean get() = draft != initial || voicingsTouched

    /** Whether Save can be sent (the voicings' validity is Python's gate). */
    val canSave: Boolean get() = phase == SettingsPhase.EDITING && draft != null && invalidNumbers.isEmpty()
}

/** The voicings editor as the form draws it: the state plus local edits not echoed yet. */
data class EditorView(val state: VoicingEditorState, val values: JsonObject)

/**
 * The Settings screen's state holder: the settings edit's life (begin, save,
 * cancel, the discard question), the General/Playback draft, navigation, and
 * the voicing commands. Plain Kotlin, fed by the repository's flows
 * ([onSettings], [onEditor], [onError]); [snapshot]/[restore] keep it across
 * a rotation (the edit itself lives on in Python).
 */
class SettingsController(private val commands: ScreenCommands, saved: SettingsUi = SettingsUi()) {
    private val _ui = MutableStateFlow(saved)
    private val _editor = MutableStateFlow<EditorView?>(null)
    private val pending = PendingEdits()
    private var limits: SettingsState? = null

    /** The screen's state. */
    val ui: StateFlow<SettingsUi> = _ui.asStateFlow()

    /** The voicings editor (null until an active state arrives). */
    val editor: StateFlow<EditorView?> = _editor.asStateFlow()

    /** Open the edit (once; a restored controller already has one). [needSchema]: also ask for the form schema. */
    fun start(needSchema: Boolean) {
        if (needSchema) commands.requestVoicingEditorSchema()
        if (_ui.value.phase != SettingsPhase.NEW) return
        commands.beginSettingsEdit()
        _ui.update { it.copy(phase = SettingsPhase.OPENING) }
    }

    /** A `SettingsState` arrived: the draft starts from the first one. */
    fun onSettings(state: SettingsState) {
        limits = state
        if (_ui.value.draft == null) {
            val draft = SettingsDraft.of(state)
            _ui.update { it.copy(draft = draft, initial = draft) }
        }
    }

    /** A `VoicingEditorState` arrived. */
    fun onEditor(state: VoicingEditorState) {
        if (state.active) pending.onState(state.values)
        val ui = _ui.value
        var next = ui
        when (ui.phase) {
            SettingsPhase.OPENING -> if (state.active) next = ui.copy(phase = SettingsPhase.EDITING)
            // The edit is gone though nobody ended it: the process was
            // restarted under a restored screen. Open a new one.
            SettingsPhase.EDITING -> if (!state.active) {
                pending.clear()
                commands.beginSettingsEdit()
                next = ui.copy(phase = SettingsPhase.OPENING, voicingsTouched = false)
            }
            SettingsPhase.SAVING -> if (!state.active) next = ui.copy(phase = SettingsPhase.CLOSED, dialog = null)
            SettingsPhase.NEW, SettingsPhase.CLOSED -> Unit
        }
        // Save refused ("Invalid Voicing"): the bad voicing is selected now. Its
        // UserError may arrive before or after this state ([onError]).
        if (state.active && next.saveRevision >= 0 && state.revision > next.saveRevision &&
            (next.phase == SettingsPhase.SAVING || next.phase == SettingsPhase.EDITING)
        ) {
            next = next.copy(
                phase = SettingsPhase.EDITING,
                nav = SettingsNav(SettingsPage.VOICINGS, voicingDetail = state.selected != null),
                saveRevision = -1,
            )
        }
        if (state.active && state.selected == null && next.nav.voicingDetail) {
            next = next.copy(nav = next.nav.copy(voicingDetail = false))
        }
        _ui.value = next
        _editor.value = if (state.active) EditorView(state, pending.applyTo(state.values)) else null
    }

    /**
     * The session reported an error: a Save that failed leaves the screen
     * open (the refusal's state, if any, still moves to the bad voicing).
     */
    fun onError() {
        _ui.update { if (it.phase == SettingsPhase.SAVING) it.copy(phase = SettingsPhase.EDITING) else it }
    }

    // -- saving and leaving -------------------------------------------------------

    /** Save: the draft's values when changed (null keeps the config's), then Python validates every voicing. */
    fun save() {
        val ui = _ui.value
        if (!ui.canSave) return
        val values = ui.draft?.takeIf { it != ui.initial }?.toValues()
        _ui.value = ui.copy(phase = SettingsPhase.SAVING, saveRevision = _editor.value?.state?.revision ?: -1)
        commands.saveSettings(values)
    }

    /** Cancel / Back out of the screen: ask first when something changed. */
    fun requestClose() {
        val ui = _ui.value
        when {
            ui.phase == SettingsPhase.SAVING || ui.phase == SettingsPhase.CLOSED -> Unit
            ui.changed -> _ui.value = ui.copy(dialog = SettingsDialog.Discard)
            else -> cancel()
        }
    }

    /** Leave without saving. */
    fun cancel() {
        if (_ui.value.phase == SettingsPhase.CLOSED) return
        commands.cancelSettingsEdit()
        pending.clear()
        _ui.update { it.copy(phase = SettingsPhase.CLOSED, dialog = null) }
    }

    /** System Back: up one page, or [requestClose]. */
    fun back(twoPane: Boolean, split: Boolean) {
        val ui = _ui.value
        val up = ui.nav.back(twoPane, split)
        if (up != null) _ui.value = ui.copy(nav = up) else requestClose()
    }

    // -- navigation and the draft -------------------------------------------------

    /** Show [page]. */
    fun openPage(page: SettingsPage) = _ui.update { it.copy(nav = SettingsNav(page)) }

    /** Change the draft. */
    fun updateDraft(change: (SettingsDraft) -> SettingsDraft) =
        _ui.update { ui -> ui.draft?.let { ui.copy(draft = change(it)) } ?: ui }

    /** Switch the draft's notation (the key is respelled). */
    fun setNotation(notation: String) {
        val l = limits ?: return
        updateDraft { it.withNotation(notation, l) }
    }

    /** A number field's text: a whole number in range goes into the draft, anything else blocks Save. */
    fun setNumber(setting: NumberSetting, text: String) {
        val l = limits ?: return
        val value = text.trim().toIntOrNull()?.takeIf { it in setting.range(l) }
        _ui.update { ui ->
            val draft = ui.draft ?: return@update ui
            if (value == null) {
                ui.copy(invalidNumbers = ui.invalidNumbers + setting)
            } else {
                ui.copy(draft = setting.set(draft, value), invalidNumbers = ui.invalidNumbers - setting)
            }
        }
    }

    // -- dialogs --------------------------------------------------------------------

    /** Close the dialog without doing anything. */
    fun dismissDialog() = _ui.update { it.copy(dialog = null) }

    /** Do what the open dialog asks ([newName] for Rename). */
    fun confirmDialog(newName: String = "") {
        val dialog = _ui.value.dialog ?: return
        _ui.update { it.copy(dialog = null) }
        when (dialog) {
            SettingsDialog.Discard -> cancel()
            is SettingsDialog.RemoveVoicing -> touch { commands.removeVoicing(dialog.name) }
            is SettingsDialog.Rename -> if (newName != dialog.name) touch { commands.renameVoicing(dialog.name, newName) }
            is SettingsDialog.ChangeModel -> setModel(dialog.model)
            is SettingsDialog.LoadPreset -> {
                pending.clear()
                touch { commands.loadVoicingPreset(VoicingPreset(dialog.label, dialog.group)) }
            }
        }
    }

    // -- the voicings editor --------------------------------------------------------

    /** Show voicing [name] in the form (on phones, open the form). */
    fun selectVoicing(name: String) {
        pending.clear()
        forgetSave()
        commands.selectVoicing(name)
        _ui.update { it.copy(nav = SettingsNav(SettingsPage.VOICINGS, voicingDetail = true)) }
    }

    /** Add a voicing (Python selects it); on phones the form opens. */
    fun addVoicing() {
        pending.clear()
        touch { commands.addVoicing() }
        _ui.update { it.copy(nav = SettingsNav(SettingsPage.VOICINGS, voicingDetail = true)) }
    }

    /** Ask before removing [name]. */
    fun askRemove(name: String) = _ui.update { it.copy(dialog = SettingsDialog.RemoveVoicing(name)) }

    /** Open the rename dialog for [name]. */
    fun askRename(name: String) = _ui.update { it.copy(dialog = SettingsDialog.Rename(name)) }

    /** Switch the selected voicing to [model], asking first when it has edits (`dirty`). */
    fun askModel(model: String) {
        val state = _editor.value?.state ?: return
        if (model == state.model) return
        if (state.dirty) _ui.update { it.copy(dialog = SettingsDialog.ChangeModel(model)) } else setModel(model)
    }

    /** Ask before loading [preset] (it replaces every parameter). */
    fun askPreset(preset: VoicingPreset) =
        _ui.update { it.copy(dialog = SettingsDialog.LoadPreset(preset.label, preset.group)) }

    /** A form edit (`set_voicing_values` with [payload], e.g. from [VoicingEdits]). */
    fun edit(payload: JsonObject) {
        pending.record(payload)
        touch { commands.setVoicingValues(payload) }
        _editor.value?.let { _editor.value = it.copy(values = pending.applyTo(it.state.values)) }
    }

    /**
     * A records cell changed: the whole list goes out, built on the rows shown
     * now (with edits not echoed yet), so quick edits of two cells both stay.
     */
    fun editCell(fieldId: String, index: Int, column: String, value: JsonElement) {
        val view = _editor.value ?: return
        val rows = pending.applyTo(view.state.values)[fieldId].asRecords()
        edit(VoicingEdits.cell(fieldId, rows, index, column, value))
    }

    /** Add a row to records field [fieldId]. */
    fun addRecord(fieldId: String) {
        pending.clear(fieldId)
        touch { commands.addVoicingRecord(fieldId) }
    }

    /** Remove row [index] of records field [fieldId]. */
    fun removeRecord(index: Int, fieldId: String) {
        pending.clear(fieldId)
        touch { commands.removeVoicingRecord(index, fieldId) }
    }

    private fun setModel(model: String) {
        pending.clear()
        touch { commands.setVoicingModel(model) }
    }

    private inline fun touch(send: () -> Unit) {
        forgetSave()
        send()
        _ui.update { it.copy(voicingsTouched = true) }
    }

    /** A new command: states from now on answer it, not a refused Save. */
    private fun forgetSave() = _ui.update { if (it.phase == SettingsPhase.EDITING) it.copy(saveRevision = -1) else it }

    /** The state to keep across a rotation ([restore] takes it back). */
    fun snapshot(): String = codec.encodeToString(SettingsUi.serializer(), _ui.value)

    companion object {
        private val codec = Json { ignoreUnknownKeys = true }

        /** A controller continuing [snapshot] (a fresh one if it can't be read). */
        fun restore(commands: ScreenCommands, snapshot: String): SettingsController {
            val ui = runCatching { codec.decodeFromString(SettingsUi.serializer(), snapshot) }.getOrNull()
            return SettingsController(commands, ui ?: SettingsUi())
        }
    }
}
