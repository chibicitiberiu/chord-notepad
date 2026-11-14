"""The editor (plan steps D1-D3): EditorPane.qml over editor_bridge.py.

The whole front end runs in the test process (QtAppHarness): a real session
on the Qt host, a FakePlayer, the config under tmp_path. Keys and clicks go
to the window, which delivers them to the focused TextArea.
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import Q_ARG, QMetaObject, QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QGuiApplication, QInputMethodEvent,
    QTextCharFormat, QTextCursor, QWheelEvent,
)
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad_desktop.offsets import utf16_length  # noqa: E402
from tests.qt.conftest import QtAppHarness, write_config  # noqa: E402

SONG = "C   G   Am  F\nOne two three four\n"
NO_MODIFIER = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
GRIN = "\U0001F600"


class Editor:
    """The started app's editor, with helpers."""

    def __init__(self, harness, qtbot):
        self.harness, self.qtbot = harness, qtbot
        self.window = harness.window
        self.bridge = harness.app.editor
        self.area = self.item("editor")
        self.submitted = []
        store = harness.store
        real_submit = store.submit

        def spy(name, args=None):
            self.submitted.append((name, args))
            return real_submit(name, args) if args is not None else real_submit(name)

        store.submit = spy

    @property
    def session(self):
        return self.harness.app._session

    @property
    def store(self):
        return self.harness.store

    def item(self, name):
        from PySide6.QtCore import QObject
        found = self.window.findChild(QQuickItem, name) or self.window.findChild(QObject, name)
        assert found is not None, name
        return found

    def text(self):
        return self.bridge.document.toPlainText()

    def run(self, ms=30):
        self.qtbot.wait(ms)

    def settle(self):
        """Until the session has the editor's text and its spans are painted."""
        self.qtbot.waitUntil(lambda: self.session.text == self.text(), timeout=2000)
        self.qtbot.waitUntil(lambda: self.bridge.highlight_current, timeout=3000)

    def type(self, text):
        for ch in text:
            if ch == "\n":
                QTest.keyClick(self.window, Qt.Key.Key_Return)
            else:
                QTest.keyClick(self.window, ch)

    def key(self, key, modifier=NO_MODIFIER):
        QTest.keyClick(self.window, key, modifier)

    def set_cursor(self, position):
        self.area.setProperty("cursorPosition", position)

    def edit(self, command, args):
        """A session command, and wait for it to run."""
        self.store.submit(command, args)
        self.run()

    def point_of(self, position, right=False):
        """The window point in the middle of the character at ``position``."""
        rect = self.area.positionToRectangle(position)
        if position < self.area.property("length"):
            nxt = self.area.positionToRectangle(position + 1)
            x = (rect.x() + nxt.x()) / 2 if nxt.y() == rect.y() else rect.x() + 3
        else:
            x = rect.x() + 3
        return self.area.mapToScene(QPointF(x, rect.y() + rect.height() / 2)).toPoint()

    def gap_point(self, position):
        """The window point just right of the gap before ``position`` (a click there puts
        the cursor at ``position``)."""
        rect = self.area.positionToRectangle(position)
        return self.area.mapToScene(QPointF(rect.x() + 1, rect.y() + rect.height() / 2)).toPoint()

    def click(self, position, button=Qt.MouseButton.LeftButton, modifier=NO_MODIFIER):
        QTest.mouseClick(self.window, button, modifier, self.point_of(position))

    def formats_at(self, position):
        """The highlighter's formats covering ``position``."""
        block = self.bridge.document.findBlock(position)
        offset = position - block.position()
        ranges = block.layout().formats()
        return [QTextCharFormat(r.format) for r in ranges if r.start <= offset < r.start + r.length]

    def action(self, name):
        """One of EditorPane's actions (``undoAction``, ...): enabled() and trigger()."""
        return PaneAction(self.item(name))

    def set_texts(self):
        return [args for name, args in self.submitted if name == "set_text"]


class PaneAction:
    def __init__(self, obj):
        self.obj = obj

    def enabled(self):
        return self.obj.property("enabled")

    def trigger(self):
        QMetaObject.invokeMethod(self.obj, "trigger")


def utf16_slice(text, start, end):
    return text.encode("utf-16-le", "surrogatepass")[2 * start:2 * end].decode("utf-16-le", "surrogatepass")


