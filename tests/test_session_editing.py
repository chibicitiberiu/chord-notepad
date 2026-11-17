"""AppSession's programmatic edits: transpose, convert, capo, inserts.

Every edit the session makes reaches the views as one ``TextEdited`` splice
with an undo policy, followed at once (no debounce) by the highlighting of the
new text. Dialog-driven edits are request/response flows. The session runs on
a ManualHost over the real parser, viewmodels and PlaybackService (with a
silent FakePlayer), so playback can lock the editor.
"""

import pytest

from chordnotepad.session import formatting

from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session.events import (
    EditRefused, InsertDirectiveRequest, TextEdited, UndoPolicy,
)
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.session import AppSession
from chordnotepad.session.state import CapoAdviceState, HighlightState, MenuItem, StatusState
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from chordnotepad.session.workers import BackgroundWorker
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel
from chordnotepad.viewmodels.text_editor_viewmodel import TextEditorViewModel


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    """A started session with some text typed and detected."""

    def __init__(self, text="", **config):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(**config)
        self.player = FakePlayer(auto_play=False)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.main = MainWindowViewModel(
            self.config, self.audio, InMemoryDocumentStore(), SongParserService(), dispatch)
        self.worker = BackgroundWorker(self.host)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()),
            worker=self.worker)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text:
            self.session.set_text(text)
            self.host.advance(0.5)
        self.recorder.clear()

    def play(self):
        """Start playback and let the render thread hand the song over."""
        self.session.play_pause()
        self.audio._render_thread.join(timeout=10)
        self.host.run_pending()
        self.recorder.clear()

    def settle(self):
        """Let the background worker finish, then deliver its outcomes."""
        assert self.worker.wait_idle(timeout=30)
        self.host.run_pending()

    def request(self, request_type):
        return self.recorder.last(request_type)

    def status(self):
        return self.recorder.last(StatusState).text


def chord(start, end):
    return ("chord", start, end)


# -- transpose ---------------------------------------------------------------------


def test_golden_transpose_is_one_grouped_edit_then_immediate_spans_and_key_shift():
    env = Env("C G\nla la\nAm")
    env.main.set_key("C")
    env.recorder.clear()

    env.session.transpose(2, None)

    assert env.recorder.compact() == [
        ("TextEdited", 2, 0, 12, "D A\nla la\nBm", "group", 0),
        ("HighlightState", 2, 0, (chord(0, 1), chord(2, 3), chord(10, 12))),
        # The key the song starts in moved (idle, PlaybackState carries it).
        ("PlaybackState", "idle", None, None, 0, 0, None, 0, ()),
        # The toolbar key moved with the song.
        ("ToolbarState", "american", 120, 120, True, 100.0, "D", 4, 4, False, "play", None, None, None),
        # So did the song's starting key.
        ("SongDefaultsState", ("SongDefault", "120", False, None),
         ("SongDefault", "4/4", False, None), ("SongDefault", "D", False, None),
         "120 · 4/4 · D", None),
        ("StatusState", "Transposed whole song by +2 semitones"),
    ]
    assert env.session.text == env.main.current_text == "D A\nla la\nBm"
    assert env.main.key == "D"  # roman numerals keep sounding the same
    assert env.main.is_modified is True
    assert env.host.pending_timers == 0


def test_transpose_a_selection_keeps_the_key():
    env = Env("C G\nC G")
    env.main.set_key("C")
    env.recorder.clear()

    env.session.transpose(-1, (4, 7))

    edit = env.recorder.last(TextEdited)
    assert (edit.replacement, edit.undo) == ("C G\nB F#", UndoPolicy.GROUP)
    assert env.main.key == "C"
    assert env.status() == "Transposed selection by -1 semitones"


def test_transpose_flushes_pending_typing_detection():
    env = Env("C")
    env.session.set_text("C G")  # typed, detection still pending
    env.session.transpose(2, None)
    assert env.session.text == "D A"
    assert env.recorder.last(HighlightState).spans != ()
    assert env.host.pending_timers == 0


