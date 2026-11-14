"""Show errors in the Qt window instead of losing them: the Qt error presenter.

The Qt counterpart of ``chordnotepad_tk.error_reporting``, with the same
texts and the same throttling:

* **Unexpected errors** (a bug, not the user's doing): Python exceptions in
  Qt callbacks and slots (``sys.excepthook``, which PySide calls for them),
  in background threads (``threading.excepthook``), in callbacks the host
  runs, the ones the core reports through ``session.errors``, and the
  ``UnexpectedError`` events of commands the bridge couldn't run. Each is
  logged with its traceback and shown as "Something went wrong: ..." with
  the log file's path. One dialog at a time: an error while one is open is
  only logged, and the same message isn't shown again within
  :data:`REPEAT_QUIET_SECONDS` of the last one being closed.
* **Messages the session decided to show** (``UserError``,
  ``AudioUnavailable``; the session's audio policy already reports
  click-to-hear failures once per session): shown one after the other.
* **Fatal startup errors**: :func:`show_fatal_error`, "Chord Notepad
  couldn't start.", in a window of its own (the main window may not exist).

The presenter only decides what to show; the window shows it. QML connects
to :attr:`ErrorPresenter.shown` (title, message) and calls
:meth:`ErrorPresenter.dismissed` when the dialog closes. What is reported
before a window has :meth:`ErrorPresenter.attach`-ed waits for it.

Importing this installs nothing. The application calls :meth:`install`
explicitly at startup, as the Tk application does with its presenter, and
:meth:`uninstall` at shutdown.
"""

import logging
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Deque, Optional, Tuple

from PySide6.QtCore import QEventLoop, QObject, QUrl, Signal, Slot

from chordnotepad.constants import APP_NAME
from chordnotepad.session import errors as session_errors
from chordnotepad.session.errors import ExcInfo

logger = logging.getLogger(__name__)

#: Don't repeat an identical error dialog within this many seconds.
REPEAT_QUIET_SECONDS = 5.0
#: The title of an unexpected error's dialog (Tk's).
ERROR_TITLE = "Error"
#: The fatal startup window.
FATAL_QML = Path(__file__).resolve().parent / "qml" / "app" / "FatalError.qml"

_Message = Tuple[str, str, bool]  # title, text, whether it is an unexpected error


def format_message(text: str, log_path: Optional[str]) -> str:
    """The dialog text for an unexpected error (Tk's wording).

    Args:
        text: The error, as one line.
        log_path: The log file, or None to leave it out.
    """
    message = f"Something went wrong:\n{text}"
    if log_path:
        message += f"\n\nDetails were written to the log file:\n{log_path}"
    return message


def exception_text(exc: BaseException) -> str:
    """An exception as the dialogs show it: its text, or its type without one."""
    return str(exc) or type(exc).__name__


def fatal_message(exc: BaseException, log_path: Optional[str]) -> str:
    """The text of the fatal startup window."""
    return f"{APP_NAME} couldn't start.\n\n{format_message(exception_text(exc), log_path)}"


