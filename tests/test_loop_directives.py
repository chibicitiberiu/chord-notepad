"""Loop directives: label names with spaces, counts, and loops that would
never finish (a loop must come after its label, so loops can't send each
other back and forth)."""
import threading

import pytest

from audio.chord_picker import ChordNotePicker
from models.directive import DirectiveType
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


@pytest.fixture
def parser():
    return SongParserService()


def _loops(parser, text):
    return [d for d in parser.parse_directives(text) if d.type == DirectiveType.LOOP]


def _played(text, timeout=10.0):
    """The chords a render of ``text`` plays; fails instead of hanging."""
    lines = SongParserService().detect_chords_in_text(text)
    result = {}

    def work():
        try:
            result['song'] = SongRenderer().render(
                lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
                note_picker=ChordNotePicker())
        except BaseException as exc:
            result['error'] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    assert not worker.is_alive(), f"rendering {text!r} did not finish"
    if 'error' in result:
        raise result['error']
    return [rc.chord_info.chord for rc in result['song'].chords]


class TestLoopLabelsWithSpaces:
    def test_count_is_the_last_token(self, parser):
        [loop] = _loops(parser, "{label: my verse}\nC\n{loop: my verse 3}")
        assert (loop.label, loop.loop_count, loop.is_valid) == ("my verse", 3, True)

    def test_label_with_spaces_without_count(self, parser):
        [loop] = _loops(parser, "{label: my verse}\nC\n{loop: my verse}")
        assert (loop.label, loop.loop_count) == ("my verse", 2)

    def test_single_word_label(self, parser):
        [loop] = _loops(parser, "{label: chorus}\nC\n{loop: chorus}")
        assert (loop.label, loop.loop_count) == ("chorus", 2)

    def test_a_label_ending_in_a_number_needs_an_explicit_count(self, parser):
        [loop] = _loops(parser, "{label: part 2}\nC\n{loop: part 2 3}")
        assert (loop.label, loop.loop_count) == ("part 2", 3)

    @pytest.mark.parametrize("value", ["x 0", "x -1"])
    def test_a_count_below_one_is_invalid(self, parser, value):
        [directive] = parser.parse_directives(f"{{loop: {value}}}")
        assert not directive.is_valid

    def test_a_label_with_spaces_can_be_looped(self):
        assert _played("{label: my verse}\nC G\n{loop: my verse 2}") == ["C", "G", "C", "G"]