def test_transpose_by_zero_does_nothing():
    env = Env("C G")
    env.session.transpose(0, None)
    assert env.recorder.items == []


def test_an_empty_selection_means_the_whole_song():
    env = Env("C G")
    env.session.transpose(1, (2, 2))
    assert env.status() == "Transposed whole song by +1 semitones"


def test_transpose_with_nothing_in_the_songs_notation_changes_nothing_and_says_so():
    # Do selected over American chords: no chord moves, so neither does the key.
    env = Env("C G Am F", notation="european")
    env.session.set_notation("european")
    env.main.set_key("Do")
    modified = env.main.is_modified
    env.recorder.clear()

    env.session.transpose(2, None)

    assert env.recorder.compact() == [("StatusState", "No European chords to transpose")]
    assert env.session.text == env.main.current_text == "C G Am F"
    assert env.main.key == "Do"
    assert env.main.is_modified is modified


def test_transpose_of_a_selection_with_no_chords_says_so():
    env = Env("C G\nla la")
    env.session.transpose(2, (4, 9))
    assert env.status() == "No American chords to transpose in the selection"
    assert env.session.text == "C G\nla la"


def test_transpose_of_roman_numerals_only_still_moves_the_key():
    # The text has nothing absolute to move, but the key moves the numerals.
    env = Env("I IV V")
    env.main.set_key("C")
    env.recorder.clear()
    env.session.transpose(2, None)
    assert env.main.key == "D"
    assert env.status() == "Transposed whole song by +2 semitones"


def test_a_selection_outside_the_text_is_rejected():
    env = Env("C G")
    with pytest.raises(ValueError):
        env.session.transpose(1, (0, 99))


# -- the cursor after a whole-text rewrite ---------------------------------------------


# +2 moves every chord without changing its length (no lyric is stretched).
LONG = "".join(f"C G Am F\nline {i}\n" for i in range(150))


def test_transpose_keeps_the_cursor_on_its_line_and_column():
    env = Env(LONG)
    at = LONG.index("line 130") + 3            # "lin|e 130"
    env.session.transpose(2, None, cursor=at)
    edit = env.recorder.last(TextEdited)
    new = env.session.text
    assert edit.cursor == new.index("line 130") + 3
    assert edit.cursor < len(new) - 100        # not the end of the song


def test_transpose_puts_the_cursor_at_the_end_of_a_line_that_got_shorter():
    # "Abm7|" (end of line 1) -> "Am7": the nearest place is the line's end.
    env = Env("Abm7\nla la\nAbm7")
    env.session.transpose(1, None, cursor=4)
    assert env.session.text == "Am7\nla la\nAm7"
    assert env.recorder.last(TextEdited).cursor == 3


def test_convert_keeps_the_cursor_on_its_line_and_column():
    env = Env("Do Sol\nhello there\nFa Do")
    env.session.set_notation("european")
    env.session.convert_notation("american", cursor=12)    # "hello| there" on line 2
    lines = env.session.text.split("\n")
    assert lines[1] == "hello there"
    assert env.recorder.last(TextEdited).cursor == len(lines[0]) + 1 + 5


def test_transpose_of_a_selection_without_a_cursor_leaves_it_at_the_selection_end():
    env = Env("C G\nla\nC G")
    env.session.transpose(2, (7, 10))
    assert env.recorder.last(TextEdited).cursor == 10


def test_without_a_cursor_it_goes_to_the_start_of_the_first_changed_line():
    env = Env("la la\nC G\nla\nAm")
    env.session.transpose(2, None)
    assert env.recorder.last(TextEdited).cursor == 6


def test_a_cursor_outside_the_text_is_rejected():
    env = Env("C G")
    with pytest.raises(ValueError):
        env.session.transpose(1, None, cursor=4)
    with pytest.raises(ValueError):
        env.session.convert_notation("european", cursor=-1)
    assert env.session.text == "C G"


