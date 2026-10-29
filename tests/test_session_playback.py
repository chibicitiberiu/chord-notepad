"""AppSession playback: transport, playing chord, status line, audio failures.

The real PlaybackService renders the song on its render thread and hands the
events to a FakePlayer, which posts the progress pings through the host like
NotePlayer does. A test joins the render thread, then runs the host's posted
callbacks, so every step is deterministic.
"""

from unittest.mock import patch

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.audio_policy import AudioFailurePolicy
from session.events import AudioUnavailable, UserError
from session.host import HostDispatch
from session.session import AppSession
from session.state import (
    ChordSheetState, EditorState, PlaybackState, PlaybackStatus, StatusState, ToolbarState,
)
from session.testing import (
    EventRecorder, FakeChordSheet, FakePlayer, InMemoryDocumentStore, ManualHost,
)
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel

SONG = "C G\nla la\n{key: G}\nAm*2 F*2"


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    """A started session over the real PlaybackService and a FakePlayer."""

    def __init__(self, auto_play=True, audio_works=True, text=SONG):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.player = FakePlayer(auto_play=auto_play)
        self.audio = PlaybackService(
            FakeConfig(), player=self.player if audio_works else None, application=dispatch)
        if not audio_works:
            def fail(soundfont_path=None):
                self.audio._init_error = "no driver"
                return False
            self.audio.initialize_player = fail
        parser = SongParserService()
        self.main = MainWindowViewModel(
            FakeConfig(), self.audio, InMemoryDocumentStore(), parser, dispatch)
        self.sheet = FakeChordSheet()
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(parser),
            chord_sheet_viewmodel=self.sheet)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        self.session.set_text(text)
        self.host.advance(0.5)
        self.recorder.clear()

    def rendered(self):
        """Wait for the render thread, then run what it (and the player) posted."""
        thread = self.audio._render_thread
        if thread is not None:
            thread.join(timeout=10)
            assert not thread.is_alive()
        self.host.run_pending()

    def playback(self):
        return self.recorder.last(PlaybackState)

    def status(self):
        return self.recorder.last(StatusState).text


def _span(start, end):
    return ("chord", start, end)


def _editor(read_only):
    """The compacted EditorState for the defaults (TkFixedFont 11, American)."""
    return ("EditorState", "TkFixedFont", 11, read_only, "american")


def _toolbar(action="play", bpm_display=120):
    """The compacted ToolbarState for the defaults (120 BPM, key C, 4/4)."""
    return ("ToolbarState", "american", 120, bpm_display, action == "play", 100.0, "C",
            4, 4, False, action)


# -- golden: play -> progress -> finished ------------------------------------------


def test_play_progress_finished():
    env = Env()
    env.session.play_pause()
    # Started: the transport and the lock are on, the chord count is shown.
    assert env.recorder.compact() == [
        ("PlaybackState", "playing", None, None, 0, 0),
        _editor(True),
        # The tempo is read-only now and the button pauses.
        _toolbar("pause"),
        ("StatusState", "Playing 4 chords..."),
    ]
    env.recorder.clear()

    env.rendered()

    # (The strip's playhead has its own test below.)
    assert env.recorder.compact(skip=(ChordSheetState,)) == [
        ("PlaybackState", "playing", _span(0, 1), 0, 1, 3),
        ("StatusState", "Bar 1/3 | 120 BPM | 4/4 | Playing: C"),
        ("PlaybackState", "playing", _span(2, 3), 1, 2, 3),
        ("StatusState", "Bar 2/3 | 120 BPM | 4/4 | Playing: G"),
        ("PlaybackState", "playing", _span(19, 23), 2, 3, 3),
        ("StatusState", "Bar 3/3 | 120 BPM | 4/4 | Key: G | Playing: Am"),
        ("PlaybackState", "playing", _span(24, 27), 3, 3, 3),
        ("StatusState", "Bar 3/3 | 120 BPM | 4/4 | Key: G | Playing: F"),
        # Finished: back to idle, unlocked, "Ready".
        ("PlaybackState", "idle", None, None, 0, 0),
        _editor(False),
        _toolbar("play"),
        ("StatusState", "Ready"),
    ]
    assert env.main.is_playing is False


def test_the_chord_sheet_playhead_follows_playback_and_clears_at_the_end():
    env = Env()
    env.session.play_pause()
    env.rendered()
    assert env.sheet.pings == [("C", 0), ("G", 1), ("Am", 2), ("F", 3), (None, None)]


