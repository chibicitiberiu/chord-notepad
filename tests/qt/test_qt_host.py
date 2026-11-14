"""QtHost: the session's host on the Qt event loop (plan step C3)."""

import threading

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from chordnotepad.session import errors as session_errors  # noqa: E402
from chordnotepad_desktop.qt_host import QtHost  # noqa: E402


@pytest.fixture
def host(qapp):
    h = QtHost()
    h.start()
    yield h
    h.stop()
    h.deleteLater()


def test_posted_callbacks_run_later_in_order_on_the_gui_thread(host, qtbot):
    ran = []
    host.post(lambda: ran.append(("a", threading.current_thread())))
    host.post(lambda: ran.append(("b", threading.current_thread())))
    assert ran == []                       # never inline
    qtbot.waitUntil(lambda: len(ran) == 2, timeout=1000)
    assert [name for name, _ in ran] == ["a", "b"]
    assert all(thread is threading.main_thread() for _, thread in ran)


def test_a_post_from_another_thread_runs_on_the_gui_thread(host, qtbot):
    ran = []

    def worker():
        assert not host.is_session_thread()
        host.post(lambda: ran.append((threading.current_thread(), host.is_session_thread())))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: bool(ran), timeout=1000)
    assert ran == [(threading.main_thread(), True)]


def test_what_is_posted_before_start_waits_for_it(qapp, qtbot):
    host = QtHost()
    ran = []
    host.post(lambda: ran.append(1))
    qtbot.wait(20)
    assert ran == []
    host.start()
    host.post(lambda: ran.append(2))
    qtbot.waitUntil(lambda: ran == [1, 2], timeout=1000)
    host.stop()


def test_nothing_runs_after_stop(qapp, qtbot):
    host = QtHost()
    host.start()
    ran = []
    host.post(lambda: ran.append("queued before stop"))
    host.stop()
    host.post(lambda: ran.append("posted after stop"))
    qtbot.wait(30)
    assert ran == []
    with pytest.raises(RuntimeError):
        host.start()


def test_call_later_fires_once_and_can_be_cancelled(host, qtbot):
    ran = []
    host.call_later(0.01, lambda: ran.append("fired"))
    cancelled = host.call_later(0.01, lambda: ran.append("cancelled"))
    cancelled.cancel()
    cancelled.cancel()                     # twice is fine
    qtbot.waitUntil(lambda: ran == ["fired"], timeout=1000)
    qtbot.wait(30)
    assert ran == ["fired"]


def test_cancelling_after_it_fired_is_a_no_op(host, qtbot):
    ran = []
    handle = host.call_later(0, lambda: ran.append(1))
    qtbot.waitUntil(lambda: ran == [1], timeout=1000)
    handle.cancel()


def test_the_clock_is_monotonic(host):
    first = host.monotonic()
    assert host.monotonic() >= first
    assert host.is_session_thread()


def test_a_failing_callback_is_reported_and_the_next_one_runs(host, qtbot):
    reported = []
    previous = session_errors.set_handler(lambda exc_info, context: reported.append(
        (context, str(exc_info[1]))))
    try:
        ran = []
        host.post(lambda: 1 / 0)
        host.post(lambda: ran.append("next"))
        host.call_later(0, lambda: [][1])
        qtbot.waitUntil(lambda: bool(ran) and len(reported) == 2, timeout=1000)
    finally:
        session_errors.set_handler(previous)
    assert ("queued UI callback", "division by zero") in reported
    assert ("timer callback", "list index out of range") in reported
