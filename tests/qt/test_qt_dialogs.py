"""The small dialogs (plan step G2): Transpose, Suggest Capo, Quick Start,
Licences, About, Help, and Escape on each (Q12).

The whole front end runs in the test process (``tests/qt/conftest.py``);
each dialog is opened the way F1's menus will (``AppDialogs.open*``).
"""

import json

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QMetaObject, QObject, QPoint, QPointF, Qt, Q_ARG  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.app_paths import AppPaths  # noqa: E402
from chordnotepad.session import quick_start  # noqa: E402
from chordnotepad.session.platform import DESKTOP_QT  # noqa: E402
from chordnotepad_desktop import dialogs as dialogs_module  # noqa: E402
from chordnotepad_desktop.help_opener import HelpOpener  # noqa: E402
from tests.qt.conftest import PATHS, QtAppHarness, write_config  # noqa: E402

SONG = "{key: G}\nG   D   Em  C\nAmazing grace\n"


def find(root, name):
    """The item named ``name`` under ``root``, through Repeater and Loader
    delegates too (pitfall 25); None if there is none."""
    if isinstance(root, QQuickWindow):
        root = root.contentItem()
    if root.objectName() == name:
        return root
    for child in root.childItems():
        hit = find(child, name)
        if hit is not None:
            return hit
    return None


def find_all(root, name, out=None):
    out = [] if out is None else out
    if isinstance(root, QQuickWindow):
        root = root.contentItem()
    if root.objectName() == name:
        out.append(root)
    for child in root.childItems():
        find_all(child, name, out)
    return out


def plain(value):
    """A QML property as Python data (a JS array may arrive as a QJSValue)."""
    return value.toVariant() if hasattr(value, "toVariant") else value


class App:
    """The started app, with helpers for its dialogs."""

    def __init__(self, harness, qtbot):
        self.harness, self.qtbot = harness, qtbot
        self.window = harness.window
        self.hub = self.window.findChild(QObject, "appDialogs")
        self.submitted = []
        store = harness.store
        real = store.submit

        def spy(name, args=None):
            self.submitted.append((name, args))
            return real(name, args) if args is not None else real(name)

        store.submit = spy

    @property
    def session(self):
        return self.harness.app._session

    @property
    def bridge(self):
        return self.harness.app.editor

    def open(self, name):
        QMetaObject.invokeMethod(self.hub, name)

    def popup(self, name):
        found = self.window.findChild(QObject, name)
        assert found is not None, name
        return found

    def item(self, name):
        found = find(self.window, name)
        assert found is not None, name
        return found

    def opened(self, name):
        dialog = self.popup(name)
        self.qtbot.waitUntil(lambda: dialog.property("opened") is True, timeout=2000)
        return dialog

    def closed(self, name):
        dialog = self.popup(name)
        self.qtbot.waitUntil(lambda: dialog.property("visible") is False, timeout=2000)

    def click(self, name):
        target = self.item(name)
        centre = target.mapToScene(QPointF(target.width() / 2, target.height() / 2))
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         centre.toPoint())

    def key(self, key, modifier=Qt.KeyboardModifier.NoModifier):
        QTest.keyClick(self.window, key, modifier)

    def type(self, text):
        for ch in text:
            QTest.keyClick(self.window, ch)

    def focus(self):
        self.window.requestActivate()
        self.qtbot.waitUntil(lambda: QGuiApplication.focusWindow() is self.window, timeout=1000)

    def set_text(self, text=SONG):
        self.bridge.document.setPlainText(text)
        self.qtbot.waitUntil(lambda: self.session.text == text, timeout=2000)

    def text(self):
        return self.bridge.document.toPlainText()

    def select(self, start, end):
        area = self.item("editor")
        QMetaObject.invokeMethod(area, "select", Q_ARG(int, start), Q_ARG(int, end))

    def status(self):
        return self.harness.store.state("StatusState").value("text")


