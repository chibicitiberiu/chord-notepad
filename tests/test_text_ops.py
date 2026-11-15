"""The editor's text operations (core/chordnotepad/session/text_ops.py)."""

import random
import re

import pytest

from chordnotepad.session import text_ops as ops
from chordnotepad.session.text_ops import TextOp


def applied(text, op):
    """The new text and its selection, as ``"text with [selection|"`` marks:
    ``[`` the anchor, ``|`` the caret (one ``|`` when they are the same)."""
    assert op is not None
    return marked(op.apply(text), op.anchor, op.cursor)


def marked(text, anchor, cursor):
    if anchor == cursor:
        return text[:cursor] + "|" + text[cursor:]
    marks = sorted([(anchor, "["), (cursor, "|")])
    out, at = [], 0
    for pos, mark in marks:
        out.append(text[at:pos])
        out.append(mark)
        at = pos
    out.append(text[at:])
    return "".join(out)


def unmark(s):
    """``"ab[cd|ef"`` -> (text, anchor, cursor)."""
    anchor = s.find("[")
    if anchor < 0:
        cursor = s.index("|")
        return s.replace("|", ""), cursor, cursor
    plain = s.replace("[", "").replace("|", "")
    cursor = s.index("|")
    if anchor < cursor:
        return plain, anchor, cursor - 1
    return plain, anchor - 1, cursor


def run(fn, s, *args, **kwargs):
    text, anchor, cursor = unmark(s)
    return fn(text, anchor, cursor, *args, **kwargs), text


# -- find ---------------------------------------------------------------------------------


def test_find_ignores_case_unless_asked():
    text = "Am C am AM"
    assert ops.find_all(text, "am") == [(0, 2), (5, 7), (8, 10)]
    assert ops.find_all(text, "am", match_case=True) == [(5, 7)]


def test_find_whole_word_isnt_inside_a_longer_word():
    text = "Am Am7 Am, xAm"
    assert ops.find_all(text, "Am", whole_word=True) == [(0, 2), (7, 9)]
    # Punctuation at the query's edges works too.
    assert ops.find_all("{bpm: 90} ({bpm: 90}) x{bpm", "{bpm", whole_word=True) == [(0, 4), (11, 15)]
    assert ops.find_all("F# F#m F#", "F#", whole_word=True, match_case=True) == [(0, 2), (7, 9)]


def test_find_takes_the_query_literally_and_doesnt_overlap():
    assert ops.find_all("a.b axb", "a.b") == [(0, 3)]
    assert ops.find_all("aaaa", "aa") == [(0, 2), (2, 4)]
    assert ops.find_all("abc", "") == []
    assert ops.find_all("", "a") == []


def reference_find(text, query, match_case, whole_word):
    """A plain scan, as a second opinion on find_all."""
    hay, needle = (text, query) if match_case else (text.lower(), query.lower())
    found, i, n = [], 0, len(needle)
    while n and i + n <= len(hay):
        ok = hay[i:i + n] == needle
        if ok and whole_word:
            ok = not (i > 0 and re.match(r"\w", text[i - 1])) \
                and not (i + n < len(text) and re.match(r"\w", text[i + n]))
        if ok:
            found.append((i, i + n))
            i += n
        else:
            i += 1
    return found


def test_find_agrees_with_a_plain_scan_on_random_texts():
    rng = random.Random(7)
    for _ in range(500):
        text = "".join(rng.choice("aAb \n#{") for _ in range(rng.randint(0, 30)))
        query = "".join(rng.choice("aAb#{") for _ in range(rng.randint(1, 3)))
        for case in (False, True):
            for word in (False, True):
                assert ops.find_all(text, query, case, word) == reference_find(text, query, case, word), \
                    (text, query, case, word)


def test_find_is_unicode_safe():
    text = "Ünd ünd 😀 ünd"
    assert ops.find_all(text, "ÜND") == [(0, 3), (4, 7), (10, 13)]


def test_next_match_from_a_position_and_wrapping():
    matches = [(2, 4), (8, 10), (15, 17)]
    assert ops.next_match(matches, 0) == (0, False)
    assert ops.next_match(matches, 2) == (0, False)
    assert ops.next_match(matches, 3) == (1, False)
    assert ops.next_match(matches, 16) == (0, True)
    assert ops.next_match(matches, 10, backward=True) == (1, False)
    assert ops.next_match(matches, 9, backward=True) == (0, False)
    assert ops.next_match(matches, 3, backward=True) == (2, True)
    assert ops.next_match([], 3) is None


def test_replace_match_only_replaces_a_real_match():
    op = ops.replace_match("Am C Am", (5, 7), "am", "Em")
    assert applied("Am C Am", op) == "Am C Em|"
    assert ops.replace_match("Am C Am", (4, 6), "am", "Em") is None
    assert ops.replace_match("Am7", (0, 2), "Am", "Em", whole_word=True) is None


