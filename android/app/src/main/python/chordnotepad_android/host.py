"""Android host entry point: starts an AppSession for the Kotlin bridge.

The contract Kotlin is written against (``bridge/BridgeContract.kt``,
docs/ANDROID.md, "Bridge contract"): :func:`start` builds the core on a
``ThreadedHost`` and returns a :class:`SessionHandle`; Kotlin submits commands
to it as ``(name, args_json)`` and gets every output through
``event_sink.onEvent(type_name, json)`` on the session thread. The startup
itself is ``chordnotepad.session.embedded_host`` (shared with iOS); this module
fixes what is Android's: the platform, the Oboe settings, the paths, the
document store that reads Java exceptions, and Kotlin's ``audio_options`` dict.
"""

import logging
from pathlib import Path
from typing import Any, Mapping

from chordnotepad.app_paths import AppPaths
from chordnotepad.audio.audio_options import AudioOptions
from chordnotepad.session import embedded_host
from chordnotepad.session.embedded_host import AUTOSAVE_DELAY_S, START_TIMEOUT_S, SessionHandle
from chordnotepad.session.platform import ANDROID

from chordnotepad_android.android_store import AndroidDocumentStore

logger = logging.getLogger(__name__)

__all__ = ["AUTOSAVE_DELAY_S", "START_TIMEOUT_S", "OBOE_SETTINGS", "SessionHandle",
           "audio_options_from", "app_paths_from", "start"]

#: Oboe stream settings (the M2 latency measurements in docs/ANDROID.md were taken with these).
OBOE_SETTINGS = {"audio.oboe.performance-mode": "LowLatency"}


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


def app_paths_from(native_lib_dir: str) -> AppPaths:
    """Where this app's files are on Android: none of them next to the code.

    There is no VERSION file (the version is ``versionName``), no
    ``resources/`` and no built help (it is served from the APK's assets).
    The SoundFont Kotlin copied to ``filesDir`` arrives in ``audio_options``
    and becomes the configured one, so it is not a bundled fallback here either.
    """
    return AppPaths(native_lib_dir=Path(native_lib_dir) if native_lib_dir else None)


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
    logger.info("Android natives in %s", native_lib_dir)
    return embedded_host.start(
        platform=ANDROID, files_dir=files_dir, document_store=document_store,
        event_sink=event_sink, audio_options=audio_options_from(options),
        soundfont_path=options.get("soundfont_path"), paths=app_paths_from(native_lib_dir),
        store_class=AndroidDocumentStore, player=player, configure_logging=configure_logging)
