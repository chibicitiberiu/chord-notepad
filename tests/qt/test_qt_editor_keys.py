"""The editor's keys: what a good text editor does with them (Tibi, 2026-11-15).

Real key events go to the window (QTest), which hands them to the focused
TextArea or to the window's shortcuts, as a user's would.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from PySide6.QtGui import QColor, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from tests.qt.test_qt_editor import Editor, song, start  # noqa: E402

K = Qt.Key
NONE = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
KEYPAD = Qt.KeyboardModifier.KeypadModifier
LONG = "".join(f"line {i:02d} la la\n" for i in range(120))


@pytest.fixture
def ed(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    editor = Editor(harness, qtbot)
    qtbot.waitUntil(lambda: editor.area.hasActiveFocus(), timeout=1000)
    yield editor
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def caret(ed):
    return ed.area.property("cursorPosition")


def selection(ed):
    """(anchor, caret)."""
    a = ed.area
    start, end, pos = a.property("selectionStart"), a.property("selectionEnd"), caret(ed)
    return (end if pos == start else start), pos


def press(ed, key, modifiers=NONE, text=""):
    """A key press and release with ``text`` as typed (Caps Lock changes only the text)."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(ed.window, QKeyEvent(kind, key, modifiers, text))
    ed.run()


def view_y(ed):
    return ed.item("editorScroll").property("contentItem").property("contentY")


def wrap(ed, on=True):
    ed.store.submit("set_word_wrap", {"on": on})
    ed.qtbot.waitUntil(lambda: ed.bridge.wordWrap is on, timeout=2000)
    ed.run(60)


def play(ed):
    ed.harness.player.auto_play = False
    ed.store.submit("play_pause", {"from_offset": None})
    ed.qtbot.waitUntil(lambda: ed.area.property("readOnly") is True, timeout=3000)


# -- Home and End ---------------------------------------------------------------------------

TEXT = "alpha beta\n    gamma delta\nzeta\n"
GAMMA = TEXT.index("gamma")
ZETA = TEXT.index("zeta")


@pytest.mark.parametrize("anchor, pos, key, mods, expected", [
    (2, ZETA + 2, K.Key_End, NONE, (ZETA + 4, ZETA + 4)),          # forward: the caret's line
    (ZETA + 2, 2, K.Key_End, NONE, (10, 10)),                      # backward: the caret's (first) line
    (2, ZETA + 2, K.Key_End, SHIFT, (2, ZETA + 4)),
    (ZETA + 2, 2, K.Key_End, SHIFT, (ZETA + 2, 10)),
    (2, ZETA + 2, K.Key_Home, NONE, (ZETA, ZETA)),
    (2, ZETA + 2, K.Key_Home, SHIFT, (2, ZETA)),
])
def test_home_and_end_go_from_the_selections_moving_end(ed, anchor, pos, key, mods, expected):
    song(ed, TEXT)
    ed.area.select(anchor, pos)
    ed.key(key, mods)
    assert selection(ed) == expected


def test_end_after_select_all_goes_to_the_last_line(ed):
    # Tibi's report: Ctrl+A then End put the caret at the end of the first line
    # (select all left the caret at the start).
    song(ed, TEXT)
    ed.key(K.Key_A, CTRL)
    assert selection(ed) == (0, len(TEXT))
    ed.key(K.Key_Up)
    ed.key(K.Key_End)
    assert caret(ed) == ZETA + 4


def test_select_all_keeps_the_view(ed):
    song(ed, LONG)
    ed.set_cursor(0)
    ed.run()
    ed.key(K.Key_A, CTRL)
    ed.run(100)
    assert caret(ed) == len(LONG) and view_y(ed) == 0


def test_home_toggles_between_the_first_non_blank_and_the_lines_start(ed):
    song(ed, TEXT)
    line = TEXT.index("    gamma")
    ed.set_cursor(GAMMA + 3)
    ed.key(K.Key_Home)
    assert caret(ed) == GAMMA
    ed.key(K.Key_Home)
    assert caret(ed) == line
    ed.key(K.Key_Home)
    assert caret(ed) == GAMMA
    ed.set_cursor(line + 2)                       # inside the indentation
    ed.key(K.Key_Home)
    assert caret(ed) == GAMMA
    ed.set_cursor(GAMMA + 5)
    ed.key(K.Key_Home, SHIFT)
    assert selection(ed) == (GAMMA + 5, GAMMA)


