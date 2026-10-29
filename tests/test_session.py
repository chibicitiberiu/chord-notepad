"""AppSession: the text mirror, debounced detection and highlight spans.

The session runs on a ManualHost, so the 0.5 s detection debounce is driven
by the test's virtual clock. Detection, the parser and the viewmodels are real.
"""

import threading
from unittest.mock import ANY, MagicMock

import pytest

from models.notation import Notation
from services.song_parser_service import SongParserService
from session.host import HostDispatch
from session.session import AppSession
from session.state import HighlightState, Span, SpanKind
from session.testing import EventRecorder, InMemoryDocumentStore, ManualHost
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
    """A session on a ManualHost with a recorder subscribed."""

    def __init__(self, notation="american"):
        self.host = ManualHost()
        parser = SongParserService()
        self.main = MainWindowViewModel(
            FakeConfig(notation=notation), MagicMock(), InMemoryDocumentStore(),
            parser, HostDispatch(self.host))
        self.detector = TextEditorViewModel(parser)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main, text_editor_viewmodel=self.detector)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()

    def highlights(self):
        return self.recorder.of_type(HighlightState)


@pytest.fixture
def env():
    return Env()


def chord(start, end):
    return ("chord", start, end)


def load(env, text):
    """Type ``text`` and let the detection debounce run out."""
    env.session.set_text(text)
    env.host.advance(0.5)


# -- golden: typing ----------------------------------------------------------


def test_type_text_no_spans_before_the_debounce_spans_after(env):
    assert env.recorder.compact() == [
        ("HighlightState", 0, 0, ()),
        ("PlaybackState", "idle", None, None, 0, 0),
        ("StatusState", "Ready"),
        ("EditorState", "TkFixedFont", 11, False, "american"),
        ("ToolbarState", "american", 120, 120, True, 100.0, "C", 4, 4, False, "play"),
        ("VoicingMenuState", "piano", ANY),
        ("InstrumentMenuState", 0, ANY),
        ("DocumentState", "Untitled", None, False, "Untitled - Chord Notepad", None),
        ("RecentDocumentsState", ()),
    ]
    env.recorder.clear()

    env.session.set_text("C G\nla la {bpm: 90} // x")
    # Only the title's "modified" mark comes at once.
    assert env.recorder.compact() == [
        ("DocumentState", "Untitled", None, True, "Untitled* - Chord Notepad", None)]
    env.recorder.clear()

    env.host.advance(0.499)
    assert env.recorder.items == []

    env.host.advance(0.001)
    assert env.recorder.compact() == [
        ("HighlightState", 1, 0, (
            ("comment", 20, 24),
            chord(0, 1), chord(2, 3),
            ("directive", 10, 19),
        )),
    ]


def test_each_keystroke_restarts_the_debounce(env):
    env.session.set_text("C")
    env.recorder.clear()  # the title's "modified" mark
    env.host.advance(0.3)
    env.session.set_text("C G")
    env.host.advance(0.3)  # 0.6 s after the first keystroke, 0.3 s after the last
    assert env.recorder.items == []
    assert env.host.pending_timers == 1

    env.host.advance(0.2)
    assert env.recorder.compact() == [("HighlightState", 2, 0, (chord(0, 1), chord(2, 3)))]


def test_set_text_keeps_the_viewmodel_text_and_modified_flag(env):
    assert env.main.is_modified is False
    env.session.set_text("C G")
    assert env.session.text == "C G"
    assert env.main.current_text == "C G"
    assert env.main.is_modified is True


def test_same_text_does_not_rearm_detection(env):
    env.session.set_text("C G")
    env.host.advance(0.5)
    env.recorder.clear()

    env.session.set_text("C G")
    assert env.host.pending_timers == 0
    env.host.advance(1)
    assert env.recorder.items == []
    assert env.session.text_revision == 1


def test_client_token_comes_back_with_the_spans(env):
    env.recorder.clear()
    env.session.set_text("C", client_token=7)
    env.session.set_text("C G", client_token=8)
    env.host.advance(0.5)
    assert env.highlights()[-1].client_token == 8
    assert env.highlights()[-1].text_revision == 2


def test_a_new_token_for_the_same_text_resends_current_spans(env):
    env.session.set_text("C G", client_token=1)
    env.host.advance(0.5)
    env.recorder.clear()

    env.session.set_text("C G", client_token=2)
    assert env.recorder.compact() == [("HighlightState", 1, 2, (chord(0, 1), chord(2, 3)))]


# -- immediate detection -----------------------------------------------------


def test_a_viewmodel_replace_highlights_without_waiting(env):
    # Open and New replace the text through the viewmodel.
    env.session.set_text("C")  # pending debounce...
    env.recorder.clear()
    env.main.set_and_notify("current_text", "C G")
    assert env.recorder.compact() == [
        ("TextEdited", 2, 0, 1, "C G", "plain", 3),
        ("HighlightState", 2, 0, (chord(0, 1), chord(2, 3))),
    ]
    assert env.host.pending_timers == 0  # ...is cancelled
    assert env.session.text == "C G"