def start(qapp, qtbot, tmp_path, **config):
    write_config(tmp_path, show_quick_start_on_startup=False, **config)
    harness = QtAppHarness(qapp, tmp_path).start()
    qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
    harness.window.requestActivate()
    qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is harness.window, timeout=1000)
    return harness


@pytest.fixture
def editor(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    ed = Editor(harness, qtbot)
    qtbot.waitUntil(lambda: ed.area.hasActiveFocus(), timeout=1000)
    yield ed
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def song(ed, text=SONG):
    """Open ``text`` the way a document is opened (a reset edit)."""
    ed.store.submit("restore_draft", {"text": text, "document": None, "modified": False,
                                     "read_only": False})
    ed.qtbot.waitUntil(lambda: ed.text() == text, timeout=2000)
    ed.settle()


# -- D1: the text and the session ---------------------------------------------------------


def test_the_editor_has_the_focus_at_startup(editor):
    assert editor.area.hasActiveFocus()
    assert editor.area.property("readOnly") is False


def test_typing_reaches_the_session_with_increasing_tokens(editor):
    editor.type("C G\nla")
    editor.qtbot.waitUntil(lambda: editor.session.text == "C G\nla", timeout=2000)
    tokens = [args["client_token"] for args in editor.set_texts()]
    assert len(tokens) == 6 and tokens == sorted(tokens) and len(set(tokens)) == 6
    assert editor.window.title() == "Untitled* - Chord Notepad"


def test_the_sessions_spans_are_painted(editor):
    editor.type("C   G7  Xyz\n{bpm: 90} {bpm: 999}\n// note\n")
    editor.settle()
    kinds = {editor.text()[s:e]: kind for s, e, kind in editor.bridge.spans}
    assert kinds["C"] == "chord" and kinds["G7"] == "chord"
    assert kinds["{bpm: 999}"] == "directive_invalid" and kinds["// note"] == "comment"
    chord = editor.formats_at(0)
    assert chord and chord[-1].fontUnderline() and chord[-1].foreground().color() == QColor("#0000ff")
    directive = editor.formats_at(editor.text().index("{bpm: 90}"))
    assert directive[-1].foreground().color() == QColor("#8b4789")
    bad = editor.formats_at(editor.text().index("{bpm: 999}"))
    assert bad[-1].foreground().color() == QColor("#ff0000") and bad[-1].fontUnderline()
    assert editor.formats_at(editor.text().index("// note"))[-1].foreground().color() == QColor("#bebebe")


def test_a_redundant_directive_is_faded(editor):
    editor.type("{bpm: 90}\n{bpm: 100}\nC G\n")
    editor.settle()
    kinds = {editor.text()[s:e]: kind for s, e, kind in editor.bridge.spans}
    assert kinds["{bpm: 90}"] == "directive_redundant"
    faded = editor.formats_at(0)[-1].foreground().color()
    # #8b4789 at 45% over white.
    assert (faded.red(), faded.green(), faded.blue()) == (203, 172, 202)


def test_spans_move_with_the_typing_until_the_next_detection(editor):
    song(editor, "C   G\n")
    assert (4, 5, "chord") in editor.bridge.spans
    editor.set_cursor(0)
    editor.type("Am ")
    assert (7, 8, "chord") in editor.bridge.spans          # moved at once
    assert not editor.bridge.highlight_current
    editor.settle()
    assert (0, 2, "chord") in editor.bridge.spans


def test_spans_for_another_text_are_not_painted(editor):
    song(editor, "C   G\n")
    before = editor.bridge.spans
    # Someone else's set_text (another token): its spans aren't for this text.
    editor.store.submit("set_text", {"text": "Am\n", "client_token": 999})
    editor.qtbot.waitUntil(lambda: editor.session.text == "Am\n", timeout=1000)
    editor.run(800)
    assert editor.bridge.spans == before and editor.text() == "C   G\n"


def test_astral_characters_keep_the_spans_in_place(editor):
    text = f"{GRIN} la\nC   Am\n{GRIN}{GRIN}\nG\n"
    song(editor, text)
    shown = editor.text()
    painted = {utf16_slice(shown, s, e) for s, e, kind in editor.bridge.spans if kind == "chord"}
    assert painted == {"C", "Am", "G"}
    g = shown.index("\nG") + 1                        # a Python (code point) index
    assert (utf16_length(shown[:g]), utf16_length(shown[:g]) + 1, "chord") in editor.bridge.spans
    assert editor.bridge.codePointAt(utf16_length(shown[:g])) == g


def test_a_group_edit_is_one_undo_step_and_isnt_sent_back(editor):
    editor.type("C G\n")
    editor.settle()
    sent = len(editor.set_texts())
    editor.edit("transpose", {"semitones": 2, "selection": None, "cursor": 2})
    editor.qtbot.waitUntil(lambda: editor.text() == "D A\n", timeout=2000)
    assert len(editor.set_texts()) == sent                  # not echoed
    assert editor.area.property("cursorPosition") == 2      # line and column kept
    editor.settle()                                         # its own spans, token 0
    editor.key(Qt.Key.Key_Z, CTRL)
    assert editor.text() == "C G\n"                         # the typing is still there
    editor.qtbot.waitUntil(lambda: editor.session.text == "C G\n", timeout=2000)


def test_a_plain_insert_puts_the_cursor_after_it(editor):
    editor.type("C G\n")
    editor.settle()
    editor.edit("insert_chord", {"at": 2, "chord": "Am"})
    editor.qtbot.waitUntil(lambda: "Am" in editor.text(), timeout=2000)
    assert editor.text() == editor.session.text
    at = editor.text().index("Am") + 2
    assert editor.area.property("cursorPosition") in (at, at + 1)   # after it (and its space)


def test_a_reset_edit_clears_the_undo_history_and_places_the_cursor(editor):
    edits = []
    editor.store.event.connect(lambda name, data: edits.append(data) if name == "TextEdited" else None)
    editor.type("x")
    assert editor.area.property("canUndo") is True
    song(editor)                                            # restore_draft: a reset edit
    assert edits[-1]["undo"] == "reset"
    assert editor.area.property("canUndo") is False
    assert editor.area.property("cursorPosition") == edits[-1]["cursor"]


def test_opening_a_document_shows_it_at_the_start(editor, tmp_path):
    song_file = tmp_path / "song.txt"
    song_file.write_text(SONG, encoding="utf-8")
    editor.store.submit("open_document", {"ref": {"id": str(song_file), "display_name": "song.txt",
                                                  "location": str(song_file)}, "read_only": False})
    editor.qtbot.waitUntil(lambda: editor.text() == SONG, timeout=2000)
    editor.settle()
    assert editor.area.property("canUndo") is False
    assert editor.window.title() == "song.txt - Chord Notepad"


def test_the_editors_own_text_wins_over_an_edit_made_on_an_older_one(editor):
    editor.type("C G\n")
    editor.settle()
    # The session runs insert_text on its text, and before it does the user
    # types (here: straight into the document) — the edit arrives while that
    # set_text is still queued.
    editor.store.submit("insert_text", {"at": 0, "text": "Am "})
    cursor = QTextCursor(editor.bridge.document)
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("la")
    editor.qtbot.waitUntil(lambda: editor.text().startswith("Am "), timeout=2000)
    assert editor.text() == "Am C G\nla"
    editor.qtbot.waitUntil(lambda: editor.session.text == editor.text(), timeout=2000)
    editor.settle()


def test_read_only_while_playing_but_the_sessions_edits_still_apply(editor):
    editor.harness.player.auto_play = False
    song(editor)
    editor.store.submit("play_pause", {"from_offset": None})
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=3000)
    editor.set_cursor(0)
    editor.type("x")
    editor.key(Qt.Key.Key_Z, CTRL)
    assert editor.text() == SONG
    # Selecting and copying still work.
    editor.area.setProperty("selectByMouse", True)
    editor.key(Qt.Key.Key_A, CTRL)
    assert editor.area.property("selectedText") == SONG
    editor.store.submit("stop")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is False, timeout=3000)


