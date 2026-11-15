"""The editor's text operations as session commands (find bar and Edit menu).

Each edit is one GROUP TextEdited with the selection text_ops works out,
refused while a song plays or is paused; text_ops itself is tested in
tests/test_text_ops.py.
"""

import json

import pytest

from chordnotepad.session import bridge
from chordnotepad.session.events import EditRefused, TextEdited, UndoPolicy
from chordnotepad.session.platform import DESKTOP_QT
from chordnotepad.session.state import PlaybackStatus
from tests.test_session_player import Env


def env(text, **kw):
    return Env(platform=DESKTOP_QT, text=text, **kw)


def edit(e):
    (edited,) = e.recorder.of_type(TextEdited)
    return edited


def selection(e):
    edited = edit(e)
    anchor = edited.cursor if edited.anchor is None else edited.anchor
    return anchor, edited.cursor


def test_replace_match_replaces_one_match_and_puts_the_caret_after_it():
    e = env("Am C Am\n")
    e.session.replace_match((5, 7), "am", "Em7")
    edited = edit(e)
    assert e.session.text == "Am C Em7\n"
    assert (edited.start, edited.end, edited.replacement) == (5, 7, "Em7")
    assert edited.undo is UndoPolicy.GROUP and edited.cursor == 8 and edited.anchor is None


def test_replace_match_does_nothing_when_the_span_is_no_longer_a_match():
    e = env("Am C Am\n")
    e.session.replace_match((4, 6), "am", "Em")
    e.session.replace_match((0, 2), "am", "Em", match_case=True)
    e.session.replace_match((0, 2), "a", "E", whole_word=True)
    assert e.session.text == "Am C Am\n" and not e.recorder.of_type(TextEdited)


def test_replace_all_is_one_step_and_says_how_many():
    e = env("Am C Am G am\n")
    e.session.replace_all("Am", "Dm", match_case=True, cursor=8)
    edited = edit(e)
    assert e.session.text == "Dm C Dm G am\n"
    assert edited.undo is UndoPolicy.GROUP and edited.cursor == 8
    assert e.status() == "Replaced 2 matches"
    e.recorder.clear()
    e.session.replace_all("G", "D")
    assert e.status() == "Replaced 1 match"


def test_replace_all_without_matches_changes_nothing_and_says_so():
    e = env("Am C\n")
    e.session.replace_all("F#", "Gb")
    assert e.session.text == "Am C\n" and not e.recorder.of_type(TextEdited)
    assert e.status() == "No matches for “F#”"


def test_duplicate_a_line_and_a_selection():
    e = env("C G\nla la\n")
    e.session.duplicate_lines(6, 6)
    assert e.session.text == "C G\nla la\nla la\n" and selection(e) == (12, 12)
    e.recorder.clear()
    e.session.duplicate_lines(0, 3)
    assert e.session.text == "C GC G\nla la\nla la\n" and selection(e) == (3, 6)
    assert edit(e).undo is UndoPolicy.GROUP


def test_move_lines_keeps_the_selection_on_the_moved_text():
    e = env("one\ntwo\nthree\n")
    e.session.move_lines(9, 5, -1)
    assert e.session.text == "two\nthree\none\n" and selection(e) == (5, 1)
    e.recorder.clear()
    e.session.move_lines(0, 0, -1)                   # the first line can't go up
    assert not e.recorder.of_type(TextEdited)
    with pytest.raises(ValueError):
        e.session.move_lines(0, 0, 2)


def test_delete_lines():
    e = env("one\ntwo\nthree")
    e.session.delete_lines(5, 5)
    assert e.session.text == "one\nthree" and selection(e) == (5, 5)


def test_toggle_comment_both_ways():
    e = env("C   G\nla la\n")
    e.session.toggle_comment(0, 8)
    assert e.session.text == "// C   G\n// la la\n" and selection(e) == (0, 14)
    e.recorder.clear()
    e.session.toggle_comment(0, 14)
    assert e.session.text == "C   G\nla la\n" and selection(e) == (0, 8)


def test_indent_and_unindent():
    e = env("C   G\nla la\n")
    e.session.indent_lines(0, 8)
    assert e.session.text == "\tC   G\n\tla la\n" and selection(e) == (0, 10)
    e.recorder.clear()
    e.session.indent_lines(0, 10, outdent=True)
    assert e.session.text == "C   G\nla la\n"


@pytest.mark.parametrize("command, args", [
    ("replace_match", ((0, 2), "Am", "Em")), ("replace_all", ("Am", "Em")),
    ("duplicate_lines", (0, 0)), ("move_lines", (5, 5, -1)), ("delete_lines", (0, 0)),
    ("toggle_comment", (0, 0)), ("indent_lines", (0, 5)),
])
def test_refused_while_playing(command, args):
    e = env("Am C\nAm G\n", auto_play=False)
    e.session.play_pause()
    e.rendered()
    assert e.playback().status is PlaybackStatus.PLAYING
    e.recorder.clear()
    getattr(e.session, command)(*args)
    assert e.session.text == "Am C\nAm G\n" and not e.recorder.of_type(TextEdited)
    assert e.recorder.of_type(EditRefused)


@pytest.mark.parametrize("command, args", [
    ("replace_match", ((0, 99), "Am", "Em")), ("replace_all", ("Am", "Em", False, False, 99)),
    ("duplicate_lines", (-1, 0)), ("delete_lines", (0, 99)), ("toggle_comment", (99, 0)),
])
def test_offsets_outside_the_text_raise(command, args):
    e = env("Am C\n")
    with pytest.raises(ValueError):
        getattr(e.session, command)(*args)


@pytest.mark.parametrize("command, args", [
    ("replace_match", {"span": [0, 2], "query": "a", "replacement": "b", "match_case": True,
                       "whole_word": False}),
    ("replace_all", {"query": "a", "replacement": "b", "match_case": False, "whole_word": True,
                     "cursor": None}),
    ("duplicate_lines", {"anchor": 0, "cursor": 1}),
    ("move_lines", {"anchor": 0, "cursor": 1, "offset": 1}),
    ("delete_lines", {"anchor": 0, "cursor": 1}),
    ("toggle_comment", {"anchor": 0, "cursor": 1}),
    ("indent_lines", {"anchor": 0, "cursor": 1, "outdent": True}),
])
def test_the_commands_decode_from_the_bridge(command, args):
    assert bridge.decode_args(command, json.dumps(args)) == (
        dict(args, span=tuple(args["span"])) if "span" in args else args)
