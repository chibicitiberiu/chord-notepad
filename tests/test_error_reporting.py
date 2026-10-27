"""Unexpected errors must be logged and shown, never lost on stderr."""

import logging
import threading
from unittest import mock

import pytest

from utils import error_reporting
from utils.observable import Observable


@pytest.fixture(autouse=True)
def reset_reporter(monkeypatch):
    monkeypatch.setattr(error_reporting, "_log_path", None)
    monkeypatch.setattr(error_reporting, "_dialog_open", False)
    monkeypatch.setattr(error_reporting, "_last_shown", ("", 0.0))
    monkeypatch.setattr(error_reporting, "_run_on_ui_thread", None)
    monkeypatch.setattr(error_reporting, "_get_parent", lambda: None)
    saved_hook = threading.excepthook
    yield
    threading.excepthook = saved_hook


def _exc_info(message="No module named 'packaging'"):
    try:
        raise ModuleNotFoundError(message)
    except ModuleNotFoundError as exc:
        return type(exc), exc, exc.__traceback__


@pytest.fixture
def showerror():
    with mock.patch("utils.error_reporting.messagebox.showerror") as patched:
        yield patched


def test_error_is_logged_and_shown(showerror, caplog):
    parent = object()
    with caplog.at_level(logging.ERROR, logger="utils.error_reporting"):
        error_reporting.report_unexpected_error(parent, _exc_info(), "UI callback")
    assert "Unhandled error in UI callback" in caplog.text
    assert "Traceback" in caplog.text
    showerror.assert_called_once()
    assert "packaging" in showerror.call_args.args[1]
    assert showerror.call_args.kwargs["parent"] is parent


def test_dialog_points_at_the_log_file(showerror):
    error_reporting.set_log_path("/home/me/.local/share/chord-notepad/logs/chord-notepad.log")
    error_reporting.report_unexpected_error(None, _exc_info(), "UI callback")
    assert "chord-notepad.log" in showerror.call_args.args[1]


def test_same_error_repeated_quickly_shows_one_dialog(showerror, caplog):
    # e.g. a failing after() loop: every occurrence is logged, one dialog shown
    with caplog.at_level(logging.ERROR, logger="utils.error_reporting"):
        for _ in range(5):
            error_reporting.report_unexpected_error(None, _exc_info(), "UI callback")
    assert showerror.call_count == 1
    assert caplog.text.count("Unhandled error") == 5


def test_different_errors_each_get_a_dialog(showerror):
    error_reporting.report_unexpected_error(None, _exc_info("first"), "UI callback")
    error_reporting.report_unexpected_error(None, _exc_info("second"), "UI callback")
    assert showerror.call_count == 2


def test_no_second_dialog_while_one_is_open(showerror, monkeypatch):
    monkeypatch.setattr(error_reporting, "_dialog_open", True)
    error_reporting.report_unexpected_error(None, _exc_info(), "UI callback")
    showerror.assert_not_called()


def test_missing_window_does_not_raise(showerror):
    import tkinter as tk
    showerror.side_effect = tk.TclError("application has been destroyed")
    error_reporting.report_unexpected_error(None, _exc_info(), "UI callback")
    assert error_reporting._dialog_open is False


def test_thread_errors_are_reported_on_the_ui_thread(showerror):
    queued = []
    parent = object()
    error_reporting.install_thread_hook(queued.append, lambda: parent)

    worker = threading.Thread(target=lambda: 1 / 0, name="RenderThread")
    worker.start()
    worker.join()

    assert len(queued) == 1
    showerror.assert_not_called()  # nothing shown from the worker thread itself
    queued[0]()
    showerror.assert_called_once()
    assert "division by zero" in showerror.call_args.args[1]
    assert showerror.call_args.kwargs["parent"] is parent


def test_tk_callback_errors_go_through_the_reporter():
    from ui.main_window import MainWindow
    window = mock.Mock()
    info = _exc_info()
    with mock.patch("ui.main_window.error_reporting.report_unexpected_error") as report:
        MainWindow.report_callback_exception(window, *info)
    report.assert_called_once_with(window, info, "UI callback")


def test_queued_callback_errors_go_through_the_reporter():
    import queue
    from application import Application

    app = mock.Mock()
    app._event_queue = queue.Queue()
    app._running = False

    def boom():
        raise RuntimeError("render failed")

    app._event_queue.put(boom)
    with mock.patch("application.error_reporting.report_unexpected_error") as report:
        Application._process_event_queue(app)
    report.assert_called_once()
    assert report.call_args.args[0] is app._main_window
    assert isinstance(report.call_args.args[1][1], RuntimeError)


def test_fatal_error_without_display_falls_back_to_stderr(capsys):
    import tkinter as tk
    with mock.patch("utils.error_reporting.tk.Tk", side_effect=tk.TclError("no display")):
        error_reporting.show_fatal_error(RuntimeError("soundfont missing"))
    assert "couldn't start" in capsys.readouterr().err


def _failing_observer(_value):
    raise KeyError("missing_tag")


def test_observer_error_is_shown_and_other_observers_still_run(showerror):
    error_reporting.install_thread_hook(lambda fn: fn(), lambda: None)
    model = Observable()
    seen = []
    model.observe("bpm", _failing_observer)
    model.observe("bpm", seen.append)
    model.notify("bpm", 120)
    assert seen == [120]
    showerror.assert_called_once()
    assert "missing_tag" in showerror.call_args.args[1]


def test_observer_error_off_the_ui_thread_is_queued(showerror):
    queued = []
    error_reporting.install_thread_hook(queued.append, lambda: None)
    model = Observable()
    model.observe("bpm", _failing_observer)
    worker = threading.Thread(target=lambda: model.notify("bpm", 120))
    worker.start()
    worker.join()
    showerror.assert_not_called()
    assert len(queued) == 1
    queued[0]()
    showerror.assert_called_once()


def test_observer_error_before_setup_is_logged(showerror, caplog):
    model = Observable()
    model.observe("bpm", _failing_observer)
    with caplog.at_level(logging.ERROR, logger="utils.error_reporting"):
        model.notify("bpm", 120)
    showerror.assert_not_called()
    assert "observer of 'bpm'" in caplog.text
