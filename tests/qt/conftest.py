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
QML warnings fail the test (``qt_log_level_fail``); the engine's own
``warnings`` signal is checked as well (:func:`load_qml`).
"""

import os

import pytest

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