def test_the_caret_and_the_selection_stay_put_when_the_editor_locks(editor):
    # TextEdit moves the caret to the end whenever readOnly changes.
    editor.harness.player.auto_play = False
    song(editor)
    QMetaObject.invokeMethod(editor.area, "select", Q_ARG(int, 8), Q_ARG(int, 4))

    def caret():
        return (editor.area.property("cursorPosition"), editor.area.property("selectionStart"),
                editor.area.property("selectionEnd"))

    assert caret() == (4, 4, 8)
    editor.store.submit("play_pause", {"from_offset": None})
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=3000)
    assert caret() == (4, 4, 8)
    editor.store.submit("stop")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is False, timeout=3000)
    assert caret() == (4, 4, 8)
    editor.window.setProperty("mode", "play")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=1000)
    editor.window.setProperty("mode", "edit")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is False, timeout=1000)
    assert caret() == (4, 4, 8)


def test_session_edits_apply_while_the_editor_is_read_only(editor):
    editor.window.setProperty("mode", "play")             # Play: read-only, as the mockup
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=1000)
    editor.edit("insert_text", {"at": 0, "text": "C G"})
    editor.qtbot.waitUntil(lambda: editor.text() == "C G", timeout=2000)
    editor.type("x")
    assert editor.text() == "C G"
    editor.window.setProperty("mode", "edit")