def started(qapp, qtbot, tmp_path, **config):
    write_config(tmp_path, **{"show_quick_start_on_startup": False, **config})
    harness = QtAppHarness(qapp, tmp_path).start()
    qtbot.waitUntil(lambda: harness.window.property("contentReady") is True, timeout=3000)
    return harness


def finish(harness, qtbot):
    warnings, unexpected = list(harness.app.warnings), list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == [] and unexpected == []


@pytest.fixture
def app(qapp, qtbot, tmp_path):
    harness = started(qapp, qtbot, tmp_path)
    a = App(harness, qtbot)
    a.focus()
    yield a
    finish(harness, qtbot)


# -- Transpose -----------------------------------------------------------------------------


def test_transpose_says_what_it_moves(app):
    app.set_text()
    app.open("openTranspose")
    app.opened("transposeDialog")
    assert app.item("transposeScope").property("text") == "Transpose whole song."
    app.key(Qt.Key.Key_Escape)
    app.closed("transposeDialog")
    app.select(9, 22)
    app.open("openTranspose")
    app.opened("transposeDialog")
    assert app.item("transposeScope").property("text") == "Transpose selection."


def test_transpose_with_enter_is_one_undo_step_and_moves_the_key(app):
    app.set_text()
    app.open("openTranspose")
    app.opened("transposeDialog")
    app.type("2")              # the box has the focus with its text selected
    app.key(Qt.Key.Key_Return)
    app.closed("transposeDialog")
    app.qtbot.waitUntil(lambda: app.text().startswith("{key: A}\nA   E   F#m D"), timeout=2000)
    transposes = [args for name, args in app.submitted if name == "transpose"]
    assert len(transposes) == 1
    assert transposes[0]["semitones"] == 2 and transposes[0]["selection"] is None
    assert app.status()
    QMetaObject.invokeMethod(app.window.findChild(QObject, "undoAction"), "trigger")
    app.qtbot.waitUntil(lambda: app.text() == SONG, timeout=2000)


def test_transpose_refuses_what_isnt_minus_11_to_11_and_0_does_nothing(app):
    app.set_text()
    app.open("openTranspose")
    dialog = app.opened("transposeDialog")
    box = app.item("transposeSemitones")
    for typed in ("12", "-"):
        box.forceActiveFocus()
        QMetaObject.invokeMethod(box, "selectAll")
        app.type(typed)
        app.click("transposeOk")
        assert dialog.property("visible") is True
        assert app.item("transposeProblem").property("text") == \
            "Enter a whole number of semitones from -11 to 11."
    box.forceActiveFocus()
    QMetaObject.invokeMethod(box, "selectAll")
    app.type("0")
    app.click("transposeOk")
    app.closed("transposeDialog")
    app.qtbot.wait(50)
    assert not [c for c in app.submitted if c[0] == "transpose"]
    assert app.text() == SONG


def test_transpose_a_selection(app):
    app.set_text()
    app.select(9, 22)          # the chord line
    app.open("openTranspose")
    app.opened("transposeDialog")
    app.type("-2")
    app.click("transposeOk")
    app.qtbot.waitUntil(lambda: "F   C   Dm  Bb" in app.text(), timeout=2000)
    assert app.text().startswith("{key: G}")       # the key stays


# -- Suggest Capo --------------------------------------------------------------------------


def test_suggest_capo_asks_for_a_voicing_and_inserts_the_capo(app):
    app.set_text("Ab  Eb  Fm  Db\nAmazing grace\n")
    app.open("openSuggestCapo")
    dialog = app.opened("capoDialog")
    assert dialog.property("title") == "Suggest Capo"
    assert app.item("capoScope").property("text")
    assert app.item("capoVoicing").property("count") >= 1
    app.key(Qt.Key.Key_Return)
    app.closed("capoDialog")
    app.qtbot.waitUntil(lambda: app.text().startswith("{capo:"), timeout=5000)


