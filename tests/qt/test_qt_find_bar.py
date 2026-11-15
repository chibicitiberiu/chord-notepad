"""The find bar under the text (FindBar.qml over find_bar.py's FindModel).

Ctrl+F / Ctrl+H open it, Escape closes it; Enter, F3 and Shift with them go
from match to match, wrapping with a notice; Replace and Replace all are
the session's replace_match / replace_all, one undo step each; while a
song plays Find works and Replace is refused with the status bar's badge.
Real key events go to the window.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad_desktop.find_bar import count_text  # noqa: E402
from tests.qt.test_qt_editor import song  # noqa: E402
from tests.qt.test_qt_editor_keys import CTRL, NONE, SHIFT, caret, ed, play, press, selection  # noqa: E402,F401

K = Qt.Key
TEXT = "Am C Am G\nla am la\nAm7 F\n"
AMS = [(0, 2), (5, 7), (13, 15), (19, 21)]          # "am", any case, not whole word


def bar(ed):
    return ed.item("findBar")


def field(ed, name="findField"):
    return ed.item(name)


def finder(ed):
    return ed.bridge.finder


def type_into(ed, text):
    for ch in text:
        QTest.keyClick(ed.window, ch)
    ed.run()


def open_find(ed, query=None, replace=False):
    ed.key(K.Key_H if replace else K.Key_F, CTRL)
    ed.qtbot.waitUntil(lambda: bar(ed).property("visible") is True, timeout=1000)
    ed.qtbot.waitUntil(lambda: field(ed).hasActiveFocus(), timeout=1000)
    if query is not None:
        ed.key(K.Key_A, CTRL)
        type_into(ed, query)


def click(ed, name):
    item = ed.item(name)
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(ed.window, Qt.MouseButton.LeftButton, NONE, centre)
    ed.run()


def find_tints(ed):
    return ed.bridge.tints["find"]


def test_the_count_text():
    assert count_text("", 0, 0) == ""
    assert count_text("x", 0, 0) == "No matches"
    assert count_text("x", 7, 3) == "3 of 7"
    assert count_text("x", 7, 0) == "7 matches" and count_text("x", 1, 0) == "1 match"


def test_ctrl_f_opens_the_bar_and_typing_finds_as_you_type(ed):
    song(ed, TEXT)
    ed.set_cursor(3)
    open_find(ed)
    assert bar(ed).y() + bar(ed).height() == pytest.approx(ed.item("editorPane").height())
    type_into(ed, "am")
    assert selection(ed) == (5, 7)                      # the first match after the caret
    assert finder(ed).countText == "2 of 4"
    assert find_tints(ed) == AMS
    assert ed.area.property("selectionColor") == QColor(_theme(ed).property("findCurrent"))


def _theme(ed):
    from PySide6.QtQml import qmlEngine
    return qmlEngine(ed.window).singletonInstance("CNTheme", "Theme")


def test_enter_f3_and_shift_go_through_the_matches_and_wrap_with_a_notice(ed):
    song(ed, TEXT)
    ed.set_cursor(0)
    open_find(ed, "am")
    assert selection(ed) == (0, 2)
    ed.key(K.Key_Return)
    assert selection(ed) == (5, 7)
    ed.key(K.Key_F3)
    assert selection(ed) == (13, 15)
    ed.key(K.Key_Return)
    assert selection(ed) == (19, 21) and finder(ed).notice == ""
    ed.key(K.Key_Return)
    assert selection(ed) == (0, 2) and finder(ed).notice == "Continued from the top"
    assert ed.item("findNotice").property("text") == "Continued from the top"
    ed.key(K.Key_Return, SHIFT)
    assert selection(ed) == (19, 21) and finder(ed).notice == "Continued from the bottom"
    ed.key(K.Key_F3, SHIFT)
    assert selection(ed) == (13, 15)
    ed.qtbot.waitUntil(lambda: finder(ed).notice == "", timeout=3000)


def test_match_case_and_whole_word(ed):
    song(ed, TEXT)
    ed.set_cursor(0)
    open_find(ed, "am")
    click(ed, "matchCase")
    assert finder(ed).matchCase and finder(ed).count == 1
    assert selection(ed) == (13, 15)
    click(ed, "matchCase")
    click(ed, "wholeWord")
    assert finder(ed).count == 3 and (19, 21) not in find_tints(ed)


def test_no_matches_says_so_and_puts_the_caret_back(ed):
    song(ed, TEXT)
    ed.set_cursor(3)
    open_find(ed, "zz")
    assert finder(ed).countText == "No matches" and finder(ed).noMatch
    assert selection(ed) == (3, 3)
    assert ed.item("findNext").property("enabled") is False


def test_escape_closes_and_gives_the_text_the_keys(ed):
    song(ed, TEXT)
    open_find(ed, "am")
    ed.key(K.Key_Escape)
    ed.qtbot.waitUntil(lambda: bar(ed).property("visible") is False, timeout=1000)
    assert ed.area.hasActiveFocus() and find_tints(ed) == []
    assert ed.area.property("selectionColor") == QColor(_theme(ed).property("selection"))
    # F3 with the bar closed: the last query again.
    ed.set_cursor(8)
    ed.key(K.Key_F3)
    assert selection(ed) == (13, 15) and bar(ed).property("visible") is False
    # Escape in the text closes the bar too.
    open_find(ed)
    ed.area.forceActiveFocus()
    ed.key(K.Key_Escape)
    assert bar(ed).property("visible") is False


def test_f3_without_a_query_opens_the_bar(ed):
    song(ed, TEXT)
    ed.key(K.Key_F3)
    ed.qtbot.waitUntil(lambda: field(ed).hasActiveFocus(), timeout=1000)


def test_ctrl_f_takes_a_one_line_selection_as_the_query(ed):
    song(ed, TEXT)
    ed.area.select(5, 9)
    open_find(ed)
    assert field(ed).property("text") == "Am G"
    assert finder(ed).countText == "1 of 1"
    ed.key(K.Key_Escape)
    ed.area.select(0, 12)                                     # two lines: not taken
    open_find(ed)
    assert field(ed).property("text") == "Am G"


def test_the_tints_follow_the_text(ed):
    song(ed, TEXT)
    open_find(ed, "la")
    assert find_tints(ed) == [(10, 12), (16, 18)]
    ed.area.forceActiveFocus()
    ed.set_cursor(0)
    type_into(ed, "x")
    assert find_tints(ed) == [(11, 13), (17, 19)]
    assert finder(ed).count == 2


def test_replace_replaces_the_selected_match_and_moves_on(ed):
    song(ed, TEXT)
    ed.set_cursor(0)
    open_find(ed, "am", replace=True)
    assert ed.item("replaceField").property("visible") is True
    assert selection(ed) == (0, 2)
    ed.key(K.Key_Tab)
    ed.qtbot.waitUntil(lambda: field(ed, "replaceField").hasActiveFocus(), timeout=1000)
    type_into(ed, "Dm")
    ed.key(K.Key_Return)
    ed.qtbot.waitUntil(lambda: ed.text().startswith("Dm C Am"), timeout=2000)
    ed.qtbot.waitUntil(lambda: selection(ed) == (5, 7), timeout=2000)
    assert "replace_match" in [n for n, _ in ed.submitted]
    click(ed, "replaceOne")
    ed.qtbot.waitUntil(lambda: ed.text().startswith("Dm C Dm G\nla am"), timeout=2000)
    ed.qtbot.waitUntil(lambda: selection(ed) == (13, 15), timeout=2000)
    # Each replacement is one undo step.
    ed.area.forceActiveFocus()
    ed.key(K.Key_Z, CTRL)
    assert ed.text().startswith("Dm C Am G")
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == TEXT


def test_replace_when_the_selection_isnt_a_match_finds_first(ed):
    song(ed, TEXT)
    open_find(ed, "am", replace=True)
    ed.area.select(3, 4)
    click(ed, "replaceOne")
    assert selection(ed) == (5, 7) and ed.text() == TEXT


def test_replace_all_is_one_undo_step(ed):
    song(ed, TEXT)
    open_find(ed, "am", replace=True)
    ed.key(K.Key_Tab)
    type_into(ed, "Em")
    click(ed, "replaceAll")
    ed.qtbot.waitUntil(lambda: ed.text() == "Em C Em G\nla Em la\nEm7 F\n", timeout=2000)
    assert finder(ed).countText == "No matches"
    status = ed.harness.app.status_bar
    ed.qtbot.waitUntil(lambda: status.statusText == "Replaced 4 matches", timeout=1000)
    ed.area.forceActiveFocus()
    ed.key(K.Key_Z, CTRL)
    assert ed.text() == TEXT


def test_while_playing_find_works_and_replace_is_refused(ed):
    song(ed, TEXT)
    play(ed)
    ed.set_cursor(0)
    open_find(ed, "am", replace=True)
    ed.key(K.Key_F3)
    assert selection(ed) == (5, 7)
    click(ed, "replaceAll")
    click(ed, "replaceOne")
    status = ed.harness.app.status_bar
    ed.qtbot.waitUntil(lambda: status.readOnlyNotice != "", timeout=1000)
    assert ed.text() == TEXT


def test_the_play_workspace_has_no_replace_row(ed):
    song(ed, TEXT)
    ed.window.setProperty("mode", "play")
    ed.qtbot.waitUntil(lambda: ed.area.property("readOnly") is True, timeout=1000)
    ed.run()
    open_find(ed, "am", replace=True)
    assert ed.item("replaceField").property("visible") is False
    assert ed.item("replaceToggle").property("enabled") is False
    assert finder(ed).count == 4


def test_caps_lock_doesnt_stop_the_shortcuts(ed):
    song(ed, TEXT)
    press(ed, K.Key_F, CTRL, "F")
    ed.qtbot.waitUntil(lambda: bar(ed).property("visible") is True, timeout=1000)
    ed.key(K.Key_Escape)
    press(ed, K.Key_H, CTRL, "H")
    ed.qtbot.waitUntil(lambda: ed.item("replaceField").property("visible") is True, timeout=1000)


# -- Go to line -------------------------------------------------------------------------------


def test_ctrl_g_goes_to_a_line(ed):
    song(ed, TEXT)
    ed.key(K.Key_G, CTRL)
    line_field = field(ed, "goToLineField")
    ed.qtbot.waitUntil(lambda: line_field.hasActiveFocus(), timeout=1000)
    assert ed.item("lineCountLabel").property("text") == "of 4"
    assert ed.item("findField").property("visible") is False
    type_into(ed, "3")
    ed.key(K.Key_Return)
    ed.qtbot.waitUntil(lambda: bar(ed).property("visible") is False, timeout=1000)
    assert caret(ed) == TEXT.index("Am7") and ed.area.hasActiveFocus()


def test_go_to_line_clamps_and_escape_closes(ed):
    song(ed, TEXT)
    ed.key(K.Key_G, CTRL)
    type_into(ed, "99")
    ed.key(K.Key_Enter, Qt.KeyboardModifier.KeypadModifier)
    assert caret(ed) == len(TEXT)                      # the last line (empty, after the newline)
    ed.key(K.Key_G, CTRL)
    ed.qtbot.waitUntil(lambda: field(ed, "goToLineField").hasActiveFocus(), timeout=1000)
    assert field(ed, "goToLineField").property("text") == ""
    ed.key(K.Key_Escape)
    assert bar(ed).property("visible") is False and ed.area.hasActiveFocus()
    assert caret(ed) == len(TEXT)


def test_go_to_line_works_while_playing(ed):
    song(ed, TEXT)
    play(ed)
    ed.key(K.Key_G, CTRL)
    type_into(ed, "2")
    ed.key(K.Key_Return)
    assert caret(ed) == TEXT.index("la")
