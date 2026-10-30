"""AppSession's player: the playhead, Android's status line, song defaults.

The playhead is the chord Play starts from. Android's player moves it with
taps, playback and ⏮; the desktop keeps playing from the top unless a
view sets one explicitly (it doesn't yet). Same harness as the playback
tests: the real PlaybackService over a FakePlayer, on a ManualHost.
"""

from types import SimpleNamespace

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.events import TextEdited, UndoPolicy, UserError
from session.highlighting import first_chord, nearest_chord
from session.host import HostDispatch
from session.platform import ANDROID, DESKTOP
from session.session import AppSession, _shift_offset
from session.state import (
    ChordSheetState, PlaybackState, PlaybackStatus, SongDefault, SongDefaultsState, StatusState,
)
from session.testing import (
    EventRecorder, FakeChordSheet, FakePlayer, InMemoryDocumentStore, ManualHost,
)
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel

#        0123456789012345678901234567
SONG = "C   G\nla la\nAm  F\nlu lu"
# Chords: C 0-1, G 4-5, Am 12-14, F 16-17 (one bar each in 4/4).


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    """A started session on ``platform`` over the real PlaybackService."""

    def __init__(self, platform=ANDROID, text=SONG, auto_play=True, sheet=True):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.player = FakePlayer(auto_play=auto_play)
        self.config = FakeConfig()
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.parser = SongParserService()
        self.main = MainWindowViewModel(
            self.config, self.audio, InMemoryDocumentStore(), self.parser, dispatch)
        self.sheet = FakeChordSheet() if sheet else None
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(self.parser),
            chord_sheet_viewmodel=self.sheet, platform=platform)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.everything = EventRecorder()  # never cleared
        self.session.subscribe(self.everything)
        self.session.start()
        if text:
            self.session.set_text(text)
            self.host.advance(0.5)
        self.recorder.clear()

    def rendered(self):
        thread = self.audio._render_thread
        if thread is not None:
            thread.join(timeout=10)
            assert not thread.is_alive()
        self.host.run_pending()

    def playback(self):
        return self.session._playback

    def playhead(self):
        return self.session._playback.playhead_offset

    def status(self):
        return self.everything.last(StatusState).text

    def first_played_chord(self):
        """The first chord the player's buffer sounds (where playback started)."""
        for event in self.player.played:
            info = event.metadata.get("chord_info")
            if info is not None and event.metadata.get("has_callback"):
                return info.chord
        return None

    def strip_song(self, spans):
        """Give the fake strip a rendered song with one chord per span (bar i+1)."""
        chords = [SimpleNamespace(chord_info=SimpleNamespace(start=s, end=e), bar=i + 1,
                                  song_bar=i + 1, skipped=False)
                  for i, (s, e) in enumerate(spans)]
        self.sheet.finish_render(SimpleNamespace(chords=chords, total_bars=len(spans)))


def lines_of(text):
    return SongParserService().detect_chords_in_text(text, "american")


# -- the snap rule -------------------------------------------------------------------


@pytest.mark.parametrize("offset, expected", [
    (0, "C"),      # on C
    (1, "C"),      # between C and G, nearer C
    (2, "G"),      # as near both: the later one
    (7, "C"),      # lyric line "la la": its chords are on the line above
    (10, "G"),     # ... at the tap's column
    (13, "Am"),    # inside Am
    (25, "F"),     # last line, under F's column
    (999, "F"),    # clamped to the end
])
def test_nearest_chord(offset, expected):
    assert nearest_chord(lines_of(SONG), SONG, offset).chord == expected


def test_nearest_chord_ties_prefer_the_line_above_and_the_later_chord():
    text = "C\nla\nG"
    assert nearest_chord(lines_of(text), text, 2).chord == "C"   # equally far: above
    text = "C  G"
    assert nearest_chord(lines_of(text), text, 2).chord == "G"   # 1 from each: later


def test_nearest_chord_skips_invalid_chords_and_needs_one():
    assert nearest_chord(lines_of("la la"), "la la", 0) is None
    assert first_chord(lines_of("la la")) is None
    assert first_chord(lines_of(SONG)).chord == "C"