def test_home_and_end_on_a_wrapped_line_stay_on_its_row(ed):
    text = "x\n" + " ".join(f"word{i}" for i in range(80)) + "\n"
    song(ed, text)
    wrap(ed)
    a = ed.area
    row_y = a.positionToRectangle(200).y()
    assert row_y > a.positionToRectangle(2).y()      # really wrapped
    ed.set_cursor(200)
    ed.key(K.Key_Home)
    assert a.positionToRectangle(caret(ed)).y() == row_y and caret(ed) < 200
    ed.set_cursor(200)
    ed.key(K.Key_End)
    assert a.positionToRectangle(caret(ed)).y() == row_y and caret(ed) > 200
    ed.area.select(10, 200)
    ed.key(K.Key_End)
    assert a.positionToRectangle(caret(ed)).y() == row_y


# -- Enter with modifiers -------------------------------------------------------------------


@pytest.mark.parametrize("key, mods", [
    (K.Key_Return, CTRL), (K.Key_Enter, CTRL | KEYPAD), (K.Key_Return, SHIFT),
    (K.Key_Enter, SHIFT | KEYPAD), (K.Key_Return, CTRL | SHIFT),
])
def test_enter_with_ctrl_or_shift_is_a_new_line(ed, key, mods):
    song(ed, "C G\nla\n")
    ed.area.select(1, 2)
    ed.key(key, mods)
    assert ed.text() == "C\nG\nla\n" and caret(ed) == 2
    assert " " not in ed.bridge.document.toRawText()
    ed.qtbot.waitUntil(lambda: ed.session.text == ed.text(), timeout=2000)
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == "C G\nla\n"


def test_ctrl_enter_while_playing_changes_nothing_and_says_why(ed):
    song(ed, "C G\nla\n")
    play(ed)
    ed.set_cursor(1)
    ed.key(K.Key_Return, CTRL)
    assert ed.text() == "C G\nla\n"
    status = ed.harness.app.status_bar
    ed.qtbot.waitUntil(lambda: status.readOnlyNotice != "", timeout=1000)


# -- Page Up / Page Down, Ctrl+Home / End, Ctrl+Up / Down -----------------------------------


