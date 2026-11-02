package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.bridge.VoicingEditorState
import com.tibich.chordnotepad.bridge.VoicingPreset
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

    /** Editing; every change is saved as it is made (`commit_settings`). */
    EDITING,

    /** Left: the edit ended and the screen goes away. */
    CLOSED,
}

/** How long a number setting's text rests before it is saved ([SettingsController.saveDraft]). */
const val DRAFT_SAVE_DELAY_MS = 400L

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
    /** Leaving with wrong values: Edit (go to the first) or Discard (drop them and leave). */
    @Serializable
    data object Problems : SettingsDialog

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
 * @property saved The General/Playback values Python has: what the screen
 *   opened with, then the last ones sent with `commit_settings`.
 * @property numberTexts Number fields whose text isn't a whole number in
 *   range, with that text (not saved; the draft keeps the saved value).
 * @property sentNumbers The [numberTexts] Python has (`invalid_numbers`, kept for next time).
 * @property adoptStaged This screen began the edit: take the number texts
 *   Python kept from last time when it opens.
 */
@Serializable
data class SettingsUi(
    val phase: SettingsPhase = SettingsPhase.NEW,
    val nav: SettingsNav = SettingsNav(),
    val draft: SettingsDraft? = null,
    val saved: SettingsDraft? = null,
    val numberTexts: Map<NumberSetting, String> = emptyMap(),
    val sentNumbers: Map<NumberSetting, String> = emptyMap(),
    val adoptStaged: Boolean = false,
    val dialog: SettingsDialog? = null,
) {
    /** The draft has changes not sent yet (a number being typed: [SettingsController.saveDraft]). */
    val draftPending: Boolean get() = draft != null && draft != saved

    /** The wrong number texts changed since they were last sent. */
    val numbersPending: Boolean get() = numberTexts != sentNumbers
}

/** The voicings editor as the form draws it: the state plus local edits not echoed yet. */
data class EditorView(val state: VoicingEditorState, val values: JsonObject)