@pytest.mark.parametrize("old, new, offset, expected", [
    ("abcdef", "abXcdef", 4, 5),     # insert before: shifts
    ("abcdef", "abcdeXf", 2, 2),     # edit after: stays
    ("abcdef", "aZZf", 3, 1),        # inside the replaced range: its start
    ("abcdef", "abcdef", 3, 3),
    ("aaa", "aaaa", 3, 4),           # repeated text: the end moves
])
def test_shift_offset(old, new, offset, expected):
    assert _shift_offset(old, new, offset) == expected


# -- desktop: unchanged ---------------------------------------------------------------


def test_desktop_has_no_playhead_and_plays_from_the_top():
    env = Env(DESKTOP)
    assert env.playhead() is None
    env.session.tap_chord_at(12)
    assert env.playhead() is None
    assert env.status() == "Playing: Am"
    env.session.play_pause()
    assert env.status() == "Playing 4 chords..."
    env.rendered()
    assert env.first_played_chord() == "C"
    assert env.playhead() is None
    assert env.status() == "Ready"


def test_desktop_set_playhead_is_explicit_and_play_starts_there():
    env = Env(DESKTOP)
    env.session.set_playhead(13)
    assert env.playhead() == 12
    env.session.play_pause()
    assert env.status() == "Playing from cursor (4 chords)..."
    env.rendered()
    assert env.first_played_chord() == "Am"
    # Playback doesn't move it on desktop; the end of the song doesn't either.
    assert env.playhead() == 12
    env.session.rewind()
    assert env.playhead() == 0
    assert env.status() == "Ready"


# -- Android: the playhead ----------------------------------------------------------


def test_android_playhead_defaults_to_the_first_chord_and_follows_edits():
    env = Env(text="")
    assert env.playhead() is None
    env.session.set_text(SONG)
    env.host.advance(0.5)
    assert env.playhead() == 0
    env.session.set_playhead(16)
    assert env.playhead() == 16
    # Text typed before it moves it at once, with the text.
    env.session.set_text("x" + SONG)
    assert env.recorder.last(PlaybackState).playhead_offset == 17
    env.host.advance(0.5)
    assert env.playhead() == 17
    # Its chord deleted: it snaps to the nearest one left.
    env.session.set_text("xC   G\nla la\nAm  \nlu lu")
    env.host.advance(0.5)
    assert env.playhead() == 13
    # No chords: no playhead.
    env.session.set_text("la la")
    env.host.advance(0.5)
    assert env.playhead() is None


def test_android_opening_a_document_puts_the_playhead_on_its_first_chord():
    env = Env()
    env.main.documents.contents["memory:song.txt"] = "{key: G}\nG  D"
    env.session.set_playhead(16)
    env.session.open_document(InMemoryDocumentStore.ref("song.txt"))
    env.session.respond(env.session.pending_request.request_id, "discard")
    assert env.session.text == "{key: G}\nG  D"
    assert env.playhead() == 9


def test_android_tap_moves_the_playhead_and_sounds_the_chord():
    env = Env()
    env.session.tap_chord_at(13)
    assert env.playhead() == 12
    assert env.player.immediate  # auditioned
    assert env.status() == "Ready"  # the strip hasn't rendered: no bar known
    # Not on a chord: nothing (set_playhead is for taps elsewhere).
    env.session.tap_chord_at(8)
    assert env.playhead() == 12


def test_android_play_starts_at_the_playhead_and_follows_playback():
    env = Env()
    env.session.set_playhead(4)
    env.session.play_pause()
    assert env.status() == "Starting…"
    env.rendered()
    assert env.first_played_chord() == "G"
    states = env.recorder.of_type(PlaybackState)
    playing = [(s.playing_span.start, s.playhead_offset, s.bar) for s in states
               if s.playing_span is not None]
    # Bars count from the top of the song although playback started at bar 2.
    assert playing == [(4, 4, 2), (12, 12, 3), (16, 16, 4)]
    # The end of the song brings it back to the first chord.
    assert env.playhead() == 0
    assert env.playback().status is PlaybackStatus.IDLE
    # ...and the bars the pings told are known for the idle status.
    assert env.status() == "Ready"  # C (bar 1) didn't play in this run


