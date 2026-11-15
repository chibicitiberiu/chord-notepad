"""A file dropped on the main window opens (Main.qml's DropArea, files.py).

The drags are QDragEnterEvent / QDragMoveEvent / QDropEvent sent to the
window with a QMimeData of file URLs, as a file manager's drag arrives. A
text drag onto the editor still inserts the text (tests/qt/test_qt_editor.py
has the normalising), and the sidebars' own drags still reach the editor
(tests/qt/test_qt_sidebar_drag.py).
"""

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QGuiApplication,
)

from chordnotepad_desktop import files as files_module  # noqa: E402
from tests.qt.test_qt_chrome import Chrome  # noqa: E402
from tests.qt.test_qt_editor import NO_MODIFIER, start  # noqa: E402

COPY = Qt.DropAction.CopyAction
LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def app(qapp, qtbot, tmp_path):
    harness = start(qapp, qtbot, tmp_path)
    ed = Chrome(harness, qtbot)
    qtbot.waitUntil(lambda: ed.area.hasActiveFocus(), timeout=1000)
    yield ed
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


def file_mime(*paths, text=None):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    if text is not None:
        mime.setText(text)
    return mime


def drag_over(app, mime, point):
    """Enter and move over ``point``; whether the window took the drag."""
    enter = QDragEnterEvent(QPointF(point), COPY, mime, LEFT, NO_MODIFIER)
    QGuiApplication.sendEvent(app.window, enter)
    move = QDragMoveEvent(QPointF(point), COPY, mime, LEFT, NO_MODIFIER)
    QGuiApplication.sendEvent(app.window, move)
    return move.isAccepted()


def drop(app, mime, point):
    """A whole drag and drop at ``point``; whether the drop was taken."""
    drag_over(app, mime, point)
    event = QDropEvent(QPointF(point), COPY, mime, LEFT, NO_MODIFIER)
    QGuiApplication.sendEvent(app.window, event)
    app.run()
    return event.isAccepted()


def editor_point(app):
    return app.point_of(0)


def song_file(tmp_path, name="Hymn.txt", text="G D\nAmazing grace\n"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def wait_opened(app, text):
    app.qtbot.waitUntil(lambda: app.text() == text, timeout=2000)


def test_a_file_dropped_on_the_editor_opens_and_joins_the_recent_list(app, tmp_path):
    path = song_file(tmp_path)
    assert drop(app, file_mime(path, text=str(path)), editor_point(app)) is True
    wait_opened(app, "G D\nAmazing grace\n")
    assert app.store.state("DocumentState").value("document_id") == str(path)
    assert list(app.files.recentLabels) == ["Hymn.txt"]
    # The path didn't go into the text.
    assert str(path) not in app.text()


def test_a_file_dropped_elsewhere_on_the_window_opens(app, tmp_path):
    path = song_file(tmp_path)
    top = QPoint(app.window.width() // 2, 8)       # the tab strip
    assert drop(app, file_mime(path), top) is True
    wait_opened(app, "G D\nAmazing grace\n")


def test_the_drag_is_taken_with_the_copy_cursor_and_the_frame_shows(app, tmp_path):
    path = song_file(tmp_path)
    frame = app.window.findChild(type(app.area), "fileDropFrame")
    assert frame is not None
    assert drag_over(app, file_mime(path), editor_point(app)) is True
    assert frame.isVisible()
    QGuiApplication.sendEvent(app.window, QDragLeaveEvent())
    app.run()
    assert not frame.isVisible()


def test_unsaved_changes_are_asked_about_first(app, tmp_path):
    path = song_file(tmp_path)
    app.type("mine")
    app.qtbot.waitUntil(
        lambda: app.store.state("DocumentState").value("is_modified") is True, timeout=2000)
    drop(app, file_mime(path), editor_point(app))
    dialog = app.item("unsavedDialog")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    app.click_item(app.it("unsavedCancel"))
    app.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)
    assert app.text() == "mine"


def test_a_drop_while_a_dialog_is_open_is_turned_down(app, tmp_path):
    path = song_file(tmp_path)
    app.type("mine")
    app.window.close()                       # unsaved: the question opens
    dialog = app.item("unsavedDialog")
    app.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
    assert drop(app, file_mime(path, text=str(path)), editor_point(app)) is False
    assert app.text() == "mine"
    app.key(Qt.Key.Key_Escape)
    app.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)


