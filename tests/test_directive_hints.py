"""Invalid directives say why, and every directive has a syntax hint.

Each invalid directive carries a short reason (``Directive.message``) that
reaches the views on its highlight span; ``directive_hint`` gives the reason
and the correct syntax for the directive at a text offset, including one
that is still being typed (``{bp``), for a tooltip while typing.
"""
import pytest

from models.directive import DIRECTIVE_SYNTAX, UNKNOWN_DIRECTIVE_SYNTAX
from services.song_parser_service import SongParserService
from session.highlighting import compute_spans, directive_hint
from session.state import SpanKind


@pytest.fixture
def parser():
    return SongParserService()


def _one(parser, text):
    [directive] = parser.parse_directives(text)
    return directive


@pytest.mark.parametrize("text, message", [
    ("{bpm: fast}", "Tempo must be a whole number from 20 to 400, a change (+10, 50%, 2x) or reset"),
    ("{bpm: 0}", "Tempo must be 20-400"),
    ("{bpm: 500}", "Tempo must be 20-400"),
    ("{bpm: 0%}", "A percentage must be above 0"),
    ("{bpm: abcx}", "A multiplier must be a number, such as 50% or 0.5x"),
    ("{bpm: +2.5}", "A tempo change must be a whole number, such as +10"),
    ("{bpm:}", "Tempo needs a value"),
    ("{bpm}", "Tempo needs a value"),
    ("{tempo: slow}", "Tempo must be a whole number from 20 to 400, a change (+10, 50%, 2x) or reset"),
    ("{time: 7}", "Time signature must be beats/unit, such as 4/4"),
    ("{time: 0/4}", "Beats must be 1-16"),
    ("{time: 4/3}", "Beat unit must be 1, 2, 4, 8 or 16"),
    ("{time}", "Time signature needs a value such as 4/4"),
    ("{key: Xyz}", "Key must be a note name such as G, Am, F#m or Sol"),
    ("{key:}", "Key needs a note name"),
    ("{capo: 30}", "Capo must be a fret from 0 to 12"),
    ("{capo: two}", "Capo must be a fret from 0 to 12"),
    ("{label}", "Label needs a name"),
    ("{loop}", "Loop needs a label to repeat"),
    ("{loop: x 0}", "Loop count must be at least 1"),
    ("{loop: nosuchlabel 2}", "No label 'nosuchlabel' in the song"),
    ("{soc}", "Unknown directive 'soc'"),
    ("{start_of_chorus: x}", "Unknown directive 'start_of_chorus'"),
])
def test_invalid_directives_say_why(parser, text, message):
    directive = _one(parser, text)
    assert not directive.is_valid
    assert directive.message == message


def test_loop_above_its_label_and_repeated_label_say_why(parser):
    text = "{label: a}\nC\n{loop: b 2}\n{label: b}\n{label: a}"
    _label_a, loop_b, _label_b, repeat = parser.parse_directives(text)
    assert loop_b.message == "Label 'b' comes after the loop; a loop repeats a section above it"
    assert repeat.message == "Label 'a' is already used on line 1"


@pytest.mark.parametrize("text, keyword", [
    ("{bpm: 120}", "bpm"), ("{TEMPO: 90}", "tempo"), ("{time: 3/4}", "time"),
    ("{key: G}", "key"), ("{capo: 2}", "capo"), ("{label: v}", "label"),
    ("{loop: @start}", "loop"), ("{bpm: fast}", "bpm"), ("{time: 7}", "time"),
])
def test_every_directive_knows_its_keyword_and_syntax(parser, text, keyword):
    directive = _one(parser, text)
    assert directive.keyword == keyword
    assert directive.syntax == DIRECTIVE_SYNTAX[keyword]


def test_valid_directives_have_no_message(parser):
    assert _one(parser, "{bpm: 120}").message is None


def test_empty_braces_are_not_a_directive(parser):
    assert parser.parse_directives("{} { }") == []


def test_unknown_directives_are_highlighted_invalid(parser):
    text = "{soc}\nC G"
    lines = parser.detect_chords_in_text(text)
    [span] = [s for s in compute_spans(lines, text) if s.start == 0]
    assert span.kind == SpanKind.DIRECTIVE_INVALID


class TestSpanMessages:
    def test_invalid_directive_spans_carry_the_reason(self, parser):
        text = "{bpm: 0}\nC G\n{key: G}"
        lines = parser.detect_chords_in_text(text)
        spans = {s.start: s for s in compute_spans(lines, text)}
        assert spans[0].message == "Tempo must be 20-400"
        assert spans[text.index("{key")].message == ""
        assert spans[text.index("C")].message == ""


class TestDirectiveHint:
    def _hint(self, text, offset):
        return directive_hint(text, offset)

    def test_inside_a_valid_directive(self):
        text = "C G\n{bpm: 120}\nAm"
        hint = self._hint(text, text.index("120"))
        assert (hint.start, hint.end) == (4, 14)
        assert (hint.keyword, hint.syntax, hint.message) == ("bpm", DIRECTIVE_SYNTAX["bpm"], "")

    def test_inside_an_invalid_directive(self):
        text = "{time: 0/4}"
        hint = self._hint(text, 3)
        assert hint.keyword == "time"
        assert hint.message == "Beats must be 1-16"
        assert hint.syntax == DIRECTIVE_SYNTAX["time"]

    def test_right_after_the_closing_brace(self):
        text = "{capo: 30}"
        assert self._hint(text, len(text)).message == "Capo must be a fret from 0 to 12"

    @pytest.mark.parametrize("typed, keyword, syntax", [
        ("{bpm: ", "bpm", DIRECTIVE_SYNTAX["bpm"]),
        ("{ti", "ti", DIRECTIVE_SYNTAX["time"]),
        ("{lo", "lo", DIRECTIVE_SYNTAX["loop"]),
        ("{l", "l", DIRECTIVE_SYNTAX["label"] + "\n" + DIRECTIVE_SYNTAX["loop"]),
        ("{", "", UNKNOWN_DIRECTIVE_SYNTAX),
        ("{xyz: 1", "xyz", UNKNOWN_DIRECTIVE_SYNTAX),
    ])
    def test_while_typing(self, typed, keyword, syntax):
        text = "C G\n" + typed
        hint = self._hint(text, len(text))
        assert (hint.start, hint.end) == (4, len(text))
        assert (hint.keyword, hint.syntax, hint.message) == (keyword, syntax, "")

    def test_nothing_outside_directives(self):
        text = "C G {bpm: 120} Am\n// {bpm"
        assert self._hint(text, 1) is None
        assert self._hint(text, len(text)) is None  # in a comment

    def test_an_unclosed_brace_on_an_earlier_line_doesnt_count(self):
        text = "{bpm\nC G"
        assert self._hint(text, len(text)) is None


def test_the_session_answers_for_the_text_as_it_is_now():
    """Even before the debounced detection has run on the new text."""
    from tests.test_session_playback import Env
    env = Env(text="C G")
    env.session.set_text("C G\n{capo: 30}", client_token=1)
    hint = env.session.directive_hint_at(len("C G\n{capo"))
    assert (hint.keyword, hint.message) == ("capo", "Capo must be a fret from 0 to 12")
    assert env.session.directive_hint_at(1).syntax == ""