def test_android_status_line_is_position_and_activity():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(2)
    env.host.run_pending()
    assert env.status() == "Bar 2/4 · Playing G"
    env.session.play_pause()
    assert env.status() == "Bar 2/4 · Paused"
    env.session.play_pause()
    assert env.status() == "Bar 2/4 · Playing G"
    env.player.play()
    env.host.run_pending()
    # Finished: back on the first chord, whose bar the run saw.
    assert env.playhead() == 0
    assert env.status() == "Bar 1/4"


def test_android_idle_status_follows_the_strip_and_the_playhead():
    env = Env()
    env.session.set_playhead(12)
    assert env.status() == "Ready"
    env.strip_song([(0, 1), (4, 5), (12, 14), (16, 17)])
    assert env.status() == "Bar 3/4"
    assert env.recorder.last(ChordSheetState).cursor_index == 2
    env.session.set_playhead(16)
    assert env.status() == "Bar 4/4"
    assert env.recorder.last(ChordSheetState).cursor_index == 3
    # Another status (an insert) isn't overwritten by a later render.
    env.session.insert_text(len(env.session.text), " ")
    env.strip_song([(0, 1), (4, 5), (12, 14), (16, 17)])
    assert env.status() == "Bar 4/4"


def test_cursor_index_is_the_first_occurrence_of_a_looped_chord():
    env = Env()
    env.strip_song([(0, 1), (4, 5), (0, 1), (4, 5)])
    env.session.set_playhead(4)
    assert env.recorder.last(ChordSheetState).cursor_index == 1


def test_android_pause_keeps_the_playhead_and_rewind_stops_and_resets():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(3)
    env.host.run_pending()
    env.session.play_pause()
    assert env.playback().status is PlaybackStatus.PAUSED
    assert env.playhead() == 12
    env.session.rewind()
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.player.calls[-1] == "stop"
    assert env.playhead() == 0


def test_android_stop_keeps_the_playhead_where_playback_was():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(2)
    env.host.run_pending()
    env.session.stop()
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.playhead() == 4
    assert env.status() == "Bar 2/4"


def test_android_moving_the_playhead_while_paused_drops_the_paused_song():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    env.session.play_pause()
    env.session.set_playhead(16)
    assert env.playback().status is PlaybackStatus.IDLE
    assert env.playhead() == 16
    env.session.play_pause()   # plays from the new playhead, not a resume
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert env.playback().playing_span.start == 16


def test_android_moving_the_playhead_while_playing_jumps_there():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    env.session.tap_chord_at(16)   # while playing: a jump, not an audition
    assert env.player.immediate == []
    assert env.playback().status is PlaybackStatus.PLAYING
    env.rendered()
    env.player.play(1)
    env.host.run_pending()
    assert env.playback().playing_span.start == 16
    assert env.playhead() == 16


def test_android_set_playhead_without_chords_does_nothing():
    env = Env(text="la la")
    env.session.set_playhead(2)
    assert env.playhead() is None


# -- song defaults --------------------------------------------------------------------


def defaults(env):
    return env.recorder.last(SongDefaultsState) or env.session._song_defaults()


def test_song_defaults_from_the_toolbar():
    env = Env(text="C G")
    state = env.session._song_defaults()
    assert state == SongDefaultsState(
        SongDefault("120", False, None), SongDefault("4/4", False, None),
        SongDefault("", False, None), "120 · 4/4")
    env.session.set_key("G")
    env.session.set_time_signature(3, 4)
    env.session.set_bpm(90)
    assert env.recorder.last(SongDefaultsState).summary == "90 · 3/4 · G"


