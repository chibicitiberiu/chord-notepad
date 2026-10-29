"""ThreadedHost: the session thread of headless hosts (Android).

Real threads and a real clock, with short delays; every wait has a timeout so
a broken host fails instead of hanging.
"""

import threading
import time

import pytest

from session import errors
from session.threaded_host import ThreadedHost


@pytest.fixture
def host():
    h = ThreadedHost(name="test-session")
    h.start()
    yield h
    h.shutdown(timeout=5)


def run_on(host, fn, timeout=5):
    return host.call(fn, timeout=timeout)


def drain(host):
    """Wait until everything posted before now has run."""
    host.call(lambda: None, timeout=5)


@pytest.fixture
def reported():
    seen = []
    previous = errors.set_handler(lambda exc_info, context: seen.append((exc_info[1], context)))
    yield seen
    errors.set_handler(previous)


def test_posts_run_on_the_session_thread_in_order(host):
    seen = []
    for i in range(200):
        host.post(lambda i=i: seen.append((i, host.is_session_thread())))
    drain(host)
    assert seen == [(i, True) for i in range(200)]
    assert not host.is_session_thread()


def test_posts_from_many_threads_keep_each_threads_order(host):
    seen = []

    def producer(name):
        for i in range(100):
            host.post(lambda i=i: seen.append((name, i)))

    threads = [threading.Thread(target=producer, args=(n,)) for n in "abcd"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    drain(host)
    for name in "abcd":
        assert [i for n, i in seen if n == name] == list(range(100))


def test_posts_made_before_start_run_after_it():
    h = ThreadedHost()
    seen = []
    h.post(lambda: seen.append("early"))
    assert h.is_session_thread() is False
    h.start()
    try:
        drain(h)
        assert seen == ["early"]
    finally:
        h.shutdown()


def test_start_twice_raises(host):
    with pytest.raises(RuntimeError):
        host.start()


def test_call_later_only_on_the_session_thread(host):
    with pytest.raises(RuntimeError):
        host.call_later(0.01, lambda: None)


def test_timers_fire_in_deadline_order_on_the_session_thread(host):
    seen = []
    done = threading.Event()

    def arm():
        host.call_later(0.06, lambda: (seen.append("late"), done.set()))
        host.call_later(0.02, lambda: seen.append(("early", host.is_session_thread())))
        host.call_later(0.04, lambda: seen.append("middle"))

    run_on(host, arm)
    assert done.wait(5)
    assert seen == [("early", True), "middle", "late"]


def test_equal_deadlines_fire_in_scheduling_order():
    now = [0.0]
    h = ThreadedHost(clock=lambda: now[0])
    h.start()
    try:
        seen = []

        def arm():
            for i in range(5):
                h.call_later(1.0, lambda i=i: seen.append(i))
            now[0] = 2.0  # every timer is due at the next round

        run_on(h, arm)
        drain(h)
        drain(h)
        assert seen == [0, 1, 2, 3, 4]
    finally:
        h.shutdown()


def test_timer_waits_for_its_delay(host):
    fired = []
    done = threading.Event()
    start = time.monotonic()
    run_on(host, lambda: host.call_later(0.15, lambda: (fired.append(time.monotonic()), done.set())))
    assert done.wait(5)
    assert fired[0] - start >= 0.14


def test_cancelled_timer_never_fires(host):
    seen = []
    done = threading.Event()

    def arm():
        timer = host.call_later(0.03, lambda: seen.append("cancelled"))
        host.call_later(0.08, done.set)
        timer.cancel()

    run_on(host, arm)
    assert done.wait(5)
    assert seen == []


def test_a_timer_can_cancel_another_due_in_the_same_round():
    now = [0.0]
    h = ThreadedHost(clock=lambda: now[0])
    h.start()
    try:
        seen = []
        timers = {}

        def arm():
            timers["first"] = h.call_later(1.0, lambda: (seen.append("first"),
                                                         timers["second"].cancel()))
            timers["second"] = h.call_later(1.5, lambda: seen.append("second"))
            now[0] = 5.0

        run_on(h, arm)
        drain(h)
        assert seen == ["first"]
    finally:
        h.shutdown()


def test_cancel_after_firing_is_a_no_op(host):
    done = threading.Event()
    timer = run_on(host, lambda: host.call_later(0.0, done.set))
    assert done.wait(5)
    timer.cancel()
    timer.cancel()


def test_debounce_pattern_rearming_a_timer(host):
    """What AppSession does on every keystroke: cancel the timer, arm a new one."""
    seen = []
    done = threading.Event()
    state = {"timer": None}

    def keystroke(i):
        if state["timer"] is not None:
            state["timer"].cancel()
        state["timer"] = host.call_later(0.05, lambda: (seen.append(i), done.set()))

    for i in range(10):
        host.post(lambda i=i: keystroke(i))
    assert done.wait(5)
    time.sleep(0.1)
    assert seen == [9]


def test_posts_are_not_starved_by_a_busy_timer(host):
    seen = []
    stop = threading.Event()

    def tick():
        if not stop.is_set():
            host.call_later(0.0, tick)

    run_on(host, lambda: host.call_later(0.0, tick))
    host.post(lambda: seen.append("posted"))
    drain(host)
    stop.set()
    assert seen == ["posted"]


def test_exceptions_in_callbacks_are_reported_and_the_thread_goes_on(host, reported):
    seen = []
    done = threading.Event()

    def boom():
        raise ValueError("posted boom")

    def timer_boom():
        raise KeyError("timer boom")

    host.post(boom)
    host.post(lambda: seen.append("after"))
    run_on(host, lambda: host.call_later(0.01, timer_boom))
    run_on(host, lambda: host.call_later(0.05, done.set))
    assert done.wait(5)
    assert seen == ["after"]
    assert [(type(e).__name__, ctx) for e, ctx in reported] == [
        ("ValueError", "session thread callback"), ("KeyError", "session thread callback")]
    assert host.is_running


def test_call_returns_the_result_and_raises_what_fn_raised(host):
    assert host.call(lambda: (host.is_session_thread(), 42)) == (True, 42)
    with pytest.raises(ZeroDivisionError):
        host.call(lambda: 1 / 0)
    # On the session thread it just calls.
    assert host.call(lambda: host.call(lambda: "nested")) == "nested"


def test_call_times_out(host):
    release = threading.Event()
    host.post(lambda: release.wait(5))
    with pytest.raises(TimeoutError):
        host.call(lambda: None, timeout=0.05)
    release.set()


def test_monotonic_is_the_clock():
    h = ThreadedHost(clock=lambda: 12.5)
    assert h.monotonic() == 12.5
    real = ThreadedHost()
    assert abs(real.monotonic() - time.monotonic()) < 1


def test_shutdown_runs_what_was_posted_and_drops_pending_timers():
    h = ThreadedHost()
    h.start()
    seen = []
    release = threading.Event()
    h.post(lambda: release.wait(5))
    timer_holder = []
    h.post(lambda: timer_holder.append(h.call_later(0.05, lambda: seen.append("timer"))))
    h.post(lambda: seen.append("queued"))
    release.set()
    time.sleep(0.01)
    start = time.monotonic()
    assert h.shutdown(timeout=5) is True
    assert time.monotonic() - start < 1  # didn't wait for the timer
    time.sleep(0.1)
    assert seen == ["queued"]
    assert not h.is_running
    h.post(lambda: seen.append("too late"))
    time.sleep(0.05)
    assert seen == ["queued"]
    with pytest.raises(RuntimeError):
        h.call(lambda: None)
    with pytest.raises(RuntimeError):
        h.start()


def test_shutdown_with_a_far_timer_ends_promptly():
    h = ThreadedHost()
    h.start()
    fired = []
    h.call(lambda: h.call_later(60.0, lambda: fired.append(1)))
    start = time.monotonic()
    assert h.shutdown(timeout=5) is True
    assert time.monotonic() - start < 1
    assert fired == []


def test_shutdown_from_the_session_thread_ends_after_the_callback():
    h = ThreadedHost()
    h.start()
    seen = []
    done = threading.Event()

    def stop_from_inside():
        assert h.shutdown() is True  # doesn't join itself
        seen.append("still running")
        done.set()

    h.post(stop_from_inside)
    assert done.wait(5)
    for _ in range(100):
        if not h.is_running:
            break
        time.sleep(0.01)
    assert seen == ["still running"] and not h.is_running


def test_shutdown_before_start_and_twice():
    h = ThreadedHost()
    assert h.shutdown() is True
    assert h.shutdown() is True
