"""Tests of the Qt Quick front end (chordnotepad_desktop), run offscreen.

They are skipped, not failed, when PySide6 or pytest-qt can't be imported
(``tests.conftest.QT_PROBLEM``), the way the Tk tests skip without a display.
Each module starts with::

    from tests.conftest import QT_PROBLEM
    if QT_PROBLEM:
        pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

before it imports anything from PySide6 or chordnotepad_desktop.

Every test here runs offscreen with the software renderer, whatever the
environment says: a Qt test must never open a window on a real display.
QML warnings fail the test (``qt_log_level_fail``); :func:`qt_app` and
:func:`sample_window` also check the engine's own ``warnings`` signal.
:func:`qt_app` runs the whole front end in the test process
(:class:`QtAppHarness`), with a FakePlayer and its config under tmp_path.

The application is set up once, as ``main.run`` does it (the text renderer,
the unhinted font, Inter, the CNStyle style), before any QML is loaded: the
style can't change once a Controls type exists.

Two Qt Quick pitfalls for tests: ``QTest.keyClicks`` takes a QWidget only
(pitfall 22), so keys go to the QQuickWindow with ``QGuiApplication.sendEvent``
or ``QTest.keyClick(window, ...)``; and Repeater delegates aren't in the
QObject tree (pitfall 25), so ``findChild`` doesn't find them.
"""

import os
from pathlib import Path

import pytest

from chordnotepad.app_paths import AppPaths

from tests.conftest import QT_PROBLEM

# Before the QGuiApplication exists (pytest-qt's qapp creates it on first use).
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
# No compiled-QML cache written to ~/.cache by a test run.
os.environ["QML_DISABLE_DISK_CACHE"] = "1"


def pytest_collection_modifyitems(config, items):
    if QT_PROBLEM is not None:
        return
    here = os.path.dirname(os.path.abspath(__file__)) + os.sep
    for item in items:
        if str(item.fspath).startswith(here):
            item.add_marker(pytest.mark.qt_log_level_fail("WARNING"))


@pytest.fixture(scope="session")
def qapp_cls():
    """The app runs a QGuiApplication (no widgets), so the tests do too."""
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication


#: The checkout's resources (icons, fonts), as the desktop resolver finds them.
REPO = Path(__file__).resolve().parents[2]
PATHS = AppPaths(resources=REPO / "resources")


@pytest.fixture(scope="session", autouse=True)
def bundled_families(qapp):
    """``main.prepare_application`` once, before the first QML is loaded.

    Autouse for the tests in this folder only; the font families it loaded.
    """
    from chordnotepad_desktop.main import prepare_application

    return prepare_application(qapp, PATHS)


#: The test-only window with C2's sample controls (the scaling recipe's tests).
SAMPLE_QML = Path(__file__).resolve().parent / "qml" / "ThemeSample.qml"


class QtAppHarness:
    """A :class:`~chordnotepad_desktop.application.QtApplication` started in
    the test process: a FakePlayer, the config and logs under tmp_path, the
    test's logging left alone. Unexpected errors the presenter is handed are
    collected in ``unexpected`` (the fixture fails on them unless the test
    clears the list)."""

    def __init__(self, qapp, tmp_path, today=None):
        import datetime

        from chordnotepad.services.appdata_service import AppDataService
        from chordnotepad.session.testing import FakePlayer
        from chordnotepad_desktop.application import QtApplication

        self.qapp = qapp
        self.root = tmp_path / "appdata"
        self.player = FakePlayer()
        kwargs = {"today": today} if today else {"today": lambda: datetime.date(2026, 11, 14)}
        self.app = QtApplication(PATHS, appdata=AppDataService(root=self.root),
                                 player=self.player, configure_logging=False, **kwargs)
        self.unexpected = []

    def start(self):
        self.main = self.app.start(self.qapp)
        presenter = self.app.presenter
        original = presenter.report_unexpected
        original_event = presenter.report_event

        def record(exc_info, context):
            self.unexpected.append((context, exc_info[1]))
            original(exc_info, context)

        def record_event(message, context):
            self.unexpected.append((context, message))
            original_event(message, context)

        presenter.report_unexpected = record
        presenter.report_event = record_event
        return self

    @property
    def window(self):
        return self.main.window

    @property
    def store(self):
        return self.app.store

    def config_file(self):
        return self.root / "config" / "chord-notepad" / "settings.json"

    def shutdown(self):
        self.app.shutdown()


def write_config(tmp_path, **values):
    """A settings.json in the harness's config folder, before it starts."""
    import json

    folder = tmp_path / "appdata" / "config" / "chord-notepad"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "settings.json").write_text(json.dumps({"version": 4, **values}), encoding="utf-8")


@pytest.fixture
def qt_app(qapp, qtbot, tmp_path):
    """The whole Qt front end, started (window shown, session running);
    shut down afterwards. Fails on QML warnings and on unexpected errors."""
    harness = QtAppHarness(qapp, tmp_path).start()
    yield harness
    warnings = list(harness.app.warnings)
    unexpected = list(harness.unexpected)
    harness.shutdown()
    qtbot.wait(1)
    assert warnings == []
    assert unexpected == []


@pytest.fixture
def main_window(qt_app):
    """The main window of a started :func:`qt_app` (a ``main.MainWindow``)."""
    return qt_app.main


@pytest.fixture
def sample_window(qapp, qtbot):
    """ThemeSample.qml (C2's sample controls) loaded with the main window's
    plumbing and shown; closed and freed afterwards. The engine's warnings
    must stay empty."""
    from chordnotepad_desktop.main import create_engine, load_window

    engine = create_engine(PATHS)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    main = load_window(engine, qapp, SAMPLE_QML)
    assert main is not None, warnings
    main.window.show()
    yield main
    qapp.removeEventFilter(main.alt)
    main.window.close()
    engine.deleteLater()
    qtbot.wait(1)
    assert warnings == []
