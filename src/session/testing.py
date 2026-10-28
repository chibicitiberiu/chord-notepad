"""Deterministic stand-ins for the session's collaborators, for tests.

:class:`ManualHost` runs nothing on its own: posted callbacks wait for
:meth:`ManualHost.run_pending`, and timers wait for the virtual clock to be
moved with :meth:`ManualHost.advance`. A test drives time explicitly, so a
500 ms debounce takes no real time and can't be flaky.
"""

import heapq
import itertools
import threading
from collections import deque
from typing import Callable, Deque, List, Tuple


class _ManualTimer:
    """A :class:`ManualHost` timer handle."""

    def __init__(self, due: float, cb: Callable[[], None]) -> None:
        self.due = due
        self.cb = cb
        self.cancelled = False

    def cancel(self) -> None:
        """Stop the timer from firing (no-op once it has fired)."""
        self.cancelled = True


class ManualHost:
    """A :class:`session.host.Host` driven by the test, with a virtual clock.

    The thread that creates it is the session thread. ``post`` may be called
    from any thread; everything else belongs to the session thread, and
    ``call_later`` raises if called elsewhere so a threading mistake fails the
    test instead of going unnoticed.

    Callbacks run by :meth:`run_pending` and :meth:`advance` are not guarded:
    an exception propagates to the test.
    """

    def __init__(self, start: float = 0.0) -> None:
        """Create a host whose clock reads ``start`` seconds."""
        self._now = float(start)
        self._lock = threading.Lock()
        self._posted: Deque[Callable[[], None]] = deque()
        self._timers: List[Tuple[float, int, _ManualTimer]] = []
        self._seq = itertools.count()
        self._session_thread = threading.current_thread()

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` until the next :meth:`run_pending`."""
        with self._lock:
            self._posted.append(cb)

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> _ManualTimer:
        """Schedule ``cb`` for ``delay_s`` seconds of virtual time from now."""
        if not self.is_session_thread():
            raise RuntimeError("call_later must be called on the session thread")
        timer = _ManualTimer(self._now + max(0.0, delay_s), cb)
        # The sequence number keeps equal deadlines in scheduling order.
        heapq.heappush(self._timers, (timer.due, next(self._seq), timer))
        return timer

    def is_session_thread(self) -> bool:
        """Whether the caller is the thread that created this host."""
        return threading.current_thread() is self._session_thread

    def monotonic(self) -> float:
        """The virtual clock, in seconds."""
        return self._now

    @property
    def pending_posts(self) -> int:
        """How many posted callbacks are waiting."""
        with self._lock:
            return len(self._posted)

    @property
    def pending_timers(self) -> int:
        """How many timers are armed (scheduled and not cancelled)."""
        return sum(1 for _, _, t in self._timers if not t.cancelled)

    def run_pending(self) -> int:
        """Run posted callbacks until none are left, in FIFO order.

        Callbacks posted while this runs are run too, like the Tk drain does.

        Returns:
            How many callbacks ran.
        """
        ran = 0
        while True:
            with self._lock:
                if not self._posted:
                    return ran
                cb = self._posted.popleft()
            cb()
            ran += 1

    def advance(self, seconds: float) -> int:
        """Move the clock forward, firing the timers that come due on the way.

        Posted callbacks run first, and again after each timer, so work a
        timer posts is done before the next timer fires. Timers fire in
        deadline order with the clock set to their deadline.

        Returns:
            How many timers fired.
        """
        target = self._now + max(0.0, seconds)
        fired = 0
        self.run_pending()
        while self._timers and self._timers[0][0] <= target:
            due, _, timer = heapq.heappop(self._timers)
            if timer.cancelled:
                continue
            self._now = max(self._now, due)
            timer.cancelled = True  # fired: a late cancel() is a no-op
            timer.cb()
            fired += 1
            self.run_pending()
        self._now = target
        return fired
