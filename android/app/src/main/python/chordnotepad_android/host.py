"""Android host entry point: starts an AppSession for the Kotlin bridge.

STUB (M3). Session step 14 replaces the body of this module with the real
thing (ThreadedHost, bootstrap.build_core_services/create_session,
bridge.encode). Only the signatures below are fixed; they are the contract
the Kotlin side (``bridge/BridgeContract.kt``) is written against, documented
in docs/ANDROID.md, "Bridge contract".

What the stub does, so the Kotlin plumbing can be exercised end to end on a
device before step 14: ``start`` sends one ``StatusState`` through the event
sink and returns a handle that only logs the commands it gets.
"""

import json
import logging

logger = logging.getLogger("chordnotepad_android.host")


class SessionHandle:
    """A running session, owned by Kotlin's PyHost.

    STUB: logs commands instead of running them.
    """

    def __init__(self, event_sink) -> None:
        self._sink = event_sink

    def submit(self, command: str, args_json: str) -> None:
        """Queue ``command`` for the session thread and return at once.

        Args:
            command: A command name (``CommandNames`` in SessionCommands.kt).
            args_json: Its keyword arguments as a JSON object.
        """
        logger.warning("stub host: ignoring %s %s", command, args_json)

    def shutdown(self) -> None:
        """Stop the session thread and release audio."""
        logger.info("stub host: shutdown")


def start(files_dir: str, native_lib_dir: str, document_store, event_sink, audio_options) -> SessionHandle:
    """Start the session; called once per process on Kotlin's bridge thread.

    Args:
        files_dir: The app's private files directory.
        native_lib_dir: ``ApplicationInfo.nativeLibraryDir``.
        document_store: Kotlin ``DocumentStoreBridge`` (SafDocumentStore).
        event_sink: Kotlin ``EventSink``; call ``onEvent(type_name, json)``
            on the session thread for every state and event.
        audio_options: ``{"sample_rate": int, "frames_per_buffer": int,
            "soundfont_path": str}``.

    Returns:
        The handle Kotlin submits commands to.
    """
    logger.warning("chordnotepad_android.host is a stub until session step 14")
    event_sink.onEvent(
        "StatusState",
        json.dumps({"text": "Python bridge stub: the session arrives with step 14"}),
    )
    return SessionHandle(event_sink)