# -- convert notation --------------------------------------------------------------------


def test_convert_is_a_plain_edit_and_switches_detection():
    env = Env("C G\nhello there")
    env.session.convert_notation("european")

    assert env.recorder.compact() == [
        # Sol is longer than G: the lyric stretches (a middle dot) so the
        # chord stays over its syllable; the way back takes it out again.
        ("TextEdited", 2, 0, 15, "Do Sol\nhe\u00b7llo there", "plain", 0),
        ("HighlightState", 2, 0, (chord(0, 2), chord(3, 6))),
        # Detection and the toolbar follow the target notation (no key set:
        # the first option).
        ("EditorState", "TkFixedFont", 11, False, "european", False),
        ("ToolbarState", "european", 120, 120, True, 100.0, "Do", 4, 4, False, "play", None, None, None),
        ("StatusState", "Converted to European notation"),
    ]
    assert env.main.notation.value == "european"

    env.recorder.clear()
    env.session.convert_notation("american")
    assert env.session.text == "C G\nhello there"
    assert env.status() == "Converted to American notation"


def test_convert_with_typing_still_pending_uses_the_current_text():
    env = Env("C")
    env.session.set_text("C G Am")
    env.session.convert_notation("european")
    assert env.session.text == "Do Sol Lam"


@pytest.mark.parametrize("text, notation, target, status", [
    # Android's Convert with AB on a solfège song: no American chords.
    ("Do Sol\nla la", "american", "european", "No American chords to convert"),
    ("C G\nhello there", "european", "american", "No European chords to convert"),
    ("just lyrics", "american", "european", "No American chords to convert"),
    ("", "european", "american", "No European chords to convert"),
])
def test_convert_with_nothing_to_convert_says_so_and_changes_nothing(
        text, notation, target, status):
    env = Env(notation=notation)
    env.session.set_notation(notation)       # by hand, or the paste would switch to the song's
    env.session.set_text(text)
    env.host.advance(0.5)
    assert env.main.notation.value == notation
    modified = env.main.is_modified
    env.recorder.clear()
    env.session.convert_notation(target)

    assert env.recorder.compact() == [("StatusState", status)]
    assert env.session.text == env.main.current_text == text
    assert env.main.notation.value == notation
    assert env.main.is_modified is modified


def test_convert_after_nothing_to_convert_still_converts():
    env = Env("Do Sol", notation="american")
    env.session.convert_notation("european")
    env.session.set_notation("european")
    env.session.convert_notation("american")
    assert env.session.text == "C G"
    assert env.status() == "Converted to American notation"


def test_convert_to_an_unknown_notation_is_rejected():
    env = Env("C")
    with pytest.raises(ValueError):
        env.session.convert_notation("klingon")


# -- insert text (chord identifier) ----------------------------------------------------------


def test_insert_text_is_a_plain_splice_with_the_cursor_after_it():
    env = Env("C G\nla")
    env.session.insert_text(3, " Am")
    assert env.recorder.compact() == [
        ("TextEdited", 2, 3, 3, " Am", "plain", 6),
        ("HighlightState", 2, 0, (chord(0, 1), chord(2, 3), chord(4, 6))),
    ]


@pytest.mark.parametrize("text, at, inserted, result", [
    # Right after a chord: a space in front, or it reads "FG7".
    ("C F", 3, " G7 ", "C F G7 "),
    # After a space, at a line start or at the very start: none needed.
    ("C F ", 4, "G7 ", "C F G7 "),
    ("C F\n", 4, "G7 ", "C F\nG7 "),
    ("", 0, "G7 ", "G7 "),
    # In the middle of a word: still kept apart.
    ("hello", 2, " G7 ", "he G7 llo"),
])
def test_insert_chord_keeps_it_apart_from_the_chord_before(text, at, inserted, result):
    env = Env(text)
    env.session.insert_chord(at, "G7")
    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.replacement, edit.cursor) == (at, inserted, at + len(inserted))
    assert env.session.text == result
    assert env.status() == "Inserted chord: G7"