class ErrorPresenter(QObject):
    """Decides which errors to show, and in what order; the window shows them.

    Create it on the GUI thread.

    Args:
        post: Queues a callable for the GUI thread from any thread (the
            host's ``post``).
        clock: Seconds, for the repeat throttle (tests pass their own).
    """

    #: Show a dialog: its title and its text.
    shown = Signal(str, str)

    def __init__(self, post: Callable[[Callable[[], None]], None],
                 clock: Callable[[], float] = time.monotonic,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._post = post
        self._clock = clock
        self._gui_thread = threading.current_thread()
        self.log_path: Optional[str] = None
        self._attached = False
        self._showing: Optional[_Message] = None
        self._queue: Deque[_Message] = deque()
        self._last_shown: Tuple[str, float] = ("", float("-inf"))
        self._installed = False
        self._previous_sys_hook = None
        self._previous_thread_hook = None
        self._previous_session_handler: Optional[session_errors.ErrorHandler] = None

    # -- set-up ---------------------------------------------------------------------

    def install(self) -> None:
        """Become the handler of every unexpected error (see the module docstring)."""
        if self._installed:
            return
        self._installed = True
        self._previous_sys_hook = sys.excepthook
        self._previous_thread_hook = threading.excepthook
        sys.excepthook = self._sys_hook
        threading.excepthook = self._thread_hook
        self._previous_session_handler = session_errors.set_handler(self.report_from_any_thread)

    def uninstall(self) -> None:
        """Put back the hooks and the session handler from before :meth:`install`."""
        if not self._installed:
            return
        self._installed = False
        if sys.excepthook == self._sys_hook:
            sys.excepthook = self._previous_sys_hook
        if threading.excepthook == self._thread_hook:
            threading.excepthook = self._previous_thread_hook
        if session_errors.get_handler() == self.report_from_any_thread:
            session_errors.set_handler(self._previous_session_handler)

    def attach(self) -> None:
        """A window shows the dialogs from now on (it is connected to :attr:`shown`)."""
        self._attached = True
        if self._showing is not None:
            self.shown.emit(self._showing[0], self._showing[1])

    def detach(self) -> None:
        """The window is going away: report to the log only."""
        self._attached = False

    # -- reporting ------------------------------------------------------------------

    def report_unexpected(self, exc_info: ExcInfo, context: str) -> None:
        """Log an unexpected error and show it (GUI thread)."""
        logger.error("Unhandled error in %s", context, exc_info=exc_info)
        self._show_unexpected(exception_text(exc_info[1]))

    def report_from_any_thread(self, exc_info: ExcInfo, context: str) -> None:
        """:meth:`report_unexpected` from any thread (queued off the GUI thread)."""
        if threading.current_thread() is self._gui_thread:
            self.report_unexpected(exc_info, context)
        else:
            self._post(lambda: self.report_unexpected(exc_info, context))

    def report_event(self, message: str, context: Optional[str]) -> None:
        """An ``UnexpectedError`` event (the bridge logged it already)."""
        logger.debug("Showing UnexpectedError from %s", context)
        self._show_unexpected(message)

    def show_message(self, title: str, message: str) -> None:
        """Show a message the session decided to show (after any already open)."""
        self._enqueue((title, message, False))

    @Slot()
    def dismissed(self) -> None:
        """The window closed the dialog; the next waiting message is shown."""
        showing, self._showing = self._showing, None
        if showing is not None and showing[2]:
            self._last_shown = (showing[1], self._clock())
        if self._queue:
            self._present(self._queue.popleft())

    @property
    def showing(self) -> Optional[Tuple[str, str]]:
        """The dialog open now (title, text), or None."""
        return None if self._showing is None else self._showing[:2]

    # -- inside -----------------------------------------------------------------------

    def _show_unexpected(self, text: str) -> None:
        message = format_message(text, self.log_path)
        if self._showing is not None:
            return      # one dialog at a time; the log has it
        last, when = self._last_shown
        if message == last and self._clock() - when < REPEAT_QUIET_SECONDS:
            return
        self._present((ERROR_TITLE, message, True))

    def _enqueue(self, item: _Message) -> None:
        if self._showing is None:
            self._present(item)
        else:
            self._queue.append(item)

    def _present(self, item: _Message) -> None:
        self._showing = item
        if self._attached:
            self.shown.emit(item[0], item[1])
        else:
            logger.info("No window to show %r yet; it waits", item[0])

    def _sys_hook(self, exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            self._previous_sys_hook(exc_type, exc_value, exc_tb)
            return
        self.report_from_any_thread((exc_type, exc_value, exc_tb), "Qt callback")

    def _thread_hook(self, args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit or args.exc_value is None:
            return
        name = args.thread.name if args.thread else "unknown"
        exc_info: ExcInfo = (args.exc_type, args.exc_value, args.exc_traceback)
        self.report_from_any_thread(exc_info, f"thread {name}")


def show_fatal_error(exc: BaseException, log_path: Optional[str] = None) -> None:
    """Tell the user the app couldn't start, in a window of its own if possible.

    Needs a ``QGuiApplication``; without one (or if the window can't be
    shown) the text goes to stderr, which is all that is left.
    """
    message = fatal_message(exc, log_path)
    try:
        if not _show_fatal_window(message):
            raise RuntimeError("no window")
    except Exception:
        logger.debug("The fatal error window couldn't be shown", exc_info=True)
        if sys.stderr is not None:
            print(message, file=sys.stderr)


def _show_fatal_window(message: str) -> bool:
    """Show FatalError.qml with ``message`` and wait until it is closed."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine

    app = QGuiApplication.instance()
    if app is None:
        return False
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"message": message, "appName": APP_NAME})
    engine.load(QUrl.fromLocalFile(str(FATAL_QML)))
    if not engine.rootObjects():
        return False
    window = engine.rootObjects()[0]
    loop = QEventLoop()
    # Not ``closing``: PySide can't pass its QQuickCloseEvent to Python.
    window.visibleChanged.connect(lambda visible: None if visible else loop.quit())
    if not window.isVisible():
        return False
    loop.exec()
    del window, engine
    return True
