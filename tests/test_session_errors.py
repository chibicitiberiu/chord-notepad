"""session.errors: Tk-free routing of unexpected errors to a handler."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from session import errors
from utils.observable import Observable

SRC = Path(__file__).parent.parent / "src"


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
    with caplog.at_level(logging.ERROR, logger="session.errors"):
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
    with caplog.at_level(logging.ERROR, logger="session.errors"):
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


_IMPORT_PROBE = r"""
import sys
sys.path.insert(0, sys.argv[1])
if sys.argv[2] == "block-tk":
    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("tkinter", "_tkinter"):
                raise ModuleNotFoundError(name)
            return None
    sys.meta_path.insert(0, _Block())
from session import errors
from utils import error_reporting
print(errors.get_handler() is error_reporting._handle_session_error, errors.get_handler() is None)
"""


def _import_presenter(mode):
    out = subprocess.run(
        [sys.executable, "-c", _IMPORT_PROBE, str(SRC), mode],
        capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.split()


def test_importing_the_tk_presenter_installs_it():
    assert _import_presenter("with-tk") == ["True", "False"]


def test_without_tkinter_the_presenter_imports_but_installs_nothing():
    assert _import_presenter("block-tk") == ["False", "True"]
