"""Where unexpected errors go, without knowing how they are shown.

Core code that catches an error it can't handle (an observer that raised, a
failed callback) calls :func:`report_from_any_thread`. The UI installs a
handler with :func:`set_handler`: on desktop that is the Tk presenter in
``utils.error_reporting``, which registers itself when imported; on Android it
will turn the error into an ``UnexpectedError`` event. With no handler
installed the error is only logged.

Throttling repeated errors is the handler's job (the Tk presenter already does
it), because only the handler knows what "shown" means.
"""

import logging
from types import TracebackType
from typing import Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

ExcInfo = Tuple[Type[BaseException], BaseException, Optional[TracebackType]]
ErrorHandler = Callable[[ExcInfo, str], None]

_handler: Optional[ErrorHandler] = None


def set_handler(handler: Optional[ErrorHandler]) -> Optional[ErrorHandler]:
    """Install the function that reports unexpected errors.

    Args:
        handler: Called as ``handler(exc_info, context)`` from whatever thread
            the error was caught on, or None to go back to logging only.

    Returns:
        The handler that was installed before, so a test can put it back.
    """
    global _handler
    previous, _handler = _handler, handler
    return previous


def get_handler() -> Optional[ErrorHandler]:
    """The installed handler, or None."""
    return _handler


def report_from_any_thread(exc_info: ExcInfo, context: str) -> None:
    """Report an error caught somewhere that may not be the session thread.

    Args:
        exc_info: ``(type, value, traceback)`` of the error.
        context: What was running, for the log (e.g. "observer of 'bpm'").
    """
    handler = _handler
    if handler is None:
        logger.error("Unhandled error in %s", context, exc_info=exc_info)
        return
    try:
        handler(exc_info, context)
    except Exception:
        # A broken handler must not hide the original error.
        logger.error("Unhandled error in %s", context, exc_info=exc_info)
        logger.exception("Error handler failed")
