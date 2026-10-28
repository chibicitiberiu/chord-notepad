"""The desktop host: the Tk main thread is the session thread.

``post`` puts callbacks on a queue that a 100 ms ``after()`` loop drains on the
main thread (this loop used to live in ``Application._process_event_queue``).
``call_later`` is ``root.after``.
"""

import logging
import queue
import sys
import threading
import time
import tkinter as tk
from typing import Callable, Optional

from constants import EVENT_QUEUE_POLL_MS
from utils import error_reporting

logger = logging.getLogger(__name__)


class _AfterHandle:
    """Cancels a ``root.after`` callback."""

    def __init__(self, root: tk.Misc, after_id: str) -> None:
        self._root = root
        self._after_id: Optional[str] = after_id

    def cancel(self) -> None:
        """Cancel the callback; a no-op if it already ran or was cancelled."""
        after_id, self._after_id = self._after_id, None
        if after_id is None:
            return
        try:
            self._root.after_cancel(after_id)
        except tk.TclError:
            pass  # the window is gone, and the callback with it

    def _fired(self) -> None:
        self._after_id = None


class TkHost:
    """:class:`session.host.Host` on the Tk event loop.

    The host exists before the window does (services and viewmodels are built
    first), so the root is attached later with :meth:`attach`. Callbacks posted
    before that wait in the queue until :meth:`start` begins draining it.
    """

    def __init__(self, root: Optional[tk.Misc] = None,
                 poll_ms: int = EVENT_QUEUE_POLL_MS) -> None:
        """Create the host.

        Args:
            root: The Tk root window, or None to attach it later.
            poll_ms: How often the queue is drained, in milliseconds.
        """
        self._root = root
        self._poll_ms = poll_ms
        self._queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._running = False
        self._drain_id: Optional[str] = None
        self._session_thread = threading.current_thread()

    def attach(self, root: tk.Misc) -> None:
        """Set the Tk root that runs callbacks and parents error dialogs."""
        self._root = root

    def start(self) -> None:
        """Start draining the queue (needs an attached root)."""
        if self._root is None:
            raise RuntimeError("TkHost.start() needs a root window; call attach() first")
        self._running = True
        self._drain()

    def stop(self) -> None:
        """Stop draining the queue. Safe to call more than once."""
        self._running = False
        drain_id, self._drain_id = self._drain_id, None
        if drain_id is not None and self._root is not None:
            try:
                self._root.after_cancel(drain_id)
            except tk.TclError:
                pass

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` for the main thread; safe from any thread."""
        self._queue.put(cb)

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> _AfterHandle:
        """Run ``cb`` on the main thread after ``delay_s`` seconds."""
        if self._root is None:
            raise RuntimeError("TkHost.call_later() needs a root window; call attach() first")
        delay_ms = max(0, int(round(delay_s * 1000)))
        handle: Optional[_AfterHandle] = None

        def run() -> None:
            handle._fired()
            cb()

        handle = _AfterHandle(self._root, self._root.after(delay_ms, run))
        return handle

    def is_session_thread(self) -> bool:
        """Whether the caller is the Tk main thread."""
        return threading.current_thread() is self._session_thread

    def monotonic(self) -> float:
        """``time.monotonic()``."""
        return time.monotonic()

    def _drain(self) -> None:
        """Run every queued callback, then schedule the next drain.

        A failing callback is reported and the rest still run.
        """
        self._drain_id = None
        try:
            while True:
                try:
                    callback = self._queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception:
                    error_reporting.report_unexpected_error(
                        self._root, sys.exc_info(), "queued UI callback")
        finally:
            if self._running and self._root is not None:
                self._drain_id = self._root.after(self._poll_ms, self._drain)
