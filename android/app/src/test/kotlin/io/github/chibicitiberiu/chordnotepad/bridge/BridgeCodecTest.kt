package io.github.chibicitiberiu.chordnotepad.bridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Payloads as `session.bridge.encode` will produce them: the dataclass's
 * fields (snake_case), enums as their values, tuples as arrays, None as null.
 */
class BridgeCodecTest {
    private inline fun <reified T : SessionOutput> decode(type: String, json: String): T {
        val out = BridgeCodec.decode(type, json)
        assertTrue("$type decoded to ${out::class}", out is T)
        return out as T
    }

    @Test
    fun `highlight state with spans`() {
        val s = decode<HighlightState>(
            "HighlightState",
            """{"text_revision": 3, "client_token": 7, "spans": [{"start": 0, "end": 2, "kind": "chord"},
               {"start": 5, "end": 9, "kind": "directive_invalid"}]}""",
        )
        assertEquals(3, s.textRevision)
        assertEquals(7, s.clientToken)
        assertEquals(listOf(Span(0, 2, SpanKind.CHORD), Span(5, 9, SpanKind.DIRECTIVE_INVALID)), s.spans)
    }

    @Test
    fun `playback state, idle and playing`() {
        val idle = decode<PlaybackState>(
            "PlaybackState",
            """{"status": "idle", "playing_span": null, "chord_index": null, "bar": 0, "total_bars": 0}""",
        )
        assertEquals(PlaybackState(PlaybackStatus.IDLE), idle)
        val playing = decode<PlaybackState>(
            "PlaybackState",
            """{"status": "playing", "playing_span": {"start": 4, "end": 6, "kind": "chord"},
               "chord_index": 2, "bar": 3, "total_bars": 16}""",
        )
        assertEquals(Span(4, 6, SpanKind.CHORD), playing.playingSpan)
        assertEquals(16, playing.totalBars)
    }

    @Test
    fun `toolbar, editor, status`() {
        val t = decode<ToolbarState>(
            "ToolbarState",
            """{"notation": "american", "bpm": 120, "bpm_display": 90, "bpm_editable": false,
               "multiplier_pct": 100.0, "key": "C", "key_options": ["C", "G"], "beats": 3, "unit": 4,
               "metronome": true, "play_action": "pause"}""",
        )
        assertEquals(PlayAction.PAUSE, t.playAction)
        assertEquals(listOf("C", "G"), t.keyOptions)
        val e = decode<EditorState>(
            "EditorState",
            """{"font_family": "TkFixedFont", "font_size": 12, "read_only": true, "notation": "european"}""",
        )
        assertTrue(e.readOnly)
        assertEquals("Ready", decode<StatusState>("StatusState", """{"text": "Ready"}""").text)
    }

    @Test
    fun `menus`() {
        val v = decode<VoicingMenuState>(
            "VoicingMenuState",
            """{"selected": "piano", "groups": [[{"label": "Piano", "value": "piano"}],
               [{"label": "Guitar", "value": "guitar:standard"}]]}""",
        )
        assertEquals("guitar:standard", v.groups[1][0].value)
        val i = decode<InstrumentMenuState>(
            "InstrumentMenuState",
            """{"current": 24, "families": [{"name": "Guitar", "is_current": true,
               "items": [{"label": "Nylon Guitar", "value": "24"}]}]}""",
        )
        assertTrue(i.families.single().isCurrent)
    }

    @Test
    fun `chord sheet state`() {
        val c = decode<ChordSheetState>(
            "ChordSheetState",
            """{"visible": true, "height": 180, "active_view": "staff",
               "views": [{"view_id": "staff", "label": "Staff", "available": true}],
               "disabled_reason": null, "zoom": 1.25, "zoom_supported": true, "current_index": null,
               "song_revision": 4}""",
        )
        assertEquals("staff", c.views.single().viewId)
        assertEquals(1.25, c.zoom, 0.0)
    }

    @Test
    fun `document and recent documents`() {
        val d = decode<DocumentState>(
            "DocumentState",
            """{"display_name": "Untitled", "location": null, "is_modified": false,
               "title": "Untitled - Chord Notepad"}""",
        )
        assertEquals(null, d.documentId) // until step 14 adds document_id
        val withId = decode<DocumentState>(
            "DocumentState",
            """{"display_name": "a.txt", "location": "Internal storage/a.txt", "is_modified": true,
               "title": "a.txt* - Chord Notepad", "document_id": "content://x/a"}""",
        )
        assertEquals("content://x/a", withId.documentId)
        val r = decode<RecentDocumentsState>(
            "RecentDocumentsState",
            """{"items": [{"id": "content://x/a", "display_name": "a.txt", "location": "Internal storage/a.txt"}]}""",
        )
        assertEquals(DocumentRef("content://x/a", "a.txt", "Internal storage/a.txt"), r.items.single())
    }

    @Test
    fun `events and errors`() {
        val e = decode<TextEdited>(
            "TextEdited",
            """{"text_revision": 9, "start": 0, "end": 3, "replacement": "D", "undo": "group", "cursor": 1}""",
        )
        assertEquals(UndoPolicy.GROUP, e.undo)
        decode<UserError>("UserError", """{"title": "Error", "message": "Failed"}""")
        assertTrue(decode<AudioUnavailable>("AudioUnavailable", """{"message": "m", "from_click": true}""").fromClick)
        assertEquals(null, decode<UnexpectedError>("UnexpectedError", """{"message": "boom"}""").context)
        assertSame(CloseApproved, BridgeCodec.decode("CloseApproved", "{}"))
    }

    @Test
    fun `requests`() {
        assertEquals(4, decode<ConfirmDiscardRequest>("ConfirmDiscardRequest", """{"request_id": 4}""").requestId)
        val p = decode<PickDocumentRequest>(
            "PickDocumentRequest",
            """{"request_id": 5, "mode": "export_midi", "suggested_name": "song.mid"}""",
        )
        assertEquals(PickMode.EXPORT_MIDI, p.mode)
        val c = decode<CapoChoiceRequest>(
            "CapoChoiceRequest",
            """{"request_id": 6, "options": [{"label": "Guitar", "value": "guitar:standard"}], "default": "guitar:standard"}""",
        )
        assertEquals("guitar:standard", c.default)
        val d = decode<InsertDirectiveRequest>(
            "InsertDirectiveRequest",
            """{"request_id": 7, "kind": "loop", "existing_labels": ["chorus"], "notation": "american"}""",
        )
        assertEquals(listOf("chorus"), d.existingLabels)
    }

    @Test
    fun `extra keys from a newer core are ignored`() {
        val s = decode<StatusState>("StatusState", """{"text": "x", "severity": "info"}""")
        assertEquals("x", s.text)
    }

    @Test(expected = BridgeDecodeException::class)
    fun `unknown type`() {
        BridgeCodec.decode("NoSuchState", "{}")
    }

    @Test(expected = BridgeDecodeException::class)
    fun `unknown enum value`() {
        BridgeCodec.decode("PlaybackState", """{"status": "rewinding"}""")
    }

    @Test(expected = BridgeDecodeException::class)
    fun `missing required field`() {
        BridgeCodec.decode("UserError", """{"title": "Error"}""")
    }

    @Test(expected = BridgeDecodeException::class)
    fun `malformed json`() {
        BridgeCodec.decode("StatusState", """{"text": """)
    }
}
