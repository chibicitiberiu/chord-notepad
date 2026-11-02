package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.ScreenCommandNames
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.VoicingPreset
import com.tibich.chordnotepad.ui.editor.EditorFontKind
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The Settings screen's state holder: the edit's life, autosave, the draft, navigation, voicing commands. */
class SettingsControllerTest {
    private val submitter = RecordingSubmitter()
    private val commands = ScreenCommands(submitter)

    /** What was sent apart from the autosaves. */
    private val voicingCommands get() = submitter.sent.filter { it.first != ScreenCommandNames.COMMIT_SETTINGS }

    /** The `values` of every `commit_settings` sent. */
    private val commits get() = submitter.sent.filter { it.first == ScreenCommandNames.COMMIT_SETTINGS }.map { it.second.getValue("values") }

    /** The `invalid_numbers` of every `commit_settings` sent. */
    private val numberCommits get() = submitter.sent.filter { it.first == ScreenCommandNames.COMMIT_SETTINGS }.map { it.second.getValue("invalid_numbers") }

    private fun texts(vararg pairs: Pair<String, String>) = JsonObject(pairs.associate { it.first to JsonPrimitive(it.second) })

    private val inactive = Fixtures.piano.copy(
        active = false, revision = 0, groups = emptyList(), invalid = emptyList(), presets = emptyList(),
        selected = null, model = null, values = JsonObject(emptyMap()), fieldErrors = JsonObject(emptyMap()),
        formErrors = emptyList(), hints = JsonObject(emptyMap()), dirty = false,
    )
    private val opened = inactive.copy(active = true, revision = 0)

    /** A controller with the edit open and the settings loaded. */
    private fun editing(): SettingsController = SettingsController(commands).apply {
        start(needSchema = true)
        onSettings(Fixtures.settings)
        onEditor(inactive)
        onEditor(opened)
        submitter.clear()
    }

    @Test
    fun `start begins the edit once and asks for the schema`() {
        val c = SettingsController(commands)
        c.start(needSchema = true)
        assertEquals(listOf(ScreenCommandNames.REQUEST_VOICING_EDITOR_SCHEMA, ScreenCommandNames.BEGIN_SETTINGS_EDIT), submitter.names)
        assertEquals(SettingsPhase.OPENING, c.ui.value.phase)
        // The old (inactive) state still in the flow doesn't count.
        c.onEditor(inactive)
        assertEquals(SettingsPhase.OPENING, c.ui.value.phase)
        c.onEditor(opened)
        assertEquals(SettingsPhase.EDITING, c.ui.value.phase)
        submitter.clear()
        c.start(needSchema = false)
        assertEquals(emptyList<String>(), submitter.names)
    }

    @Test
    fun `the draft starts from the first SettingsState`() {
        val c = editing()
        val draft = c.ui.value.draft!!
        assertEquals(EditorFontKind.MONOSPACE, draft.fontKind)
        assertEquals(11, draft.fontSize)
        assertEquals("C", draft.key)
        assertFalse(c.ui.value.draftPending)
        // A later SettingsState (the toolbar, or our own save) doesn't reset the draft.
        c.updateDraft { it.copy(bpm = 90) }
        c.onSettings(Fixtures.settings)
        assertEquals(90, c.ui.value.draft!!.bpm)
    }

    @Test
    fun `a General or Playback change is saved at once`() {
        val c = editing()
        c.updateDraft { it.copy(fontKind = EditorFontKind.SERIF) }
        c.setNotation(EUROPEAN)
        assertEquals(2, commits.size)
        assertEquals("Serif", commits[0].jsonObject.getValue("font_family").jsonPrimitive.content)
        val values = commits[1].jsonObject
        assertEquals("european", values.getValue("notation").jsonPrimitive.content)
        // The key stays American (shown as Do); the config never holds European names.
        assertEquals("C", values.getValue("key").jsonPrimitive.content)
        assertEquals("Do", shownKey(c.ui.value.draft!!.key, EUROPEAN, Fixtures.settings))
        assertFalse(c.ui.value.draftPending)
        assertEquals(SettingsPhase.EDITING, c.ui.value.phase)
    }