def test_directive_tempo_reaches_the_toolbar_and_the_status():
    env = Env(text="{bpm: 90}\nC G")
    env.session.play_pause()
    env.rendered()
    # Read-only 120 until the first chord, then the directive's 90, then
    # the user's 120 again once the song is over.
    assert [(t.bpm_display, t.bpm_editable) for t in env.recorder.of_type(ToolbarState)] == [
        (120, False), (90, False), (120, True)]
    assert all(t.bpm == 120 for t in env.recorder.of_type(ToolbarState))
    assert "90 BPM" in env.recorder.of_type(StatusState)[1].text


# -- pause / resume / stop ---------------------------------------------------------


def test_pause_and_resume_keep_the_playing_chord():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(chords=1)
    env.host.run_pending()
    env.recorder.clear()

    env.session.play_pause()
    assert env.recorder.compact() == [
        ("PlaybackState", "paused", _span(0, 1), 0, 1, 3),
        _toolbar("resume"),
        ("StatusState", "Paused playback"),
    ]
    assert env.player.calls[-1] == "pause"
    env.recorder.clear()

    env.session.play_pause(from_offset=10)  # Shift is ignored when paused
    assert env.recorder.compact() == [
        ("PlaybackState", "playing", _span(0, 1), 0, 1, 3),
        _toolbar("pause"),
        ("StatusState", "Resumed playback"),
    ]
    assert env.player.calls[-1] == "resume"

    env.player.play()
    env.host.run_pending()
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.status() == "Ready"


def test_stop_returns_to_idle_and_drops_pings_posted_before_it():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(chords=1)
    env.host.run_pending()
    env.recorder.clear()

    env.session.stop()
    assert env.recorder.compact() == [
        ("PlaybackState", "idle", None, None, 0, 0),
        _editor(False),
        _toolbar("play"),
        ("StatusState", "Stopped playback"),
    ]
    env.recorder.clear()

    # A ping the player posted before it saw the stop arrives late.
    env.player.play(chords=1)
    env.host.run_pending()
    assert env.recorder.items == []
    assert env.sheet.pings == [("C", 0)]


def test_pings_and_the_end_of_a_stopped_run_are_dropped_during_the_next_run():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    old_ping = env.player.on_event_callback
    old_end = env.player.on_playback_finished_callback
    env.session.stop()
    env.session.play_pause()  # a new run, started before the old run's posts arrived
    env.rendered()
    env.recorder.clear()

    # The old run's ping and its end arrive now (posted before it saw the stop).
    from models.chord import ChordInfo
    from models.playback_event import PlaybackEventArgs, PlaybackEventType
    chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)
    old_ping(PlaybackEventArgs(event_type=PlaybackEventType.CHORD_START, chord_info=chord,
                               chord_index=0, current_bar=1, total_bars=3))
    old_end()
    env.host.run_pending()

    assert env.recorder.items == []
    assert env.main.is_playing is True

    # The new run's own pings still get through.
    env.player.play(chords=1)
    env.host.run_pending()
    assert env.recorder.last(PlaybackState).playing_span is not None


def test_stop_while_idle_only_says_so():
    env = Env()
    env.session.stop()
    assert env.recorder.compact() == [("StatusState", "Stopped playback")]


# -- play from the cursor -----------------------------------------------------------


def test_play_from_offset_starts_at_the_next_chord():
    env = Env()
    env.session.play_pause(from_offset=2)  # the cursor right before G
    assert env.status() == "Playing from cursor (4 chords)..."
    env.rendered()
    first = env.recorder.of_type(PlaybackState)[1]
    assert first.playing_span.start == 2
    assert [p[0] for p in env.sheet.pings] == ["G", "Am", "F", None]


def test_play_from_offset_after_the_last_chord_plays_nothing():
    env = Env()
    env.session.play_pause(from_offset=len(SONG))
    assert env.recorder.compact() == [("StatusState", "No chords to play from cursor")]
    assert env.main.is_playing is False


def test_play_without_chords():
    env = Env(text="just words")
    env.session.play_pause()
    assert env.recorder.compact() == [("StatusState", "No chords to play")]


def test_play_uses_the_text_typed_before_the_debounce():
    env = Env(text="")
    env.session.set_text("C G")  # detection still pending
    env.session.play_pause()
    env.rendered()
    assert [p[0] for p in env.sheet.pings] == ["C", "G", None]


# -- tap to hear --------------------------------------------------------------------


def test_tap_plays_the_chord_under_the_offset():
    env = Env()
    env.session.tap_chord_at(2)
    assert len(env.player.immediate) == 1
    assert env.recorder.compact() == [("StatusState", "Playing: G")]


