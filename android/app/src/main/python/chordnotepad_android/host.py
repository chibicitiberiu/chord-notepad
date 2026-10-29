"""Android host entry point: starts an AppSession for the Kotlin bridge.

The contract Kotlin is written against (``bridge/BridgeContract.kt``,
docs/ANDROID.md, "Bridge contract"): :func:`start` builds the core
(``session.bootstrap``) on a ``ThreadedHost`` and returns a
:class:`SessionHandle`; Kotlin submits commands to it as ``(name,
args_json)`` and gets every output through ``event_sink.onEvent(type_name,
json)`` on the session thread. Decoding, dispatch, the lifecycle commands
(``app_background``, ``app_foreground``, ``pause``, ``restore_draft``) and
the error events live in ``session.bridge`` so they are tested with the rest
of the core; this module only wires the Android pieces in.
"""

import logging
import os
import sys
from typing import Any, Mapping, Optional

from audio.audio_options import AudioOptions
from services.appdata_service import AppDataService
from services.logging_service import LoggingService
from session import errors
from session.bootstrap import CoreServices, build_core_services, create_session
from session.platform import ANDROID
from session.bridge import ErrorEvents, SessionBridge
from session.host import HostDispatch
from session.threaded_host import ThreadedHost

from chordnotepad_android.android_store import AndroidDocumentStore

logger = logging.getLogger("chordnotepad_android.host")

#: Oboe stream settings (the M2 spike's measurements were taken with these).
OBOE_SETTINGS = {"audio.oboe.performance-mode": "LowLatency"}

#: Settings are written this long after the last change, so a process kill
#: (not only leaving the screen) keeps the toolbar's state.
AUTOSAVE_DELAY_S = 1.5

#: How long start() waits for the session thread to build the session.
START_TIMEOUT_S = 120.0


def audio_options_from(options: Mapping[str, Any]) -> AudioOptions:
    """The synth settings for Kotlin's ``audio_options`` dict.

    ``sample_rate`` is the device's native output rate (no resampler);
    ``frames_per_buffer`` becomes ``audio.period-size`` when positive.
    """
    sample_rate = int(options.get("sample_rate") or 0)
    frames = int(options.get("frames_per_buffer") or 0)
    return AudioOptions(
        sample_rate=sample_rate or None,
        period_size=frames or None,
        settings=dict(OBOE_SETTINGS),
    )


class SessionHandle:
    """A running session, owned by Kotlin's PyHost."""

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

    def submit(self, command: str, args_json: str) -> None:
        """Queue ``command`` for the session thread and return at once.

        Args:
            command: A command name (``CommandNames`` in SessionCommands.kt).
            args_json: Its keyword arguments as a JSON object.
        """
        self._bridge.submit(str(command), str(args_json))

    def chord_sheet_buffer(self, height: float) -> Optional[bytes]:
        """The active chord-sheet view as a packed op buffer, or None.

        Called directly by Kotlin (``callAttr("chord_sheet_buffer", height)
        .toJava(ByteArray::class.java)``) on its bridge thread, not through
        ``submit``: bytes don't fit the JSON events. Packs on the caller's
        thread from the last rendered song, so it never waits for the
        session thread. A failure is reported as an ``UnexpectedError`` and
        returns None.
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


def start(files_dir: str, native_lib_dir: str, document_store, event_sink, audio_options,
          *, player=None, configure_logging: bool = True) -> SessionHandle:
    """Start the session; called once per process on Kotlin's bridge thread.

    Args:
        files_dir: The app's private files directory (config, logs, data).
        native_lib_dir: ``ApplicationInfo.nativeLibraryDir`` (FluidSynth is
            loaded by soname, so only logged).
        document_store: Kotlin ``DocumentStoreBridge`` (SafDocumentStore).
        event_sink: Kotlin ``EventSink``; ``onEvent(type_name, json)`` is
            called on the session thread for every state and event.
        audio_options: ``{"sample_rate": int, "frames_per_buffer": int,
            "soundfont_path": str}``.
        player: A ready player instead of FluidSynth (tests only).
        configure_logging: Set up the log file and console logging (tests
            turn it off).

    Returns:
        The handle Kotlin submits commands to.
    """
    options = dict(audio_options or {})
    appdata = AppDataService(root=files_dir)
    host = ThreadedHost(name="python-session")
    host.start()
    services = build_core_services(appdata, HostDispatch(host), player=player,
                                   audio_options=audio_options_from(options))
    if configure_logging:
        LoggingService().configure_logging(
            appdata, log_level=services.config.get("log_level", "INFO"), console_output=True)
    logger.info("Starting the session (files %s, natives %s)", files_dir, native_lib_dir)

    _init_audio(services, options.get("soundfont_path"), player is not None)
    store = AndroidDocumentStore(
        document_store, max_recent=lambda: services.config.get("max_recent_files", 10))

    def sink(type_name: str, payload: str) -> None:
        event_sink.onEvent(type_name, payload)

    def build() -> SessionBridge:
        session = create_session(host, services, store, chord_sheet=_chord_sheet_available(),
                                 platform=ANDROID)
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

    The SoundFont Kotlin copied to ``filesDir`` becomes the configured one,
    so a later lazy re-initialization (after a failure) finds it too. A
    failure is reported when the user plays something (``AudioUnavailable``).
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

    The renderers are headless and Pillow-free (``src/chord_sheet``); if a
    build still can't import them, the session runs without the strip
    rather than not at all.
    """
    try:
        import viewmodels.chord_sheet_viewmodel  # noqa: F401
    except ImportError as e:
        logger.warning("No chord sheet on this build: %s", e)
        return False
    return True