/**
 * The Settings screen's state holder: the settings edit's life (begin,
 * autosave, leaving), the General/Playback draft, navigation, and the
 * voicing commands. Every change is saved as it is made: a voicing command
 * is followed by `commit_settings` (Python writes each voicing's valid
 * fields), and a General/Playback change goes out at once, or after
 * [DRAFT_SAVE_DELAY_MS] for a number being typed (the screen calls
 * [saveDraft]). Wrong values aren't saved; Python keeps them for next time,
 * and leaving asks what to do with them ([SettingsDialog.Problems]). Plain Kotlin, fed by the repository's flows ([onSettings],
 * [onEditor]); [snapshot]/[restore] keep it across a rotation (the edit
 * itself lives on in Python).
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
        _ui.update { it.copy(phase = SettingsPhase.OPENING, adoptStaged = true) }
    }

    /** A `SettingsState` arrived: the draft starts from the first one. */
    fun onSettings(state: SettingsState) {
        limits = state
        if (_ui.value.draft == null) {
            val draft = SettingsDraft.of(state)
            _ui.update { it.copy(draft = draft, saved = draft) }
        }
    }

    /** A `VoicingEditorState` arrived. */
    fun onEditor(state: VoicingEditorState) {
        if (state.active) pending.onState(state.values)
        val ui = _ui.value
        var next = ui
        when (ui.phase) {
            SettingsPhase.OPENING -> if (state.active) {
                // Python's number texts: kept from last time (adopted when
                // this screen began the edit) or after a restart.
                val staged = NumberSetting.fromKeys(state.stagedNumbers)
                next = ui.copy(
                    phase = SettingsPhase.EDITING,
                    sentNumbers = staged,
                    numberTexts = if (ui.adoptStaged && ui.numberTexts.isEmpty()) staged else ui.numberTexts,
                    adoptStaged = false,
                )
            }
            // The edit is gone though nobody ended it: the process was
            // restarted under a restored screen. Open a new one.
            SettingsPhase.EDITING -> if (!state.active) {
                pending.clear()
                commands.beginSettingsEdit()
                next = ui.copy(phase = SettingsPhase.OPENING)
            }
            SettingsPhase.NEW, SettingsPhase.CLOSED -> Unit
        }
        if (state.active && state.selected == null && next.nav.voicingDetail) {
            next = next.copy(nav = next.nav.copy(voicingDetail = false))
        }
        _ui.value = next
        _editor.value = if (state.active) EditorView(state, pending.applyTo(state.values)) else null
    }

    // -- saving and leaving -------------------------------------------------------

    /** Whether commands can go to the edit now (it is open in this process). */
    private val live: Boolean get() = _ui.value.phase == SettingsPhase.EDITING && _editor.value != null

    /** Send the draft's General/Playback values and the wrong number texts if they changed since the last save. */
    fun saveDraft() {
        val ui = _ui.value
        if (live && (ui.draftPending || ui.numbersPending)) commit()
    }

    /**
     * `commit_settings`, with the draft's values when they changed (null keeps
     * the config's) and the wrong number texts when they changed.
     */
    private fun commit() {
        val ui = _ui.value
        val values = ui.draft?.takeIf { ui.draftPending }?.toValues()
        val numbers = ui.numberTexts.takeIf { ui.numbersPending }
        _ui.value = ui.copy(saved = if (values != null) ui.draft else ui.saved, sentNumbers = ui.numberTexts)
        commands.commitSettings(values, numbers?.mapKeys { it.key.key })
    }

    /** Whether something wrong isn't saved: a number field's text or a voicing value. */
    val hasProblems: Boolean
        get() = _ui.value.numberTexts.isNotEmpty() || _editor.value?.state?.problems?.isNotEmpty() == true

    /** Back out of the screen: asks first ([SettingsDialog.Problems]) while something wrong isn't saved. */
    fun requestClose() {
        val ui = _ui.value
        when {
            ui.phase == SettingsPhase.CLOSED -> Unit
            hasProblems -> _ui.value = ui.copy(dialog = SettingsDialog.Problems)
            else -> close()
        }
    }

    /** Leave: save what the draft still holds, then end the edit (Python drops the wrong values). */
    fun close() {
        if (_ui.value.phase == SettingsPhase.CLOSED) return
        saveDraft()
        commands.cancelSettingsEdit()
        pending.clear()
        _ui.update { it.copy(phase = SettingsPhase.CLOSED, dialog = null, numberTexts = emptyMap()) }
    }

    /** Edit (the leave dialog, or the banner of values kept from last time): go to the first problem. */
    fun editProblems() {
        _ui.update { it.copy(dialog = null) }
        val number = NumberSetting.entries.firstOrNull { it in _ui.value.numberTexts }
        if (number != null) {
            openPage(number.page)
            return
        }
        val state = _editor.value?.state ?: return
        val name = state.problems.firstOrNull()?.voicing ?: return
        if (name == state.selected) {
            _ui.update { it.copy(nav = SettingsNav(SettingsPage.VOICINGS, voicingDetail = true)) }
        } else {
            selectVoicing(name)
        }
    }

    /** Drop the wrong values and stay (the banner of values kept from last time). */
    fun discardProblems() {
        commands.discardSettingsProblems()
        _ui.update { it.copy(numberTexts = emptyMap(), sentNumbers = emptyMap()) }
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

    /** Change the draft and save it at once. */
    fun updateDraft(change: (SettingsDraft) -> SettingsDraft) {
        _ui.update { ui -> ui.draft?.let { ui.copy(draft = change(it)) } ?: ui }
        saveDraft()
    }

    /** Switch the draft's notation (the key stays; it shows in the new spelling). */
    fun setNotation(notation: String) = updateDraft { it.withNotation(notation) }

    /**
     * A number field's text: a whole number in range goes into the draft
     * (saved once the typing rests, [saveDraft]); anything else is marked
     * invalid and not saved.
     */
    fun setNumber(setting: NumberSetting, text: String) {
        val l = limits ?: return
        val value = text.trim().toIntOrNull()?.takeIf { it in setting.range(l) }
        _ui.update { ui ->
            val draft = ui.draft ?: return@update ui
            if (value == null) {
                // Back to the saved value: a number typed on the way (the 9
                // of 999) must not be saved when the typing rests.
                val kept = ui.saved?.let { setting.set(draft, setting.get(it)) } ?: draft
                ui.copy(draft = kept, numberTexts = ui.numberTexts + (setting to text))
            } else {
                ui.copy(draft = setting.set(draft, value), numberTexts = ui.numberTexts - setting)
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
            SettingsDialog.Problems -> {
                _ui.update { it.copy(numberTexts = emptyMap()) }
                close()
            }
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

    /** Move row [index] of records field [fieldId] by [offset] rows (-1 up, +1 down). */
    fun moveRecord(index: Int, offset: Int, fieldId: String) {
        pending.clear(fieldId)
        touch { commands.moveVoicingRecord(index, offset, fieldId) }
    }

    private fun setModel(model: String) {
        pending.clear()
        touch { commands.setVoicingModel(model) }
    }

    /** Send a voicing command, then save (Python writes it once every voicing is valid). */
    private inline fun touch(send: () -> Unit) {
        send()
        commit()
    }

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
