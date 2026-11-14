"""Qt's own messages (QML warnings, ``console.log``, plugin errors) into logging.

Without a handler Qt prints them to stderr, which nobody sees in a packaged
app and which never reaches the log file. :func:`install_message_handler`
sends each one to a logger named after its category (``qt.qpa.xcb``;
``qt.qml`` and ``qt.js`` for QML's ``qml`` and ``js``, ``qt.default`` for
uncategorised ones) at the matching level,
with the QML file and line when Qt knows them.

A handler that was installed before (pytest-qt's, in the tests) still gets
every message, so a test that installs this one still fails on a QML
warning.
"""

import logging
from typing import Callable

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

#: Qt's message types as logging levels.
LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


def logger_name(category) -> str:
    """The logger for a Qt message category (``qt.`` once, in front)."""
    category = category or "default"
    return category if category.startswith("qt.") else f"qt.{category}"


def install_message_handler() -> Callable[[], None]:
    """Route Qt's messages into logging; returns a function that undoes it."""
    previous = None

    def handler(mode, context, message):
        level = LEVELS.get(mode, logging.WARNING)
        log = logging.getLogger(logger_name(context.category))
        if context.file:
            log.log(level, "%s (%s:%s)", message, context.file, context.line)
        else:
            log.log(level, "%s", message)
        if mode == QtMsgType.QtFatalMsg:
            # Qt aborts the process after this returns.
            for h in logging.getLogger().handlers:
                h.flush()
        if previous is not None:
            previous(mode, context, message)

    previous = qInstallMessageHandler(handler)

    def uninstall() -> None:
        qInstallMessageHandler(previous)

    return uninstall