def test_the_editor_font_follows_the_config(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path, font_family="TkFixedFont", font_size=14)
    try:
        area = Editor(harness, qtbot).area
        font = area.property("font")
        assert font.family() == "Noto Sans Mono" and round(font.pointSizeF()) == 14
        assert font.hintingPreference() == font.HintingPreference.PreferDefaultHinting
    finally:
        harness.shutdown()


def test_an_installed_family_from_the_config_is_used(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path, font_family="Inter", font_size=11)
    try:
        assert Editor(harness, qtbot).area.property("font").family() == "Inter"
    finally:
        harness.shutdown()


def test_preedit_text_doesnt_reach_the_session(editor):
    editor.type("C ")
    editor.qtbot.waitUntil(lambda: editor.session.text == "C ", timeout=1000)
    sent = len(editor.set_texts())
    QGuiApplication.sendEvent(editor.area, QInputMethodEvent("ka", []))
    editor.run()
    assert editor.text() == "C " and len(editor.set_texts()) == sent
    commit = QInputMethodEvent("", [])
    commit.setCommitString("か")
    QGuiApplication.sendEvent(editor.area, commit)
    editor.qtbot.waitUntil(lambda: editor.session.text == "C か", timeout=1000)
    assert len(editor.set_texts()) == sent + 1


# -- D2: paste, on every path ---------------------------------------------------------------

DIRTY = "C G\r\nAm​ F﻿\r"


def test_ctrl_v_pastes_normalised_over_the_selection(editor):
    editor.type("one two")
    editor.area.select(4, 7)
    QGuiApplication.clipboard().setText(DIRTY)
    editor.key(Qt.Key.Key_V, CTRL)
    assert editor.text() == "one C G\nAm F\n"
    assert editor.area.property("cursorPosition") == len(editor.text())
    editor.key(Qt.Key.Key_Z, CTRL)
    assert editor.text() == "one two"                       # one undo step


def test_shift_insert_pastes_normalised(editor):
    QGuiApplication.clipboard().setText("A\r\nB")
    editor.key(Qt.Key.Key_Insert, Qt.KeyboardModifier.ShiftModifier)
    assert editor.text() == "A\nB"


def test_an_empty_clipboard_pastes_nothing(editor):
    editor.type("x")
    QGuiApplication.clipboard().setText("")
    editor.key(Qt.Key.Key_V, CTRL)
    editor.action("pasteAction").trigger()
    assert editor.text() == "x"


def test_pasting_a_song_into_an_empty_document_picks_the_notation(editor):
    QGuiApplication.clipboard().setText("Do   Sol  Lam\nla la la\n")
    editor.key(Qt.Key.Key_V, CTRL)
    editor.qtbot.waitUntil(
        lambda: editor.store.state("EditorState").value("notation") == "european", timeout=2000)


def test_the_context_menu_enables_what_applies(editor):
    actions = {name: editor.action(name + "Action") for name in
               ("undo", "redo", "cut", "copy", "paste", "selectAll")}
    QGuiApplication.clipboard().setText("Am")

    def enabled():
        return {name: a.enabled() for name, a in actions.items()}

    assert enabled() == {"undo": False, "redo": False, "cut": False, "copy": False,
                         "paste": True, "selectAll": False}
    editor.type("C G")
    editor.area.select(0, 1)
    assert enabled() == {"undo": True, "redo": False, "cut": True, "copy": True,
                         "paste": True, "selectAll": True}
    actions["undo"].trigger()
    assert enabled()["redo"] is True
    actions["redo"].trigger()
    assert editor.text() == "C G"
    editor.window.setProperty("mode", "play")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=1000)
    editor.area.select(0, 1)
    assert enabled() == {"undo": False, "redo": False, "cut": False, "copy": True,
                         "paste": False, "selectAll": True}
    editor.window.setProperty("mode", "edit")