# -- insert directive ------------------------------------------------------------------------


def test_insert_directive_after_a_chord_puts_a_space_in_front():
    env = Env("C Am F G")
    env.session.request_insert_directive("bpm", 8)
    env.session.respond(1, {"value": "100"})
    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.replacement, edit.cursor) == (8, " {bpm: 100} ", 20)
    assert env.session.text == "C Am F G {bpm: 100} "
    # G is still a chord, and so is everything before it.
    spans = [(s.kind.value, s.start, s.end) for s in env.recorder.last(HighlightState).spans]
    assert chord(7, 8) in spans and ("directive", 9, 19) in spans


def test_insert_directive_request_then_response_inserts_it():
    env = Env("C G\n{label: verse}\nAm")
    env.session.request_insert_directive("bpm", 4)

    assert env.recorder.compact() == [
        ("InsertDirectiveRequest", 1, "bpm", ("verse",), "american")]
    assert env.request(InsertDirectiveRequest).key_options == ()      # only for key
    env.recorder.clear()

    env.session.respond(1, {"value": " 90 "})
    assert env.recorder.compact() == [
        ("TextEdited", 2, 4, 4, "{bpm: 90} ", "plain", 14),
        ("HighlightState", 2, 0, (
            chord(0, 1), chord(2, 3), chord(29, 31), ("directive", 4, 13),
            ("directive", 14, 28))),
        ("StatusState", "Inserted: {bpm: 90}"),
    ]
    assert env.session.text == "C G\n{bpm: 90} {label: verse}\nAm"


def test_a_cancelled_directive_inserts_nothing():
    env = Env("C G")
    env.session.request_insert_directive("key", 0)
    env.recorder.clear()
    env.session.respond(1, None)
    assert env.recorder.items == []
    assert env.session.text == "C G"


def test_a_duplicate_label_is_rejected_with_a_user_error():
    env = Env("{label: chorus}\nC G")
    env.session.request_insert_directive("label", 0)
    request = env.request(InsertDirectiveRequest)
    assert request.existing_labels == ("chorus",)
    env.recorder.clear()

    env.session.respond(request.request_id, {"label": "chorus"})
    assert env.recorder.compact() == [
        ("UserError", "Duplicate Label",
         "A label named 'chorus' already exists. Please use a unique name.")]
    assert env.session.text == "{label: chorus}\nC G"


def test_labels_typed_since_the_last_detection_count():
    env = Env("C G")
    env.session.set_text("{label: intro}\nC G")  # detection still pending
    env.session.request_insert_directive("loop", 0)
    assert env.request(InsertDirectiveRequest).existing_labels == ("intro",)


def test_loop_offers_the_start_and_the_labels():
    from chordnotepad.session.directives import loop_label_choices

    env = Env("{label: verse}\nC\n{label: bridge}\nG")
    env.session.request_insert_directive("loop", 34)
    request = env.request(InsertDirectiveRequest)
    assert loop_label_choices(request.existing_labels) == ("@start", "bridge", "verse")

    env.session.respond(request.request_id, {"label": "bridge", "count": 3})
    assert env.session.text.endswith("G {loop: bridge 3} ")


def test_the_key_options_follow_the_notation():
    env = Env("Do Re", notation="european")
    env.session.request_insert_directive("key", 0)
    request = env.request(InsertDirectiveRequest)
    assert request.notation == "european"
    assert request.key_options[:3] == ("Do", "Sol", "Re") and "Lam" in request.key_options
    env.session.respond(request.request_id, {"key": "Sol"})
    assert env.session.text == "{key: Sol} Do Re"


def test_an_insert_offset_past_a_shrunken_text_is_clamped():
    env = Env("C G Am F")
    env.session.request_insert_directive("bpm", 8)
    env.session.set_text("C")  # the text changed while the dialog was open
    env.session.respond(1, {"value": "100"})
    assert env.session.text == "C {bpm: 100} "