def test_escape_cancels_suggest_capo(app):
    app.set_text()
    app.open("openSuggestCapo")
    dialog = app.opened("capoDialog")
    request = dialog.property("requestId")
    app.key(Qt.Key.Key_Escape)
    app.closed("capoDialog")
    app.qtbot.waitUntil(lambda: ("respond", {"request_id": request, "value": None}) in app.submitted,
                        timeout=1000)
    app.qtbot.wait(50)
    assert app.text() == SONG


# -- Quick Start ---------------------------------------------------------------------------


def test_quick_start_shows_the_qt_pages(app):
    app.open("openQuickStart")
    dialog = app.opened("quickStartDialog")
    expected = quick_start.pages(DESKTOP_QT)
    app.qtbot.waitUntil(lambda: app.item("quickStartPageIndicator").property("text")
                        == f"1 / {len(expected)}", timeout=2000)
    assert app.item("quickStartPageTitle").property("text") == expected[0]["title"]
    paragraphs = [b[1] for b in expected[0]["blocks"] if b[0] == "text"]
    shown = [t.property("text") for t in find_all(app.window.contentItem(), "quickStartText")]
    assert shown == paragraphs
    assert dialog.property("width") > 0


def test_quick_start_snippets_use_the_editors_font_and_colours(app):
    app.open("openQuickStart")
    dialog = app.opened("quickStartDialog")
    pages = quick_start.pages(DESKTOP_QT)
    page = next(i for i, p in enumerate(pages) if any(b[0] == "snippet" for b in p["blocks"]))
    dialog.setProperty("page", page)
    app.qtbot.waitUntil(lambda: find(app.window, "quickStartSnippetText") is not None, timeout=2000)
    snippet = app.item("quickStartSnippetText")
    editor = app.item("editor")
    font, editor_font = snippet.property("font"), editor.property("font")
    assert font.family() == editor_font.family() and font.pointSizeF() == editor_font.pointSizeF()
    # The chords are painted like the editor's: blue and underlined.
    doc = snippet.property("textDocument").textDocument()
    text = doc.toPlainText()
    chord = next(i for i, ch in enumerate(text) if ch.isupper())
    block = doc.findBlock(chord)
    from PySide6.QtGui import QTextCharFormat
    formats = [QTextCharFormat(r.format) for r in block.layout().formats()
               if r.start <= chord - block.position() < r.start + r.length]
    assert formats and formats[0].fontUnderline()
    assert formats[0].foreground().color() == QColor("#0000ff")


def test_quick_start_keeps_one_size_on_every_page(app):
    app.window.resize(1000, 800)
    app.open("openQuickStart")
    dialog = app.opened("quickStartDialog")
    count = len(quick_start.pages(DESKTOP_QT))
    app.qtbot.waitUntil(lambda: len(plain(dialog.property("pages")) or []) == count, timeout=2000)
    app.qtbot.wait(300)                              # the pictures load and settle the height
    nxt = app.item("quickStartNext")
    sizes, ys, bodies = set(), set(), []
    width = dialog.property("width")
    for page in range(count):
        dialog.setProperty("page", page)
        app.qtbot.wait(60)
        sizes.add((round(dialog.property("width")), round(dialog.property("height"))))
        ys.add(round(nxt.mapToScene(QPointF(0, 0)).y()))
        bodies.append(app.item("quickStartPage").implicitHeight())
    assert len(sizes) == 1 and len(ys) == 1, (sizes, ys)
    assert len(set(round(h) for h in bodies)) > 1     # the pages do differ; the dialog is the tallest's
    tallest = max(bodies)
    assert app.item("quickStartBody").property("tallest") == pytest.approx(tallest, abs=1)
    # A narrower window makes the dialog narrower: every page is measured again.
    sizes.clear()
    app.window.resize(420, 800)
    app.qtbot.wait(300)
    narrow = []
    for page in range(count):
        dialog.setProperty("page", page)
        app.qtbot.wait(60)
        sizes.add((round(dialog.property("width")), round(dialog.property("height"))))
        narrow.append(app.item("quickStartPage").implicitHeight())
    assert len(sizes) == 1
    assert app.item("quickStartBody").property("tallest") == pytest.approx(max(narrow), abs=1)
    assert sizes.pop()[0] < width


