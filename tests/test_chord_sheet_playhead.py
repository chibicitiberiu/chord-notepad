"""The chord sheet's playhead while a song plays from anywhere in it.

The strip renders the whole song itself; playback renders from the start
point and tags each chord ping with the chord's index in its own song.
These tests run both for real (the session, the real ChordSheetViewModel and
PlaybackService over a FakePlayer on a ManualHost) and check that the strip
always lights the chord that is sounding: from the top, from the middle,
inside a looped section, past tempo and key changes, and when the strip's
render lands after playback started.
"""

import pytest

from audio.chord_picker import ChordNotePicker
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from session.host import HostDispatch
from session.platform import ANDROID, DESKTOP
from session.session import AppSession
from session.state import ChordSheetState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
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
    """A started session with the real strip, playing through a FakePlayer."""

    def __init__(self, platform, text=None, **config):
        self.platform = platform
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.player = FakePlayer(auto_play=False)
        self.config = FakeConfig(chord_sheet_visible=True, **config)
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        parser = SongParserService()
        self.main = MainWindowViewModel(
            self.config, self.audio, InMemoryDocumentStore(), parser, dispatch)
        self.sheet = ChordSheetViewModel(self.config, self.audio, host=self.host,
                                         executor=lambda fn: fn(), platform=platform)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(parser),
            chord_sheet_viewmodel=self.sheet, platform=platform)
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        if text is not None:
            self.load(text)

    def load(self, text):
        """Set the text and let detection and the strip's render finish."""
        self.session.set_text(text)
        self.host.advance(2.0)
        assert self.sheet.rendered_song is not None

    def play_from(self, offset):
        """Start playing at the chord starting at ``offset`` (0: the top)."""
        if self.platform == ANDROID:
            self.session.set_playhead(offset)
            self.session.play_pause()
        else:
            # The desktop's Shift+click / play-from-cursor.
            self.session.play_pause(offset if offset else None)
        thread = self.audio._render_thread
        thread.join(timeout=10)
        assert not thread.is_alive()
        self.host.run_pending()

    def step(self):
        """Sound the next chord; return (playing chord's start, strip chord's start)."""
        assert self.player.play(1) == 1
        self.host.run_pending()
        span = self.session._playback.playing_span
        return span.start, self.strip_start(self.sheet.current_index)

    def strip_start(self, index):
        if index is None:
            return None
        return self.sheet.rendered_song.chords[index].chord_info.start

    def published_index(self):
        return self.recorder.last(ChordSheetState).current_index


def _starts(text, *names):
    """Offsets of the chords named, each the first match after the previous one."""
    out, at = [], 0
    for name in names:
        at = text.index(name, at)
        out.append(at)
        at += len(name)
    return out


PLATFORMS = pytest.mark.parametrize("platform", [ANDROID, DESKTOP])

SONG = "C G Am F\nEm D C G\nAm F G C\n"


@PLATFORMS
def test_from_the_top_the_strip_follows_every_chord(platform):
    env = Env(platform, SONG)
    env.play_from(0)
    for expected in range(12):
        playing, strip = env.step()
        assert strip == playing
        assert env.sheet.current_index == expected
        assert env.published_index() == expected


@PLATFORMS
def test_from_a_chord_in_the_middle(platform):
    env = Env(platform, SONG)
    em = SONG.index("Em")
    env.play_from(em)
    playing, strip = env.step()
    assert playing == em
    assert strip == em
    assert env.sheet.current_index == 4
    for expected in range(5, 12):
        playing, strip = env.step()
        assert strip == playing
        assert env.sheet.current_index == expected


LOOPED = "{label: verse}\nC G\nAm F\n{loop: verse 2}\nEm D\n"


