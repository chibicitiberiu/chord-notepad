"""Starts the Qt Quick front end.

Run it with ``python -m chordnotepad_tk.main --ui qt`` (the entry point every
build runs) or ``python -m chordnotepad_desktop.main``, which goes through
the same entry point. Either way :func:`run` gets the paths the entry point
resolved and the command line without ``--ui``.

The order matters: the text renderer, the application font and the style
are set before the engine loads any QML, and the main window's
:class:`~chordnotepad_desktop.dpr.DprWatcher` starts as soon as the window
exists (its content stays hidden until the ratio has settled).

``--smoke`` loads the window, waits until its content is shown and quits:
exit code 0 when the QML loaded without a warning, 1 otherwise. The
packaging tracer (plan C5) runs it inside each build.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from chordnotepad.app_paths import AppPaths
from chordnotepad_desktop import fonts
from chordnotepad_desktop.alt_watcher import AltWatcher
from chordnotepad_desktop.dpr import DprWatcher
from chordnotepad_desktop.icons import PROVIDER_ID, IconProvider, icon_folders

logger = logging.getLogger(__name__)

#: The QML, shipped inside this package: CNTheme, CNStyle and app/.
QML_DIR = Path(__file__).resolve().parent / "qml"
#: The main window.
MAIN_QML = QML_DIR / "app" / "Main.qml"
#: The Controls style (qml/CNStyle), the one look on every OS.
STYLE = "CNStyle"
#: ``--smoke`` quits this long after the content is shown (a few frames).
SMOKE_LINGER_MS = 200


def parse_args(argv):
    """The Qt front end's own options, and the rest (for QGuiApplication)."""
    parser = argparse.ArgumentParser(prog="chord-notepad --ui qt", add_help=False)
    parser.add_argument("--smoke", action="store_true",
                        help="load and show the window, then quit (exit 1 on a QML warning)")
    return parser.parse_known_args(argv)


def prepare_application(app: QGuiApplication, paths: AppPaths) -> list:
    """Process-wide set-up, before any QML is loaded.

    Native text rendering, the unhinted application font, the bundled Inter
    and the CNStyle style (it can't change once a Controls type is created).

    Returns:
        The font families loaded from resources/fonts.
    """
    fonts.use_native_text_rendering()
    fonts.set_application_font(app)
    families = fonts.load_bundled_fonts(fonts.font_folder(paths))
    QQuickStyle.setStyle(STYLE)
    return families


def create_engine(paths: AppPaths, parent: Optional[QObject] = None) -> QQmlApplicationEngine:
    """An engine that finds CNTheme and CNStyle and serves ``image://icons``."""
    engine = QQmlApplicationEngine(parent)
    engine.addImportPath(str(QML_DIR))
    engine.addImageProvider(PROVIDER_ID, IconProvider(icon_folders(paths)))
    return engine


@dataclass
class MainWindow:
    """The loaded main window and the Python helpers that watch it."""

    window: QQuickWindow
    dpr: DprWatcher
    alt: AltWatcher


def load_main_window(engine: QQmlApplicationEngine, app: QGuiApplication) -> Optional[MainWindow]:
    """Load Main.qml and start its watchers; None if it created no window.

    Main.qml is loaded from its file. An ``inline:`` or data URL hangs
    ``engine.load`` (Qt Quick pitfall 24), and relative imports need a file.
    """
    alt = AltWatcher(parent=app)
    engine.setInitialProperties({"altWatcher": alt})
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))
    roots = engine.rootObjects()
    if not roots or not isinstance(roots[0], QQuickWindow):
        alt.deleteLater()
        return None
    window = roots[0]
    app.installEventFilter(alt)
    return MainWindow(window=window, dpr=DprWatcher(window, parent=window), alt=alt)


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
    prepare_application(app, paths)
    engine = create_engine(paths)
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
    main = load_main_window(engine, app)
    if main is None:
        for text in warnings:
            logger.error("QML: %s", text)
        return 1
    if options.smoke:
        main.dpr.revealed.connect(lambda: QTimer.singleShot(SMOKE_LINGER_MS, app.quit))
    code = app.exec()
    for text in warnings:
        logger.warning("QML: %s", text)
    app.removeEventFilter(main.alt)
    del main, engine
    if options.smoke and warnings:
        return 1
    return code


if __name__ == "__main__":
    from chordnotepad_tk.main import main

    main(["--ui", "qt", *sys.argv[1:]])