def test_quick_start_pages_with_the_buttons_and_left_right(app):
    app.open("openQuickStart")
    dialog = app.opened("quickStartDialog")
    count = len(quick_start.pages(DESKTOP_QT))
    app.qtbot.waitUntil(lambda: len(plain(dialog.property("pages")) or []) == count, timeout=2000)
    assert not app.item("quickStartPrevious").isEnabled()
    app.key(Qt.Key.Key_Left)                         # Previous is off: nothing
    assert dialog.property("page") == 0
    app.key(Qt.Key.Key_Right)
    assert dialog.property("page") == 1
    app.click("quickStartNext")
    assert dialog.property("page") == 2
    app.key(Qt.Key.Key_Left)                         # after a click on a button too
    assert dialog.property("page") == 1
    for _ in range(count + 2):
        app.key(Qt.Key.Key_Right)
    assert dialog.property("page") == count - 1
    assert not app.item("quickStartNext").isEnabled()
    assert app.item("quickStartPageIndicator").property("text") == f"{count} / {count}"
    app.key(Qt.Key.Key_Escape)
    app.closed("quickStartDialog")


def test_dont_show_again_can_only_turn_quick_start_off(qapp, qtbot, tmp_path):
    harness = started(qapp, qtbot, tmp_path, show_quick_start_on_startup=False)
    try:
        a = App(harness, qtbot)
        a.focus()
        a.open("openQuickStart")
        a.opened("quickStartDialog")
        a.click("quickStartClose")                   # unticked: nothing turns it on
        a.closed("quickStartDialog")
        qtbot.wait(50)
        assert not [c for c in a.submitted if c[0] == "set_show_quick_start_on_startup"]
        assert harness.app.core.config.get("show_quick_start_on_startup") is False
    finally:
        finish(harness, qtbot)


# -- Licences and About ----------------------------------------------------------------------


def test_licences_lists_source_code_first_and_shows_the_selected_one(app):
    app.open("openLicences")
    dialog = app.opened("licencesDialog")
    rows = dialog.property("rows")
    assert rows[0] == {"id": "__source__", "label": "Source code", "licence": "", "group": False}
    assert dialog.property("selectedId") == "__source__"
    assert app.item("licenceTitle").property("text") == "Source code"
    assert app.item("licenceText").property("text") == \
        app.harness.app.dialogs._catalog.source_offer
    entry = next(r for r in rows if not r["group"] and r["id"] != "__source__")
    QMetaObject.invokeMethod(dialog, "select", Q_ARG("QVariant", entry["id"]))
    assert app.item("licenceTitle").property("text") == entry["label"]
    assert app.item("licenceDetails").property("text").startswith("Licence: " + entry["licence"])
    assert app.item("licenceText").property("text")
    # Down skips the group headings.
    list_view = app.item("licencesList")
    list_view.forceActiveFocus()
    QMetaObject.invokeMethod(dialog, "select", Q_ARG("QVariant", "__source__"))
    app.key(Qt.Key.Key_Down)
    assert not next(r for r in rows if r["id"] == dialog.property("selectedId"))["group"]


def test_a_licence_link_shows_the_hand_and_opens_in_the_browser(app, monkeypatch):
    opened = []
    monkeypatch.setattr(dialogs_module.QDesktopServices, "openUrl",
                        lambda url: opened.append(url.toString()) or True)
    app.open("openLicences")
    dialog = app.opened("licencesDialog")
    entry = next(r for r in dialog.property("rows")
                 if not r["group"] and r["id"] != "__source__"
                 and app.harness.app.dialogs._catalog.get(r["id"]).url)
    QMetaObject.invokeMethod(dialog, "select", Q_ARG("QVariant", entry["id"]))
    link = app.item("licenceLink")
    app.qtbot.waitUntil(lambda: link.isVisible() and link.property("text") != "", timeout=1000)
    url = link.property("text")
    with app.qtbot.waitSignal(app.window.frameSwapped, timeout=1000):   # laid out
        app.window.update()
    centre = link.mapToScene(QPointF(min(link.width(), link.implicitWidth()) / 2,
                                     link.height() / 2)).toPoint()
    QTest.mouseMove(app.window, QPoint(2, 2))
    app.qtbot.wait(10)
    QTest.mouseMove(app.window, centre)
    app.qtbot.waitUntil(lambda: app.window.cursor().shape() == Qt.CursorShape.PointingHandCursor,
                        timeout=1000)
    QTest.mouseClick(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre)
    app.qtbot.waitUntil(lambda: opened == [url], timeout=1000)