def test_song_defaults_from_directives_before_the_first_chord():
    text = "{bpm: 90} {key: G}\n{time: 3/4}\nG D\n{bpm: 140} {time: 4/4}\nC"
    env = Env(text=text)
    state = env.session._song_defaults()
    assert state.tempo == SongDefault("90", True, 0)
    assert state.key == SongDefault("G", True, 10)
    assert state.time == SongDefault("3/4", True, 19)
    assert state.summary == "90 · 3/4 · G"


def test_relative_tempo_directives_apply_to_the_toolbar_tempo():
    env = Env(text="{bpm: +20}\nC")
    assert env.session._song_defaults().tempo == SongDefault("140", True, 0)


def test_write_song_defaults_inserts_the_missing_ones_as_one_undo_step():
    env = Env(text="{key: G}\nG D")
    env.session.set_bpm(90)
    env.recorder.clear()
    env.session.write_song_defaults()
    edit = env.recorder.last(TextEdited)
    assert (edit.start, edit.end, edit.replacement, edit.undo) == (
        0, 0, "{bpm: 90} {time: 4/4}\n", UndoPolicy.GROUP)
    assert env.session.text == "{bpm: 90} {time: 4/4}\n{key: G}\nG D"
    # Highlighted at once, and now all three are the song's.
    kinds = [type(i).__name__ for i in env.recorder.items]
    assert kinds.index("HighlightState") == kinds.index("TextEdited") + 1
    state = env.recorder.last(SongDefaultsState)
    assert (state.tempo.from_directive, state.time.from_directive,
            state.key.from_directive) == (True, True, True)
    assert env.status() == "Inserted: {bpm: 90} {time: 4/4}"
    env.session.write_song_defaults()
    assert env.status() == "The song already sets its tempo, time signature and key"


def test_write_song_defaults_is_refused_while_playing():
    env = Env(auto_play=False)
    env.session.play_pause()
    env.session.write_song_defaults()
    assert env.session.text == SONG


@pytest.mark.parametrize("platform", [ANDROID, DESKTOP])
def test_song_defaults_lock_while_playing_or_paused_says_why(platform):
    env = Env(platform=platform, auto_play=False)
    reason = "Stop playback to change the tempo or write into the song"
    assert defaults(env).locked_reason is None
    env.session.play_pause()
    env.rendered()
    assert defaults(env).locked_reason == reason
    env.session.play_pause()  # pause
    assert env.session._playback.status is PlaybackStatus.PAUSED
    assert defaults(env).locked_reason == reason
    # What the lock stands for: the tempo is ignored, the write refused.
    env.session.set_bpm(90)
    env.session.write_song_defaults()
    assert defaults(env).tempo.value == "120"
    assert env.session.text == SONG
    env.session.stop()
    assert defaults(env).locked_reason is None
    env.session.set_bpm(90)
    assert defaults(env).tempo.value == "90"


def test_song_defaults_unlock_when_the_song_ends():
    env = Env()
    env.session.play_pause()
    env.rendered()
    assert env.session._playback.status is PlaybackStatus.IDLE
    assert defaults(env).locked_reason is None
    locks = [s.locked_reason for s in env.everything.of_type(SongDefaultsState)]
    assert locks[-2:] == ["Stop playback to change the tempo or write into the song", None]


# -- capo in the Insert menu ------------------------------------------------------------


def test_insert_capo_directive():
    env = Env()
    env.session.request_insert_directive("capo", 0)
    request = env.session.pending_request
    assert request.kind == "capo"
    env.session.check_directive("capo", {"capo": "13"}, request.request_id)
    from session.events import DirectiveCheck
    check = env.recorder.last(DirectiveCheck)
    assert check.errors == {"capo": "The capo must be on a fret from 0 to 12 (0 means no capo)."}
    env.session.respond(request.request_id, {"capo": "3"})
    assert env.session.text.startswith("{capo: 3} C")
    env.session.request_insert_directive("capo", 0)
    env.session.respond(env.session.pending_request.request_id, {"capo": "x"})
    assert env.recorder.last(UserError).message.startswith("The capo must be on a fret")
