"""Highlight spans and chord hit-testing (session.highlighting).

``fixtures/highlight_spans.json`` holds what the Tk editor painted before the
highlighting moved out of it: each example song (and a few edge cases) was
loaded into the old ``ChordTextEditor`` in both notations and its tag ranges
were read back. ``compute_spans`` must paint exactly the same ranges.
"""

import json
from pathlib import Path

import pytest

from services.song_parser_service import SongParserService
from session.highlighting import chord_at, compute_spans, find_comments
from session.state import Span, SpanKind

FIXTURE = Path(__file__).parent / "fixtures" / "highlight_spans.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
_PARSER = SongParserService()


def _as_painted(spans):
    """Merge same-kind ranges that touch or overlap, like Tk tag ranges do."""
    by_kind = {}
    for span in spans:
        by_kind.setdefault(span.kind.value, []).append((span.start, span.end))
    painted = []
    for kind, ranges in by_kind.items():
        merged = []
        for start, end in sorted(ranges):
            if start >= end:
                continue  # an empty tag range paints nothing
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        painted.extend([kind, s, e] for s, e in merged)
    return sorted(painted, key=lambda s: (s[1], s[2], s[0]))


def _id(case):
    return f"{case['name']}-{case['notation']}"


@pytest.mark.parametrize("case", CASES, ids=_id)
def test_spans_match_what_the_old_tk_editor_painted(case):
    lines = _PARSER.detect_chords_in_text(case["text"], case["notation"])
    assert _as_painted(compute_spans(lines, case["text"])) == case["spans"]


@pytest.mark.parametrize("case", CASES, ids=_id)
def test_chord_at_matches_the_old_hit_test(case):
    text = case["text"]
    lines = _PARSER.detect_chords_in_text(text, case["notation"])
    old_chords = case["chords"]  # the old editor's detected_chords, in order
    for offset in range(len(text) + 1):
        expected = next(((s, e, v) for s, e, v in old_chords if s <= offset < e), None)
        found = chord_at(lines, offset)
        got = None if found is None else (found.start, found.end, found.is_valid)
        assert got == expected, f"offset {offset}"


def test_the_fixture_covers_every_kind():
    kinds = {span[0] for case in CASES for span in case["spans"]}
    assert kinds == {kind.value for kind in SpanKind}


def test_find_comments_runs_to_the_end_of_the_line():
    text = "C G // intro\nla // x\n// whole line"
    assert find_comments(text) == [(4, 12), (16, 20), (21, 34)]


def test_spans_come_as_comments_then_chords_then_directives():
    text = "{bpm: 90}\nC  Cmaj13#11b9  G // end\n"
    lines = _PARSER.detect_chords_in_text(text, "american")
    assert compute_spans(lines, text) == (
        Span(28, 34, SpanKind.COMMENT),
        Span(10, 11, SpanKind.CHORD),
        Span(13, 24, SpanKind.CHORD_INVALID),
        Span(26, 27, SpanKind.CHORD),
        Span(0, 9, SpanKind.DIRECTIVE),
    )


def test_offsets_are_code_points():
    text = "\U0001F3B8 x\nC G\n"  # a non-BMP character before the chords
    lines = _PARSER.detect_chords_in_text(text, "american")
    chords = [s for s in compute_spans(lines, text) if s.kind is SpanKind.CHORD]
    assert [(s.start, s.end) for s in chords] == [(4, 5), (6, 7)]
    assert text[4] == "C" and text[6] == "G"


def test_chord_at_ignores_text_lines_and_gaps():
    text = "C  G\nCome on\n"
    lines = _PARSER.detect_chords_in_text(text, "american")
    assert chord_at(lines, 0).chord == "C"
    assert chord_at(lines, 1) is None  # end is exclusive
    assert chord_at(lines, 3).chord == "G"
    assert chord_at(lines, 5) is None  # "Come" is a lyric, not a chord
    assert chord_at(lines, 100) is None
