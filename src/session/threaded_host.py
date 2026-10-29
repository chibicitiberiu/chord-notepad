"""The headless host: a dedicated Python thread is the session thread.

Android (and any host without a toolkit event loop) runs the session on a
:class:`ThreadedHost`. Other threads only :meth:`~ThreadedHost.post`; the
session thread runs posted callbacks in FIFO order and fires timers set with
:meth:`~ThreadedHost.call_later` when they come due.

A callback that raises is reported through :mod:`session.errors` (on Android
the handler turns it into an ``UnexpectedError`` event) and the thread goes
on with the next one: one bad callback must not stop the session.
"""

import heapq
import itertools
import logging
import sys
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, List, Optional, Tuple, TypeVar

from session import errors

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _Timer:
    """A :class:`ThreadedHost` timer handle."""

    def __init__(self, due: float, cb: Callable[[], None]) -> None:
        self.due = due
        self.cb = cb
        self.cancelled = False

    def cancel(self) -> None:
        """Stop the timer from firing (no-op once it has fired); any thread."""
        self.cancelled = True


class ThreadedHost:
    """:class:`session.host.Host` on a thread of its own.

    Lifecycle: create, :meth:`start`, use, :meth:`shutdown`. Callbacks
    posted before :meth:`start` wait and run once the thread is up.
    :meth:`shutdown` lets the callbacks already posted run, drops the timers
    still pending and every later post, then ends the thread.

    Each round of the loop fires the timers due at that moment (in deadline
    order, ties in scheduling order), then runs the callbacks posted by then
    (in posting order), so neither can starve the other.
    """

    def __init__(self, name: str = "SessionThread",
                 clock: Callable[[], float] = time.monotonic) -> None:
        """Create the host; nothing runs until :meth:`start`.

        Args:
            name: The thread's name, for logs and debuggers.
            clock: Seconds on a monotonic clock (tests may pass their own).
        """
        self._name = name
        self._clock = clock
        self._cond = threading.Condition()
        self._posted: Deque[Callable[[], None]] = deque()
        self._timers: List[Tuple[float, int, _Timer]] = []
        self._seq = itertools.count()
        self._thread: Optional[threading.Thread] = None
        self._stopping = False

    # -- lifecycle --------------------------------------------------------------

    def start(self) -> None:
        """Start the session thread.

        Raises:
            RuntimeError: If it was started (or shut down) before.
        """
        with self._cond:
            if self._thread is not None or self._stopping:
                raise RuntimeError("ThreadedHost.start() may be called only once")
            self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
            self._thread.start()

    def shutdown(self, timeout: Optional[float] = 5.0) -> bool:
        """Stop the session thread after the callbacks already posted.

        Pending timers never fire; posts made from now on are dropped. Called
        on the session thread itself (from a callback) it returns at once and
        the thread ends after that callback.

        Args:
            timeout: How long to wait for the thread to end; None waits.

        Returns:
            True if the thread has ended (or never started, or this is the
            session thread), False if it was still busy after ``timeout``.
        """
        with self._cond:
            self._stopping = True
            for _, _, timer in self._timers:
                timer.cancelled = True
            self._timers.clear()
            self._cond.notify_all()
            thread = self._thread
        if thread is None or thread is threading.current_thread():
            return True
        thread.join(timeout)
        return not thread.is_alive()

    @property
    def is_running(self) -> bool:
        """Whether the session thread is alive."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    # -- Host -----------------------------------------------------------------

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` for the session thread (FIFO); safe from any thread.

        Dropped (and logged) after :meth:`shutdown`.
        """
        with self._cond:
            if self._stopping:
                logger.debug("Dropping a callback posted after shutdown")
                return
            self._posted.append(cb)
            self._cond.notify()

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> _Timer:
        """Run ``cb`` on the session thread after ``delay_s`` seconds.

        Raises:
            RuntimeError: If not called on the session thread.
        """
        if not self.is_session_thread():
            raise RuntimeError("call_later must be called on the session thread")
        with self._cond:
            timer = _Timer(self._clock() + max(0.0, float(delay_s)), cb)
            if self._stopping:
                timer.cancelled = True  # shutting down: it would never fire
                return timer
            heapq.heappush(self._timers, (timer.due, next(self._seq), timer))
            self._cond.notify()
        return timer

    def is_session_thread(self) -> bool:
        """Whether the caller is the session thread."""
        thread = self._thread
        return thread is not None and threading.current_thread() is thread

    def monotonic(self) -> float:
        """The host's clock, in seconds."""
        return self._clock()

    # -- helpers for the thread that owns the host --------------------------------

    def call(self, fn: Callable[[], T], timeout: Optional[float] = None) -> T:
        """Run ``fn`` on the session thread and wait for its result.

        For setting things up from the thread that started the host (e.g.
        building the session, whose constructor arms timers). Never call it
        from a callback that other threads wait on. On the session thread it
        just calls ``fn``.

        Returns:
            What ``fn`` returned.

        Raises:
            Whatever ``fn`` raised; TimeoutError if it didn't finish in
            ``timeout`` seconds; RuntimeError if the host is shut down.
        """
        if self.is_session_thread():
            return fn()
        done = threading.Event()
        result: List[Any] = []
        failure: List[BaseException] = []

        def run() -> None:
            try:
                result.append(fn())
            except BaseException as e:  # handed to the caller, not reported here
                failure.append(e)
            finally:
                done.set()

        with self._cond:
            if self._stopping:
                raise RuntimeError("the host has been shut down")
            self._posted.append(run)
            self._cond.notify()
        if not done.wait(timeout):
            raise TimeoutError(f"the session thread didn't run the call within {timeout} s")
        if failure:
            raise failure[0]
        return result[0]

    # -- the session thread -------------------------------------------------------

    def _run(self) -> None:
        while True:
            batch = self._next_batch()
            if batch is None:
                return
            for item in batch:
                if isinstance(item, _Timer):
                    # A callback earlier in the batch may have cancelled it,
                    # or shut the host down.
                    if item.cancelled or self._stopping:
                        continue
                    item.cancelled = True  # fired: a late cancel() is a no-op
                    self._invoke(item.cb)
                else:
                    self._invoke(item)

    def _next_batch(self) -> Optional[List[Any]]:
        """Wait for work: the due timers (in deadline order), then the posted callbacks.

        Returns None when the host is shut down and nothing posted is left.
        """
        with self._cond:
            while True:
                batch: List[Any] = []
                now = self._clock()
                while self._timers and self._timers[0][0] <= now:
                    _, _, timer = heapq.heappop(self._timers)
                    if not timer.cancelled:
                        batch.append(timer)
                batch.extend(self._posted)
                self._posted.clear()
                if batch:
                    return batch
                if self._stopping:
                    return None
                wait = self._timers[0][0] - now if self._timers else None
                self._cond.wait(wait)

    def _invoke(self, cb: Callable[[], None]) -> None:
        try:
            cb()
        except Exception:
            errors.report_from_any_thread(sys.exc_info(), "session thread callback")
