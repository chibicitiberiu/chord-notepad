"""The host entry point shared by the apps that embed Python (Android, iOS).

Android's Kotlin and iOS's Swift both start the core the same way:
:func:`start` builds the core (``session.bootstrap``) on a ``ThreadedHost`` and
returns a :class:`SessionHandle`. The native side submits commands to the
handle as ``(name, args_json)`` and gets every output through
``event_sink.onEvent(type_name, json)``. Decoding, dispatch, the lifecycle
commands (``app_background``, ``app_foreground``, ``pause``, ``restore_draft``)
and the error events live in ``session.bridge`` so they are tested with the
rest of the core; this module only wires a platform's pieces in. Each platform
keeps a thin wrapper that fixes what differs: Android's is
``chordnotepad_android.host``.

Tests (Linux) may set ``CN_TEST_FAKE_PLAYER=1`` to run with
``session.testing.FakePlayer`` instead of starting FluidSynth, so the Swift
kit's tests can start a real session with no audio output; ``hold`` makes the
FakePlayer keep a started song playing until it is paused or stopped (the iOS
session test pauses one by an audio interruption). This only skips
creating the synth: importing the core still loads libfluidsynth (on Linux
the system's), as ``services/__init__.py`` pulls ``audio.fluid_ctypes`` in.
"""

import logging
import os
import sys
from typing import Any, Callable, Optional

from chordnotepad.app_paths import AppPaths
from chordnotepad.audio.audio_options import AudioOptions
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.services.logging_service import LoggingService
from chordnotepad.session import errors
from chordnotepad.session.bootstrap import CoreServices, build_core_services, create_session
from chordnotepad.session.bridge import ErrorEvents, SessionBridge
from chordnotepad.session.callback_store import CallbackDocumentStore
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import check_platform
from chordnotepad.session.threaded_host import ThreadedHost

logger = logging.getLogger(__name__)

#: Settings are written this long after the last change, so a process kill
#: (not only leaving the screen) keeps the toolbar's state.
AUTOSAVE_DELAY_S = 1.5

#: How long start() waits for the session thread to build the session.
START_TIMEOUT_S = 120.0

#: Set to ``1`` to start with a ``FakePlayer`` that plays a song through at
#: once, or to ``hold`` for one that keeps it playing (tests only).
FAKE_PLAYER_ENV = "CN_TEST_FAKE_PLAYER"


class SessionHandle:
    """A running session, owned by the native side."""

    def __init__(self, host: ThreadedHost, bridge: SessionBridge, services: CoreServices,
                 error_events: ErrorEvents) -> None:
        self._host = host
        self._bridge = bridge
        self._services = services
        self._error_events = error_events
        self._shut_down = False

    @property
    def session(self) -> Any:
        """The AppSession (tests)."""
        return self._bridge.session

    @property
    def host(self) -> ThreadedHost:
        """The session's host (tests)."""
        return self._host

    @property
    def services(self) -> CoreServices:
        """The core's services (tests, and the iOS self-test's audio status)."""
        return self._services

    def submit(self, command: str, args_json: str) -> None:
        """Queue ``command`` for the session thread and return at once.

        Args:
            command: A command name (``CommandNames`` in SessionCommands.kt).
            args_json: Its keyword arguments as a JSON object.
        """
        self._bridge.submit(str(command), str(args_json))

    def chord_sheet_buffer(self, height: float) -> Optional[bytes]:
        """The active chord-sheet view as a packed op buffer, or None.

        Called directly by the native side (Kotlin:
        ``callAttr("chord_sheet_buffer", height).toJava(ByteArray::class.java)``)
        on its bridge thread, not through ``submit``: bytes don't fit the JSON
        events. Packs on the caller's thread from the last rendered song, so
        it never waits for the session thread. A failure is reported as an
        ``UnexpectedError`` and returns None.
        """
        try:
            return self._bridge.session.chord_sheet_buffer(float(height))
        except Exception:
            errors.report_from_any_thread(sys.exc_info(), "chord_sheet_buffer")
            return None

    def shutdown(self) -> None:
        """Stop playback and the session thread, save the config, release audio."""
        if self._shut_down:
            return
        self._shut_down = True
        session = self._bridge.session

        def stop() -> None:
            session.stop()
            self._bridge.close()
            session.shutdown()

        try:
            self._host.call(stop, timeout=10.0)
        except Exception:
            logger.exception("Stopping the session failed")
        self._error_events.uninstall()
        self._host.shutdown(timeout=5.0)
        try:
            self._services.config.save_config()
        except Exception:
            logger.exception("Saving the config failed")
        self._services.playback.cleanup()