def test_unknown_kind_or_offset_is_rejected():
    env = Env("C")
    with pytest.raises(ValueError):
        env.session.request_insert_directive("tempo", 0)
    with pytest.raises(ValueError):
        env.session.request_insert_directive("bpm", 5)


def test_stale_answers_are_ignored():
    env = Env("C")
    env.session.request_insert_directive("bpm", 0)
    env.session.request_insert_directive("bpm", 1)  # replaces the first
    env.recorder.clear()

    env.session.respond(1, {"value": "90"})
    assert env.recorder.items == []
    env.session.respond(2, {"value": "90"})
    assert env.session.text == "C {bpm: 90} "
    env.session.respond(2, {"value": "90"})  # answered already
    assert env.session.text == "C {bpm: 90} "


# -- suggest capo ------------------------------------------------------------------------------

BARRE_SONG = "{key: F#}\nF#  B  C#  D#m  F#  B"
STANDARD_LABEL = "Guitar (Standard - EADGBE)"


def _advice(env):
    """The latest CapoAdviceState (a new listener gets every state replayed)."""
    recorder = EventRecorder()
    subscription = env.session.subscribe(recorder)
    subscription.cancel()
    return recorder.last(CapoAdviceState)


def _open(env, region=None):
    """Open Suggest Capo and let the worker score it."""
    env.session.capo_advice_open(region)
    env.settle()
    return _advice(env)


def test_the_dialog_is_closed_from_the_start_without_services():
    env = Env("C")
    advice = _advice(env)
    assert advice is not None and not advice.active and advice.rows == ()


def test_open_computes_then_ranks_the_capos_with_the_recommended_one_first():
    env = Env(BARRE_SONG)
    env.session.capo_advice_open(None)

    computing = _advice(env)
    assert computing.active and computing.status == "computing" and computing.rows == ()
    assert computing.scope == formatting.capo_scope_text(False)
    assert computing.voicing == "guitar:standard" and not computing.playing
    assert env.session.text == BARRE_SONG          # nothing changes yet

    env.settle()
    ready = _advice(env)
    assert ready.status == "ready" and ready.message == ""
    rows = ready.rows
    assert sorted(r.capo for r in rows) == list(range(0, 8))
    first = rows[0]
    assert first.recommended and first.capo > 0 and first.ease == "Easier"
    assert [r.recommended for r in rows[1:]] == [False] * 7
    assert first.label == f"Capo {first.capo} \u00b7 {first.shapes} \u00b7 Easier"
    no_capo = next(r for r in rows if r.capo == 0)
    assert no_capo.label == "No capo \u00b7 F# B C# D#m" and no_capo.ease == "No capo"
    assert no_capo.current                         # no capo in force
    assert [r.current for r in rows].count(True) == 1


def test_the_rows_name_the_shapes_in_the_songs_notation():
    env = Env("{key: Si}\nSi Fa# Sol#m Mi", notation="european")
    rows = {r.capo: r for r in _open(env).rows}
    assert rows[0].shapes == "Si Fa# Sol#m Mi"
    assert rows[2].shapes == "La Mi Fa#m Re"
    assert rows[4].shapes == "Sol Re Mim Do"


def test_the_voicings_are_the_fretboard_ones_with_the_active_one_chosen():
    env = Env("C", voicing="guitar:drop_d")
    env.session.capo_advice_open(None)
    advice = _advice(env)
    assert advice.voicing == "guitar:drop_d"
    assert MenuItem(STANDARD_LABEL, "guitar:standard") in advice.voicings
    assert all(o.value.startswith(("guitar:", "voicing:")) for o in advice.voicings)


def test_a_piano_voicing_scores_for_standard_guitar():
    env = Env("C", voicing="piano")
    env.session.capo_advice_open(None)
    assert _advice(env).voicing == "guitar:standard"