def test_replace_all_is_one_edit_with_the_caret_kept():
    text = "Am C Am G Am"
    op, count = ops.replace_all(text, "Am", "Dm7", match_case=True, cursor=8)
    assert count == 3
    assert (op.start, op.end) == (0, 12)
    assert applied(text, op) == "Dm7 C Dm7 |G Dm7"
    # Before the first match, inside one, at the end.
    assert applied(text, ops.replace_all(text, "C", "Cmaj7", cursor=1)[0]) == "A|m Cmaj7 Am G Am"
    assert applied(text, ops.replace_all(text, "Am", "E", cursor=6)[0]) == "E C E| G E"
    assert applied(text, ops.replace_all(text, "Am", "E", cursor=12)[0]) == "E C E G E|"
    assert ops.replace_all(text, "x", "y") == (None, 0)


def test_replace_all_with_an_empty_replacement_deletes():
    op, count = ops.replace_all("a, b, c", ", ", "", cursor=7)
    assert count == 2 and applied("a, b, c", op) == "abc|"


def test_a_selected_words_occurrences():
    text = "Am C Am7 Am\nam"
    assert ops.occurrences(text, (0, 2)) == [(0, 2), (9, 11)]
    assert ops.occurrences(text, (2, 0)) == [(0, 2), (9, 11)]
    assert ops.occurrences(text, (5, 7)) == []           # the Am of Am7 isn't a word
    assert ops.occurrences(text, (0, 4)) == []           # spaces
    assert ops.occurrences(text, (1, 1)) == []
    assert ops.occurrences("F# x F#", (0, 2)) == [(0, 2), (5, 7)]


# -- lines --------------------------------------------------------------------------------


def test_line_numbers_and_offsets():
    text = "a\nbc\n\nd"
    assert ops.line_count(text) == 4 and ops.line_count("") == 1 and ops.line_count("x\n") == 2
    assert [ops.line_offset(text, n) for n in (1, 2, 3, 4)] == [0, 2, 5, 6]
    assert ops.line_offset(text, 0) == 0 and ops.line_offset(text, -3) == 0
    assert ops.line_offset(text, 99) == 6


def test_the_lines_a_selection_touches():
    text = "one\ntwo\nthree\n"
    assert ops.touched_lines(text, 5, 5) == (4, 7)
    assert ops.touched_lines(text, 1, 6) == (0, 7)
    assert ops.touched_lines(text, 6, 1) == (0, 7)
    # Ending at a line's start leaves that line out.
    assert ops.touched_lines(text, 0, 8) == (0, 7)
    assert ops.touched_lines(text, 14, 14) == (14, 14)


@pytest.mark.parametrize("before, after", [
    ("one\nt|wo\nthree", "one\n[two\n|three"),
    ("[one\ntwo\n|three", "[one\ntwo\nthree|"),
    ("one\ntw[o\nth|ree", "one\n[two\nthree|"),
    ("one\ntw|o", "one\n[two|"),
    ("o|ne\n", "[one\n|"),
    ("|", "|"),
])
def test_select_lines(before, after):
    text, anchor, cursor = unmark(before)
    a, c = ops.select_lines(text, anchor, cursor)
    assert marked(text, a, c) == after


@pytest.mark.parametrize("before, after", [
    ("one\nt|wo\nthree", "one\ntwo\nt|wo\nthree"),
    ("one\ntwo|", "one\ntwo\ntwo|"),
    ("|", "\n|"),
    ("o[ne t|wo", "one t[ne t|wo"),
    ("o|ne t[wo", "one t|ne t[wo"),
    ("[one\n|two", "one\n[one\n|two"),
])
def test_duplicate(before, after):
    op, text = run(ops.duplicate, before)
    assert applied(text, op) == after


@pytest.mark.parametrize("before, offset, after", [
    ("one\nt|wo\nthree", -1, "t|wo\none\nthree"),
    ("one\nt|wo\nthree", 1, "one\nthree\nt|wo"),
    ("one\nt[wo\nthr|ee\nfour", -1, "t[wo\nthr|ee\none\nfour"),
    ("one\nt[wo\nthr|ee\nfour", 1, "one\nfour\nt[wo\nthr|ee"),
    ("[one\ntwo\n|three", 1, "three\n[one\ntwo|"),
    ("one\nt|wo\n", -1, "t|wo\none\n"),
])
def test_move_lines(before, offset, after):
    op, text = run(ops.move_lines, before, offset)
    assert applied(text, op) == after


@pytest.mark.parametrize("before, offset", [
    ("o|ne\ntwo", -1), ("one\nt|wo", 1), ("one\nt|wo\n", 1), ("one\n|", -1), ("one\n|", 1),
])
def test_move_lines_stops_at_the_edges(before, offset):
    op, _ = run(ops.move_lines, before, offset)
    assert op is None


