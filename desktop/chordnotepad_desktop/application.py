"""The Qt front end's lifecycle: build the core, show the window, shut down.

:class:`QtApplication` is the Qt counterpart of ``chordnotepad_tk.application
.Application``, in the same order (parity checklist §9, "Startup order"):

1. the core services (config loaded) on a :class:`~chordnotepad_desktop.qt_host.QtHost`;
2. logging, Qt's messages into it, and the error presenter
   (:meth:`ErrorPresenter.install`, explicitly, as Tk installs its own);
3. **audio before the UI**, so the instrument list is there for the menus;
4. the UI: fonts and style, the renderer (GPU or software), the session
   (``platform=DESKTOP_QT``), the :class:`~chordnotepad_desktop.session_store.SessionStore`,
   the window (sized from the saved geometry, its content hidden until the
   device pixel ratio settles);
5. the host starts running callbacks, then ``session.start()``, then
   ``app_started``, which decides whether Quick Start opens.

Closing: the window's close button (and later Quit, ☰, File) send
``request_close``; the session may ask about unsaved changes first, then
publishes ``CloseApproved``. :meth:`QtApplication._close_window` then saves
the geometry, stops playback, stops listening and closes the window; the
event loop ends and :meth:`QtApplication.shutdown` shuts the session and
the audio down and saves the config, as Tk's ``on_shutdown`` does.
"""

import datetime
import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtGui import QGuiApplication, QIcon

from chordnotepad.app_paths import AppPaths
from chordnotepad.audio.player_interface import IPlayer
from chordnotepad.constants import APP_NAME, WM_CLASS
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.logging_service import LoggingService
from chordnotepad.session.bootstrap import CoreServices, build_core_services, create_session
from chordnotepad.session.documents import FileSystemDocumentStore
from chordnotepad.session.formatting import AUDIO_ERROR_TITLE
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import DESKTOP_QT
from chordnotepad_desktop import rendering, window_geometry
from chordnotepad_desktop.error_presenter import ErrorPresenter
from chordnotepad_desktop.main import (
    MainWindow, create_engine, load_main_window, prepare_application,
)
from chordnotepad_desktop.qt_host import QtHost
from chordnotepad_desktop.qt_messages import install_message_handler
from chordnotepad_desktop.editor_bridge import EditorBridge
from chordnotepad_desktop.session_store import SessionStore

logger = logging.getLogger(__name__)

#: The .desktop file's name without ``.desktop``: Wayland's app id, and what
#: desktops match the window to (``tests/test_desktop_entry.py``).
DESKTOP_FILE_NAME = "io.github.chibicitiberiu.ChordNotepad"
#: The window icon, every size resources/ has.
ICON_FILES = ("icon-32.png", "icon-128.png", "icon-256.png")
#: The session's requests the window answers (Main.qml). The others are
#: answered "cancel" at once, so a flow that asks one doesn't wait forever:
#: the file pickers come with F3, the capo choice and the directive dialogs
#: with G2 and D5.
HANDLED_REQUESTS = frozenset({"ConfirmDiscardRequest"})


def set_identity(app: QGuiApplication, paths: AppPaths) -> None:
    """Name the app as the desktop knows it, and give it its icon.

    On X11 Qt makes the window class from the application name (first
    letter upper case), so the name is ``WM_CLASS``, the ``StartupWMClass``
    of the .desktop file. Wayland matches the desktop file name instead.
    """
    app.setApplicationName(WM_CLASS)
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    app.setApplicationVersion(paths.read_version())
    icon = window_icon(paths)
    if icon is not None:
        app.setWindowIcon(icon)


def window_icon(paths: AppPaths) -> Optional[QIcon]:
    """The app icon from resources/, or None if none is there."""
    if paths.resources is None:
        return None
    icon = QIcon()
    for name in ICON_FILES:
        path = paths.resources / name
        if path.is_file():
            icon.addFile(str(path))
    if icon.isNull():
        logger.warning("No window icon in %s", paths.resources)
        return None
    return icon