    @Test
    fun `a number waits for saveDraft, and only a valid one is saved`() {
        val c = editing()
        c.setNumber(NumberSetting.BPM, "9")
        c.setNumber(NumberSetting.BPM, "96")
        assertEquals(emptyList<String>(), submitter.names)
        assertTrue(c.ui.value.draftPending)
        c.saveDraft()
        assertEquals(96, commits.single().jsonObject.getValue("bpm").jsonPrimitive.content.toInt())
        c.saveDraft()
        assertEquals(1, commits.size)

        submitter.clear()
        c.setNumber(NumberSetting.BPM, "1000")
        assertEquals(mapOf(NumberSetting.BPM to "1000"), c.ui.value.numberTexts)
        assertEquals(96, c.ui.value.draft!!.bpm)
        c.saveDraft()
        // Not saved: only kept by Python, for next time.
        assertEquals(listOf(JsonNull), commits)
        assertEquals(listOf(texts("bpm" to "1000")), numberCommits)
        c.setNumber(NumberSetting.BPM, " 100 ")
        assertEquals(emptyMap<NumberSetting, String>(), c.ui.value.numberTexts)
        c.saveDraft()
        assertEquals(100, commits.last().jsonObject.getValue("bpm").jsonPrimitive.content.toInt())
        assertEquals(texts(), numberCommits.last())
        c.saveDraft()
        assertEquals(2, commits.size)
    }

    @Test
    fun `a valid number typed on the way to an invalid one isn't saved`() {
        val c = editing()
        val saved = c.ui.value.saved!!.bpm
        // Typing 2500 a digit at a time: 25 and 250 are in range, 2500 isn't.
        for (text in listOf("2", "25", "250", "2500")) c.setNumber(NumberSetting.BPM, text)
        assertEquals(saved, c.ui.value.draft!!.bpm)
        assertFalse(c.ui.value.draftPending)
        c.saveDraft()
        assertEquals(listOf(JsonNull), commits)
        assertEquals(listOf(texts("bpm" to "2500")), numberCommits)
    }

    @Test
    fun `every voicing command but select is followed by an autosave`() {
        val c = editing()
        c.selectVoicing("New voicing")
        assertEquals(listOf(ScreenCommandNames.SELECT_VOICING), submitter.names)
        c.onEditor(Fixtures.piano)
        c.edit(VoicingEdits.text("rh_center", "60"))
        c.addVoicing()
        assertEquals(
            listOf(
                ScreenCommandNames.SELECT_VOICING, ScreenCommandNames.SET_VOICING_VALUES,
                ScreenCommandNames.COMMIT_SETTINGS, ScreenCommandNames.ADD_VOICING, ScreenCommandNames.COMMIT_SETTINGS,
            ),
            submitter.names,
        )
        // Nothing pending on General: the config's values stay.
        assertEquals(listOf(JsonNull, JsonNull), commits)
        // A number still being typed goes out with the voicing's save.
        c.setNumber(NumberSetting.FONT_SIZE, "14")
        c.edit(VoicingEdits.text("rh_center", "62"))
        assertEquals(14, commits.last().jsonObject.getValue("font_size").jsonPrimitive.content.toInt())
        assertFalse(c.ui.value.draftPending)
    }

