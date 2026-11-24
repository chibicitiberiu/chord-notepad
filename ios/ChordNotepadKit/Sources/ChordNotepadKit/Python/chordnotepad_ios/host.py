"""iOS host entry point: starts an AppSession for ChordNotepadKit's Swift bridge.

Swift's ``Session.start`` calls :func:`start` on its bridge thread with the
launch options as one JSON object. Everything else is the shared embedded host
(``session.embedded_host``); this module only connects the Swift pieces that
``_cnbridge`` (the kit's C extension module) exposes:

- events go to ``_cnbridge.emit(type_name, json)``, which hands them to Swift's
  ``AsyncStream`` without waiting;
- the document store is :class:`SwiftStoreCallbacks`, whose methods call the
  Swift ``DocumentStore`` through ``_cnbridge.store_*``. A failure arrives as
  ``_cnbridge.StoreError`` with the user-facing message as its only argument
  (``RenameUnsupportedError`` when the storage can't rename), which
  :class:`IOSDocumentStore` turns into ``FileOperationError`` or
  ``RenameNotSupported``.
"""

import json
from typing import Any, Optional

import _cnbridge

from chordnotepad.audio.audio_options import AudioOptions
from chordnotepad.session import embedded_host
from chordnotepad.session.callback_store import CallbackDocumentStore
from chordnotepad.session.platform import IOS


class SwiftStoreCallbacks:
    """The callbacks object ``session.callback_store`` expects, over ``_cnbridge``."""

    def readBytes(self, document_id: str) -> bytes:  # noqa: N802 (the contract's names)
        return _cnbridge.store_read_bytes(document_id)

    def writeBytes(self, document_id: str, data: bytes) -> None:  # noqa: N802
        _cnbridge.store_write_bytes(document_id, bytes(data))

    def copyFromFile(self, document_id: str, path: str) -> None:  # noqa: N802
        _cnbridge.store_copy_from_file(document_id, str(path))

    def isAvailable(self, document_id: str) -> bool:  # noqa: N802
        return _cnbridge.store_is_available(document_id)

    def recent(self) -> str:
        return _cnbridge.store_recent()

    def addRecent(self, document_id: str, display_name: str, location: str) -> None:  # noqa: N802
        _cnbridge.store_add_recent(document_id, display_name, location)

    def setMaxRecent(self, count: int) -> None:  # noqa: N802
        _cnbridge.store_set_max_recent(int(count))

    def describe(self, document_id: str) -> Optional[str]:
        return _cnbridge.store_describe(document_id)

    def rename(self, document_id: str, display_name: str) -> str:
        return _cnbridge.store_rename(document_id, display_name)


class IOSDocumentStore(CallbackDocumentStore):
    """``CallbackDocumentStore`` that knows ``_cnbridge``'s rename refusal."""

    def is_rename_unsupported(self, exc: BaseException) -> bool:
        return isinstance(exc, _cnbridge.RenameUnsupportedError) or super().is_rename_unsupported(exc)


def audio_options_from(options: dict) -> AudioOptions:
    """The synth settings for the launch options' ``sample_rate`` and
    ``frames_per_buffer`` (0 or missing: FluidSynth's defaults)."""
    sample_rate = int(options.get("sample_rate") or 0)
    frames = int(options.get("frames_per_buffer") or 0)
    return AudioOptions(sample_rate=sample_rate or None, period_size=frames or None)


def start(options_json: str) -> Any:
    """Start the session; called once per process on Swift's bridge thread.

    Args:
        options_json: A JSON object: ``files_dir`` (Application Support),
            ``soundfont_path`` (str or null), ``sample_rate`` and
            ``frames_per_buffer`` (ints, 0 for the defaults),
            ``configure_logging`` (bool) and ``platform`` (``"ios"``; tests
            may name another).

    Returns:
        ``session.embedded_host.SessionHandle``.
    """
    options = json.loads(options_json)
    return embedded_host.start(
        platform=options.get("platform") or IOS,
        files_dir=options["files_dir"],
        document_store=SwiftStoreCallbacks(),
        event_sink=_cnbridge.emit,
        audio_options=audio_options_from(options),
        soundfont_path=options.get("soundfont_path") or None,
        store_class=IOSDocumentStore,
        configure_logging=bool(options.get("configure_logging", True)),
    )
