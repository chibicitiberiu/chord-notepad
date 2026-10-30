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


class TestLoopsThatWouldNeverEnd:
    MUTUAL = "{label: a}\nC\n{loop: b 2}\n{label: b}\nG\n{loop: a 2}"

    def test_mutually_referencing_loops_finish(self):
        # {loop: b} sits above its label, so it's invalid and ignored; the
        # remaining {loop: a 2} plays the whole song twice.
        assert _played(self.MUTUAL) == ["C", "G", "C", "G"]

    def test_a_loop_above_its_label_is_invalid(self, parser):
        loop_b, loop_a = _loops(parser, self.MUTUAL)
        assert (loop_b.label, loop_b.is_valid) == ("b", False)
        assert (loop_a.label, loop_a.is_valid) == ("a", True)

    def test_a_loop_to_a_missing_label_is_invalid(self, parser):
        [loop] = _loops(parser, "C\n{loop: nosuchlabel 2}")
        assert not loop.is_valid

    def test_at_start_is_always_a_valid_target(self, parser):
        [loop] = _loops(parser, "C\n{loop: @start 2}")
        assert loop.is_valid

    def test_a_repeated_label_is_invalid_and_loops_use_the_first(self, parser):
        text = "{label: a}\nC\n{loop: a 2}\n{label: a}\nG"
        labels = [d for d in parser.parse_directives(text) if d.type == DirectiveType.LABEL]
        assert [d.is_valid for d in labels] == [True, False]
        assert _loops(parser, text)[0].is_valid
        assert _played(text) == ["C", "C", "G"]

    def test_loops_in_a_label_in_comment_are_not_targets(self, parser):
        [loop] = _loops(parser, "// {label: a}\nC\n{loop: a 2}")
        assert not loop.is_valid

    def test_nested_and_overlapping_loops_still_play(self):
        text = "{label: v}\nC\n{label: c}\nG\n{loop: c 2}\n{loop: v 2}"
        assert _played(text) == ["C", "G", "G", "C", "G"]

    def test_runaway_loop_counts_are_capped(self):
        from services.song_renderer import MAX_RENDERED_CHORDS
        chords = _played("{label: a}\nC*0.25\n{loop: a 100000000}", timeout=60.0)
        assert len(chords) == MAX_RENDERED_CHORDS


class TestRendererRecursionGuard:
    """The renderer itself refuses to re-enter a loop it is expanding, even
    for lines that didn't come through the parser's checks."""

    def test_hand_built_mutual_loops_finish(self):
        from models.directive import Directive
        from models.chord import ChordInfo
        from models.line import Line

        def chord(name, pos):
            return ChordInfo(chord=name, start=pos, end=pos + 1, is_valid=True)

        def directive(kind, pos, label, count=2):
            return Directive(type=kind, start=pos, end=pos + 1, label=label, loop_count=count)

        items = [directive(DirectiveType.LABEL, 0, "a"), chord("C", 1),
                 directive(DirectiveType.LOOP, 2, "b"),
                 directive(DirectiveType.LABEL, 3, "b"), chord("G", 4),
                 directive(DirectiveType.LOOP, 5, "a")]
        line = Line(content="x", line_number=1)
        line.set_as_chord_line([i for i in items if isinstance(i, ChordInfo)])
        line.items = items  # directives stay in the walk
        result = {}

        def work():
            result['song'] = SongRenderer().render(
                lines=[line], initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
                note_picker=ChordNotePicker())

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(10.0)
        assert not worker.is_alive()
        assert len(result['song'].chords) < 20