    @Test
    fun `leaving with nothing invalid ends the edit at once, saving a pending number first`() {
        val c = editing()
        c.onEditor(Fixtures.piano)
        c.setNumber(NumberSetting.MAX_RECENT_FILES, "7")
        c.requestClose()
        assertNull(c.ui.value.dialog)
        assertEquals(listOf(ScreenCommandNames.COMMIT_SETTINGS, ScreenCommandNames.CANCEL_SETTINGS_EDIT), submitter.names)
        assertEquals(7, commits.single().jsonObject.getValue("max_recent_files").jsonPrimitive.content.toInt())
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `leaving with a wrong voicing value asks - Edit opens that voicing`() {
        val c = editing()
        val bad = Fixtures.fretboardInvalid
        assertTrue(bad.problems.isNotEmpty())
        c.onEditor(bad.copy(selected = null, model = null))
        c.openPage(SettingsPage.GENERAL)
        c.requestClose()
        assertEquals(SettingsDialog.Problems, c.ui.value.dialog)
        assertEquals(emptyList<String>(), submitter.names)
        c.editProblems()
        assertNull(c.ui.value.dialog)
        assertEquals(SettingsPhase.EDITING, c.ui.value.phase)
        assertEquals(SettingsNav(SettingsPage.VOICINGS, voicingDetail = true), c.ui.value.nav)
        assertEquals(ScreenCommandNames.SELECT_VOICING to bad.problems.first().voicing, submitter.sent.single().let { it.first to it.second.getValue("name").jsonPrimitive.content })

        // Already shown: Edit just opens the form.
        submitter.clear()
        c.onEditor(bad)
        c.openPage(SettingsPage.VOICINGS)
        c.requestClose()
        c.editProblems()
        assertEquals(SettingsNav(SettingsPage.VOICINGS, voicingDetail = true), c.ui.value.nav)
        assertEquals(emptyList<String>(), submitter.names)
    }

    @Test
    fun `Discard in the leave dialog drops the wrong values and leaves`() {
        val c = editing()
        c.onEditor(Fixtures.fretboardInvalid)
        c.setNumber(NumberSetting.FONT_SIZE, "999")
        c.back(twoPane = true, split = true)
        assertEquals(SettingsDialog.Problems, c.ui.value.dialog)
        c.confirmDialog()
        assertEquals(ScreenCommandNames.CANCEL_SETTINGS_EDIT, submitter.names.last())
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
        assertEquals(emptyMap<NumberSetting, String>(), c.ui.value.numberTexts)
    }

    @Test
    fun `a wrong number counts as a problem and Edit opens its page`() {
        val c = editing()
        c.onEditor(Fixtures.piano)
        c.setNumber(NumberSetting.BPM, "1000")
        c.setNumber(NumberSetting.FONT_SIZE, "")
        c.requestClose()
        assertEquals(SettingsDialog.Problems, c.ui.value.dialog)
        // General comes before Playback.
        c.editProblems()
        assertEquals(SettingsNav(SettingsPage.GENERAL), c.ui.value.nav)
        c.setNumber(NumberSetting.FONT_SIZE, "12")
        c.requestClose()
        c.editProblems()
        assertEquals(SettingsNav(SettingsPage.PLAYBACK), c.ui.value.nav)
        // Nothing wrong left: Back just leaves.
        c.setNumber(NumberSetting.BPM, "100")
        c.requestClose()
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `values kept from last time come back on entry and can be discarded`() {
        val c = SettingsController(commands)
        c.start(needSchema = false)
        c.onSettings(Fixtures.settings)
        c.onEditor(inactive)
        val restored = Fixtures.fretboardInvalid.copy(selected = null, model = null, restored = true, stagedNumbers = mapOf("bpm" to "5"))
        c.onEditor(restored)
        assertEquals(mapOf(NumberSetting.BPM to "5"), c.ui.value.numberTexts)
        // Python has them already: nothing to send.
        assertFalse(c.ui.value.numbersPending)
        assertTrue(c.hasProblems)
        submitter.clear()
        c.discardProblems()
        assertEquals(listOf(ScreenCommandNames.DISCARD_SETTINGS_PROBLEMS), submitter.names)
        assertEquals(emptyMap<NumberSetting, String>(), c.ui.value.numberTexts)
        c.onEditor(Fixtures.piano.copy(revision = 30))
        assertFalse(c.hasProblems)
        c.requestClose()
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `a reopened edit after a restart keeps this screen's number texts`() {
        val c = editing()
        c.setNumber(NumberSetting.BPM, "7")
        c.saveDraft()
        c.setNumber(NumberSetting.BPM, "120")
        submitter.clear()
        // Process restarted: the new edit has the texts sent before (bpm 7), the screen has none.
        c.onEditor(inactive.copy(revision = 3))
        c.onEditor(opened.copy(stagedNumbers = mapOf("bpm" to "7")))
        assertEquals(emptyMap<NumberSetting, String>(), c.ui.value.numberTexts)
        assertTrue(c.ui.value.numbersPending)
        c.saveDraft()
        assertEquals(texts(), numberCommits.last())
    }

    @Test
    fun `leaving before the edit opened just ends it`() {
        val c = SettingsController(commands)
        c.start(needSchema = false)
        c.onSettings(Fixtures.settings)
        c.setNumber(NumberSetting.BPM, "90")
        submitter.clear()
        c.requestClose()
        assertEquals(listOf(ScreenCommandNames.CANCEL_SETTINGS_EDIT), submitter.names)
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `phone navigation - pages, voicing form, back up to the list then out`() {
        val c = editing()
        c.openPage(SettingsPage.VOICINGS)
        c.selectVoicing("New voicing")
        c.onEditor(Fixtures.piano)
        assertEquals(SettingsNav(SettingsPage.VOICINGS, voicingDetail = true), c.ui.value.nav)
        c.back(twoPane = false, split = false)
        assertEquals(SettingsNav(SettingsPage.VOICINGS), c.ui.value.nav)
        c.back(twoPane = false, split = false)
        assertEquals(SettingsNav(), c.ui.value.nav)
        c.back(twoPane = false, split = false)
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `tablet navigation - General shows by default, back leaves`() {
        assertEquals(SettingsPage.GENERAL, SettingsNav().shown(twoPane = true))
        assertNull(SettingsNav().shown(twoPane = false))
        val detail = SettingsNav(SettingsPage.VOICINGS, voicingDetail = true)
        // Split: list and form are both on screen, so Back leaves.
        assertNull(detail.back(twoPane = true, split = true))
        // Two panes but no split: the form goes back to the list first.
        assertEquals(SettingsNav(SettingsPage.VOICINGS), detail.back(twoPane = true, split = false))
        assertNull(SettingsNav(SettingsPage.PLAYBACK).back(twoPane = true, split = false))
    }

    @Test
    fun `the form closes on phones when its voicing goes away`() {
        val c = editing()
        c.selectVoicing("New voicing")
        c.onEditor(Fixtures.piano)
        c.onEditor(Fixtures.piano.copy(selected = null, model = null, revision = 9))
        assertEquals(SettingsNav(SettingsPage.VOICINGS), c.ui.value.nav)
    }

    @Test
    fun `remove, rename, model switch and preset go through their dialogs`() {
        val c = editing()
        c.onEditor(Fixtures.fretboardInvalid)
        c.askRemove("New voicing")
        assertEquals(SettingsDialog.RemoveVoicing("New voicing"), c.ui.value.dialog)
        c.confirmDialog()
        assertEquals(ScreenCommandNames.REMOVE_VOICING to "New voicing", voicingCommands.last().let { it.first to it.second.getValue("name").jsonPrimitive.content })
        assertEquals(ScreenCommandNames.COMMIT_SETTINGS, submitter.names.last())

        c.askRename("A")
        c.confirmDialog("A")
        assertEquals(1, voicingCommands.size) // same name: nothing sent
        c.askRename("A")
        c.confirmDialog("B")
        assertEquals(ScreenCommandNames.RENAME_VOICING, voicingCommands.last().first)
        assertEquals("B", voicingCommands.last().second.getValue("new").jsonPrimitive.content)

        // dirty → ask before switching model.
        c.askModel("piano")
        assertEquals(SettingsDialog.ChangeModel("piano"), c.ui.value.dialog)
        c.confirmDialog()
        assertEquals(ScreenCommandNames.SET_VOICING_MODEL, voicingCommands.last().first)
        // Not dirty → no question; the same model → nothing.
        c.onEditor(Fixtures.fretboardInvalid.copy(dirty = false, revision = 20))
        c.askModel("ensemble")
        assertNull(c.ui.value.dialog)
        assertEquals("ensemble", voicingCommands.last().second.getValue("model").jsonPrimitive.content)
        val before = submitter.sent.size
        c.askModel("fretboard")
        assertEquals(before, submitter.sent.size)

        c.askPreset(VoicingPreset("Ukulele", "fretboard"))
        c.confirmDialog()
        val (name, args) = voicingCommands.last()
        assertEquals(ScreenCommandNames.LOAD_VOICING_PRESET, name)
        assertEquals("Ukulele", args.getValue("label").jsonPrimitive.content)
        assertEquals("fretboard", args.getValue("group").jsonPrimitive.content)
    }

    @Test
    fun `form edits go out at once and show before the echo`() {
        val c = editing()
        c.onEditor(Fixtures.ensemble)
        val rows = c.editor.value!!.values.getValue("voices").asRecords()
        c.edit(VoicingEdits.cell("voices", rows, 1, "low", JsonPrimitive("G2")))
        val (name, args) = voicingCommands.single()
        assertEquals(ScreenCommandNames.SET_VOICING_VALUES, name)
        assertEquals("G2", args.getValue("values").jsonObject.getValue("voices").jsonArray[1].jsonObject.getValue("low").jsonPrimitive.content)
        val shown = c.editor.value!!.values.getValue("voices").asRecords()[1].getValue("low").jsonPrimitive.content
        assertEquals("G2", shown)

        c.addRecord("voices")
        c.removeRecord(0, "voices")
        assertEquals(listOf(ScreenCommandNames.ADD_VOICING_RECORD, ScreenCommandNames.REMOVE_VOICING_RECORD), voicingCommands.drop(1).map { it.first })
        assertEquals(0, voicingCommands.last().second.getValue("index").jsonPrimitive.content.toInt())

        c.moveRecord(2, -1, "voices")
        val (move, moveArgs) = voicingCommands.last()
        assertEquals(ScreenCommandNames.MOVE_VOICING_RECORD, move)
        assertEquals(2, moveArgs.getValue("index").jsonPrimitive.content.toInt())
        assertEquals(-1, moveArgs.getValue("offset").jsonPrimitive.content.toInt())
        assertEquals("voices", moveArgs.getValue("field_id").jsonPrimitive.content)
    }

    @Test
    fun `two quick cell edits both stay before any echo`() {
        val c = editing()
        c.onEditor(Fixtures.ensemble)
        c.editCell("voices", 0, "name", JsonPrimitive("Bass"))
        c.editCell("voices", 1, "low", JsonPrimitive("G2"))
        // The (late) echo of the first edit doesn't undo the second.
        val first = voicingCommands[0].second.getValue("values").jsonObject
        c.onEditor(Fixtures.ensemble.copy(revision = 50, values = first))
        val rows = c.editor.value!!.values.getValue("voices").asRecords()
        assertEquals("Bass", rows[0].getValue("name").jsonPrimitive.content)
        assertEquals("G2", rows[1].getValue("low").jsonPrimitive.content)
        val last = voicingCommands.last().second.getValue("values").jsonObject.getValue("voices").jsonArray
        assertEquals("Bass", last[0].jsonObject.getValue("name").jsonPrimitive.content)
    }

    @Test
    fun `a lost edit (process restarted under the screen) is opened again`() {
        val c = editing()
        c.onEditor(inactive.copy(revision = 3))
        assertEquals(listOf(ScreenCommandNames.BEGIN_SETTINGS_EDIT), submitter.names)
        assertEquals(SettingsPhase.OPENING, c.ui.value.phase)
    }

    @Test
    fun `a number not saved yet is saved after the process restarted, once the new edit is open`() {
        val c = editing()
        c.setNumber(NumberSetting.BPM, "88")
        val restored = SettingsController.restore(commands, c.snapshot())
        restored.start(needSchema = false)
        // No edit in this process yet: nothing goes out.
        restored.saveDraft()
        assertEquals(emptyList<String>(), submitter.names)
        restored.onEditor(inactive)
        restored.saveDraft()
        assertEquals(listOf(ScreenCommandNames.BEGIN_SETTINGS_EDIT), submitter.names)
        restored.onEditor(opened)
        restored.saveDraft()
        assertEquals(88, commits.single().jsonObject.getValue("bpm").jsonPrimitive.content.toInt())
    }

    @Test
    fun `the state survives a rotation`() {
        val c = editing()
        c.openPage(SettingsPage.PLAYBACK)
        c.setNumber(NumberSetting.TIME_SIGNATURE_BEATS, "3")
        val restored = SettingsController.restore(commands, c.snapshot())
        assertEquals(c.ui.value, restored.ui.value)
        // No second begin: the edit lives on in Python.
        restored.start(needSchema = false)
        restored.onEditor(opened)
        assertEquals(emptyList<String>(), submitter.names)
        assertEquals(SettingsPhase.EDITING, restored.ui.value.phase)
        assertTrue(restored.ui.value.draftPending)
    }

    @Test
    fun `the draft keeps the key American whatever the notation`() {
        val s = Fixtures.settings
        // An older config could send a European key: the draft takes it as American.
        val old = s.copy(values = s.values.copy(notation = EUROPEAN, key = "Sol"))
        assertEquals("G", SettingsDraft.of(old).key)
        val draft = SettingsDraft.of(s).copy(key = "Bb")
        assertEquals("Bb", draft.withNotation(EUROPEAN).key)
        assertEquals("Bb", draft.withNotation(EUROPEAN).toValues().key)
        assertEquals("Sib", shownKey("Bb", EUROPEAN, s))
        assertEquals("Bb", shownKey("Bb", AMERICAN, s))
    }

    @Test
    fun `respelling keys between notations`() {
        val s = Fixtures.settings
        assertEquals("Sol#", respellKey("G#", EUROPEAN, s))
        assertEquals("Bb", respellKey("Sib", AMERICAN, s))
        assertEquals("C", respellKey("C", AMERICAN, s))
        assertEquals("", respellKey("", EUROPEAN, s))
        assertEquals("", respellKey("Xyz", EUROPEAN, s))
    }
}
