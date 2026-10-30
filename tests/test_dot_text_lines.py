"""A line whose first non-space character is ``.`` is plain text.

No chords or directives are detected on it, so it isn't highlighted, isn't
played and isn't changed by Transpose or Convert. The dot stays in the text.
It's the way out for lyric lines that look like chords ("la la la" in
European notation).
"""
import pytest

from audio.chord_picker import ChordNotePicker
from chord.detector import ChordDetector
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from services.transpose_service import transpose_text
from session.highlighting import compute_spans

EURO = "Do Fa Sol\n.la la la\nDo"


def test_european_la_la_la_is_detected_as_chords_without_the_dot():
    chords = ChordDetector(notation="european").detect_chords_in_text("la la la")
    assert len(chords) == 3


@pytest.mark.parametrize("line", [".la la la", "   .la la la", "\t. C G Am", ".{key: G}"])
def test_dot_lines_have_no_chords_or_directives(line):
    parser = SongParserService()
    [model] = parser.detect_chords_in_text(line, "european")
    assert model.items == []
    assert not model.is_chord_line()
    assert parser.parse_directives(line) == []


def test_not_highlighted_and_not_played():
    parser = SongParserService()
    lines = parser.detect_chords_in_text(EURO, "european")
    spans = compute_spans(lines, EURO)
    dot_start = EURO.index(".la")
    dot_end = dot_start + len(".la la la")
    assert not [s for s in spans if s.start < dot_end and s.end > dot_start]
    song = SongRenderer().render(lines=lines, initial_key="Do", initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    assert [rc.chord_info.chord for rc in song.chords] == ["Do", "Fa", "Sol", "Do"]


def test_transpose_and_convert_leave_dot_lines_alone():
    parser = SongParserService()
    # The words stay; like any lyric line under a chord line, its spacing may
    # be adjusted to keep it aligned with the transposed chords.
    assert transpose_text(EURO, 2, "european").splitlines()[1].split() == [".la", "la", "la"]
    assert transpose_text(".la la la\nDo", 2, "european") == ".la la la\nRe"
    assert parser.convert_to_american(EURO).splitlines()[1] == ".la la la"
    assert transpose_text(". C G\nC G", 2, "american") == ". C G\nD A"

