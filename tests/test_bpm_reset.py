"""``{bpm: reset}`` goes back to the song's starting tempo.

The starting tempo is the one the song's first chord plays at: set by the
``{bpm}`` directives before it, else the toolbar tempo. It must not depend on
whether the toolbar happened to be set from the file (opening a song copies
its first ``{bpm}`` into the toolbar; typing it in doesn't).
"""
import pytest

from audio.chord_picker import ChordNotePicker
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer

SONG = "{bpm: 100}\nC\n{bpm: 160}\nG\n{bpm: reset}\nAm"


def _bpms(text, toolbar_bpm):
    lines = SongParserService().detect_chords_in_text(text)
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=toolbar_bpm,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    return [rc.bpm for rc in song.chords]


@pytest.mark.parametrize("toolbar_bpm", [100, 120, 60])
def test_reset_returns_to_the_first_chords_tempo(toolbar_bpm):
    assert _bpms(SONG, toolbar_bpm) == [100, 160, 100]


def test_relative_start_counts_from_the_toolbar():
    assert _bpms("{bpm: +10}\nC\n{bpm: 200}\nG\n{bpm: reset}\nAm", 120) == [130, 200, 130]


def test_without_a_starting_bpm_reset_goes_to_the_toolbar_tempo():
    assert _bpms("C\n{bpm: 160}\nG\n{bpm: reset}\nAm", 90) == [90, 160, 90]


def test_reset_before_the_first_chord_uses_the_toolbar_tempo():
    assert _bpms("{bpm: 100}\n{bpm: reset}\nC\n{bpm: 150}\nG\n{bpm: reset}\nAm", 120) == [
        120, 150, 120]


def test_play_from_cursor_resets_to_the_same_tempo():
    lines = SongParserService().detect_chords_in_text(SONG)
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker(),
                                 start_line_index=3)
    assert [rc.bpm for rc in song.chords if not rc.skipped] == [160, 100]