def test_a_right_click_opens_the_context_menu_and_its_paste_normalises(editor):
    editor.type("ab")
    QGuiApplication.clipboard().setText("x\r\ny")
    editor.click(1, Qt.MouseButton.RightButton)
    menu = editor.item("editorContextMenu")
    editor.qtbot.waitUntil(lambda: menu.property("opened") is True, timeout=1000)
    paste = editor.item("menuPaste")
    centre = paste.mapToScene(QPointF(paste.width() / 2, paste.height() / 2)).toPoint()
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, centre)
    editor.qtbot.waitUntil(lambda: "x\ny" in editor.text(), timeout=1000)
    assert "\r" not in editor.text()


def test_select_all_puts_the_cursor_at_the_start(editor):
    editor.type("C G\nla")
    editor.key(Qt.Key.Key_A, CTRL)
    assert editor.area.property("selectedText") == "C G\nla"
    assert editor.area.property("cursorPosition") == 0


def test_middle_click_pastes_primary_at_the_pointer_normalised(editor, monkeypatch):
    editor.type("C   G")
    monkeypatch.setattr(type(editor.bridge), "_selection_text", staticmethod(lambda: "Am \r\n"))
    QTest.mouseClick(editor.window, Qt.MouseButton.MiddleButton, NO_MODIFIER, editor.point_of(4))
    editor.qtbot.waitUntil(lambda: "Am" in editor.text(), timeout=1000)
    assert editor.text() in ("C   Am \nG", "C   GAm \n")


def test_a_drop_inserts_normalised_text(editor):
    editor.type("C G")
    mime = QMimeData()
    mime.setText("Am\r\nF")
    point = editor.point_of(1)
    actions = Qt.DropAction.CopyAction
    for event in (QDragEnterEvent(QPointF(point), actions, mime, Qt.MouseButton.LeftButton, NO_MODIFIER),
                  QDragMoveEvent(QPointF(point), actions, mime, Qt.MouseButton.LeftButton, NO_MODIFIER),
                  QDropEvent(QPointF(point), actions, mime, Qt.MouseButton.LeftButton, NO_MODIFIER)):
        QGuiApplication.sendEvent(editor.window, event)
    editor.qtbot.waitUntil(lambda: "Am" in editor.text(), timeout=1000)
    assert "\r" not in editor.text() and "Am\nF" in editor.text()


# -- D3: interactions -----------------------------------------------------------------------


def test_a_click_on_a_chord_sounds_it_and_moves_the_playhead(editor):
    song(editor)
    editor.click(SONG.index("G"))
    editor.qtbot.waitUntil(lambda: len(editor.harness.player.immediate) == 1, timeout=2000)
    editor.qtbot.waitUntil(lambda: editor.bridge.playheadPos == SONG.index("G"), timeout=1000)
    assert editor.area.property("cursorPosition") in (SONG.index("G"), SONG.index("G") + 1)
    playhead = editor.item("playhead")
    assert playhead.property("visible") is True


def test_a_double_click_selects_the_word_and_sounds_the_chord_once(editor):
    song(editor)
    at = editor.point_of(SONG.index("Am"))
    QTest.mouseDClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, at)
    editor.run(100)
    assert len(editor.harness.player.immediate) == 1
    assert editor.area.property("selectedText") == "Am"


def test_a_click_on_lyrics_or_an_invalid_chord_sounds_nothing(editor):
    text = "C  Cmaj13#11b9\nCome on\n"
    song(editor, text)
    editor.click(1)                                    # the space after C
    editor.click(text.index("maj"))                    # an invalid chord
    editor.click(text.index("on"))
    editor.run(100)
    assert editor.harness.player.immediate == []


def test_the_hand_cursor_shows_over_valid_chords_only(editor):
    song(editor, "C  Cmaj13#11b9\nCome on\n")
    hover = editor.item("editorHover")
    pane = editor.item("editorPane")

    def over(position):
        QTest.mouseMove(editor.window, editor.point_of(position))
        editor.run(20)
        return pane.property("overChord"), hover.property("cursorShape")

    assert over(0) == (True, Qt.CursorShape.PointingHandCursor)
    assert over(5) == (False, Qt.CursorShape.IBeamCursor)   # an invalid chord
    assert over(17) == (False, Qt.CursorShape.IBeamCursor)  # lyrics


