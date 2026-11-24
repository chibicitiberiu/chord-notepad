"""session.errors: toolkit-free routing of unexpected errors to a handler."""

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from chordnotepad.session import errors
from chordnotepad.utils.observable import Observable

REPO = Path(__file__).parent.parent
CORE = REPO / "core"
DESKTOP = REPO / "desktop"


@pytest.fixture(autouse=True)
def restore_handler():
    saved = errors.get_handler()
    yield
    errors.set_handler(saved)


def _exc_info(message="boom"):
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        return type(exc), exc, exc.__traceback__


def test_without_a_handler_the_error_is_logged(caplog):
    errors.set_handler(None)
    with caplog.at_level(logging.ERROR, logger="chordnotepad.session.errors"):
        errors.report_from_any_thread(_exc_info(), "background job")
    assert "Unhandled error in background job" in caplog.text
    assert "Traceback" in caplog.text


def test_handler_receives_the_error_and_context():
    seen = []
    errors.set_handler(lambda info, context: seen.append((info[1], context)))
    info = _exc_info()
    errors.report_from_any_thread(info, "observer of 'bpm'")
    assert seen == [(info[1], "observer of 'bpm'")]


def test_set_handler_returns_the_previous_one():
    def first(info, context):
        pass

    errors.set_handler(first)
    assert errors.set_handler(None) is first
    assert errors.get_handler() is None


def test_a_failing_handler_does_not_lose_the_error(caplog):
    def broken(info, context):
        raise ValueError("handler bug")

    errors.set_handler(broken)
    with caplog.at_level(logging.ERROR, logger="chordnotepad.session.errors"):
        errors.report_from_any_thread(_exc_info("original"), "observer")
    assert "original" in caplog.text
    assert "Error handler failed" in caplog.text


def test_observable_reports_observer_errors_through_the_router():
    seen = []
    errors.set_handler(lambda info, context: seen.append((type(info[1]), context)))
    model = Observable()
    model.observe("bpm", lambda value: {}["missing"])
    model.notify("bpm", 120)
    assert seen == [(KeyError, "observer of 'bpm'")]


def test_an_observer_that_raises_doesnt_stop_the_others():
    reported, values = [], []
    errors.set_handler(lambda info, context: reported.append(context))
    model = Observable()
    model.observe("bpm", lambda value: {}["missing"])
    model.observe("bpm", values.append)
    model.notify("bpm", 120)
    assert reported == ["observer of 'bpm'"]
    assert values == [120]


#: The desktop toolkits the core must never import (Android has none of them).
_DESKTOP_ONLY = ("tkinter", "_tkinter", "PySide6", "shiboken6")

_IMPORT_PROBE = r"""
import os, sys
sys.path[:0] = sys.argv[1].split(os.pathsep)
if sys.argv[2] == "block-desktop":
    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in sys.argv[3].split(","):
                raise ModuleNotFoundError(name)
            return None
    sys.meta_path.insert(0, _Block())
from chordnotepad.session import errors
import chordnotepad.session.session, chordnotepad.utils.observable  # the core that reports errors
if sys.argv[2] == "with-presenter":
    from chordnotepad_desktop import error_presenter
print(errors.get_handler() is None)
"""


def _handler_is_unset_after_import(mode):
    out = subprocess.run(
        # The core alone, or with the Qt window's presenter.
        [sys.executable, "-I", "-c", _IMPORT_PROBE,
         os.pathsep.join(map(str, [CORE] + ([DESKTOP] if mode == "with-presenter" else []))), mode,
         ",".join(_DESKTOP_ONLY)],
        capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    # The probe's answer is its last line, whatever a library prints first.
    return out.stdout.splitlines()[-1:] == ["True"]


def test_the_core_imports_without_a_desktop_toolkit_and_only_logs():
    # Android and the tests: no presenter, so session.errors logs.
    assert _handler_is_unset_after_import("block-desktop")


def test_importing_the_qt_presenter_installs_nothing():
    # The application installs it explicitly (ErrorPresenter.install, from
    # QtApplication's start-up).
    pytest.importorskip("PySide6.QtCore")
    assert _handler_is_unset_after_import("with-presenter")