def test_the_scope_says_where_the_capo_goes():
    env = Env("C G Am F")
    env.session.capo_advice_open(None)
    assert _advice(env).scope == formatting.capo_scope_text(False)
    assert "top of the song" in formatting.capo_scope_text(False)
    env.session.capo_advice_open((2, 5))
    assert _advice(env).scope == formatting.capo_scope_text(True)
    # The capo stays in force after the selection: the text mustn't say "only".
    assert "selected part" in formatting.capo_scope_text(True)
    assert "only" not in formatting.capo_scope_text(True)


def test_switching_the_voicing_scores_again():
    env = Env(BARRE_SONG)
    _open(env)
    env.recorder.clear()

    env.session.capo_advice_voicing("guitar:drop_d")

    assert _advice(env).status == "computing" and _advice(env).voicing == "guitar:drop_d"
    env.settle()
    assert _advice(env).status == "ready" and len(_advice(env).rows) == 8


def test_an_unknown_voicing_is_ignored():
    env = Env(BARRE_SONG)
    _open(env)
    env.recorder.clear()
    env.session.capo_advice_voicing("voicing:no such thing")
    env.session.capo_advice_voicing("piano")
    assert env.recorder.items == []


def test_apply_inserts_the_directive_as_one_grouped_edit_and_closes():
    env = Env(BARRE_SONG)
    capo = _open(env).rows[0].capo
    env.recorder.clear()

    env.session.capo_advice_apply(capo)

    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.end, edit.undo) == (0, len(BARRE_SONG), UndoPolicy.GROUP)
    assert edit.replacement == f"{{capo: {capo}}}\n{BARRE_SONG}"
    assert env.status() == f"Suggested capo {capo} for the whole song on {STANDARD_LABEL}"
    assert not _advice(env).active


def test_apply_takes_any_row_not_just_the_recommended_one():
    env = Env(BARRE_SONG)
    rows = _open(env).rows
    other = next(r.capo for r in rows if r.capo not in (0, rows[0].capo))
    env.session.capo_advice_apply(other)
    assert env.session.text == f"{{capo: {other}}}\n{BARRE_SONG}"
    # Not the recommended one: the status says what went in, not "Suggested".
    assert env.status() == f"Inserted: {{capo: {other}}}"


def test_apply_replaces_a_capo_before_the_first_chord():
    song = "{capo: 0}\n" + BARRE_SONG
    env = Env(song)
    advice = _open(env)
    assert next(r for r in advice.rows if r.capo == 0).current
    env.session.capo_advice_apply(advice.rows[0].capo)
    lines = env.session.text.split("\n")
    assert lines[0] == f"{{capo: {advice.rows[0].capo}}}"
    assert "\n".join(lines[1:]) == BARRE_SONG


def test_a_selection_replaces_its_own_capo():
    song = "C G\n{capo: 0}\n" + BARRE_SONG
    env = Env(song)
    start = song.index("{capo")
    advice = _open(env, (start, len(song)))
    env.session.capo_advice_apply(advice.rows[0].capo)
    text = env.session.text
    assert text == f"C G\n{{capo: {advice.rows[0].capo}}}\n{BARRE_SONG}"
    assert env.status().endswith(f"for the selection on {STANDARD_LABEL}")


def test_no_capo_helps_puts_no_capo_first():
    env = Env("C G Am F")
    advice = _open(env, (0, 3))
    first = advice.rows[0]
    assert first.capo == 0 and first.recommended and first.label == "No capo \u00b7 C G"
    assert advice.scope == formatting.capo_scope_text(True)


def test_no_capo_with_none_in_force_changes_nothing_and_closes():
    env = Env("C G Am F")
    _open(env)
    env.recorder.clear()
    env.session.capo_advice_apply(0)
    assert env.recorder.of_type(TextEdited) == []
    assert env.session.text == "C G Am F"
    assert not _advice(env).active


