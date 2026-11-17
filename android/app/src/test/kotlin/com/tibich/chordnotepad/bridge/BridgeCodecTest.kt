package com.tibich.chordnotepad.bridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
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
        assertEquals(0, playing.beat)
        assertEquals(emptyList<TimelineSection>(), playing.sections)
    }

    @Test
    fun `playback state, beat and timeline sections`() {
        val playing = decode<PlaybackState>(
            "PlaybackState",
            """{"status": "playing", "playing_span": null, "chord_index": 5, "bar": 7, "total_bars": 12,
               "playhead_offset": 30, "beat": 3,
               "sections": [{"label": "", "first_bar": 1, "last_bar": 2, "repeat": false},
                            {"label": "chorus", "first_bar": 3, "last_bar": 6, "repeat": false},
                            {"label": "chorus", "first_bar": 7, "last_bar": 12, "repeat": true}]}""",
        )
        assertEquals(3, playing.beat)
        assertEquals(
            listOf(
                TimelineSection("", 1, 2),
                TimelineSection("chorus", 3, 6),
                TimelineSection("chorus", 7, 12, repeat = true),
            ),
            playing.sections,
        )
    }

    @Test
    fun `playback state, the live song values`() {
        val playing = decode<PlaybackState>(
            "PlaybackState",
            """{"status": "playing", "playing_span": null, "chord_index": 1, "bar": 2, "total_bars": 4,
               "key": "Sol", "time_signature": [6, 8],
               "tempo_clamped": "Tempo clamped to 400 BPM at line 5"}""",
        )
        assertEquals("Sol", playing.key)
        assertEquals(listOf(6, 8), playing.timeSignature)
        assertEquals("Tempo clamped to 400 BPM at line 5", playing.tempoClamped)
        val idle = decode<PlaybackState>("PlaybackState", """{"status": "idle"}""")
        assertEquals(null, idle.key)
        assertEquals(listOf(4, 4), idle.timeSignature)
        assertEquals(null, idle.tempoClamped)
    }

    @Test
    fun `toolbar, editor, status`() {
        val t = decode<ToolbarState>(
            "ToolbarState",
            """{"notation": "american", "bpm": 120, "bpm_display": 90, "bpm_editable": false,
               "multiplier_pct": 100.0, "key": "C", "key_options": ["C", "G"], "beats": 3, "unit": 4,
               "metronome": true, "play_action": "pause", "bpm_set_by": "{bpm: 120}",
               "time_set_by": null, "key_set_by": null}""",
        )
        assertEquals(PlayAction.PAUSE, t.playAction)
        assertEquals(listOf("C", "G"), t.keyOptions)
        assertEquals("{bpm: 120}", t.bpmSetBy)
        assertEquals(null, t.timeSetBy)
        val e = decode<EditorState>(
            "EditorState",
            """{"font_family": "TkFixedFont", "font_size": 12, "read_only": true, "notation": "european"}""",
        )
        assertTrue(e.readOnly)
        // An older core sends no word_wrap: unwrapped, the default.
        assertFalse(e.wordWrap)
        val wrapped = decode<EditorState>(
            "EditorState",
            """{"font_family": "TkFixedFont", "font_size": 12, "read_only": false, "notation": "american",
               "word_wrap": true}""",
        )
        assertTrue(wrapped.wordWrap)
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
        assertEquals(null, v.lockedReason)
        val locked = decode<VoicingMenuState>(
            "VoicingMenuState",
            """{"selected": "piano", "groups": [], "locked_reason": "Pause to change the voicing"}""",
        )
        assertEquals("Pause to change the voicing", locked.lockedReason)
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
        assertEquals(null, d.documentId)
        assertEquals(false, d.readOnly)
        val withId = decode<DocumentState>(
            "DocumentState",
            """{"display_name": "a.txt", "location": "Internal storage/a.txt", "is_modified": true,
               "title": "a.txt* - Chord Notepad", "document_id": "content://x/a"}""",
        )
        assertEquals("content://x/a", withId.documentId)
        val readOnly = decode<DocumentState>(
            "DocumentState",
            """{"display_name": "a.txt", "location": "a.txt", "is_modified": false,
               "title": "a.txt - Chord Notepad", "document_id": "content://x/a", "read_only": true}""",
        )
        assertEquals(true, readOnly.readOnly)
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
        assertEquals(null, e.anchor)
        val selecting = decode<TextEdited>(
            "TextEdited",
            """{"text_revision": 9, "start": 0, "end": 0, "replacement": "{bpm: 120}", "undo": "group", "cursor": 9, "anchor": 6}""",
        )
        assertEquals(6, selecting.anchor)
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

    @Test
    fun `suggest capo's state`() {
        val advice = decode<CapoAdviceState>(
            "CapoAdviceState",
            """{"active": true, "scope": "Applies to the whole song.",
               "voicings": [{"label": "Guitar", "value": "guitar:standard"}], "voicing": "guitar:standard",
               "status": "ready", "message": "", "playing": false,
               "rows": [{"capo": 3, "label": "Capo 3 · G D Em C · Easier", "shapes": "G D Em C",
                         "ease": "Easier", "recommended": true, "current": false},
                        {"capo": 0, "label": "No capo · Bb F Gm Eb", "shapes": "Bb F Gm Eb",
                         "ease": "No capo", "recommended": false, "current": true}]}""",
        )
        assertEquals(listOf(3, 0), advice.rows.map { it.capo })
        assertTrue(advice.rows[0].recommended && advice.rows[1].current)
        assertFalse(advice.computing)
        val computing = decode<CapoAdviceState>(
            "CapoAdviceState",
            """{"active": true, "scope": "", "voicings": [], "voicing": "", "status": "computing",
               "message": "", "playing": true, "rows": []}""",
        )
        assertTrue(computing.computing && computing.playing)
    }

    @Test
    fun `the player's outputs`() {
        val playback = decode<PlaybackState>(
            "PlaybackState",
            """{"status": "idle", "playing_span": null, "chord_index": null, "bar": 0, "total_bars": 0,
               "playhead_offset": 12}""",
        )
        assertEquals(12, playback.playheadOffset)
        val defaults = decode<SongDefaultsState>(
            "SongDefaultsState",
            """{"tempo": {"value": "90", "from_directive": true, "directive_offset": 0},
               "time": {"value": "3/4", "from_directive": false, "directive_offset": null},
               "key": {"value": "", "from_directive": false, "directive_offset": null},
               "summary": "90 · 3/4"}""",
        )
        assertEquals(SongDefault("90", true, 0), defaults.tempo)
        assertEquals("90 · 3/4", defaults.summary)
        assertNull(defaults.lockedReason)
        val locked = decode<SongDefaultsState>(
            "SongDefaultsState",
            """{"tempo": {"value": "90", "from_directive": false, "directive_offset": null},
               "time": {"value": "3/4", "from_directive": false, "directive_offset": null},
               "key": {"value": "", "from_directive": false, "directive_offset": null},
               "summary": "90 · 3/4",
               "locked_reason": "Pause to change the playback settings"}""",
        )
        assertEquals("Pause to change the playback settings", locked.lockedReason)
        val failed = decode<RenameFailed>(
            "RenameFailed",
            """{"name": "a/b", "reason": "A name can't contain / or \\.", "can_save_as": false}""",
        )
        assertEquals(RenameFailed("a/b", "A name can't contain / or \\.", false), failed)
        assertEquals(
            EditRefused("Stop playback to edit the song"),
            decode<EditRefused>("EditRefused", """{"message": "Stop playback to edit the song"}"""),
        )
    }

    @Test
    fun `the startup screen`() {
        for ((wire, screen) in listOf(
            "none" to StartupScreen.NONE,
            "quick_start" to StartupScreen.QUICK_START,
            "support_prompt" to StartupScreen.SUPPORT_PROMPT,
        )) {
            assertEquals(StartupState(screen), decode<StartupState>("StartupState", """{"screen": "$wire"}"""))
        }
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