def test_tap_outside_a_valid_chord_does_nothing():
    env = Env(text="C  Cmaj13#11b9\nCome")
    env.session.tap_chord_at(1)   # space
    env.session.tap_chord_at(5)   # inside the invalid chord
    env.session.tap_chord_at(16)  # the lyric line
    assert env.player.immediate == []
    assert env.recorder.items == []


def test_tap_works_while_a_song_plays():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.session.tap_chord_at(0)
    assert len(env.player.immediate) == 1
    assert env.playback().status is PlaybackStatus.PLAYING


# -- audio unavailable ------------------------------------------------------------------


def test_audio_unavailable_is_reported_once_for_taps():
    env = Env(audio_works=False)
    env.session.tap_chord_at(0)
    env.session.tap_chord_at(2)
    events = env.recorder.of_type(AudioUnavailable)
    assert len(events) == 1
    assert events[0].from_click is True
    assert "no driver" in events[0].message
    assert "Clicked chords won't play" in events[0].message
    assert env.status() == "Audio is not available"


def test_audio_unavailable_is_reported_every_time_for_play():
    env = Env(audio_works=False)
    env.session.play_pause()
    env.session.play_pause()
    events = env.recorder.of_type(AudioUnavailable)
    assert [e.from_click for e in events] == [False, False]
    assert "no driver" in events[0].message
    assert "Clicked chords" not in events[0].message
    assert env.status() == "Audio is not available"
    assert env.main.is_playing is False


def test_play_failures_do_not_use_up_the_tap_report():
    env = Env(audio_works=False)
    env.session.play_pause()
    env.session.tap_chord_at(0)
    env.session.tap_chord_at(0)
    assert [e.from_click for e in env.recorder.of_type(AudioUnavailable)] == [False, True]


def test_the_policy_can_be_shared():
    policy = AudioFailurePolicy()
    assert policy.should_report(from_click=True) is True  # e.g. the chord sheet
    host = ManualHost()
    env = Env(audio_works=False)
    session = AppSession(host, main_window_viewmodel=env.main,
                         text_editor_viewmodel=TextEditorViewModel(SongParserService()),
                         audio_failure_policy=policy)
    assert session.audio_failure_policy is policy
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.set_text("C")
    host.advance(0.5)
    session.tap_chord_at(0)
    assert recorder.of_type(AudioUnavailable) == []


# -- render failure -----------------------------------------------------------------------


def test_render_failure_returns_to_idle_and_reports_a_user_error():
    env = Env()
    with patch("services.playback_service.SongRenderer.render",
               side_effect=ValueError("render broke")):
        env.session.play_pause()
        env.recorder.clear()
        env.rendered()
    assert env.recorder.compact() == [
        ("PlaybackState", "idle", None, None, 0, 0),
        _editor(False),
        _toolbar("play"),
        ("StatusState", "Ready"),
        ("StatusState", "Playback failed"),
        ("UserError", "Playback Error", "Could not play the song.\n\nrender broke"),
    ]


# -- status line, lifecycle ------------------------------------------------------------------


def test_initial_states():
    host = ManualHost()
    env = Env()
    session = AppSession(host, main_window_viewmodel=env.main,
                         text_editor_viewmodel=TextEditorViewModel(SongParserService()))
    recorder = EventRecorder()
    session.subscribe(recorder)
    assert recorder.compact()[1:5] == [
        ("PlaybackState", "idle", None, None, 0, 0),
        ("StatusState", "Ready"),
        _editor(False),
        _toolbar("play"),
    ]
    assert [type(item).__name__ for item in recorder.items[5:]] == [
        "VoicingMenuState", "InstrumentMenuState", "DocumentState", "RecentDocumentsState"]


def test_an_inserted_chord_status_goes_through_the_status_state():
    env = Env(text="C G ")
    env.session.insert_chord(4, "Am")
    env.session.tap_chord_at(0)
    env.session.insert_chord(0, "F")
    assert [s.text for s in env.recorder.of_type(StatusState)] == [
        "Inserted chord: Am", "Playing: C", "Inserted chord: F"]
    assert env.session.text == "F C G Am "


def test_playback_commands_need_the_session_thread():
    import threading

    env = Env()
    errors = []

    def call():
        try:
            env.session.play_pause()
        except RuntimeError as e:
            errors.append(e)

    t = threading.Thread(target=call)
    t.start()
    t.join()
    assert errors and "session thread" in str(errors[0])


def test_shutdown_stops_following_playback():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    seen = len(env.recorder.items)
    env.session.shutdown()
    env.player.play()
    env.host.run_pending()
    assert len(env.recorder.items) == seen