def test_licences_unavailable(qapp, qtbot, tmp_path):
    harness = started(qapp, qtbot, tmp_path)
    try:
        dialogs = harness.app.dialogs
        dialogs._paths = AppPaths(resources=tmp_path / "nowhere")
        a = App(harness, qtbot)
        a.open("openLicences")
        error = a.opened("errorDialog")
        assert error.property("title") == "Licences Unavailable"
        assert error.property("message").startswith("Could not read the licence list.")
        assert a.popup("licencesDialog").property("visible") is False
    finally:
        finish(harness, qtbot)


def test_about_shows_the_build_and_opens_the_licences_on_top(app):
    about = app.harness.app.dialogs.about
    assert [line["label"] for line in about["lines"]] == [
        "Version:", "Build Type:", "Build Number:", "Commit:", "Build Date:"]
    assert about["lines"][1]["value"] == "development"           # no build_info: dev-local
    assert about["icon"].endswith("icon-128.png")
    app.open("openAbout")
    app.opened("aboutDialog")
    app.click("aboutLicences")
    app.opened("licencesDialog")
    # Escape closes the Licences only; About is back underneath.
    app.key(Qt.Key.Key_Escape)
    app.closed("licencesDialog")
    assert app.popup("aboutDialog").property("visible") is True
    app.key(Qt.Key.Key_Escape)
    app.closed("aboutDialog")


def test_about_links_to_the_repository_with_a_hand_and_opens_it(app, monkeypatch):
    import re
    about = app.harness.app.dialogs.about
    plain = re.sub(r"<[^>]+>", "", about["copyrightHtml"].replace("<br>", "\n"))
    assert plain == about["copyright"]                        # the same words
    assert about["copyrightHtml"].count("<a href=") == 1
    opened = []
    monkeypatch.setattr(dialogs_module.QDesktopServices, "openUrl",
                        lambda url: opened.append(url.toString()) or True)
    app.open("openAbout")
    app.opened("aboutDialog")
    label = app.item("aboutCopyright")
    app.qtbot.waitUntil(lambda: label.property("hoveredLink") is not None, timeout=1000)
    with app.qtbot.waitSignal(app.window.frameSwapped, timeout=1000):   # laid out
        app.window.update()
    # Find the link by scanning the label's rows for a hovered link.
    spot = None
    QTest.mouseMove(app.window, QPoint(2, 2))
    for y in range(2, int(label.height()), 4):
        for x in range(2, int(label.width()), 6):
            point = label.mapToScene(QPointF(x, y)).toPoint()
            QTest.mouseMove(app.window, point)
            if label.property("hoveredLink"):
                spot = point
                break
        if spot:
            break
    assert spot is not None
    assert label.property("hoveredLink") == dialogs_module.ABOUT_REPO_URL
    app.qtbot.waitUntil(lambda: app.window.cursor().shape() == Qt.CursorShape.PointingHandCursor,
                        timeout=1000)
    QTest.mouseClick(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot)
    app.qtbot.waitUntil(lambda: opened == [dialogs_module.ABOUT_REPO_URL], timeout=1000)
    QTest.mouseMove(app.window, label.mapToScene(QPointF(label.width() / 2, 1)).toPoint())
    app.key(Qt.Key.Key_Escape)
    app.closed("aboutDialog")