def test_the_placeholder_is_shown_while_empty_and_never_in_the_text(editor):
    assert editor.area.property("placeholderText") == "Type or paste a song here"
    assert editor.text() == "" and editor.session.text == ""


def test_the_caret_blinks_and_restarts_when_it_moves(editor):
    caret = editor.item("caret")
    assert caret.property("visible") is True
    editor.qtbot.waitUntil(lambda: caret.property("visible") is False, timeout=1500)
    editor.type("a")
    assert caret.property("visible") is True


def test_the_playing_chord_is_painted_on_top_and_followed(editor):
    lines = ["one two"] * 120 + ["C   G   Am  F" + " " * 300 + "Dm"]
    text = "\n".join(lines) + "\n"
    editor.harness.player.auto_play = False
    song(editor, text)
    editor.store.submit("play_pause", {"from_offset": None})
    player = editor.harness.player
    # The song renders on its own thread: play once its first chord is there.
    editor.qtbot.waitUntil(lambda: player.calls[-1:] == ["start"] and player.play(chords=1) == 1,
                           timeout=3000)
    editor.qtbot.waitUntil(lambda: editor.bridge.playingStart == text.index("C   G"), timeout=3000)
    fmt = editor.formats_at(text.index("C   G"))[-1]
    assert fmt.background().color() == QColor("#ffff00") and fmt.fontUnderline()
    flick = editor.item("editorScroll").property("contentItem")
    editor.qtbot.waitUntil(lambda: flick.property("contentY") > 0, timeout=1000)
    editor.harness.player.play(chords=4)
    editor.qtbot.waitUntil(lambda: editor.bridge.playingStart == text.index("Dm"), timeout=3000)
    editor.qtbot.waitUntil(lambda: flick.property("contentX") > 0, timeout=1000)
    assert editor.formats_at(text.index("C   G"))[-1].background().color() != QColor("#ffff00")
    editor.store.submit("stop")
    editor.qtbot.waitUntil(lambda: editor.bridge.playingStart == -1, timeout=3000)


def test_word_wrap_follows_the_setting(editor):
    song(editor, "la " * 200 + "\n")
    flick = editor.item("editorScroll").property("contentItem")
    assert editor.bridge.wordWrap is False                 # the default
    assert flick.property("contentWidth") > flick.property("width")
    editor.edit("set_word_wrap", {"on": True})
    editor.qtbot.waitUntil(lambda: editor.bridge.wordWrap, timeout=1000)
    editor.qtbot.waitUntil(lambda: flick.property("contentWidth") <= flick.property("width") + 1,
                           timeout=1000)
    assert editor.harness.app.core.config.get("word_wrap") is True
    editor.edit("set_word_wrap", {"on": False})
    editor.qtbot.waitUntil(lambda: flick.property("contentWidth") > flick.property("width"), timeout=1000)


def chip_text(ed):
    return ed.item("zoomPercent").property("text")


def test_ctrl_plus_minus_and_zero_zoom_the_text(editor):
    editor.key(Qt.Key.Key_Equal, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 12, timeout=1000)
    assert chip_text(editor) == "110%"
    editor.key(Qt.Key.Key_Plus, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 13, timeout=1000)
    editor.key(Qt.Key.Key_Minus, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 12, timeout=1000)
    editor.key(Qt.Key.Key_0, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 11, timeout=1000)
    assert chip_text(editor) == "100%"
    assert round(editor.area.property("font").pointSizeF()) == 11


def test_the_zoom_chip_steps_and_resets(editor):
    def click(name):
        button = editor.item(name)
        centre = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
        QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, centre)

    click("zoomInButton")
    click("zoomInButton")
    editor.qtbot.waitUntil(lambda: chip_text(editor) == "120%", timeout=1000)
    assert editor.area.hasActiveFocus()                    # the chip doesn't take the focus
    click("zoomResetButton")
    editor.qtbot.waitUntil(lambda: chip_text(editor) == "100%", timeout=1000)
    for _ in range(8):
        click("zoomOutButton")
    editor.qtbot.waitUntil(lambda: chip_text(editor) == "50%", timeout=1000)
    assert editor.bridge.fontSize == 6
    editor.harness.shutdown()
    import json
    assert json.loads(editor.harness.config_file().read_text())["font_size"] == 6