def test_page_down_and_up_move_the_caret_and_the_view_by_a_page(ed):
    song(ed, LONG)
    ed.set_cursor(LONG.index("line 00") + 3)
    ed.run()
    line_h = ed.area.property("cursorRectangle").height()
    view_h = ed.item("editorScroll").property("contentItem").property("height")
    ed.key(K.Key_PageDown)
    lines = int(LONG[:caret(ed)].count("\n"))
    assert lines == int((view_h - line_h) // line_h)
    assert caret(ed) - LONG.rfind("\n", 0, caret(ed)) - 1 == 3        # same column
    assert view_y(ed) > 0
    on_screen = ed.area.property("cursorRectangle").y() - view_y(ed)
    ed.key(K.Key_PageDown)
    assert LONG[:caret(ed)].count("\n") == 2 * lines
    assert ed.area.property("cursorRectangle").y() - view_y(ed) == pytest.approx(on_screen, abs=1)
    ed.key(K.Key_PageUp)
    assert LONG[:caret(ed)].count("\n") == lines
    ed.key(K.Key_PageUp)
    ed.key(K.Key_PageUp)
    assert caret(ed) == 3 and view_y(ed) == 0


def test_shift_page_down_extends_the_selection(ed):
    song(ed, LONG)
    ed.set_cursor(2)
    ed.key(K.Key_PageDown, SHIFT)
    anchor, pos = selection(ed)
    assert anchor == 2 and pos > 20
    ed.key(K.Key_PageUp, SHIFT)
    assert selection(ed) == (2, 2)


def test_page_down_on_the_last_page_goes_to_the_last_line(ed):
    song(ed, "a\nbb\nccc")
    ed.set_cursor(1)
    ed.key(K.Key_PageDown)
    assert ed.text()[:caret(ed)].count("\n") == 2


def test_ctrl_home_and_end(ed):
    song(ed, LONG)
    ed.set_cursor(40)
    ed.key(K.Key_End, CTRL)
    assert caret(ed) == len(LONG)
    ed.key(K.Key_Home, CTRL | SHIFT)
    assert selection(ed) == (len(LONG), 0)


def test_ctrl_up_and_down_scroll_without_moving_the_caret(ed):
    song(ed, LONG)
    ed.set_cursor(5)
    ed.run()
    ed.key(K.Key_Down, CTRL)
    ed.key(K.Key_Down, CTRL)
    line_h = ed.area.property("cursorRectangle").height()
    assert caret(ed) == 5 and view_y(ed) == pytest.approx(2 * line_h)
    ed.key(K.Key_Up, CTRL)
    assert caret(ed) == 5 and view_y(ed) == pytest.approx(line_h)
    ed.key(K.Key_Up, CTRL)
    ed.key(K.Key_Up, CTRL)
    assert view_y(ed) == 0


# -- what Qt already did: word moves and deletes, Shift+Ctrl selection -----------------------


def test_word_moves_and_word_deletes(ed):
    song(ed, "alpha beta gamma\n")
    ed.set_cursor(0)
    ed.key(K.Key_Right, CTRL)
    assert caret(ed) == 6
    ed.key(K.Key_Right, CTRL | SHIFT)
    assert selection(ed) == (6, 11)
    ed.set_cursor(8)
    ed.key(K.Key_Backspace, CTRL)
    assert ed.text() == "alpha ta gamma\n"
    ed.key(K.Key_Delete, CTRL)
    assert ed.text() == "alpha gamma\n"


# -- line operations ------------------------------------------------------------------------

LINES = "one\ntwo\nthree\n"


def wait_text(ed, text):
    ed.qtbot.waitUntil(lambda: ed.text() == text, timeout=2000)


def test_ctrl_d_duplicates_the_line_or_the_selection(ed):
    song(ed, LINES)
    ed.set_cursor(5)
    ed.key(K.Key_D, CTRL)
    wait_text(ed, "one\ntwo\ntwo\nthree\n")
    assert caret(ed) == 9                                   # same column, the copy
    ed.area.select(0, 3)
    ed.key(K.Key_D, CTRL)
    wait_text(ed, "oneone\ntwo\ntwo\nthree\n")
    assert selection(ed) == (3, 6)
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == "one\ntwo\ntwo\nthree\n"
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == LINES


def test_ctrl_shift_up_and_down_move_the_lines_with_the_selection(ed):
    song(ed, LINES)
    ed.area.select(5, 10)                                   # "wo\nth"
    ed.key(K.Key_Up, CTRL | SHIFT)
    wait_text(ed, "two\nthree\none\n")
    assert selection(ed) == (1, 6)
    ed.key(K.Key_Down, CTRL | SHIFT)
    wait_text(ed, LINES)
    assert selection(ed) == (5, 10)
    ed.key(K.Key_Down, CTRL | SHIFT)                        # "three" is last: the final newline stays
    ed.run(60)
    assert ed.text() == LINES
    ed.key(K.Key_Z, CTRL)
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == LINES


def test_moving_the_first_line_up_does_nothing(ed):
    song(ed, LINES)
    ed.set_cursor(1)
    ed.key(K.Key_Up, CTRL | SHIFT)
    ed.run(60)
    assert ed.text() == LINES and caret(ed) == 1


def test_ctrl_shift_k_deletes_the_lines(ed):
    song(ed, LINES)
    ed.set_cursor(6)
    ed.key(K.Key_K, CTRL | SHIFT)
    wait_text(ed, "one\nthree\n")
    assert caret(ed) == 6
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == LINES


def test_ctrl_l_selects_the_line_and_more_on_repeat(ed):
    song(ed, LINES)
    ed.set_cursor(5)
    ed.key(K.Key_L, CTRL)
    assert selection(ed) == (4, 8)
    ed.key(K.Key_L, CTRL)
    assert selection(ed) == (4, 14)


def test_line_operations_are_refused_while_playing(ed):
    text = "C G\nAm F\nla\n"
    song(ed, text)
    play(ed)
    ed.set_cursor(5)
    for key, mods in ((K.Key_D, CTRL), (K.Key_K, CTRL | SHIFT), (K.Key_Up, CTRL | SHIFT)):
        ed.key(key, mods)
    ed.run(60)
    assert ed.text() == text
    status = ed.harness.app.status_bar
    ed.qtbot.waitUntil(lambda: status.readOnlyNotice != "", timeout=1000)
    assert not any(n in ("duplicate_lines", "delete_lines", "move_lines") for n, _ in ed.submitted)
    ed.key(K.Key_L, CTRL)                                  # selecting still works
    assert selection(ed) == (4, 9)


def test_the_line_shortcuts_work_with_caps_lock(ed):
    song(ed, LINES)
    ed.set_cursor(1)
    press(ed, K.Key_D, CTRL, "D")
    wait_text(ed, "one\none\ntwo\nthree\n")
    press(ed, K.Key_K, CTRL | SHIFT, "K")
    wait_text(ed, LINES)
    press(ed, K.Key_L, CTRL, "L")
    assert selection(ed)[1] > selection(ed)[0]


# -- comments and indentation ----------------------------------------------------------------

SHEET = "G       D\nAmazing grace\n"


def test_ctrl_slash_toggles_comments(ed):
    song(ed, SHEET)
    ed.area.select(0, len(SHEET) - 1)
    ed.key(K.Key_Slash, CTRL)
    wait_text(ed, "// G       D\n// Amazing grace\n")
    ed.key(K.Key_Slash, CTRL)
    wait_text(ed, SHEET)
    ed.set_cursor(12)                                       # one line, no selection
    ed.key(K.Key_Slash, CTRL)
    wait_text(ed, "G       D\n// Amazing grace\n")
    assert caret(ed) == 15
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == SHEET


def test_the_comment_is_what_the_highlighter_paints_grey(ed):
    song(ed, SHEET)
    ed.set_cursor(0)
    ed.key(K.Key_Slash, CTRL)
    wait_text(ed, "// G       D\nAmazing grace\n")
    ed.settle()
    assert ("comment" in [kind for start, end, kind in ed.bridge.spans if start == 0])


def test_tab_over_several_lines_indents_and_shift_tab_unindents(ed):
    song(ed, SHEET)
    ed.area.select(2, 15)
    ed.key(K.Key_Tab)
    wait_text(ed, "\tG       D\n\tAmazing grace\n")
    assert selection(ed) == (3, 17)
    ed.key(K.Key_Backtab, SHIFT)
    wait_text(ed, SHEET)
    # Within one line, Tab types a tab over the selection as before.
    ed.area.select(0, 1)
    ed.key(K.Key_Tab)
    wait_text(ed, "\t       D\nAmazing grace\n")
    # Shift+Tab without a selection unindents the caret's line.
    ed.set_cursor(3)
    ed.key(K.Key_Backtab, SHIFT)
    wait_text(ed, "       D\nAmazing grace\n")
    assert ed.area.hasActiveFocus()


def test_unindent_keeps_chords_over_their_words(ed):
    text = "      G\n    la la\n"
    song(ed, text)
    ed.area.select(0, len(text) - 1)
    ed.key(K.Key_Backtab, SHIFT)
    wait_text(ed, "  G\nla la\n")


def test_comment_and_indent_are_refused_while_playing(ed):
    song(ed, SHEET)
    play(ed)
    ed.area.select(0, 15)
    ed.key(K.Key_Slash, CTRL)
    ed.key(K.Key_Tab)
    ed.key(K.Key_Backtab, SHIFT)
    ed.run(60)
    assert ed.text() == SHEET
    status = ed.harness.app.status_bar
    ed.qtbot.waitUntil(lambda: status.readOnlyNotice != "", timeout=1000)


# -- a selected word's other occurrences --------------------------------------------------------


def occurrences(ed):
    return ed.bridge.tints["occurrence"]


def test_a_selected_words_other_occurrences_are_tinted(ed):
    text = "Am C Am7 Am\nam Am\n"
    song(ed, text)
    QTest.mouseDClick(ed.window, Qt.MouseButton.LeftButton, NONE, ed.point_of(1))
    ed.run(60)
    assert ed.area.property("selectedText") == "Am"            # a double click selects the word
    assert occurrences(ed) == [(9, 11), (15, 17)]               # not Am7, not "am"
    fmt = ed.formats_at(9)[-1]
    assert fmt.background().color() == QColor(_theme(ed).property("occurrence"))
    ed.set_cursor(3)
    ed.run(60)
    assert occurrences(ed) == []
    ed.area.select(0, 4)                                       # not a word
    ed.run(60)
    assert occurrences(ed) == []


def test_the_find_bar_takes_over_from_the_occurrences(ed):
    text = "Am C Am\n"
    song(ed, text)
    ed.area.select(0, 2)
    ed.run(60)
    assert occurrences(ed) == [(5, 7)]
    ed.key(K.Key_F, CTRL)
    ed.qtbot.waitUntil(lambda: ed.bridge.tints["find"] == [(0, 2), (5, 7)], timeout=1000)
    assert occurrences(ed) == []
    ed.key(K.Key_Escape)
    ed.run(60)
    assert ed.bridge.tints["find"] == [] and occurrences(ed) == [(5, 7)]


def _theme(ed):
    from PySide6.QtQml import qmlEngine
    return qmlEngine(ed.window).singletonInstance("CNTheme", "Theme")