def test_about_takes_the_build_info_ci_writes(app):
    info = dialogs_module.DialogsModel(app.harness.store, PATHS, build_info={
        "VERSION": "v0.6.0", "BUILD_TYPE": "release", "BUILD_NUMBER": "42",
        "COMMIT_SHORT": "abc1234", "BUILD_DATE": "2026-11-14"}).about
    assert [line["value"] for line in info["lines"]] == [
        "v0.6.0", "release", "42", "abc1234", "2026-11-14"]
    from chordnotepad_tk import main as entry
    assert [key for key, _ in dialogs_module.BUILD_FIELDS] == list(entry.BUILD_INFO_FIELDS)


# -- Help --------------------------------------------------------------------------------------


def test_help_unavailable(app):
    app.open("openHelp")
    error = app.opened("errorDialog")
    assert error.property("title") == "Help Unavailable"
    assert error.property("message").startswith("Could not find the help documentation.")


def test_f1_opens_the_help(app, tmp_path):
    (tmp_path / "help").mkdir()
    (tmp_path / "help" / "index.html").write_text("<h1>Help</h1>", encoding="utf-8")
    opened = []
    app.harness.app.dialogs._help = HelpOpener(tmp_path / "help", open_url=lambda u: opened.append(u) or True,
                                               sandboxed=False)
    app.key(Qt.Key.Key_F1)
    app.qtbot.waitUntil(lambda: len(opened) == 1, timeout=1000)
    assert opened[0].startswith("file://") and opened[0].endswith("/help/index.html")


def test_help_in_a_sandbox_is_served_on_localhost(tmp_path):
    import urllib.request

    (tmp_path / "index.html").write_text("<h1>Help</h1>", encoding="utf-8")
    opened = []
    opener = HelpOpener(tmp_path, open_url=lambda u: opened.append(u) or True, sandboxed=True)
    try:
        url = opener.open()
        assert url.startswith("http://127.0.0.1:") and opened == [url]
        with urllib.request.urlopen(url, timeout=5) as response:
            assert b"<h1>Help</h1>" in response.read()
        assert opener.open() == url                        # one server per run
    finally:
        opener.stop()


def test_no_browser_says_where_the_help_is(tmp_path):
    from chordnotepad.exceptions import ChordNotepadError

    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    opener = HelpOpener(tmp_path, open_url=lambda u: False, sandboxed=False)
    with pytest.raises(ChordNotepadError, match="Could not open a web browser to show the help"):
        opener.open()


# -- Escape closes every dialog (Q12) ------------------------------------------------------


@pytest.mark.parametrize("opener, name", [
    ("openTranspose", "transposeDialog"), ("openQuickStart", "quickStartDialog"),
    ("openAbout", "aboutDialog"), ("openLicences", "licencesDialog"), ("openHelp", "errorDialog"),
])
def test_escape_closes_every_dialog(app, opener, name):
    app.open(opener)
    app.opened(name)
    app.key(Qt.Key.Key_Escape)
    app.closed(name)
    # And the editor has the keys back.
    app.qtbot.waitUntil(lambda: app.item("editor").hasActiveFocus(), timeout=1000)


def test_the_requests_the_window_answers():
    from chordnotepad_desktop.application import HANDLED_REQUESTS

    # The file pickers are F3's (files.py, FileDialogs.qml).
    assert HANDLED_REQUESTS == {"ConfirmDiscardRequest", "CapoChoiceRequest", "PickDocumentRequest"}


def test_the_settings_window_closes_with_the_main_window(app):
    settings = app.window.findChild(QQuickWindow, "settingsWindow")
    QMetaObject.invokeMethod(app.hub, "openSettings", Q_ARG("QVariant", "general"))
    app.qtbot.waitUntil(lambda: settings.isVisible(), timeout=2000)
    app.window.close()
    app.qtbot.waitUntil(lambda: not app.window.isVisible(), timeout=2000)
    assert not settings.isVisible()
    assert json.loads(app.harness.config_file().read_text(encoding="utf-8"))