def wheel(ed, delta, modifiers):
    host = ed.item("editHost")
    point = host.mapToScene(QPointF(host.width() / 3, host.height() / 2))
    event = QWheelEvent(point, ed.window.mapToGlobal(point), QPoint(0, 0), QPoint(0, delta),
                        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
    QGuiApplication.sendEvent(ed.window, event)
    ed.run()


def test_ctrl_wheel_zooms_and_doesnt_scroll(editor):
    song(editor, "la\n" * 300)
    editor.set_cursor(0)
    flick = editor.item("editorScroll").property("contentItem")
    flick.setProperty("contentY", 0)
    # Down a notch with Ctrl: smaller text, and the view stays at the top.
    wheel(editor, -120, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 10, timeout=1000)
    editor.run(50)
    assert flick.property("contentY") == 0
    wheel(editor, 60, CTRL)                                 # half a notch: nothing yet
    editor.run(50)
    assert editor.bridge.fontSize == 10
    wheel(editor, 60, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 11, timeout=1000)
    wheel(editor, 120, CTRL)
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 12, timeout=1000)
    # Without Ctrl the wheel scrolls.
    wheel(editor, -120, NO_MODIFIER)
    editor.qtbot.waitUntil(lambda: flick.property("contentY") > 0, timeout=1000)
    assert editor.bridge.fontSize == 12


def test_tab_inserts_a_tab_and_keypad_enter_replaces_the_selection(editor):
    editor.type("C G")
    editor.key(Qt.Key.Key_Tab)
    assert editor.text() == "C G\t" and editor.area.hasActiveFocus()
    editor.area.select(1, 2)
    QTest.keyClick(editor.window, Qt.Key.Key_Enter, Qt.KeyboardModifier.KeypadModifier)
    assert editor.text() == "C\nG\t"


def test_the_play_workspace_shows_the_same_text_read_only_with_the_pencil(editor):
    editor.type("C G")
    editor.window.setProperty("mode", "play")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=1000)
    editor.run()          # the Play split (text over the chord sheet) lays out on the next polish
    host = editor.item("playTextHost")
    assert editor.item("editorPane").parentItem() == host
    pencil = editor.item("playZoomChip").findChild(QQuickItem, "editPencil")
    assert pencil.property("visible") is True
    centre = pencil.mapToScene(QPointF(pencil.width() / 2, pencil.height() / 2)).toPoint()
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, centre)
    editor.qtbot.waitUntil(lambda: editor.window.property("mode") == "edit", timeout=1000)
    assert editor.area.property("readOnly") is False and editor.area.hasActiveFocus()


def test_the_dark_theme_repaints_the_highlighting(editor):
    from PySide6.QtQml import qmlEngine

    song(editor, "C   G\n")
    theme = qmlEngine(editor.window).singletonInstance("CNTheme", "Theme")
    theme.setProperty("dark", True)
    try:
        assert editor.formats_at(0)[-1].foreground().color() == QColor("#8ab4f8")
    finally:
        theme.setProperty("dark", False)
    assert editor.formats_at(0)[-1].foreground().color() == QColor("#0000ff")


def test_ctrl_o_doesnt_insert_a_newline(editor):
    editor.type("C G")
    editor.set_cursor(1)
    editor.key(Qt.Key.Key_O, CTRL)
    assert editor.text() == "C G"


def test_editor_shortcuts_dont_reach_behind_a_dialog(editor):
    editor.type("C G")
    editor.window.close()                                 # unsaved: the dialog opens
    dialog = editor.item("unsavedDialog")
    editor.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    editor.key(Qt.Key.Key_A, CTRL)
    QGuiApplication.clipboard().setText("xyz")
    editor.key(Qt.Key.Key_V, CTRL)
    assert editor.area.property("selectedText") == "" and editor.text() == "C G"
    editor.key(Qt.Key.Key_Escape)
    editor.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    editor.qtbot.waitUntil(lambda: editor.area.hasActiveFocus(), timeout=1000)