def test_a_viewmodel_replace_with_the_same_text_redetects_at_once(env):
    env.session.set_text("C G")
    env.recorder.clear()
    env.main.new_file()
    env.main.set_and_notify("current_text", "C G")
    assert env.recorder.compact()[-1] == ("HighlightState", 3, 0, (chord(0, 1), chord(2, 3)))
    assert env.host.pending_timers == 0


def test_insert_text_splices_and_highlights_immediately(env):
    load(env, "C G\nla la")
    env.recorder.clear()

    env.session.insert_text(4, "Am ")
    assert env.session.text == "C G\nAm la la"
    assert env.main.current_text == "C G\nAm la la"
    # "Am la la" is still a lyric line; inserting into the chord line is not.
    env.session.insert_text(3, " Am")
    assert env.session.text == "C G Am\nAm la la"
    assert env.highlights()[-1] == HighlightState(3, 0, (
        Span(0, 1, SpanKind.CHORD), Span(2, 3, SpanKind.CHORD), Span(4, 6, SpanKind.CHORD)))


def test_insert_text_rejects_an_offset_outside_the_text(env):
    load(env, "C")
    with pytest.raises(ValueError):
        env.session.insert_text(2, "G")
    with pytest.raises(ValueError):
        env.session.insert_text(-1, "G")


def test_notation_change_redetects_immediately(env):
    load(env, "Do Re Mi")
    assert env.highlights()[-1].spans == ()

    env.recorder.clear()
    env.main.set_notation(Notation.EUROPEAN)
    assert env.recorder.compact() == [
        ("HighlightState", 1, 0, (chord(0, 2), chord(3, 5), chord(6, 8))),
        ("EditorState", "TkFixedFont", 11, False, "european"),
        ("ToolbarState", "european", 120, 120, True, 100.0, "Do", 4, 4, False, "play")]


def test_detection_starts_in_the_saved_notation():
    env = Env(notation="european")
    load(env, "Do Re")
    assert [s.kind for s in env.highlights()[-1].spans] == [SpanKind.CHORD, SpanKind.CHORD]


# -- hit-testing ---------------------------------------------------------------


def test_chord_at_uses_the_latest_detection(env):
    load(env, "C  Cmaj13#11b9\nCome")
    assert env.session.chord_at(0) == Span(0, 1, SpanKind.CHORD)
    assert env.session.chord_at(1) is None
    assert env.session.chord_at(5) == Span(3, 14, SpanKind.CHORD_INVALID)
    assert env.session.chord_at(16) is None


def test_chord_at_lags_until_the_debounce_like_the_highlighting(env):
    env.session.set_text("C G")
    assert env.session.chord_at(0) is None
    env.host.advance(0.5)
    assert env.session.chord_at(0) == Span(0, 1, SpanKind.CHORD)


# -- delivery contract through the session ---------------------------------------


def test_listeners_are_only_called_between_commands(env):
    seen_during = []

    def listener(item):
        # Delivery happens after the command returned: the mirror is complete.
        seen_during.append(env.session.text)

    env.session.subscribe(listener)
    seen_during.clear()
    load(env, "C G")
    # The title's "modified" mark, then the highlight.
    assert seen_during == ["C G", "C G"]


def test_a_listener_may_run_a_command(env):
    def echo(item):
        if isinstance(item, HighlightState) and item.text_revision == 1:
            env.session.insert_text(0, "G ")

    env.session.subscribe(echo)
    env.recorder.clear()
    load(env, "C")
    revisions = [h.text_revision for h in env.highlights()]
    assert revisions == [1, 2]
    assert env.session.text == "G C"


def test_new_subscriber_gets_the_current_highlight(env):
    load(env, "C G")
    late = EventRecorder()
    env.session.subscribe(late)
    assert late.of_type(HighlightState) == [late.items[0]]
    assert late.compact()[0] == ("HighlightState", 1, 0, (chord(0, 1), chord(2, 3)))


def test_commands_must_run_on_the_session_thread(env):
    errors = []

    def call():
        try:
            env.session.set_text("C")
        except RuntimeError as exc:
            errors.append(exc)

    worker = threading.Thread(target=call)
    worker.start()
    worker.join()
    assert len(errors) == 1
    assert env.session.text == ""


def test_shutdown_cancels_detection_and_stops_delivery(env):
    env.session.set_text("C G")
    env.recorder.clear()
    env.session.shutdown()
    env.session.shutdown()  # idempotent
    assert env.host.pending_timers == 0
    env.main.set_notation(Notation.EUROPEAN)  # no longer observed
    env.host.advance(1)
    assert env.recorder.items == []