@PLATFORMS
def test_from_a_chord_inside_a_looped_section(platform):
    env = Env(platform, LOOPED)
    am = LOOPED.index("Am")
    env.play_from(am)
    # The strip's song: C G Am F (pass 1), C G Am F (pass 2), Em D.
    seen = []
    for _ in range(8):
        playing, strip = env.step()
        assert strip == playing
        seen.append(env.sheet.current_index)
    # Am and F of the first pass, all of the second pass, then the ending.
    assert seen == [2, 3, 4, 5, 6, 7, 8, 9]


def test_a_later_pass_lights_its_own_chord_and_the_resting_playhead_the_first_pass():
    env = Env(ANDROID, LOOPED)
    env.play_from(LOOPED.index("Am"))
    for _ in range(5):  # Am F | C G Am
        env.step()
    assert env.sheet.current_index == 6  # Am of the second pass
    env.session.stop()
    env.host.run_pending()
    state = env.recorder.last(ChordSheetState)
    assert state.current_index is None
    assert state.cursor_index == 2  # where the playhead rests: Am's first pass


@PLATFORMS
def test_from_a_chord_after_tempo_and_key_changes(platform):
    text = "{bpm: 90} {key: G}\nC G\n{bpm: 140}\n{key: D}\nAm Em*2\n{time: 3/4}\nF C\n"
    env = Env(platform, text)
    em = text.index("Em")
    env.play_from(em)
    for expected in (3, 4, 5):
        playing, strip = env.step()
        assert strip == playing
        assert env.sheet.current_index == expected


@PLATFORMS
def test_a_strip_render_landing_after_playback_started_lights_the_playing_chord(platform):
    env = Env(platform, SONG)
    em = SONG.index("Em")
    env.play_from(em)
    # The strip renders again (re-fed) while Em sounds; the render lands later.
    env.sheet.set_song(env.session._detector.detected_lines, env.main.key)
    assert env.step() == (em, em)
    env.host.advance(2.0)
    assert env.sheet.current_index == 4
    assert env.published_index() == 4


def test_a_strip_rendered_for_the_first_time_while_playing_lights_the_playing_chord():
    env = Env(ANDROID)
    env.session.set_text(SONG)
    env.host.advance(0.6)  # detected; the strip's debounced render still pending
    env.sheet._scheduler.cancel(env.sheet._render_handle)  # hold it back
    em = SONG.index("Em")
    env.play_from(em)
    playing, strip = env.step()
    assert playing == em and env.sheet.rendered_song is None
    env.sheet._dispatch()  # the render lands now
    env.host.run_pending()
    assert env.strip_start(env.sheet.current_index) == em


def test_a_strip_rendered_after_playback_stopped_has_no_playing_chord():
    env = Env(ANDROID, SONG)
    env.play_from(0)
    env.step()
    env.sheet.set_song(env.session._detector.detected_lines, env.main.key)
    env.step()  # the strip is rendering: no chord lit
    env.session.stop()
    env.host.advance(2.0)
    assert env.sheet.rendered_song is not None
    assert env.sheet.current_index is None


ROMAN = "I IV\nC G Am F Em D\n"


@PLATFORMS
def test_unresolvable_chords_before_the_start_point(platform):
    # Without a key the roman numerals can't sound: both renders leave them out.
    env = Env(platform, ROMAN)
    am = ROMAN.index("Am")
    env.play_from(am)
    playing, strip = env.step()
    assert playing == am and strip == am
    playing, strip = env.step()
    assert strip == playing


def test_render_from_the_cursor_keeps_the_chord_indices_of_a_render_from_the_top():
    lines = SongParserService().detect_chords_in_text(ROMAN, "american")

    def render(line, item):
        return SongRenderer().render(
            lines=lines, initial_key=None, initial_bpm=120, initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(), start_line_index=line, start_item_index=item)

    top = [c.chord_info.start for c in render(0, 0).chords]
    assert top == _starts(ROMAN, "C", "G", "Am", "F", "Em", "D")
    assert [c.chord_info.start for c in render(1, 2).chords] == top
