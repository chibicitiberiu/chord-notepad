"""TkHost: the desktop host on top of Tk's after() loop.

A fake root stands in for the Tk window, so no display is needed.
"""

import threading
import tkinter as tk
from unittest import mock

import pytest

from constants import EVENT_QUEUE_POLL_MS
from ui.tk_host import TkHost


class FakeRoot:
    """Records after()/after_cancel() calls and fires them on demand."""

    def __init__(self):
        self.scheduled = {}
        self._next = 0

    def after(self, ms, fn):
        self._next += 1
        after_id = f"after#{self._next}"
        self.scheduled[after_id] = (ms, fn)
        return after_id

    def after_cancel(self, after_id):
        self.scheduled.pop(after_id, None)

    def fire(self, after_id):
        _, fn = self.scheduled.pop(after_id)
        fn()

    def fire_all(self):
        for after_id in list(self.scheduled):
            if after_id in self.scheduled:
                self.fire(after_id)


def test_posted_callbacks_run_in_order_on_drain():
    host = TkHost(FakeRoot())
    seen = []
    host.post(lambda: seen.append(1))
    host.post(lambda: seen.append(2))
    assert seen == []
    host._drain()
    assert seen == [1, 2]


def test_posts_before_the_window_exists_wait_for_start():
    host = TkHost()
    seen = []
    host.post(lambda: seen.append("early"))
    root = FakeRoot()
    host.attach(root)
    host.start()
    assert seen == ["early"]


def test_start_without_a_root_raises():
    with pytest.raises(RuntimeError):
        TkHost().start()


def test_drain_reschedules_itself_while_running():
    root = FakeRoot()
    host = TkHost(root)
    host.start()
    assert [ms for ms, _ in root.scheduled.values()] == [EVENT_QUEUE_POLL_MS]

    seen = []
    host.post(lambda: seen.append("later"))
    root.fire_all()
    assert seen == ["later"]
    assert len(root.scheduled) == 1  # re-armed


def test_stop_cancels_the_drain_loop_and_is_idempotent():
    root = FakeRoot()
    host = TkHost(root)
    host.start()
    host.stop()
    assert root.scheduled == {}
    host.stop()
    host._drain()
    assert root.scheduled == {}  # not re-armed after stop


def test_stop_survives_a_destroyed_window():
    root = mock.Mock()
    root.after.return_value = "after#1"
    root.after_cancel.side_effect = tk.TclError("application has been destroyed")
    host = TkHost(root)
    host.start()
    host.stop()


def test_failing_callback_is_reported_and_the_rest_still_run():
    root = FakeRoot()
    host = TkHost(root)
    seen = []
    host.post(lambda: 1 / 0)
    host.post(lambda: seen.append("after the error"))
    with mock.patch("ui.tk_host.error_reporting.report_unexpected_error") as report:
        host._drain()
    report.assert_called_once()
    assert report.call_args.args[0] is root
    assert isinstance(report.call_args.args[1][1], ZeroDivisionError)
    assert report.call_args.args[2] == "queued UI callback"
    assert seen == ["after the error"]


def test_call_later_uses_after_in_milliseconds():
    root = FakeRoot()
    host = TkHost(root)
    seen = []
    host.call_later(0.5, lambda: seen.append("fired"))
    (after_id, (ms, _)), = root.scheduled.items()
    assert ms == 500
    root.fire(after_id)
    assert seen == ["fired"]


def test_call_later_handle_cancels_with_after_cancel():
    root = FakeRoot()
    host = TkHost(root)
    seen = []
    handle = host.call_later(0.2, lambda: seen.append("fired"))
    handle.cancel()
    assert root.scheduled == {}
    handle.cancel()  # second cancel is a no-op
    assert seen == []


def test_cancel_after_firing_does_not_touch_tk():
    root = FakeRoot()
    host = TkHost(root)
    handle = host.call_later(0, lambda: None)
    root.fire_all()
    with mock.patch.object(root, "after_cancel") as after_cancel:
        handle.cancel()
    after_cancel.assert_not_called()


def test_negative_delay_is_clamped():
    root = FakeRoot()
    TkHost(root).call_later(-1, lambda: None)
    (ms, _), = root.scheduled.values()
    assert ms == 0


def test_post_is_safe_from_another_thread():
    root = FakeRoot()
    host = TkHost(root)
    seen = []
    threads = [threading.Thread(target=lambda i=i: host.post(lambda: seen.append(i)))
               for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    host._drain()
    assert sorted(seen) == list(range(20))


def test_session_thread_is_the_creating_thread():
    host = TkHost(FakeRoot())
    assert host.is_session_thread()
    result = []
    t = threading.Thread(target=lambda: result.append(host.is_session_thread()))
    t.start()
    t.join()
    assert result == [False]


def test_application_queue_ui_callback_posts_to_the_host():
    from application import Application

    app = Application()
    seen = []
    app.queue_ui_callback(lambda: seen.append("ok"))
    root = FakeRoot()
    app.set_main_window(root)
    app.host.start()
    assert seen == ["ok"]
    app.host.stop()
