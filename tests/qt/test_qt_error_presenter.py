"""The Qt error presenter (plan step C3; parity checklist §7, "Errors").

The texts are compared with the Tk presenter's (``chordnotepad_tk
.error_reporting``) where both exist; the window side (the ErrorDialog in
Main.qml) is checked in ``test_qt_window_shell.py``.
"""

import sys
import threading

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QObject, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from chordnotepad.session import errors as session_errors  # noqa: E402
from chordnotepad_desktop import error_presenter  # noqa: E402
from chordnotepad_desktop.error_presenter import (  # noqa: E402
    ERROR_TITLE, REPEAT_QUIET_SECONDS, ErrorPresenter, fatal_message, format_message,
    show_fatal_error,
)

LOG = "/tmp/logs/chord-notepad.log"


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def exc_info_of(exc):
    try:
        raise exc
    except type(exc):
        return sys.exc_info()


@pytest.fixture
def presenter(qapp):
    posted = []
    clock = Clock()
    p = ErrorPresenter(posted.append, clock=clock)
    p.log_path = LOG
    p.clock = clock
    p.posted = posted
    p.shown_log = []
    p.shown.connect(lambda title, message: p.shown_log.append((title, message)))
    p.attach()
    yield p
    p.uninstall()


def test_the_texts_are_the_tk_presenters():
    tk_reporting = pytest.importorskip("chordnotepad_tk.error_reporting")
    tk_reporting.set_log_path(LOG)
    try:
        assert format_message("boom", LOG) == tk_reporting.format_message(RuntimeError("boom"))
        assert format_message("ValueError", LOG) == tk_reporting.format_message(ValueError())
    finally:
        tk_reporting.set_log_path(None)
    assert format_message("boom", None) == "Something went wrong:\nboom"
    assert fatal_message(OSError("disk"), LOG) == (
        "Chord Notepad couldn't start.\n\nSomething went wrong:\ndisk"
        f"\n\nDetails were written to the log file:\n{LOG}")
    assert ERROR_TITLE == "Error"


def test_an_unexpected_error_is_logged_and_shown(presenter, caplog):
    presenter.report_unexpected(exc_info_of(RuntimeError("broken")), "UI callback")
    assert presenter.shown_log == [("Error", format_message("broken", LOG))]
    assert "Unhandled error in UI callback" in caplog.text and "RuntimeError: broken" in caplog.text


def test_one_dialog_at_a_time_and_no_repeat_within_five_seconds(presenter):
    boom = exc_info_of(RuntimeError("boom"))
    presenter.report_unexpected(boom, "a")
    presenter.report_unexpected(exc_info_of(RuntimeError("other")), "b")   # one open: log only
    assert len(presenter.shown_log) == 1
    presenter.dismissed()
    presenter.clock.now += REPEAT_QUIET_SECONDS - 0.1
    presenter.report_unexpected(boom, "a")                                  # same, too soon
    assert len(presenter.shown_log) == 1
    presenter.report_unexpected(exc_info_of(RuntimeError("different")), "c")
    assert len(presenter.shown_log) == 2
    presenter.dismissed()
    presenter.clock.now += REPEAT_QUIET_SECONDS + 0.1
    presenter.report_unexpected(boom, "a")
    assert len(presenter.shown_log) == 3


def test_the_quiet_time_counts_from_when_the_dialog_closed(presenter):
    boom = exc_info_of(RuntimeError("boom"))
    presenter.report_unexpected(boom, "a")
    presenter.clock.now += 60                  # it stayed open a minute
    presenter.dismissed()
    presenter.clock.now += 1
    presenter.report_unexpected(boom, "a")
    assert len(presenter.shown_log) == 1


def test_the_sessions_messages_wait_their_turn(presenter):
    presenter.show_message("Audio Error", "No sound")
    presenter.show_message("Could not open", "Missing")
    assert presenter.shown_log == [("Audio Error", "No sound")]
    assert presenter.showing == ("Audio Error", "No sound")
    presenter.dismissed()
    assert presenter.shown_log[-1] == ("Could not open", "Missing")
    presenter.dismissed()
    assert presenter.showing is None


def test_an_unexpected_error_event_is_shown_like_an_exception(presenter):
    presenter.report_event("unknown command 'x'", "bridge")
    assert presenter.shown_log == [("Error", format_message("unknown command 'x'", LOG))]


def test_what_comes_before_a_window_waits_for_it(qapp):
    p = ErrorPresenter(lambda cb: None)
    shown = []
    p.shown.connect(lambda title, message: shown.append(title))
    p.show_message("Early", "before the window")
    assert shown == []
    p.attach()
    assert shown == ["Early"]
    p.detach()
    p.dismissed()
    p.show_message("Late", "after it")
    assert shown == ["Early"]


def test_install_takes_over_every_hook_and_uninstall_puts_them_back(presenter):
    before = (sys.excepthook, threading.excepthook, session_errors.get_handler())
    presenter.install()
    presenter.install()                       # twice is fine
    assert sys.excepthook != before[0] and threading.excepthook != before[1]
    assert session_errors.get_handler() == presenter.report_from_any_thread
    presenter.uninstall()
    assert (sys.excepthook, threading.excepthook, session_errors.get_handler()) == before


def test_errors_from_the_core_go_to_the_presenter(presenter):
    presenter.install()
    session_errors.report_from_any_thread(exc_info_of(KeyError("k")), "observer of 'bpm'")
    assert presenter.shown_log == [("Error", format_message("'k'", LOG))]


def test_a_thread_error_is_shown_on_the_gui_thread(presenter):
    presenter.install()
    thread = threading.Thread(target=lambda: 1 / 0, name="worker")
    thread.start()
    thread.join()
    assert presenter.shown_log == []              # posted, not shown off the GUI thread
    assert len(presenter.posted) == 1
    presenter.posted[0]()
    assert presenter.shown_log == [("Error", format_message("division by zero", LOG))]


class Emitter(QObject):
    fire = Signal()


def test_an_exception_in_a_qt_slot_is_shown(presenter):
    presenter.install()
    emitter = Emitter()

    def boom():
        raise ValueError("slot failed")

    emitter.fire.connect(boom)
    emitter.fire.emit()
    assert presenter.shown_log == [("Error", format_message("slot failed", LOG))]


def test_keyboard_interrupt_is_left_to_python(presenter):
    presenter.install()
    passed = []
    presenter._previous_sys_hook = lambda *args: passed.append(args[0])
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert passed == [KeyboardInterrupt] and presenter.shown_log == []


def test_a_fatal_error_without_a_window_goes_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(error_presenter, "_show_fatal_window", lambda message: False)
    show_fatal_error(RuntimeError("no display"), LOG)
    assert capsys.readouterr().err.startswith("Chord Notepad couldn't start.\n\nSomething went wrong:\nno display")


def test_the_fatal_error_window_shows_the_message_and_closes(qapp, qtbot):
    from PySide6.QtQuick import QQuickItem

    seen = []

    def close_it():
        try:
            for window in QGuiApplication.topLevelWindows():
                text = window.findChild(QQuickItem, "fatalMessage")
                if text is not None and window.isVisible():
                    seen.append((window.title(), text.property("text")))
        finally:
            # Always, or show_fatal_error would wait for ever.
            for window in QGuiApplication.topLevelWindows():
                if window.findChild(QQuickItem, "fatalMessage") is not None:
                    window.close()

    QTimer.singleShot(200, close_it)
    show_fatal_error(RuntimeError("the config is broken"), LOG)
    assert seen == [("Chord Notepad", fatal_message(RuntimeError("the config is broken"), LOG))]
