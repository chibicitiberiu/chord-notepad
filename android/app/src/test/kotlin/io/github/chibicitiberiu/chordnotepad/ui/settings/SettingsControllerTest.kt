package io.github.chibicitiberiu.chordnotepad.ui.settings

import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommandNames
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.bridge.VoicingPreset
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorFontKind
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

/** The Settings screen's state holder: the edit's life, the draft, navigation, voicing commands. */
class SettingsControllerTest {
    private val submitter = RecordingSubmitter()
    private val commands = ScreenCommands(submitter)

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
        assertFalse(c.ui.value.changed)
        // A later SettingsState (the toolbar) doesn't reset the draft.
        c.updateDraft { it.copy(bpm = 90) }
        c.onSettings(Fixtures.settings)
        assertEquals(90, c.ui.value.draft!!.bpm)
    }

    @Test
    fun `save sends the changed values, then closes when the edit ends`() {
        val c = editing()
        c.updateDraft { it.copy(fontKind = EditorFontKind.SERIF) }
        c.setNotation(EUROPEAN)
        c.setNumber(NumberSetting.BPM, "96")
        c.save()
        val (name, args) = submitter.sent.single()
        assertEquals(ScreenCommandNames.SAVE_SETTINGS, name)
        val values = args.getValue("values").jsonObject
        assertEquals("Serif", values.getValue("font_family").jsonPrimitive.content)
        assertEquals("european", values.getValue("notation").jsonPrimitive.content)
        // C respelled in European notation.
        assertEquals("Do", values.getValue("key").jsonPrimitive.content)
        assertEquals(96, values.getValue("bpm").jsonPrimitive.content.toInt())
        assertEquals(SettingsPhase.SAVING, c.ui.value.phase)
        c.onEditor(inactive)
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `save with nothing changed on General sends null values`() {
        val c = editing()
        c.save()
        assertEquals(JsonNull, submitter.sent.single().second.getValue("values"))
    }

    @Test
    fun `an invalid voicing keeps the screen open with it selected`() {
        val c = editing()
        c.onEditor(Fixtures.piano)
        c.openPage(SettingsPage.GENERAL)
        c.save()
        val refused = Fixtures.fretboardInvalid.copy(revision = Fixtures.piano.revision + 1)
        // The UserError and the state may come in either order.
        for (errorFirst in listOf(true, false)) {
            val c2 = SettingsController.restore(commands, c.snapshot())
            if (errorFirst) c2.onError()
            c2.onEditor(refused)
            if (!errorFirst) c2.onError()
            val ui = c2.ui.value
            assertEquals(SettingsPhase.EDITING, ui.phase)
            assertEquals(SettingsNav(SettingsPage.VOICINGS, voicingDetail = true), ui.nav)
            // Later states (the user's own commands) don't move the screen again.
            c2.openPage(SettingsPage.GENERAL)
            c2.edit(VoicingEdits.text("tuning", "E2 A2 D3"))
            c2.onEditor(refused.copy(revision = refused.revision + 1))
            assertEquals(SettingsNav(SettingsPage.GENERAL), c2.ui.value.nav)
        }
    }

    @Test
    fun `a config that can't be written leaves the screen open`() {
        val c = editing()
        c.save()
        c.onError()
        assertEquals(SettingsPhase.EDITING, c.ui.value.phase)
        assertTrue(c.ui.value.canSave)
    }

    @Test
    fun `an out of range number blocks Save`() {
        val c = editing()
        c.setNumber(NumberSetting.BPM, "1000")
        assertFalse(c.ui.value.canSave)
        c.save()
        assertEquals(emptyList<String>(), submitter.names)
        c.setNumber(NumberSetting.BPM, " 100 ")
        assertTrue(c.ui.value.canSave)
        assertEquals(100, c.ui.value.draft!!.bpm)
    }

    @Test
    fun `leaving unchanged cancels at once`() {
        val c = editing()
        c.requestClose()
        assertEquals(listOf(ScreenCommandNames.CANCEL_SETTINGS_EDIT), submitter.names)
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `leaving with changes asks first - keep editing or discard`() {
        val c = editing()
        c.updateDraft { it.copy(showQuickStartOnStartup = false) }
        c.requestClose()
        assertEquals(SettingsDialog.Discard, c.ui.value.dialog)
        assertEquals(emptyList<String>(), submitter.names)
        c.dismissDialog()
        assertNull(c.ui.value.dialog)
        assertEquals(SettingsPhase.EDITING, c.ui.value.phase)
        c.requestClose()
        c.confirmDialog()
        assertEquals(listOf(ScreenCommandNames.CANCEL_SETTINGS_EDIT), submitter.names)
        assertEquals(SettingsPhase.CLOSED, c.ui.value.phase)
    }

    @Test
    fun `a voicing edit counts as a change, selecting one doesn't`() {
        val c = editing()
        c.selectVoicing("New voicing")
        assertFalse(c.ui.value.changed)
        c.onEditor(Fixtures.piano)
        c.edit(VoicingEdits.text("rh_center", "60"))
        assertTrue(c.ui.value.changed)
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
        assertEquals(ScreenCommandNames.REMOVE_VOICING to "New voicing", submitter.sent.last().let { it.first to it.second.getValue("name").jsonPrimitive.content })

        c.askRename("A")
        c.confirmDialog("A")
        assertEquals(1, submitter.sent.size) // same name: nothing sent
        c.askRename("A")
        c.confirmDialog("B")
        assertEquals(ScreenCommandNames.RENAME_VOICING, submitter.names.last())
        assertEquals("B", submitter.sent.last().second.getValue("new").jsonPrimitive.content)

        // dirty → ask before switching model.
        c.askModel("piano")
        assertEquals(SettingsDialog.ChangeModel("piano"), c.ui.value.dialog)
        c.confirmDialog()
        assertEquals(ScreenCommandNames.SET_VOICING_MODEL, submitter.names.last())
        // Not dirty → no question; the same model → nothing.
        c.onEditor(Fixtures.fretboardInvalid.copy(dirty = false, revision = 20))
        c.askModel("ensemble")
        assertNull(c.ui.value.dialog)
        assertEquals("ensemble", submitter.sent.last().second.getValue("model").jsonPrimitive.content)
        val before = submitter.sent.size
        c.askModel("fretboard")
        assertEquals(before, submitter.sent.size)

        c.askPreset(VoicingPreset("Ukulele", "fretboard"))
        c.confirmDialog()
        val (name, args) = submitter.sent.last()
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
        val (name, args) = submitter.sent.single()
        assertEquals(ScreenCommandNames.SET_VOICING_VALUES, name)
        assertEquals("G2", args.getValue("values").jsonObject.getValue("voices").jsonArray[1].jsonObject.getValue("low").jsonPrimitive.content)
        val shown = c.editor.value!!.values.getValue("voices").asRecords()[1].getValue("low").jsonPrimitive.content
        assertEquals("G2", shown)

        c.addRecord("voices")
        c.removeRecord(0, "voices")
        assertEquals(listOf(ScreenCommandNames.ADD_VOICING_RECORD, ScreenCommandNames.REMOVE_VOICING_RECORD), submitter.names.drop(1))
        assertEquals(0, submitter.sent.last().second.getValue("index").jsonPrimitive.content.toInt())
    }

    @Test
    fun `two quick cell edits both stay before any echo`() {
        val c = editing()
        c.onEditor(Fixtures.ensemble)
        c.editCell("voices", 0, "name", JsonPrimitive("Bass"))
        c.editCell("voices", 1, "low", JsonPrimitive("G2"))
        // The (late) echo of the first edit doesn't undo the second.
        val first = submitter.sent[0].second.getValue("values").jsonObject
        c.onEditor(Fixtures.ensemble.copy(revision = 50, values = first))
        val rows = c.editor.value!!.values.getValue("voices").asRecords()
        assertEquals("Bass", rows[0].getValue("name").jsonPrimitive.content)
        assertEquals("G2", rows[1].getValue("low").jsonPrimitive.content)
        val last = submitter.sent.last().second.getValue("values").jsonObject.getValue("voices").jsonArray
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
    fun `the state survives a rotation`() {
        val c = editing()
        c.openPage(SettingsPage.PLAYBACK)
        c.updateDraft { it.copy(timeSignatureBeats = 3) }
        val restored = SettingsController.restore(commands, c.snapshot())
        assertEquals(c.ui.value, restored.ui.value)
        // No second begin: the edit lives on in Python.
        restored.start(needSchema = false)
        restored.onEditor(opened)
        assertEquals(emptyList<String>(), submitter.names)
        assertEquals(SettingsPhase.EDITING, restored.ui.value.phase)
        assertTrue(restored.ui.value.changed)
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
