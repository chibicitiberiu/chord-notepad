package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Test

class SessionCommandsTest {
    private val sent = mutableListOf<Pair<String, JsonElement>>()
    private val answered = mutableListOf<Int>()
    private val commands = SessionCommands(
        submitter = { command, args -> sent += command to Json.parseToJsonElement(args) },
        onResponded = { answered += it },
    )

    private fun assertSent(command: String, json: String) {
        val (c, args) = sent.removeAt(0)
        assertEquals(command, c)
        assertEquals(Json.parseToJsonElement(json), args)
    }

    @Test
    fun `editing commands use the AppSession parameter names`() {
        commands.setText("C 😀", clientToken = 3)
        assertSent("set_text", """{"text": "C 😀", "client_token": 3}""")
        commands.insertText(at = 2, text = "Am ")
        assertSent("insert_text", """{"at": 2, "text": "Am "}""")
        commands.transpose(2, Selection(1, 4))
        assertSent("transpose", """{"semitones": 2, "selection": [1, 4]}""")
        commands.transpose(-1)
        assertSent("transpose", """{"semitones": -1, "selection": null}""")
        commands.requestInsertDirective("bpm", at = 0)
        assertSent("request_insert_directive", """{"kind": "bpm", "at": 0}""")
    }

    @Test
    fun `playback and toolbar`() {
        commands.playPause()
        assertSent("play_pause", """{"from_offset": null}""")
        commands.playPause(fromOffset = 12)
        assertSent("play_pause", """{"from_offset": 12}""")
        commands.setKey(null)
        assertSent("set_key", """{"key": null}""")
        commands.setTimeSignature(6, 8)
        assertSent("set_time_signature", """{"beats": 6, "unit": 8}""")
        commands.stop()
        assertSent("stop", "{}")
    }

    @Test
    fun `documents carry refs as objects`() {
        val ref = DocumentRef("content://p/doc%3A1", "song.txt", "song.txt (Drive)")
        commands.openRecent(ref)
        assertSent(
            "open_recent",
            """{"ref": {"id": "content://p/doc%3A1", "display_name": "song.txt", "location": "song.txt (Drive)"}}""",
        )
        commands.openDocument()
        assertSent("open_document", """{"ref": null}""")
    }

    @Test
    fun `answers encode by request type and clear the request`() {
        commands.respondDiscard(1, DiscardChoice.SAVE)
        assertSent("respond", """{"request_id": 1, "value": "save"}""")
        commands.respondPick(2, null)
        assertSent("respond", """{"request_id": 2, "value": null}""")
        commands.respondPick(3, DocumentRef("content://a", "a.txt", "a.txt"))
        assertSent("respond", """{"request_id": 3, "value": {"id": "content://a", "display_name": "a.txt", "location": "a.txt"}}""")
        commands.respondCapo(4, "guitar:standard")
        assertSent("respond", """{"request_id": 4, "value": "guitar:standard"}""")
        commands.respondDirective(5, mapOf("label" to "chorus", "count" to "2"))
        assertSent("respond", """{"request_id": 5, "value": {"label": "chorus", "count": "2"}}""")
        commands.respondDirective(6, null)
        assertSent("respond", """{"request_id": 6, "value": null}""")
        assertEquals(listOf(1, 2, 3, 4, 5, 6), answered)
    }

    @Test
    fun `host commands`() {
        commands.appBackground()
        assertSent("app_background", "{}")
        commands.appForeground()
        assertSent("app_foreground", "{}")
        commands.pause()
        assertSent("pause", "{}")
        commands.restoreDraft("G 😀", DocumentRef("content://a", "a.txt", "a.txt"), modified = true)
        assertSent(
            "restore_draft",
            """{"text": "G 😀", "document": {"id": "content://a", "display_name": "a.txt", "location": "a.txt"},
               "modified": true}""",
        )
    }

    @Test
    fun `every command name is listed`() {
        // Each builder's name must be in CommandNames.ALL (the contract test's list).
        with(commands) {
            setText("", 0); insertText(0, ""); requestInsertDirective("bpm", 0); transpose(1)
            requestSuggestCapo(); convertNotation("american"); playPause(); stop(); tapChordAt(0)
            setBpm(100.0); setMultiplierPct(100.0); setKey("C"); setTimeSignature(4, 4); toggleMetronome()
            setVoicing("piano"); setInstrument(0); setNotation("american"); setFont("Monospace", 12)
            stepFontSize(1); resetFontSize(); setChordSheetVisible(true); setChordSheetHeight(100)
            setChordSheetView("staff"); chordSheetZoom(1); audition(0); newDocument(); openDocument()
            openRecent(DocumentRef("a", "a", "a")); save(); saveAs(); exportMidi(); requestClose()
            respondDiscard(1, null); appBackground(); appForeground(); pause(); restoreDraft("", null, false)
        }
        assertEquals(CommandNames.ALL, sent.map { it.first }.toSet())
    }
}