def start(*, platform: str, files_dir: str, document_store: Any, event_sink: Any,
          audio_options: Optional[AudioOptions] = None,
          soundfont_path: Optional[str] = None,
          paths: Optional[AppPaths] = None,
          store_class: Callable[..., CallbackDocumentStore] = CallbackDocumentStore,
          player: Any = None, configure_logging: bool = True) -> SessionHandle:
    """Start the session; called once per process on the native side's bridge thread.

    Args:
        platform: ``session.platform.ANDROID`` or ``IOS``: which texts and
            player behaviour the session has.
        files_dir: The app's private writable folder (Android's ``filesDir``,
            iOS's Application Support). Config lives in
            ``files_dir/config/chord-notepad``, data and logs in
            ``files_dir/data/chord-notepad``.
        document_store: The callbacks object for documents. It must have the
            methods listed in ``session.callback_store``'s docstring
            (``readBytes``, ``writeBytes``, ``copyFromFile``, ``isAvailable``,
            ``describe``, ``recent``, ``addRecent``, ``setMaxRecent``,
            ``rename``). They are called on the session thread, except
            ``copyFromFile`` and ``writeBytes``, which an audio or PDF export's
            worker thread may call. A failure is any exception with a
            user-facing message.
        event_sink: Receives the session's output: an object with
            ``onEvent(type_name: str, json: str)``, or a plain callable taking
            the same two arguments. It is called on the ``python-session``
            thread, once per state or event, in delivery order. It must return
            quickly, must not raise, and must not wait for the thread that
            called :func:`start` or :meth:`SessionHandle.submit`.
        audio_options: Sample rate, period size and driver settings for the
            synth (``audio.audio_options``); None for FluidSynth's defaults.
        soundfont_path: The SoundFont the native side put in ``files_dir``.
            It becomes the configured one unless the user chose another that
            still exists. None to leave the configuration alone.
        paths: The files the app ships (``app_paths.AppPaths``); None when it
            ships none next to the code.
        store_class: Wraps ``document_store`` into a ``DocumentStore``; a
            platform subclass of ``CallbackDocumentStore`` that reads its own
            exceptions (Android's).
        player: A ready player instead of FluidSynth (tests only). With the
            environment variable ``CN_TEST_FAKE_PLAYER=1`` and no player, a
            ``FakePlayer`` is used; with ``hold``, one that doesn't play a
            started song through (``auto_play=False``).
        configure_logging: Set up the log file and console logging (tests
            turn it off).

    Returns:
        The handle the native side submits commands to. Call
        :meth:`SessionHandle.shutdown` once when the app ends.

    Raises:
        ValueError: For an unknown ``platform``.
    """
    check_platform(platform)
    fake = os.environ.get(FAKE_PLAYER_ENV)
    if player is None and fake in ("1", "hold"):
        from chordnotepad.session.testing import FakePlayer
        player = FakePlayer(auto_play=fake != "hold")
    has_on_event = hasattr(event_sink, "onEvent")

    appdata = AppDataService(root=files_dir)
    host = ThreadedHost(name="python-session")
    host.start()
    services = build_core_services(appdata, HostDispatch(host), paths=paths or AppPaths(),
                                   player=player, audio_options=audio_options)
    if configure_logging:
        LoggingService().configure_logging(
            appdata, log_level=services.config.get("log_level", "INFO"), console_output=True)
    logger.info("Starting the %s session (files %s)", platform, files_dir)

    _init_audio(services, soundfont_path, player is not None)
    store = store_class(
        document_store, max_recent=lambda: services.config.get("max_recent_files", 10))

    def sink(type_name: str, payload: str) -> None:
        if has_on_event:
            event_sink.onEvent(type_name, payload)
        else:
            event_sink(type_name, payload)

    def build() -> SessionBridge:
        session = create_session(host, services, store, chord_sheet=_chord_sheet_available(),
                                 platform=platform)
        bridge = SessionBridge(host, session, sink, autosave_s=AUTOSAVE_DELAY_S)
        session.start()
        return bridge

    try:
        bridge = host.call(build, timeout=START_TIMEOUT_S)
    except BaseException:
        host.shutdown(timeout=1.0)
        raise
    error_events = ErrorEvents(host, bridge.session)
    error_events.install()
    logger.info("Session started")
    return SessionHandle(host, bridge, services, error_events)


def _init_audio(services: CoreServices, soundfont_path: Optional[str], has_player: bool) -> None:
    """Start FluidSynth now, so the instrument menu has the SoundFont's programs.

    The SoundFont the native side copied to ``files_dir`` becomes the
    configured one, so a later lazy re-initialization (after a failure) finds
    it too. A failure is reported when the user plays something
    (``AudioUnavailable``).
    """
    if has_player:
        return
    if soundfont_path:
        configured = services.config.get("soundfont_path")
        if configured != soundfont_path and not (configured and os.path.isfile(configured)):
            services.config.set("soundfont_path", soundfont_path)
    if not services.playback.initialize_player(soundfont_path or None):
        logger.warning("Audio isn't available yet: %s", services.playback.audio_error)


def _chord_sheet_available() -> bool:
    """Whether the chord-sheet strip can be built here.

    The renderers are headless and Pillow-free (``core/chordnotepad/chord_sheet``); if a
    build still can't import them, the session runs without the strip
    rather than not at all.
    """
    try:
        import chordnotepad.viewmodels.chord_sheet_viewmodel  # noqa: F401
    except ImportError as e:
        logger.warning("No chord sheet on this build: %s", e)
        return False
    return True