def test_a_file_that_cant_be_read_gets_opens_error(app, tmp_path):
    shown = []
    app.harness.app.presenter.shown.connect(lambda title, message: shown.append(message))
    missing = tmp_path / "gone.txt"
    song_file(tmp_path, "gone.txt")
    mime = file_mime(missing)
    drag_over(app, mime, editor_point(app))
    missing.unlink()                         # gone between the drag and the drop
    QGuiApplication.sendEvent(app.window, QDropEvent(QPointF(editor_point(app)), COPY, mime,
                                                     LEFT, NO_MODIFIER))
    app.qtbot.waitUntil(lambda: shown != [], timeout=2000)
    assert shown[0].startswith("Failed to open file")


def test_of_several_files_the_first_opens_and_the_status_says_so(app, tmp_path):
    first = song_file(tmp_path, "a.txt", "A\n")
    second = song_file(tmp_path, "b.txt", "B\n")
    third = song_file(tmp_path, "c.txt", "C\n")
    drop(app, file_mime(first, second, third), editor_point(app))
    wait_opened(app, "A\n")
    status = app.harness.app.status_bar
    app.qtbot.waitUntil(
        lambda: status.property("statusText") == files_module.only_one_note(3), timeout=2000)
    assert status.property("statusText") == (
        "Only one file opens at a time; the other 2 files were left out.")


def test_a_folder_or_a_web_link_isnt_a_file(app, tmp_path):
    folder_mime = QMimeData()
    folder_mime.setUrls([QUrl.fromLocalFile(str(tmp_path))])
    assert drop(app, folder_mime, QPoint(app.window.width() // 2, 8)) is False
    link = QMimeData()
    link.setUrls([QUrl("https://example.com/song.txt")])
    link.setText("https://example.com/song.txt")
    # A link is text for the editor, as before.
    assert drop(app, link, editor_point(app)) is True
    app.qtbot.waitUntil(lambda: "https://example.com/song.txt" in app.text(), timeout=1000)


def test_a_text_drag_onto_the_editor_still_inserts_the_text(app):
    app.type("C G")
    mime = QMimeData()
    mime.setText("Am ")
    assert drop(app, mime, app.point_of(2)) is True
    app.qtbot.waitUntil(lambda: "Am" in app.text(), timeout=1000)
    assert app.store.state("DocumentState").value("document_id") is None


def test_the_one_file_note_counts_the_others():
    assert files_module.only_one_note(2) == (
        "Only one file opens at a time; the other file was left out.")
    assert files_module.only_one_note(4) == (
        "Only one file opens at a time; the other 3 files were left out.")


def test_dropped_paths_keeps_local_files_in_order(tmp_path):
    a, b = song_file(tmp_path, "a.txt"), song_file(tmp_path, "b.txt")
    urls = [QUrl("https://example.com/x.txt"), QUrl.fromLocalFile(str(tmp_path)),
            QUrl.fromLocalFile(str(b)), QUrl.fromLocalFile(str(a)).toString()]
    assert files_module.dropped_paths(urls) == [str(b), str(a)]
    assert files_module.dropped_paths(None) == []


def test_open_path_opens_like_a_picked_file(app, tmp_path):
    path = song_file(tmp_path)
    app.files.openPath(str(path))
    wait_opened(app, "G D\nAmazing grace\n")
    assert list(app.files.recentLabels) == ["Hymn.txt"]
    assert ("open_document", {"ref": {"id": str(path), "display_name": "Hymn.txt",
                                      "location": app.store.direct("document_ref",
                                                                   str(path)).location},
                              "read_only": False}) in app.submitted