class QtApplication:
    """Builds and owns everything the Qt window runs on.

    Args:
        paths: Where the app's files are (``chordnotepad_tk.desktop_paths``).
        appdata: Where config and logs live; the platform's folders by
            default (tests pass a private root).
        player: A ready player instead of FluidSynth (tests).
        configure_logging: Set up the log file and the console (tests leave
            pytest's logging alone).
        software_rendering: ``--software-rendering`` was given.
        today: Today's local date (tests).
    """

    def __init__(self, paths: AppPaths, *, appdata: Optional[AppDataService] = None,
                 player: Optional[IPlayer] = None, configure_logging: bool = True,
                 software_rendering: bool = False,
                 today: Callable[[], datetime.date] = datetime.date.today) -> None:
        self._paths = paths
        self._appdata = appdata or AppDataService()
        self._player = player
        self._configure_logging = configure_logging
        self._software_rendering = software_rendering
        self._today = today
        self._app: Optional[QGuiApplication] = None
        self.host: Optional[QtHost] = None
        self.core: Optional[CoreServices] = None
        self.presenter: Optional[ErrorPresenter] = None
        self.store: Optional[SessionStore] = None
        self.editor: Optional[EditorBridge] = None
        self.main: Optional[MainWindow] = None
        self.renderer: Optional[str] = None
        #: The engine's QML warnings (``--smoke`` fails on any).
        self.warnings: list = []
        self._session: Any = None
        self._engine: Optional[QObject] = None
        self._geometry: Optional[window_geometry.GeometryKeeper] = None
        self._uninstall_messages: Optional[Callable[[], None]] = None
        self._closing = False
        self._shut_down = False

    @property
    def log_path(self) -> Optional[str]:
        """The log file, once logging is set up."""
        return self.presenter.log_path if self.presenter is not None else None

    # -- start-up -------------------------------------------------------------------

    def start(self, app: QGuiApplication) -> MainWindow:
        """Build the core and show the window (the event loop runs after).

        Raises:
            Exception: Whatever stopped start-up; the caller shows it with
                ``error_presenter.show_fatal_error`` and calls :meth:`shutdown`.
        """
        self._app = app
        self.host = QtHost()
        self.core = core = build_core_services(
            self._appdata, HostDispatch(self.host), paths=self._paths, player=self._player)
        self._start_logging(core)
        logger.info("%s %s (Qt) initializing", APP_NAME, self._paths.read_version())

        logger.info("Initializing audio system")
        if not core.playback.initialize_player():
            logger.warning("Audio isn't available yet: %s", core.playback.audio_error)

        prepare_application(app, self._paths)
        self.renderer = rendering.choose_renderer(app, flag=self._software_rendering)
        self._session = create_session(
            self.host, core, FileSystemDocumentStore(core.files), platform=DESKTOP_QT)
        self.store = SessionStore(self.host, self._session)
        self.store.event.connect(self._on_event)
        self.store.request.connect(self._on_request)
        self.store.closeApproved.connect(self._close_window)
        self.editor = EditorBridge(self.store, parent=self.store)

        self._engine = create_engine(self._paths)
        self._engine.warnings.connect(
            lambda errors: self.warnings.extend(e.toString() for e in errors))
        main = load_main_window(self._engine, app, store=self.store, errors=self.presenter,
                                editor=self.editor)
        if main is None:
            raise RuntimeError("The main window couldn't be loaded:\n" + "\n".join(self.warnings))
        self.main = main
        rendering.watch_scene_graph(main.window, app)
        geometry = window_geometry.apply(
            main.window, window_geometry.load(self._session, main.window))
        self._geometry = window_geometry.GeometryKeeper(main.window, geometry, parent=main.window)
        self.presenter.attach()
        window_geometry.show(main.window, geometry)

        self.host.start()
        self._session.start()
        today = self._today().isoformat()
        # Quick Start opens when the setting says so (StartupState); the
        # desktop has no support prompt.
        self.store.submit("app_started", {"launch_kind": "direct", "today": today,
                                          "installed_on": today, "can_ask_for_support": False})
        logger.info("Application initialization complete")
        return main

    def _start_logging(self, core: CoreServices) -> None:
        if self._configure_logging:
            LoggingService().configure_logging(
                core.appdata, log_level=core.config.get("log_level", "INFO"), console_output=True)
        self._uninstall_messages = install_message_handler()
        self.presenter = ErrorPresenter(self.host.post)
        self.presenter.log_path = str(core.appdata.get_log_file_path())
        self.presenter.install()

    # -- the session's events -------------------------------------------------------

    def _on_event(self, type_name: str, data: Any) -> None:
        if type_name == "UserError":
            self.presenter.show_message(data["title"], data["message"])
        elif type_name == "AudioUnavailable":
            self.presenter.show_message(AUDIO_ERROR_TITLE, data["message"])
        elif type_name == "UnexpectedError":
            self.presenter.report_event(data["message"], data["context"])

    def _on_request(self, type_name: str, data: Any) -> None:
        if type_name not in HANDLED_REQUESTS:
            logger.warning("The Qt window can't answer %s yet; cancelled", type_name)
            self.store.submit("respond", {"request_id": data["request_id"], "value": None})

    # -- closing --------------------------------------------------------------------

    def _close_window(self) -> None:
        """The session approved closing: keep what is kept, then close."""
        if self._closing or self.main is None:
            return
        self._closing = True
        window = self.main.window
        try:
            window_geometry.save(self._session, window, self._geometry.current())
        except Exception:
            logger.exception("Saving the window geometry failed")
        self._session.stop()
        self.store.close()
        window.setProperty("closeApproved", True)
        window.close()

    def shutdown(self) -> None:
        """Shut the session and the audio down and save the config (once)."""
        if self._shut_down:
            return
        self._shut_down = True
        logger.info("%s shutting down", APP_NAME)
        if self.host is not None:
            self.host.stop()
        if self.store is not None:
            self.store.close()
        if self._session is not None:
            self._session.shutdown()
        if self.main is not None:
            if self._app is not None:
                self._app.removeEventFilter(self.main.alt)
            if self.main.window.isVisible():
                self.main.window.setProperty("closeApproved", True)
                self.main.window.close()
        if self.presenter is not None:
            self.presenter.detach()
        if self.core is not None:
            try:
                self.core.playback.cleanup()
            except Exception:
                logger.exception("Failed to clean up the audio")
            try:
                self.core.config.save_config()
                logger.info("Configuration saved")
            except Exception:
                logger.exception("Failed to save the configuration")
        if self.presenter is not None:
            self.presenter.uninstall()
        if self._uninstall_messages is not None:
            self._uninstall_messages()
            self._uninstall_messages = None
        if self._engine is not None:
            # Now, with the window it owns, while the store its bindings
            # read is still alive (dropped first, they would read null).
            self._engine.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self._engine = None
            self.main = None
        logger.info("Application shutdown complete")
