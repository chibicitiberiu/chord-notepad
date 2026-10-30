"""A relative tempo change that would leave 20-400 is clamped (it stays a
valid directive) and the status says so while the clamped tempo plays.

Each rendered chord carries ``tempo_clamp``: ``(bpm, line)`` of the clamped
directive whose tempo it plays at, or None."""
import pytest

from audio.chord_picker import ChordNotePicker
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from session import formatting
from session.platform import ANDROID, DESKTOP
from session.state import StatusState


def _render(text, bpm=120, start_line_index=0):
    lines = SongParserService().detect_chords_in_text(text)
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=bpm,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker(),
                                 start_line_index=start_line_index)
    return [(rc.chord_info.chord, rc.bpm, rc.tempo_clamp) for rc in song.chords]


def test_the_warning_text():
    assert formatting.tempo_clamped_warning(400, 3) == "Tempo clamped to 400 BPM at line 3"


def test_relative_change_is_valid_and_clamped():
    [directive] = SongParserService().parse_directives("{bpm: +500}")
    assert directive.is_valid


def test_clamped_chords_carry_the_warning_until_the_tempo_changes():
    text = "{bpm: 380}\nC\n{bpm: +50}\nG Am\n{bpm: 100}\nF"
    warn = (400, 3)
    assert _render(text) == [("C", 380, None), ("G", 400, warn), ("Am", 400, warn),
                             ("F", 100, None)]


def test_clamp_down_to_the_minimum():
    text = "C\n{bpm: 10%}\nG"
    assert _render(text, bpm=100) == [
        ("C", 100, None), ("G", 20, (20, 2))]


def test_a_clamp_inside_a_loop_warns_on_every_pass():
    # Each pass restores the label's tempo (300), then +150 clamps to 400.
    text = "{bpm: 300}\n{label: a}\nC\n{bpm: +150}\nG\n{loop: a 2}\nAm"
    warn = (400, 4)
    assert _render(text) == [("C", 300, None), ("G", 400, warn),
                             ("C", 300, None), ("G", 400, warn), ("Am", 400, warn)]


def test_a_clamp_inside_a_nested_loop():
    # A loop restores its label's tempo on each pass, so every pass of a
    # section starts from the same tempo and clamps the same way; here the
    # outer section's {bpm: +150} sets the inner label's tempo.
    text = ("{bpm: 200}\n{label: outer}\nC\n{loop: outer 2}\n"
            "{bpm: +150}\n{label: inner}\nG\n{bpm: +100}\nAm\n{loop: inner 2}")
    warn = (400, 8)
    assert _render(text) == [("C", 200, None), ("C", 200, None), ("G", 350, None),
                             ("Am", 400, warn), ("G", 350, None), ("Am", 400, warn)]


@pytest.mark.parametrize("platform, expected", [
    (DESKTOP, "Bar 2/2 | 400 BPM | 4/4 | Playing: G | Tempo clamped to 400 BPM at line 3"),
    (ANDROID, "Bar 2/2 · Playing G · Tempo clamped to 400 BPM at line 3"),
])
def test_the_status_shows_the_warning(platform, expected):
    from tests.test_session_playback import Env
    env = Env(text="{bpm: 380}\nC\n{bpm: +50}\nG")
    if platform == ANDROID:
        env.session._android = True
    env.session.play_pause()
    env.rendered()
    texts = [s.text for s in env.recorder.of_type(StatusState)]
    assert expected in texts
    assert not any("clamped" in t for t in texts if "Playing: C" in t or "Playing C" in t)
