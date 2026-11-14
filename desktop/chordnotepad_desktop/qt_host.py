"""The Qt host: the GUI thread is the session thread.

:class:`QtHost` is :class:`chordnotepad.session.host.Host` on the Qt event
loop, as ``chordnotepad_tk.tk_host.TkHost`` is on Tk's. ``post`` is a queued
signal (safe from any thread; the slot runs on the GUI thread), so a
callback posted from a playback or worker thread runs between Qt events,
never inside another callback. ``call_later`` is a single-shot ``QTimer``.

Like TkHost, the host exists before the window and the session are built;
callbacks posted before :meth:`QtHost.start` wait and run, in order, once
it is called. After :meth:`QtHost.stop` nothing posted runs any more.

A callback that raises is reported through ``session.errors`` (the Qt
error presenter once it is installed, the log before that), and the next
one still runs.
"""

import logging
import sys
import threading
import time
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from chordnotepad.session import errors as session_errors

logger = logging.getLogger(__name__)


class _Timer:
    """Cancels a ``call_later`` callback (:class:`session.host.Cancellable`)."""

    def __init__(self, timer: QTimer) -> None:
        self._timer: Optional[QTimer] = timer

    def cancel(self) -> None:
        """Cancel the callback; a no-op if it already ran or was cancelled."""
        timer, self._timer = self._timer, None
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def _fired(self) -> None:
        timer, self._timer = self._timer, None
        if timer is not None:
            timer.deleteLater()


class QtHost(QObject):
    """Runs the session's callbacks on the GUI thread.

    Create it on the GUI thread, after the ``QGuiApplication``.
    """

    #: Carries a posted callback to the GUI thread (queued connection).
    _posted = Signal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._session_thread = threading.current_thread()
        self._lock = threading.Lock()
        self._running = False
        self._stopped = False
        # Posted before start(), in order.
        self._waiting: List[Callable[[], None]] = []
        self._posted.connect(self._run, Qt.ConnectionType.QueuedConnection)

    # -- lifecycle -------------------------------------------------------------

    def start(self) -> None:
        """Run what was posted so far (on the next turn of the loop), and
        everything posted from now on."""
        with self._lock:
            if self._stopped:
                raise RuntimeError("QtHost.start() after stop()")
            self._running = True
            waiting, self._waiting = self._waiting, []
        for cb in waiting:
            self._posted.emit(cb)

    def stop(self) -> None:
        """Run nothing posted any more (callbacks already queued are dropped).
        Safe to call more than once."""
        with self._lock:
            self._running = False
            self._stopped = True
            self._waiting.clear()

    @property
    def running(self) -> bool:
        """Between :meth:`start` and :meth:`stop`."""
        return self._running

    # -- session.host.Host -------------------------------------------------------

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` for the GUI thread, in FIFO order; safe from any thread."""
        with self._lock:
            if self._stopped:
                return
            if not self._running:
                self._waiting.append(cb)
                return
        self._posted.emit(cb)

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> _Timer:
        """Run ``cb`` on the GUI thread after ``delay_s`` seconds.

        Must be called on the GUI thread (the session thread).
        """
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        handle = _Timer(timer)

        def fire() -> None:
            handle._fired()
            self._call(cb, "timer callback")

        timer.timeout.connect(fire)
        timer.start(max(0, int(round(delay_s * 1000))))
        return handle

    def is_session_thread(self) -> bool:
        """Whether the caller is the GUI thread."""
        return threading.current_thread() is self._session_thread

    def monotonic(self) -> float:
        """``time.monotonic()``."""
        return time.monotonic()

    # -- delivery -----------------------------------------------------------------

    def _run(self, cb: Callable[[], None]) -> None:
        if not self._running:
            return      # stopped after it was queued
        self._call(cb, "queued UI callback")

    @staticmethod
    def _call(cb: Callable[[], None], context: str) -> None:
        try:
            cb()
        except Exception:
            session_errors.report_from_any_thread(sys.exc_info(), context)
