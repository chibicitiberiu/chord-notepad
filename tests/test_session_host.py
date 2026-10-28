"""ManualHost: the deterministic host the session tests run on."""

import threading

import pytest

from session.host import HostDispatch
from session.testing import ManualHost


def test_posted_callbacks_wait_for_run_pending_and_run_in_order():
    host = ManualHost()
    seen = []
    host.post(lambda: seen.append(1))
    host.post(lambda: seen.append(2))
    assert seen == []
    assert host.pending_posts == 2

    assert host.run_pending() == 2
    assert seen == [1, 2]
    assert host.pending_posts == 0


def test_callbacks_posted_while_running_also_run():
    host = ManualHost()
    seen = []
    host.post(lambda: host.post(lambda: seen.append("nested")))
    assert host.run_pending() == 2
    assert seen == ["nested"]


def test_post_from_another_thread_lands_on_the_session_thread():
    host = ManualHost()
    ran_on = []
    worker = threading.Thread(
        target=lambda: host.post(lambda: ran_on.append(host.is_session_thread())))
    worker.start()
    worker.join()
    host.run_pending()
    assert ran_on == [True]


def test_timer_fires_only_when_the_clock_reaches_it():
    host = ManualHost()
    seen = []
    host.call_later(0.5, lambda: seen.append(host.monotonic()))

    assert host.advance(0.4) == 0
    assert seen == []
    assert host.advance(0.1) == 1
    assert seen == [pytest.approx(0.5)]
    assert host.monotonic() == pytest.approx(0.5)


def test_timers_fire_in_deadline_order_at_their_deadline():
    host = ManualHost(start=10.0)
    seen = []
    host.call_later(0.3, lambda: seen.append(("b", host.monotonic())))
    host.call_later(0.1, lambda: seen.append(("a", host.monotonic())))
    host.call_later(0.3, lambda: seen.append(("c", host.monotonic())))

    assert host.advance(1.0) == 3
    assert [name for name, _ in seen] == ["a", "b", "c"]
    assert seen[0][1] == pytest.approx(10.1)
    assert seen[1][1] == pytest.approx(10.3)
    assert host.monotonic() == pytest.approx(11.0)


def test_cancelled_timer_never_fires():
    host = ManualHost()
    seen = []
    handle = host.call_later(0.5, lambda: seen.append("x"))
    assert host.pending_timers == 1
    handle.cancel()
    assert host.pending_timers == 0
    assert host.advance(1.0) == 0
    assert seen == []


def test_cancel_after_firing_is_harmless():
    host = ManualHost()
    handle = host.call_later(0.1, lambda: None)
    host.advance(0.1)
    handle.cancel()


def test_timer_scheduled_by_a_timer_fires_within_the_same_advance():
    host = ManualHost()
    seen = []
    host.call_later(0.2, lambda: host.call_later(0.2, lambda: seen.append(host.monotonic())))
    host.advance(0.5)
    assert seen == [pytest.approx(0.4)]


def test_work_posted_by_a_timer_runs_before_the_next_timer():
    host = ManualHost()
    seen = []
    host.call_later(0.1, lambda: host.post(lambda: seen.append("posted")))
    host.call_later(0.2, lambda: seen.append("second timer"))
    host.advance(0.2)
    assert seen == ["posted", "second timer"]


def test_call_later_off_the_session_thread_raises():
    host = ManualHost()
    errors = []

    def worker():
        try:
            host.call_later(0.1, lambda: None)
        except RuntimeError as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert len(errors) == 1


def test_callback_errors_propagate_to_the_test():
    host = ManualHost()
    host.post(lambda: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        host.run_pending()


def test_host_dispatch_gives_queue_ui_callback_shape():
    host = ManualHost()
    seen = []
    HostDispatch(host).queue_ui_callback(lambda: seen.append("ok"))
    assert seen == []
    host.run_pending()
    assert seen == ["ok"]
