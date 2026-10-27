"""Show unexpected errors to the user instead of losing them.

Errors nothing else catches end up here: exceptions in Tk callbacks, in
background threads, in callbacks queued from those threads, and fatal startup
errors. Each is logged with its traceback and shown in an error dialog that
points at the log file.

Dialogs are throttled: only one at a time, and the same message isn't shown
again within a few seconds, so an error in a timer callback can't flood the
screen.
"""

import logging
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from types import TracebackType
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

ExcInfo = Tuple[Type[BaseException], BaseException, Optional[TracebackType]]

# Don't repeat an identical dialog within this many seconds.
REPEAT_QUIET_SECONDS = 5.0

_log_path: Optional[str] = None
# Set by install_thread_hook(): how to reach the UI thread, and the window.
_run_on_ui_thread: Optional[Callable[[Callable[[], None]], None]] = None
_get_parent: Callable[[], Optional[tk.Misc]] = lambda: None
_dialog_open = False
_last_shown: Tuple[str, float] = ("", 0.0)


def set_log_path(path: Optional[str]) -> None:
    """Set the log file path mentioned in error dialogs.

    Args:
        path: Absolute path of the log file, or None to leave it out.
    """
    global _log_path
    _log_path = path


def format_message(exc: BaseException) -> str:
    """Build the dialog text for an unexpected error.

    Args:
        exc: The exception.

    Returns:
        A short message with the error and, if known, where the log is.
    """
    text = str(exc) or type(exc).__name__
    message = f"Something went wrong:\n{text}"
    if _log_path:
        message += f"\n\nDetails were written to the log file:\n{_log_path}"
    return message


def report_unexpected_error(parent: Optional[tk.Misc], exc_info: ExcInfo, context: str) -> None:
    """Log an unexpected error and show it in an error dialog.

    Must be called on the Tk main thread.

    Args:
        parent: Window to attach the dialog to, or None for Tk's default root.
        exc_info: ``(type, value, traceback)`` of the error.
        context: What was running, for the log (e.g. "UI callback").
    """
    global _dialog_open, _last_shown
    logger.error("Unhandled error in %s", context, exc_info=exc_info)

    message = format_message(exc_info[1])
    now = time.monotonic()
    if _dialog_open:
        return
    if message == _last_shown[0] and now - _last_shown[1] < REPEAT_QUIET_SECONDS:
        return

    _dialog_open = True
    try:
        kwargs = {"parent": parent} if parent is not None else {}
        messagebox.showerror("Error", message, **kwargs)
    except tk.TclError:
        # No usable window (e.g. it's being destroyed); the log has it.
        pass
    finally:
        _dialog_open = False
        _last_shown = (message, time.monotonic())


def install_thread_hook(run_on_ui_thread: Callable[[Callable[[], None]], None],
                        get_parent: Callable[[], Optional[tk.Misc]]) -> None:
    """Report uncaught exceptions in background threads.

    Python's default prints them to stderr, which nobody sees in a packaged
    app. The dialog is shown on the UI thread.

    Args:
        run_on_ui_thread: Queues a callable to run on the Tk main thread.
        get_parent: Returns the window to attach the dialog to.
    """
    global _run_on_ui_thread, _get_parent
    _run_on_ui_thread = run_on_ui_thread
    _get_parent = get_parent

    def hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit or args.exc_value is None:
            return
        exc_info: ExcInfo = (args.exc_type, args.exc_value, args.exc_traceback)
        name = args.thread.name if args.thread else "unknown"
        run_on_ui_thread(lambda: report_unexpected_error(get_parent(), exc_info, f"thread {name}"))

    threading.excepthook = hook


def report_from_any_thread(exc_info: ExcInfo, context: str) -> None:
    """Report an error caught somewhere that may not be the UI thread.

    On the UI thread the dialog is shown right away; elsewhere it is queued to
    the UI thread. Before install_thread_hook() has run (early startup, unit
    tests) the error is only logged.

    Args:
        exc_info: ``(type, value, traceback)`` of the error.
        context: What was running, for the log.
    """
    if _run_on_ui_thread is None:
        logger.error("Unhandled error in %s", context, exc_info=exc_info)
    elif threading.current_thread() is threading.main_thread():
        report_unexpected_error(_get_parent(), exc_info, context)
    else:
        _run_on_ui_thread(lambda: report_unexpected_error(_get_parent(), exc_info, context))


def show_fatal_error(exc: BaseException) -> None:
    """Tell the user the app couldn't start, if a window can be shown at all.

    Args:
        exc: The error that stopped startup.
    """
    message = f"Chord Notepad couldn't start.\n\n{format_message(exc)}"
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror("Chord Notepad", message, parent=root)
        finally:
            root.destroy()
    except tk.TclError:
        # No display either; stderr is all that's left. It is None in the
        # windowed Windows build, where a display always exists anyway.
        if sys.stderr is not None:
            print(message, file=sys.stderr)