def test_no_capo_with_a_capo_in_force_writes_capo_0():
    song = "{capo: 3}\nC G Am F"
    env = Env(song)
    advice = _open(env)
    assert next(r for r in advice.rows if r.capo == 3).current
    env.session.capo_advice_apply(0)
    assert env.session.text == "{capo: 0}\nC G Am F"
    assert env.status() == "Inserted: {capo: 0}"
    assert not _advice(env).active


def test_the_capo_in_force_above_a_selection_is_current():
    song = "{capo: 2}\nC G\nAm F"
    env = Env(song)
    start = song.index("Am")
    advice = _open(env, (start, len(song)))
    assert [r.capo for r in advice.rows if r.current] == [2]
    env.session.capo_advice_apply(0)   # no capo from the selection on
    assert env.session.text == "{capo: 2}\nC G\n{capo: 0}\nAm F"


def test_applying_the_capo_already_in_force_changes_nothing():
    song = "{capo: 2}\nC G Am F"
    env = Env(song)
    _open(env)
    env.recorder.clear()
    env.session.capo_advice_apply(2)
    assert env.recorder.of_type(TextEdited) == []
    assert not _advice(env).active


def test_apply_before_the_rows_are_in_or_of_no_row_is_ignored():
    env = Env(BARRE_SONG)
    env.session.capo_advice_open(None)
    env.session.capo_advice_apply(2)              # still computing
    env.settle()
    env.session.capo_advice_apply(40)             # no such row
    assert env.session.text == BARRE_SONG
    assert _advice(env).active


def test_apply_after_the_text_changed_scores_again():
    env = Env(BARRE_SONG)
    capo = _open(env).rows[0].capo
    env.session.set_text(BARRE_SONG + "\nmore")
    env.recorder.clear()

    env.session.capo_advice_apply(capo)

    assert env.recorder.of_type(TextEdited) == []
    assert _advice(env).status == "computing" and _advice(env).active
    env.settle()
    env.session.capo_advice_apply(_advice(env).rows[0].capo)
    assert env.session.text.startswith("{capo: ")


def test_apply_is_refused_while_playing_and_the_state_says_so():
    env = Env(BARRE_SONG)
    capo = _open(env).rows[0].capo
    env.play()
    assert _advice(env).playing

    env.session.capo_advice_apply(capo)

    assert env.recorder.of_type(TextEdited) == []
    assert EditRefused(formatting.EDIT_REFUSED_MESSAGE) in env.recorder.items
    assert _advice(env).active
    env.session.stop()
    assert not _advice(env).playing
    env.session.capo_advice_apply(capo)
    assert env.session.text.startswith(f"{{capo: {capo}}}")


def test_close_cancels_the_scoring_and_changes_nothing():
    env = Env(BARRE_SONG)
    env.session.capo_advice_open(None)
    env.session.capo_advice_close()
    assert not _advice(env).active
    env.recorder.clear()
    env.settle()
    assert env.recorder.items == []
    assert env.session.text == BARRE_SONG


def test_a_newer_open_supersedes_the_older_scoring():
    env = Env(BARRE_SONG)
    env.session.capo_advice_open(None)
    env.session.capo_advice_open((0, 9))
    env.settle()
    readies = [a for a in env.recorder.of_type(CapoAdviceState) if a.status == "ready"]
    assert readies, env.recorder.compact()
    assert len(readies) == 1 and readies[0].scope == formatting.capo_scope_text(True)


def test_no_chords_in_range_says_so():
    env = Env("{key: C}\nsome words\nC G")
    advice = _open(env, (0, 8))
    assert advice.status == "ready" and advice.rows == ()
    assert advice.message == "No chords in this range"


def test_a_render_failure_shows_its_error_in_the_dialog():
    from unittest.mock import patch

    env = Env(BARRE_SONG)
    with patch.object(env.audio, "render_song", side_effect=ValueError("boom")):
        advice = _open(env)
    assert advice.status == "error" and advice.rows == ()
    assert advice.message == "Couldn't score the capos: boom"
    assert env.session.text == BARRE_SONG


