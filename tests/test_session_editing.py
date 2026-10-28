"""AppSession's programmatic edits: transpose, convert, capo, inserts.

Every edit the session makes reaches the views as one ``TextEdited`` splice
with an undo policy, followed at once (no debounce) by the highlighting of the
new text. Dialog-driven edits are request/response flows. The session runs on
a ManualHost over the real parser, viewmodels and PlaybackService (with a
silent FakePlayer), so playback can lock the editor.
"""

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.events import (
    CapoChoiceRequest, InsertDirectiveRequest, TextEdited, UndoPolicy,
)
from session.host import HostDispatch
from session.session import AppSession
from session.state import HighlightState, MenuItem, StatusState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


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
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()))
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
        ("TextEdited", 2, 0, 12, "D A\nla la\nBm", "group", 12),
        ("HighlightState", 2, 0, (chord(0, 1), chord(2, 3), chord(10, 12))),
        # The toolbar key moved with the song.
        ("ToolbarState", "american", 120, 120, True, 100.0, "D", 4, 4, False, "play"),
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


def test_a_selection_outside_the_text_is_rejected():
    env = Env("C G")
    with pytest.raises(ValueError):
        env.session.transpose(1, (0, 99))


# -- convert notation --------------------------------------------------------------------


def test_convert_is_a_plain_edit_and_switches_detection():
    env = Env("C G\nhello there")
    env.session.convert_notation("european")

    assert env.recorder.compact() == [
        ("TextEdited", 2, 0, 15, "Do Sol\nhello there", "plain", 18),
        ("HighlightState", 2, 0, (chord(0, 2), chord(3, 6))),
        # The toolbar follows the target notation (no key set: the first option).
        ("ToolbarState", "european", 120, 120, True, 100.0, "Do", 4, 4, False, "play"),
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


# -- insert directive ------------------------------------------------------------------------


def test_insert_directive_request_then_response_inserts_it():
    env = Env("C G\n{label: verse}\nAm")
    env.session.request_insert_directive("bpm", 4)

    assert env.recorder.compact() == [
        ("InsertDirectiveRequest", 1, "bpm", ("verse",), "american")]
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
    from session.directives import loop_label_choices

    env = Env("{label: verse}\nC\n{label: bridge}\nG")
    env.session.request_insert_directive("loop", 34)
    request = env.request(InsertDirectiveRequest)
    assert loop_label_choices(request.existing_labels) == ("@start", "bridge", "verse")

    env.session.respond(request.request_id, {"label": "bridge", "count": 3})
    assert env.session.text.endswith("G{loop: bridge 3} ")


def test_the_key_options_follow_the_notation():
    env = Env("Do Re", notation="european")
    env.session.request_insert_directive("key", 0)
    request = env.request(InsertDirectiveRequest)
    assert request.notation == "european"
    env.session.respond(request.request_id, {"key": "Sol"})
    assert env.session.text == "{key: Sol} Do Re"


def test_an_insert_offset_past_a_shrunken_text_is_clamped():
    env = Env("C G Am F")
    env.session.request_insert_directive("bpm", 8)
    env.session.set_text("C")  # the text changed while the dialog was open
    env.session.respond(1, {"value": "100"})
    assert env.session.text == "C{bpm: 100} "


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
    assert env.session.text == "C{bpm: 90} "
    env.session.respond(2, {"value": "90"})  # answered already
    assert env.session.text == "C{bpm: 90} "


# -- suggest capo ------------------------------------------------------------------------------

BARRE_SONG = "{key: F#}\nF#  B  C#  D#m  F#  B"


def test_capo_request_lists_the_fretboard_voicings_with_the_active_one_preselected():
    env = Env("C", voicing="guitar:drop_d")
    env.session.request_suggest_capo(None)
    request = env.request(CapoChoiceRequest)
    assert request.default == "guitar:drop_d"
    assert MenuItem("Guitar (Standard - EADGBE)", "guitar:standard") in request.options
    assert all(o.value.startswith(("guitar:", "voicing:")) for o in request.options)


def test_capo_defaults_to_standard_guitar_for_a_piano_voicing():
    env = Env("C", voicing="piano")
    env.session.request_suggest_capo(None)
    assert env.request(CapoChoiceRequest).default == "guitar:standard"


def test_capo_response_inserts_the_directive_as_one_grouped_edit():
    env = Env(BARRE_SONG)
    env.session.request_suggest_capo(None)
    env.recorder.clear()

    env.session.respond(1, "guitar:standard")

    edit = env.recorder.last(TextEdited)
    capo = int(edit.replacement.split("}")[0].split(":")[1])
    assert capo > 0
    assert (edit.start, edit.end, edit.undo) == (0, len(BARRE_SONG), UndoPolicy.GROUP)
    assert edit.replacement == f"{{capo: {capo}}}\n{BARRE_SONG}"
    assert [type(i).__name__ for i in env.recorder.items] == [
        "TextEdited", "HighlightState", "StatusState"]
    assert env.status() == f"Suggested capo {capo} for the whole song on Guitar (Standard - EADGBE)"


def test_no_capo_helps_only_says_so():
    env = Env("C G Am F")
    env.session.request_suggest_capo((0, 3))
    env.recorder.clear()

    env.session.respond(1, "guitar:standard")

    assert env.recorder.compact() == [
        ("StatusState", "No capo makes the selection easier on Guitar (Standard - EADGBE)")]
    assert env.session.text == "C G Am F"


def test_capo_cancelled_or_unknown_voicing_does_nothing():
    env = Env(BARRE_SONG)
    env.session.request_suggest_capo(None)
    env.recorder.clear()
    env.session.respond(1, None)
    env.session.request_suggest_capo(None)
    env.session.respond(2, "voicing:no such thing")
    assert env.recorder.of_type(TextEdited) == []
    assert env.recorder.of_type(StatusState) == []


# -- read-only while playing ------------------------------------------------------------------


def test_programmatic_edits_are_refused_while_playing():
    env = Env("C G Am F")
    env.main.set_key("C")
    env.play()

    env.session.transpose(2, None)
    env.session.convert_notation("european")
    env.session.insert_text(0, "G ")

    assert env.recorder.items == []
    assert env.session.text == env.main.current_text == "C G Am F"
    assert env.main.key == "C"
    assert env.main.notation.value == "american"


def test_dialogs_still_open_while_playing_but_their_answers_are_refused():
    env = Env(BARRE_SONG)
    env.session.request_insert_directive("bpm", 0)
    env.play()  # started while the dialog was open
    env.session.respond(1, {"value": "90"})

    env.session.request_suggest_capo(None)
    assert env.request(CapoChoiceRequest) is not None
    env.session.respond(2, "guitar:standard")

    assert env.recorder.of_type(TextEdited) == []
    assert env.session.text == BARRE_SONG

    env.session.stop()
    env.session.request_insert_directive("bpm", 0)
    env.session.respond(3, {"value": "90"})
    assert env.session.text.startswith("{bpm: 90} ")


def test_paused_counts_as_playing():
    env = Env("C G")
    env.play()
    env.session.play_pause()  # pause
    env.recorder.clear()
    env.session.transpose(1, None)
    assert env.recorder.of_type(TextEdited) == []


# -- open / new go through the same path ----------------------------------------------------------


def test_opening_a_document_is_a_plain_whole_text_edit():
    env = Env("C")
    store = env.main._documents
    store.contents[store.ref("song.txt").id] = "G D\n{bpm: 90}"
    env.main.open_file(store.ref("song.txt"))

    edit = env.recorder.of_type(TextEdited)[0]
    assert (edit.start, edit.end, edit.replacement, edit.undo) == (
        0, 1, "G D\n{bpm: 90}", UndoPolicy.PLAIN)
    assert env.recorder.last(HighlightState).text_revision == edit.text_revision
    assert env.main.is_modified is False
