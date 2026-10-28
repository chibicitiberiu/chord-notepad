"""The host: the thing that owns the session thread.

Session code never touches a toolkit's event loop directly. It asks the host to
run a callback on the session thread (``post``), or to run one later
(``call_later``). On desktop the host is :class:`ui.tk_host.TkHost` and the
session thread is the Tk main thread; tests use
:class:`session.testing.ManualHost`, which runs nothing until told to.
"""

from typing import Callable, Protocol


class Cancellable(Protocol):
    """A handle to something scheduled that can still be called off."""

    def cancel(self) -> None:
        """Cancel it; a no-op if it already ran or was cancelled."""
        ...


class Host(Protocol):
    """Runs callbacks on the session thread."""

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` to run on the session thread, in FIFO order.

        Safe to call from any thread.
        """
        ...

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> Cancellable:
        """Run ``cb`` on the session thread after ``delay_s`` seconds.

        Must be called on the session thread.
        """
        ...

    def is_session_thread(self) -> bool:
        """Whether the calling thread is the session thread."""
        ...

    def monotonic(self) -> float:
        """The host's clock in seconds (virtual in tests)."""
        ...


class HostDispatch:
    """Gives a host the ``queue_ui_callback`` shape older code expects.

    ``PlaybackService``, ``NotePlayer`` and ``MainWindowViewModel`` marshal to
    the UI thread through ``application.queue_ui_callback``. Handing them a
    ``HostDispatch`` instead of the Tk ``Application`` keeps them unchanged.
    """

    def __init__(self, host: Host) -> None:
        """Wrap ``host``."""
        self._host = host

    def queue_ui_callback(self, callback: Callable[[], None]) -> None:
        """Post ``callback`` to the session thread."""
        self._host.post(callback)
