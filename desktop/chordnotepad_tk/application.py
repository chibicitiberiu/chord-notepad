"""Central application container with lifecycle management."""

import logging
import sys
import tkinter as tk
from typing import Optional, Callable

from chordnotepad.app_paths import AppPaths
from chordnotepad.constants import APP_NAME
from chordnotepad.exceptions import ServiceNotInitializedError
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.config_service import ConfigService
from chordnotepad.services.logging_service import LoggingService
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.services.file_service import FileService
from chordnotepad.services.resource_service import ResourceService
from chordnotepad.session.bootstrap import CoreServices, build_core_services, create_session
from chordnotepad.session.documents import FileSystemDocumentStore
from chordnotepad.session.session import AppSession
from chordnotepad_tk import error_reporting
from chordnotepad_tk.tk_host import TkHost


class Application:
    """Central application container managing lifecycle and dependency injection.

    This class serves as the main application container, managing:
    - Application lifecycle (initialization, running, shutdown)
    - Service instantiation and access
    - The Tk host: the cross-thread queue and timers on the UI thread
    """

    def __init__(self, paths: AppPaths):
        """Create the container; nothing is built until :meth:`on_initialize`.

        Args:
            paths: Where the app's files are (``main.py`` resolves them with
                ``chordnotepad_tk.desktop_paths.resolve_desktop_paths``).
        """
        self._paths = paths

        # Private service instances (initialized in on_initialize_services);
        # the Tk-free ones are the shared core (session.bootstrap)
        self._core: Optional[CoreServices] = None
        self._appdata_service: Optional[AppDataService] = None
        self._config_service: Optional[ConfigService] = None
        self._logging_service: Optional[LoggingService] = None
        self._audio_service: Optional[PlaybackService] = None
        self._song_parser_service: Optional[SongParserService] = None
        self._file_service: Optional[FileService] = None
        self._resource_service: Optional[ResourceService] = None
        self._document_store: Optional[FileSystemDocumentStore] = None

        # The application layer the window drives, with the viewmodels it
        # composes (initialized in on_initialize_ui)
        self._session: Optional[AppSession] = None

        # Runs callbacks on the Tk main thread (cross-thread queue, timers).
        # The root window is attached in set_main_window().
        self._host = TkHost()

        # Main window reference
        self._main_window: Optional[tk.Tk] = None

        # Lifecycle state
        self._initialized = False
        self._running = False

    # Service properties with validation

    @property
    def appdata_service(self) -> AppDataService:
        """Get the AppData service."""
        if self._appdata_service is None:
            raise ServiceNotInitializedError(
                "AppDataService not initialized. Call on_initialize() first."
            )
        return self._appdata_service

    @property
    def config_service(self) -> ConfigService:
        """Get the Config service."""
        if self._config_service is None:
            raise ServiceNotInitializedError(
                "ConfigService not initialized. Call on_initialize() first."
            )
        return self._config_service

    @property
    def logging_service(self) -> LoggingService:
        """Get the Logging service."""
        if self._logging_service is None:
            raise ServiceNotInitializedError(
                "LoggingService not initialized. Call on_initialize() first."
            )
        return self._logging_service

    @property
    def audio_service(self) -> PlaybackService:
        """Get the Audio service."""
        if self._audio_service is None:
            raise ServiceNotInitializedError(
                "AudioService not initialized. Call on_initialize() first."
            )
        return self._audio_service

    @property
    def song_parser_service(self) -> SongParserService:
        """Get the Song Parser service."""
        if self._song_parser_service is None:
            raise ServiceNotInitializedError(
                "SongParserService not initialized. Call on_initialize() first."
            )
        return self._song_parser_service

    @property
    def file_service(self) -> FileService:
        """Get the File service."""
        if self._file_service is None:
            raise ServiceNotInitializedError(
                "FileService not initialized. Call on_initialize() first."
            )
        return self._file_service

    @property
    def documents(self) -> FileSystemDocumentStore:
        """Get the document store (local files)."""
        if self._document_store is None:
            raise ServiceNotInitializedError(
                "Document store not initialized. Call on_initialize() first."
            )
        return self._document_store

    @property
    def session(self) -> AppSession:
        """Get the application session."""
        if self._session is None:
            raise ServiceNotInitializedError(
                "AppSession not initialized. Call on_initialize() first."
            )
        return self._session

    @property
    def resource_service(self) -> ResourceService:
        """Get the Resource service."""
        if self._resource_service is None:
            raise ServiceNotInitializedError(
                "ResourceService not initialized. Call on_initialize() first."
            )
        return self._resource_service

    # Lifecycle methods

    def on_initialize(self) -> None:
        """Initialize the application.

        This is the main entry point that orchestrates the initialization sequence.
        """
        if self._initialized:
            return

        # Initialize services first
        self.on_initialize_services()

        # Configure logging
        self.on_configure_logging()

        logger = logging.getLogger(__name__)
        logger.info(f"{APP_NAME} application initializing")

        # Initialize audio player before UI (so instruments are available for menu)
        logger.info("Initializing audio system")
        self._audio_service.initialize_player()

        # Initialize UI
        self.on_initialize_ui()

        self._initialized = True
        logger.info("Application initialization complete")

    def on_initialize_services(self) -> None:
        """Initialize all application services in dependency order."""
        # The shared core: data directories, config (loaded), parser,
        # playback (pings posted through this application), file I/O
        core = build_core_services(AppDataService(), self, paths=self._paths)
        self._core = core
        self._appdata_service = core.appdata
        self._config_service = core.config
        self._song_parser_service = core.song_parser
        self._audio_service = core.playback
        self._file_service = core.files
        self._document_store = FileSystemDocumentStore(core.files)

        # Desktop-only: icons and other bundled resources, logging setup
        self._resource_service = ResourceService(self._paths)
        self._logging_service = LoggingService()

    def on_configure_logging(self) -> None:
        """Configure the logging system."""
        log_level = self.config_service.get("log_level", "INFO")
        self.logging_service.configure_logging(
            self.appdata_service,
            log_level=log_level,
            console_output=True
        )
        # Errors nothing else catches get logged and shown, not lost on stderr.
        # Until here the core's errors (session.errors) are only logged, which
        # is all the presenter would do before install_thread_hook anyway.
        error_reporting.set_log_path(str(self.appdata_service.get_log_file_path()))
        error_reporting.install_thread_hook(self.queue_ui_callback, lambda: self._main_window)
        error_reporting.install_session_handler()

    def on_initialize_ui(self) -> None:
        """Initialize the user interface.

        Creates ViewModels and passes them to the View layer.
        """
        logger = logging.getLogger(__name__)
        logger.info("Creating ViewModels")

        # The viewmodels over the core services (cross-thread callbacks go
        # through this application) and the session that composes them. It
        # only uses the host's timers once started, after the main window
        # has attached itself.
        if self._core is None:
            raise ServiceNotInitializedError(
                "Core services not initialized. Call on_initialize() first."
            )
        self._session = create_session(self._host, self._core, self.documents, dispatch=self)

        logger.info("ViewModels created successfully")

    def on_run(self) -> None:
        """Start the application main loop."""
        if not self._initialized:
            self.on_initialize()

        logger = logging.getLogger(__name__)
        logger.info(f"{APP_NAME} starting")

        self._running = True

        # Start draining the cross-thread queue
        if self._main_window is not None:
            self._host.start()
            self.session.start()
            logger.info("Starting Tkinter main loop")
            self._main_window.mainloop()
        else:
            logger.warning("No main window created, application not started")

    def on_shutdown(self) -> None:
        """Shutdown the application and cleanup resources."""
        logger = logging.getLogger(__name__)
        logger.info(f"{APP_NAME} shutting down")

        self._running = False
        self._host.stop()
        if self._session is not None:
            # Also drops what still observes its viewmodels (the chord-sheet
            # panel observed the strip directly).
            self._session.shutdown()

        # Cleanup audio service
        if self._audio_service is not None:
            try:
                self._audio_service.cleanup()
                logger.info("Audio service cleaned up")
            except Exception as e:
                logger.error(f"Failed to cleanup audio service: {e}")

        # Save configuration
        if self._config_service is not None:
            try:
                self._config_service.save_config()
                logger.info("Configuration saved")
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")

        logger.info("Application shutdown complete")

    # Cross-thread callbacks

    @property
    def host(self) -> TkHost:
        """The host that runs callbacks on the Tk main thread."""
        return self._host

    def queue_ui_callback(self, callback: Callable) -> None:
        """Queue a callback to be executed on the UI thread.

        This is used for cross-thread communication, allowing background threads
        to safely update the UI. Kept as the entry point PlaybackService,
        NotePlayer and MainWindowViewModel use; it posts to the host.

        Args:
            callback: Function to execute on UI thread
        """
        self._host.post(callback)

    # Utility methods

    def set_main_window(self, window: tk.Tk) -> None:
        """Set the main window reference.

        Args:
            window: The main Tkinter window
        """
        self._main_window = window
        self._host.attach(window)

    @property
    def is_initialized(self) -> bool:
        """Check if the application is initialized."""
        return self._initialized

    @property
    def is_running(self) -> bool:
        """Check if the application is running."""
        return self._running

    @classmethod
    def main(cls, paths: AppPaths) -> int:
        """Main entry point for the application.

        Args:
            paths: Where the app's files are (see :meth:`__init__`).

        Returns:
            Exit code (0 for success, 1 for error)
        """
        app = None
        try:
            # Create and initialize the application
            app = cls(paths)
            app.on_initialize()

            # Get logger after initialization
            logger = logging.getLogger(__name__)

            # Import build info
            try:
                from chordnotepad_tk.build_info import VERSION, BUILD_TYPE, COMMIT_HASH, BUILD_DATE
                try:
                    from chordnotepad_tk.build_info import BUILD_NUMBER
                except ImportError:
                    BUILD_NUMBER = "0"
            except ImportError:
                VERSION = "dev-local"
                BUILD_TYPE = "development"
                COMMIT_HASH = "unknown"
                BUILD_DATE = "unknown"
                BUILD_NUMBER = "0"

            # Log version information
            logger.info("=" * 60)
            logger.info(f"{APP_NAME}")
            logger.info("=" * 60)
            logger.info(f"Version:      {VERSION}")
            logger.info(f"Build Type:   {BUILD_TYPE}")
            logger.info(f"Build Number: {BUILD_NUMBER}")
            logger.info(f"Commit:       {COMMIT_HASH}")
            logger.info(f"Build Date:   {BUILD_DATE}")
            logger.info("=" * 60)

            # The main window is a view over the session
            from chordnotepad_tk.main_window import MainWindow
            root = MainWindow(app.session, app.host, app.resource_service)
            app.set_main_window(root)

            # Show quick start dialog if this is the first run
            root.show_quick_start_if_needed()

            # Start the application
            app.on_run()

            # Normal shutdown
            return 0

        except Exception as e:
            # Try to log the error if logging is configured
            try:
                logger = logging.getLogger(__name__)
                logger.critical(f"Fatal error: {e}", exc_info=True)
            except:
                # If logging isn't available, print to stderr
                import traceback
                print(f"Fatal error: {e}", file=sys.stderr)
                traceback.print_exc()
            error_reporting.show_fatal_error(e)
            return 1

        finally:
            # Cleanup on exit
            if app is not None:
                try:
                    app.on_shutdown()
                except Exception as e:
                    print(f"Error during shutdown: {e}", file=sys.stderr)