def test_the_editor_gets_the_focus_back_after_quick_start(qapp, qtbot, tmp_path):
    write_config(tmp_path, show_quick_start_on_startup=True)
    harness = QtAppHarness(qapp, tmp_path).start()
    try:
        qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
        harness.window.requestActivate()
        qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is harness.window, timeout=1000)
        from PySide6.QtCore import QObject
        dialog = harness.window.findChild(QObject, "quickStartDialog")
        qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
        QTest.keyClick(harness.window, Qt.Key.Key_Escape)
        qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
        area = harness.window.findChild(QQuickItem, "editor")
        qtbot.waitUntil(lambda: area.hasActiveFocus(), timeout=1000)
    finally:
        harness.shutdown()


def test_fast_zoom_steps_stay_on_the_ladder(editor):
    for _ in range(5):
        editor.bridge.zoomIn()                             # before the session answers
    editor.qtbot.waitUntil(lambda: editor.bridge.fontSize == 17, timeout=1000)
    assert chip_text(editor) == "150%"


def test_mouse_selection_gestures(editor):
    song(editor, "C   G   Am\none two three\n")
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, editor.gap_point(4))
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier,
                     editor.gap_point(8))
    assert editor.area.property("selectedText") == "G   "                 # Shift+click extends
    QTest.mousePress(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, editor.gap_point(15))
    QTest.mouseMove(editor.window, editor.gap_point(17))
    QTest.mouseMove(editor.window, editor.gap_point(19))
    QTest.mouseRelease(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, editor.gap_point(19))
    assert editor.area.property("selectedText") == "two "                 # a drag selects


def test_shift_wheel_scrolls_sideways_with_wrap_off(editor):
    song(editor, "C" + " " * 400 + "G\n")
    flick = editor.item("editorScroll").property("contentItem")
    editor.set_cursor(0)
    wheel(editor, -240, Qt.KeyboardModifier.ShiftModifier)
    editor.qtbot.waitUntil(lambda: flick.property("contentX") > 0, timeout=1000)
    assert flick.property("contentY") == 0


def test_a_click_on_the_placeholder_focuses_the_editor(editor):
    editor.item("playTab").forceActiveFocus()
    assert not editor.area.hasActiveFocus()
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, editor.point_of(0))
    editor.qtbot.waitUntil(lambda: editor.area.hasActiveFocus(), timeout=1000)
    assert editor.text() == ""


def test_chord_clicks_and_the_hand_work_while_read_only(editor):
    song(editor)
    editor.window.setProperty("mode", "play")
    editor.qtbot.waitUntil(lambda: editor.area.property("readOnly") is True, timeout=1000)
    editor.run()          # the Play split (text over the chord sheet) lays out on the next polish
    QTest.mouseMove(editor.window, editor.point_of(0))
    editor.run(20)
    assert editor.item("editorPane").property("overChord") is True
    editor.click(SONG.index("Am"))
    editor.qtbot.waitUntil(lambda: len(editor.harness.player.immediate) == 1, timeout=2000)
    editor.window.setProperty("mode", "edit")


def test_an_edit_with_an_anchor_selects_up_to_the_cursor(editor):
    # B4's insert_snippet selects the value it inserted (TextEdited.anchor).
    editor.type("C G")
    editor.qtbot.waitUntil(lambda: editor.session.text == "C G", timeout=1000)
    editor.bridge._on_event("TextEdited", {"text_revision": 99, "start": 3, "end": 3,
                                           "replacement": " {bpm: 120}", "undo": "group",
                                           "cursor": 13, "anchor": 10})
    assert editor.text() == "C G {bpm: 120}"
    assert editor.area.property("selectedText") == "120"
    assert editor.area.property("cursorPosition") == 13


def test_a_triple_click_selects_the_line(editor):
    song(editor, "C   G   Am\none two three\n")
    at = editor.point_of(16)
    QTest.mouseDClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, at)
    QTest.mouseClick(editor.window, Qt.MouseButton.LeftButton, NO_MODIFIER, at)
    assert editor.area.property("selectedText").rstrip("\n") == "one two three"


def test_a_shorter_song_doesnt_draw_the_old_playhead_past_its_end(editor):
    # The playhead was on C at 15; the new text is shorter than that until the
    # session moves the playhead (Qt warned "Position '15' out of range", and
    # the fixture fails on Qt warnings).
    song(editor, "{label: verse}\nC   G\n")
    playback = editor.store.state("PlaybackState")
    editor.qtbot.waitUntil(lambda: playback.value("playhead_offset") == 15, timeout=1000)
    song(editor, "C G Am F\n")
    editor.qtbot.waitUntil(lambda: playback.value("playhead_offset") == 0, timeout=1000)
