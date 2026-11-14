"""Starts the Qt Quick front end.

Run it with ``python -m chordnotepad_tk.main --ui qt`` (the entry point every
build runs) or ``python -m chordnotepad_desktop.main``, which goes through
the same entry point. Either way :func:`run` gets the paths the entry point
resolved and the command line without ``--ui``.

``--smoke`` loads the window, waits until it is shown and quits: exit code 0
when the QML loaded without a warning, 1 otherwise. The packaging tracer
(plan C5) runs it inside each build.
"""

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from chordnotepad.app_paths import AppPaths

logger = logging.getLogger(__name__)

#: The QML, shipped inside this package.
QML_DIR = Path(__file__).resolve().parent / "qml"
#: The main window.
MAIN_QML = QML_DIR / "app" / "Main.qml"


def parse_args(argv):
    """The Qt front end's own options, and the rest (for QGuiApplication)."""
    parser = argparse.ArgumentParser(prog="chord-notepad --ui qt", add_help=False)
    parser.add_argument("--smoke", action="store_true",
                        help="load and show the window, then quit (exit 1 on a QML warning)")
    return parser.parse_known_args(argv)


def load_main_window(engine: QQmlApplicationEngine) -> bool:
    """Load Main.qml into ``engine``; False if it created no window.

    It is loaded from its file. An ``inline:`` or data URL hangs
    ``engine.load`` (Qt Quick pitfall 24), and relative imports need a file.
    """
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    return bool(engine.rootObjects())


def run(paths: AppPaths, argv) -> int:
    """Start the Qt window and run the event loop.

    Args:
        paths: Where the app's files are (``chordnotepad_tk.desktop_paths``).
        argv: The command line after the program name, without ``--ui``.

    Returns:
        The exit code.
    """
    options, qt_args = parse_args(argv)
    app = QGuiApplication([sys.argv[0], *qt_args])
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    if not load_main_window(engine):
        for text in warnings:
            logger.error("QML: %s", text)
        return 1
    if options.smoke:
        QTimer.singleShot(0, app.quit)
    code = app.exec()
    for text in warnings:
        logger.warning("QML: %s", text)
    del engine
    if options.smoke and warnings:
        return 1
    return code


if __name__ == "__main__":
    from chordnotepad_tk.main import main

    main(["--ui", "qt", *sys.argv[1:]])
