"""Fonts, the chord sheet and click-to-hear audio through the session.

The session publishes ``EditorState`` (font, lock, notation) and
``ChordSheetState`` and takes the View menu's font commands, the chord sheet's
commands and the click-to-hear failures of sources it doesn't play itself
(the chord identifier). Runs on a ManualHost over the real viewmodel and
PlaybackService with a FakePlayer and a FakeChordSheet.
"""

from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session.events import AudioUnavailable
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.session import AppSession
from chordnotepad.session.state import ChordSheetState, ChordSheetView, EditorState
from chordnotepad.session.testing import (
    EventRecorder, FakeChordSheet, FakePlayer, InMemoryDocumentStore, ManualHost,
)
from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel
from chordnotepad.viewmodels.text_editor_viewmodel import TextEditorViewModel


class FakeConfig:
    def __init__(self, **values):
        self.values = dict(values)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class Env:
    def __init__(self, sheet=True, **config):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(**config)
        self.player = FakePlayer(auto_play=False)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.main = MainWindowViewModel(
            self.config, self.audio, InMemoryDocumentStore(), SongParserService(), dispatch)
        self.sheet = FakeChordSheet() if sheet else None
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()),
            chord_sheet_viewmodel=self.sheet)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()

    def editor(self) -> EditorState:
        return self.recorder.last(EditorState)

    def sheet_state(self) -> ChordSheetState:
        return self.recorder.last(ChordSheetState)


# -- fonts --------------------------------------------------------------------------


def test_editor_state_carries_font_and_notation():
    env = Env(font_family="Consolas", font_size=14, notation="european")
    assert env.editor() == EditorState("Consolas", 14, False, "european")


def test_set_font():
    env = Env()
    env.session.set_font("Consolas", 16)
    assert (env.editor().font_family, env.editor().font_size) == ("Consolas", 16)
    assert env.config.get("font_family") == "Consolas"


def test_step_font_size_stays_within_limits():
    env = Env(font_size=71)
    env.session.step_font_size(1)
    env.session.step_font_size(1)
    assert env.editor().font_size == 72
    env.session.step_font_size(-100)
    assert env.editor().font_size == 6


def test_reset_font_size():
    env = Env(font_size=20)
    env.session.reset_font_size()
    assert env.editor().font_size == 11


def test_notation_change_reaches_the_editor_state():
    env = Env()
    env.session.set_notation("european")
    assert env.editor().notation == "european"


# -- chord sheet ------------------------------------------------------------------------


def test_initial_chord_sheet_state():
    env = Env()
    assert env.sheet_state() == ChordSheetState(
        visible=False, height=200, active_view="keyboard",
        views=(ChordSheetView("keyboard", "Keyboard", True),
               ChordSheetView("fret", "Fret", False)),
        disabled_reason="Pick a fretted instrument.", zoom=1.0, zoom_supported=True,
        current_index=None, song_revision=0)


def test_no_chord_sheet_no_state_and_commands_do_nothing():
    env = Env(sheet=False)
    assert env.recorder.of_type(ChordSheetState) == []
    env.session.set_chord_sheet_visible(True)
    env.session.audition(0)
    env.session.chord_sheet_zoom(1)
    env.session.chord_sheet_zoom_reset()
    assert env.recorder.of_type(ChordSheetState) == []


def test_visibility_and_height():
    env = Env()
    env.session.set_chord_sheet_visible(True)
    assert env.sheet_state().visible is True
    env.session.set_chord_sheet_height(321)
    assert env.sheet_state().height == 321


def test_views_and_zoom():
    env = Env()
    env.session.chord_sheet_zoom(1)
    assert env.sheet_state().zoom == 1.25
    env.session.chord_sheet_zoom(-1)
    assert env.sheet_state().zoom == 1.0
    env.session.chord_sheet_zoom(2)
    env.session.chord_sheet_zoom_reset()
    assert env.sheet_state().zoom == 1.0

    env.session.set_chord_sheet_view("fret")  # unavailable: ignored
    assert env.sheet_state().active_view == "keyboard"
    env.sheet.finish_render(object(), fingering=True)
    state = env.sheet_state()
    assert state.song_revision == 1
    assert state.disabled_reason is None
    assert all(v.available for v in state.views)
    env.session.set_chord_sheet_view("fret")
    assert env.sheet_state().active_view == "fret"
    assert env.sheet_state().zoom_supported is False


def test_a_notation_switch_republishes_the_sheet_with_a_new_revision(monkeypatch):
    from chordnotepad.chord_sheet import pack

    env = Env()
    env.sheet.finish_render(object(), fingering=True)
    revision = env.sheet_state().song_revision
    published = len(env.recorder.of_type(ChordSheetState))
    env.session.set_notation("european")
    assert len(env.recorder.of_type(ChordSheetState)) > published
    assert env.sheet_state().song_revision == revision + 1

    # The buffer is packed in the notation the snapshot caught.
    calls = []
    monkeypatch.setattr(pack, "pack_view",
                        lambda *args, **kwargs: calls.append(kwargs) or b"")
    env.session.chord_sheet_buffer(130.0)
    assert calls[-1]["notation"] == "european"
    env.session.set_notation("american")
    assert env.sheet_state().song_revision == revision + 2
    env.session.chord_sheet_buffer(130.0)
    assert calls[-1]["notation"] == "american"


def test_a_time_signature_or_key_from_the_player_bar_renders_the_sheet_again():
    # Tibi, 2026-11-15: 7/8 picked in the player bar left the strip on the
    # old bars. The strip renders with the document's time signature, so a
    # change feeds it the song again (it debounces).
    env = Env()
    env.session.set_text("C G Am F")
    env.host.advance(0.5)
    fed = len(env.sheet.fed)
    env.session.set_time_signature(7, 8)
    assert len(env.sheet.fed) > fed
    fed = len(env.sheet.fed)
    env.session.set_time_signature(7, 8)              # unchanged: nothing new
    assert len(env.sheet.fed) == fed
    env.session.set_key("D")
    assert env.sheet.fed[-1][1] == "D"


def test_playhead_reaches_the_state():
    env = Env()
    env.session.set_text("C G")
    env.host.advance(0.5)
    env.session.play_pause()
    env.audio._render_thread.join(timeout=10)
    env.host.run_pending()
    env.player.play(chords=2)
    env.host.run_pending()
    assert env.sheet_state().current_index == 1


def test_audition():
    env = Env()
    env.session.audition(3)
    assert env.sheet.auditioned == [3]


# -- click-to-hear failures share one policy -------------------------------------------------


def test_audition_failures_are_reported_once():
    env = Env()
    env.sheet.audition_error = "no driver"
    env.session.audition(0)
    env.session.audition(1)
    events = env.recorder.of_type(AudioUnavailable)
    assert len(events) == 1
    assert events[0].from_click is True
    assert "no driver" in events[0].message
    assert "Clicked chords won't play" in events[0].message


def test_identifier_failures_share_the_policy_with_auditions_and_taps():
    env = Env()
    env.session.report_audio_failure("no driver")
    env.sheet.audition_error = "no driver"
    env.session.audition(0)
    assert len(env.recorder.of_type(AudioUnavailable)) == 1


def test_play_failures_are_reported_every_time():
    env = Env()
    env.session.report_audio_failure("no driver", from_click=False)
    env.session.report_audio_failure("no driver", from_click=False)
    events = env.recorder.of_type(AudioUnavailable)
    assert [e.from_click for e in events] == [False, False]