def test_replacing_the_document_closes_the_dialog():
    env = Env(BARRE_SONG)
    env.session.capo_advice_open(None)
    env.session.new_document()
    from chordnotepad.session.events import ConfirmDiscardRequest, DiscardChoice
    pending = env.recorder.last(ConfirmDiscardRequest)
    if pending is not None:
        env.session.respond(pending.request_id, DiscardChoice.DISCARD)
    assert not _advice(env).active
    env.recorder.clear()
    env.settle()
    assert env.recorder.of_type(CapoAdviceState) == []   # the scoring was called off

    _open(env)
    env.session.restore_draft("Am", None, True)
    assert not _advice(env).active

    _open(env)
    env.session.open_recovered("Dm G", None, "Song")
    pending = env.recorder.last(ConfirmDiscardRequest)
    if pending is not None:
        env.session.respond(pending.request_id, DiscardChoice.DISCARD)
    assert not _advice(env).active


def test_opening_a_document_closes_the_dialog():
    env = Env(BARRE_SONG)
    store = env.main.documents
    ref = store.ref("other.txt")
    store.contents[ref.id] = "Em C"
    _open(env)
    env.session.open_document(ref)
    from chordnotepad.session.events import ConfirmDiscardRequest, DiscardChoice
    pending = env.recorder.last(ConfirmDiscardRequest)
    if pending is not None:
        env.session.respond(pending.request_id, DiscardChoice.DISCARD)
    assert env.session.text == "Em C"
    assert not _advice(env).active


# -- read-only while playing ------------------------------------------------------------------


def test_programmatic_edits_are_refused_while_playing():
    env = Env("C G Am F")
    env.main.set_key("C")
    env.play()

    env.session.transpose(2, None)
    env.session.convert_notation("european")
    env.session.insert_text(0, "G ")
    env.session.insert_chord(0, "Am")       # the identifier's Insert

    # Nothing but the refusals (the Qt status bar says why).
    assert env.recorder.items == [EditRefused(formatting.EDIT_REFUSED_MESSAGE)] * 4
    assert env.session.text == env.main.current_text == "C G Am F"
    assert env.main.key == "C"
    assert env.main.notation.value == "american"


def test_dialogs_still_open_while_playing_but_their_answers_are_refused():
    env = Env(BARRE_SONG)
    env.session.request_insert_directive("bpm", 0)
    env.play()  # started while the dialog was open
    env.session.respond(1, {"value": "90"})

    env.session.capo_advice_open(None)
    env.settle()
    assert _advice(env).active and _advice(env).playing
    env.session.capo_advice_apply(_advice(env).rows[0].capo)

    assert env.recorder.of_type(TextEdited) == []
    assert env.session.text == BARRE_SONG

    env.session.stop()
    env.session.request_insert_directive("bpm", 0)
    env.session.respond(2, {"value": "90"})
    assert env.session.text.startswith("{bpm: 90} ")


def test_paused_counts_as_playing():
    env = Env("C G")
    env.play()
    env.session.play_pause()  # pause
    env.recorder.clear()
    env.session.transpose(1, None)
    assert env.recorder.of_type(TextEdited) == []


# -- open / new go through the same path ----------------------------------------------------------
# (the document flows themselves: tests/test_session_documents.py)


def test_opening_a_document_is_a_reset_whole_text_edit():
    env = Env("C")
    store = env.main.documents
    store.contents[store.ref("song.txt").id] = "G D\n{bpm: 90}"
    env.main.set_and_notify("is_modified", False)
    env.session.open_document(store.ref("song.txt"))

    edit = env.recorder.of_type(TextEdited)[0]
    assert (edit.start, edit.end, edit.replacement, edit.undo) == (
        0, 1, "G D\n{bpm: 90}", UndoPolicy.RESET)
    assert env.recorder.last(HighlightState).text_revision == edit.text_revision
    assert env.main.is_modified is False
