package io.github.chibicitiberiu.chordnotepad.ui.menus

import androidx.compose.foundation.text.input.TextFieldState
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.InstrumentFamily
import io.github.chibicitiberiu.chordnotepad.bridge.InstrumentMenuState
import io.github.chibicitiberiu.chordnotepad.bridge.MenuItem
import io.github.chibicitiberiu.chordnotepad.bridge.RecentDocumentsState
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.bridge.VoicingMenuState
import io.github.chibicitiberiu.chordnotepad.ui.MainActions
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorController
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MenuModelsTest {
    private val voicing = VoicingMenuState(
        selected = "guitar:standard",
        groups = listOf(
            listOf(MenuItem("Piano", "piano")),
            listOf(MenuItem("Guitar (standard)", "guitar:standard"), MenuItem("Ukulele", "guitar:ukulele")),
            emptyList(),
            listOf(MenuItem("SATB choir", "ensemble:satb")),
        ),
    )

    private val instruments = InstrumentMenuState(
        current = 25,
        families = listOf(
            InstrumentFamily("Piano", false, listOf(MenuItem("  0 - Acoustic Grand Piano", "0"))),
            InstrumentFamily(
                "Guitar",
                true,
                listOf(MenuItem(" 24 - Nylon Guitar", "24"), MenuItem(" 25 - Steel Guitar", "25"), MenuItem("bad", "x")),
            ),
        ),
    )

    @Test
    fun `voicing rows keep the groups apart and mark the selection`() {
        assertEquals(
            listOf(
                VoicingRow.Choice("Piano", "piano", false),
                VoicingRow.Divider,
                VoicingRow.Choice("Guitar (standard)", "guitar:standard", true),
                VoicingRow.Choice("Ukulele", "guitar:ukulele", false),
                VoicingRow.Divider,
                VoicingRow.Choice("SATB choir", "ensemble:satb", false),
            ),
            voicingRows(voicing),
        )
        assertEquals(emptyList<VoicingRow>(), voicingRows(VoicingMenuState("piano", emptyList())))
    }

    @Test
    fun `instrument families mark the current family and program`() {
        val families = instrumentFamilies(instruments)
        assertEquals(listOf("Piano", "Guitar"), families.map { it.name })
        assertEquals(listOf(false, true), families.map { it.isCurrent })
        assertEquals(
            listOf(ProgramRow("24 - Nylon Guitar", 24, false), ProgramRow("25 - Steel Guitar", 25, true)),
            families[1].programs,
        )
        assertEquals(listOf(ProgramRow("0 - Acoustic Grand Piano", 0, false)), families[0].programs)
        assertEquals(1, initialFamilyIndex(families))
        assertEquals(0, initialFamilyIndex(families.map { it.copy(isCurrent = false) }))
        assertEquals(0, initialFamilyIndex(emptyList()))
    }

    @Test
    fun `recent entries are the session's list, newest first`() {
        val a = DocumentRef("content://a", "a.txt", "Downloads/a.txt")
        val b = DocumentRef("content://b", "b.txt", "Drive/b.txt")
        assertEquals(listOf(a, b), recentEntries(RecentDocumentsState(listOf(a, b))))
        assertTrue(recentEntries(RecentDocumentsState(emptyList())).isEmpty())
        assertTrue(recentEntries(null).isEmpty())
    }

    @Test
    fun `menu choices send their commands`() {
        val sent = mutableListOf<Pair<String, JsonElement>>()
        val commands = SessionCommands({ c, args -> sent += c to Json.parseToJsonElement(args) })
        val actions = MainActions(commands, EditorController(commands, TextFieldState()))
        fun assertSent(command: String, json: String) {
            val (c, args) = sent.removeAt(0)
            assertEquals(command, c)
            assertEquals(Json.parseToJsonElement(json), args)
        }

        val choice = voicingRows(voicing).filterIsInstance<VoicingRow.Choice>().last()
        actions.setVoicing(choice.value)
        assertSent("set_voicing", """{"voicing": "ensemble:satb"}""")
        actions.setInstrument(instrumentFamilies(instruments)[1].programs[0].program)
        assertSent("set_instrument", """{"program": 24}""")
        actions.setFont("Serif", 14)
        assertSent("set_font", """{"family": "Serif", "size": 14}""")
        actions.setChordSheetVisible(false)
        assertSent("set_chord_sheet_visible", """{"visible": false}""")
        // The editor's text is unchanged (empty), so no set_text goes first.
        actions.openRecent(DocumentRef("content://a", "a.txt", "Downloads/a.txt"))
        assertSent("open_recent", """{"ref": {"id": "content://a", "display_name": "a.txt", "location": "Downloads/a.txt"}}""")
        actions.requestClose()
        assertSent("request_close", "{}")
        assertTrue(sent.isEmpty())
    }
}

class VoicingGroupsTest {
    @Test
    fun `voicings are grouped by their values, missing groups left out`() {
        val state = VoicingMenuState(
            selected = "voicing:Trio",
            groups = listOf(
                listOf(MenuItem("Piano", "piano")),
                listOf(MenuItem("Guitar (standard)", "guitar:standard")),
                listOf(MenuItem("Trio", "voicing:Trio")),
            ),
        )
        val groups = voicingGroups(state)
        assertEquals(listOf(VoicingGroupKind.PIANO, VoicingGroupKind.FRETTED, VoicingGroupKind.YOURS), groups.map { it.kind })
        assertTrue(groups.last().choices.single().selected)
        assertEquals("Trio", selectedVoicingLabel(state))
    }

    @Test
    fun `program labels split into name and number`() {
        assertEquals("Nylon Guitar" to "24", programParts(ProgramRow("24 - Nylon Guitar", 24, false)))
        assertEquals("Odd" to "7", programParts(ProgramRow("Odd", 7, false)))
        val families = listOf(FamilyRow("Guitar", true, listOf(ProgramRow("25 - Steel Guitar", 25, true))))
        assertEquals("Steel Guitar", currentProgramName(families))
    }
}
