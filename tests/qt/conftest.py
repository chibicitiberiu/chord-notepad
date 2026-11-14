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
QML warnings fail the test (``qt_log_level_fail``); :func:`main_window` also
checks the engine's own ``warnings`` signal.

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


@pytest.fixture
def main_window(qapp, qtbot):
    """Main.qml loaded the way ``main.run`` loads it; closed and freed afterwards.

    The engine's warnings must stay empty (checked at teardown).
    """
    from chordnotepad_desktop.main import create_engine, load_main_window

    engine = create_engine(PATHS)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    main = load_main_window(engine, qapp)
    assert main is not None, warnings
    yield main
    qapp.removeEventFilter(main.alt)
    main.window.close()
    engine.deleteLater()
    qtbot.wait(1)
    assert warnings == []