def test_move_lines_up_then_down_gives_the_text_back():
    rng = random.Random(3)
    for _ in range(200):
        lines = ["".join(rng.choice("ab ") for _ in range(rng.randint(0, 4)))
                 for _ in range(rng.randint(2, 6))]
        # Not ending in an empty line: nothing moves below the final newline.
        text = "\n".join(lines) + "z"
        a, c = rng.randint(0, len(text)), rng.randint(0, len(text))
        up = ops.move_lines(text, a, c, -1)
        if up is None:
            continue
        moved = up.apply(text)
        if moved.endswith("\n"):
            continue        # an empty line moved to the end: nothing goes below it
        down = ops.move_lines(moved, up.anchor, up.cursor, 1)
        assert down is not None and down.apply(moved) == text
        assert (down.anchor, down.cursor) == (a, c)


@pytest.mark.parametrize("before, after", [
    ("one\ntw|o\nthree", "one\nth|ree"),
    ("one\ntwo\nthr|ee", "one\ntwo|"),
    ("o[ne\ntw|o\nthree", "th|ree"),
    ("o|ne", "|"),
    ("one\nlonger tex|t\nab", "one\nab|"),
    ("[one\n|two", "|two"),
])
def test_delete_lines(before, after):
    op, text = run(ops.delete_lines, before)
    assert applied(text, op) == after


# -- comments and indentation ------------------------------------------------------------


@pytest.mark.parametrize("before, after", [
    ("C   G|", "// C   G|"),
    ("|", "// |"),
    ("  C   G\n  la| la", "  C   G\n  // la| la"),
    ("[  C   G\nla la\n|", "[//   C   G\n// la la\n|"),
    ("  [C   G\n    la la|", "  [// C   G\n  //   la la|"),
    ("a\n\nb|", "a\n\nb|"),
])
def test_comment_lines(before, after):
    if before == "a\n\nb|":
        op, text = run(ops.toggle_comment, "[a\n\nb|")
        assert applied(text, op) == "[// a\n\n// b|"
        return
    op, text = run(ops.toggle_comment, before)
    assert applied(text, op) == after


@pytest.mark.parametrize("before, after", [
    ("// C   G|", "C   G|"),
    ("//C|", "C|"),
    ("  // la| la", "  la| la"),
    ("[// C   G\n\n//   la la|", "[C   G\n\n  la la|"),
    ("// a|", "a|"),
])
def test_uncomment_lines(before, after):
    op, text = run(ops.toggle_comment, before)
    assert applied(text, op) == after


def test_a_mix_of_comments_and_lines_gets_commented():
    op, text = run(ops.toggle_comment, "[// one\ntwo|")
    assert applied(text, op) == "[// // one\n// two|"


def test_comment_toggle_twice_gives_the_text_back():
    rng = random.Random(11)
    for _ in range(300):
        lines = [rng.choice(["", "  ", "C G", "  la", "\tx", "// c", "  //d"]) for _ in range(rng.randint(1, 5))]
        text = "\n".join(lines)
        a, c = rng.randint(0, len(text)), rng.randint(0, len(text))
        once = ops.toggle_comment(text, a, c)
        if once is None:
            continue
        mid = once.apply(text)
        twice = ops.toggle_comment(mid, once.anchor, once.cursor)
        filled = [line for line in text[slice(*ops.touched_lines(text, a, c))].split("\n") if line.strip()]
        commented = filled and all(line.lstrip().startswith("//") for line in filled)
        if not commented and all(not line.lstrip().startswith("//") for line in filled):
            assert twice is not None and twice.apply(mid) == text, (text, a, c)


@pytest.mark.parametrize("before, after", [
    ("[one\n\ntwo|", "[\tone\n\n\ttwo|"),
    ("o[ne\nt|wo", "\to[ne\n\tt|wo"),
    ("[    G\n  la|", "[\t    G\n\t  la|"),
])
def test_indent(before, after):
    op, text = run(ops.indent_lines, before)
    assert applied(text, op) == after


@pytest.mark.parametrize("before, after", [
    ("[\tone\n\ttwo|", "[one\ntwo|"),
    # The same number of spaces off each line, so they stay aligned.
    ("[      G\n  la|", "[    G\nla|"),
    ("[        G\n      la|", "[    G\n  la|"),
    ("[\tG\n   la|", "[G\nla|"),
    ("   a|", "a|"),
])
def test_unindent(before, after):
    op, text = run(ops.indent_lines, before, outdent=True)
    assert applied(text, op) == after


def test_unindent_with_nothing_to_take_off_is_nothing():
    op, _ = run(ops.indent_lines, "[one\ntwo|", outdent=True)
    assert op is None


def test_spans_lines():
    assert ops.spans_lines("a\nb", 0, 3) and ops.spans_lines("a\nb", 3, 0)
    assert not ops.spans_lines("a\nb", 0, 1)


def test_text_op_apply():
    assert TextOp(1, 2, "XY", 0, 0).apply("abc") == "aXYc"
