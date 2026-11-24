"""A DocumentStore over a host's callbacks object (Android's Kotlin, iOS's Swift).

The embedded hosts (``session.embedded_host``) do their file access in native
code: Android through the Storage Access Framework, iOS through security-scoped
URLs. That native side gives Python a *callbacks object*, and this adapter gives
it the shape of ``session.documents.DocumentStore``. Text normalization and
encoding stay in Python. Called on the session thread only, except
:meth:`CallbackDocumentStore.write_file`, which the audio export's worker calls.

The callbacks object provides these methods (the names Android's
``DocumentStoreBridge`` has, ``bridge/BridgeContract.kt``). A ``ref`` is a JSON
object ``{"id", "display_name", "location"}``; ``id`` is whatever the host uses
to find the document again (a content URI, a bookmark key).

* ``readBytes(id) -> bytes``
* ``writeBytes(id, data: bytes)``
* ``copyFromFile(id, local_path: str)``: stream a local file into the document
* ``isAvailable(id) -> bool``
* ``describe(id) -> str | None``: the ref as JSON, None if unreachable
* ``recent() -> str``: a JSON list of refs, the host pruning unavailable ones
* ``addRecent(id, display_name, location)``, ``setMaxRecent(count)``
* ``rename(id, display_name) -> str``: the new ref as JSON

A failure is any exception whose message is user-facing; it is raised again as
``FileOperationError`` with that message, like ``FileService`` does on desktop.
A host that can't rename a document raises ``RenameNotSupported`` itself, or
(Android) an exception :meth:`CallbackDocumentStore.is_rename_unsupported`
recognises.
"""

import json
import logging
from typing import Any, Callable, List, Optional

from chordnotepad.exceptions import FileOperationError, RenameNotSupported
from chordnotepad.services.text_codec import TextFormat, decode_text, encode_text, format_of
from chordnotepad.session.documents import DocumentRef
from chordnotepad.utils.text_normalization import normalize_song_text

logger = logging.getLogger(__name__)


def _ref(data: Any) -> DocumentRef:
    return DocumentRef(id=str(data["id"]), display_name=str(data["display_name"]),
                       location=str(data["location"]))


class CallbackDocumentStore:
    """:class:`session.documents.DocumentStore` backed by a callbacks object."""

    def __init__(self, bridge: Any, max_recent: Callable[[], int] = lambda: 10) -> None:
        """Wrap ``bridge``.

        Args:
            bridge: The host's callbacks object (see the module docstring).
            max_recent: The configured recent-list length (read again before
                each ``add_recent``, so a Settings change takes effect).
        """
        self._bridge = bridge
        self._max_recent = max_recent
        self._sent_max: Optional[int] = None
        self.sync_max_recent()

    # -- what a host may override ----------------------------------------------------

    def message_of(self, exc: BaseException) -> str:
        """The user-facing message of a failure the callbacks raised."""
        return str(exc) or type(exc).__name__

    def is_rename_unsupported(self, exc: BaseException) -> bool:
        """Whether ``exc`` says the storage can't rename documents."""
        return isinstance(exc, RenameNotSupported)

    # -- DocumentStore ---------------------------------------------------------------

    def sync_max_recent(self) -> None:
        """Tell the host the recent list's cap if it changed."""
        try:
            count = int(self._max_recent())
        except Exception:
            logger.exception("Couldn't read max_recent_files")
            return
        if count != self._sent_max:
            self._call(self._bridge.setMaxRecent, count)
            self._sent_max = count

    def ref_for(self, document_id: str) -> Optional[DocumentRef]:
        """The ref for a document id, or None if it can't be reached."""
        data = self._call(self._bridge.describe, document_id)
        return _ref(json.loads(str(data))) if data is not None else None

    def read_text(self, ref: DocumentRef) -> str:
        """Read a song (UTF-8, Windows-1252, a BOM's encoding: see
        :mod:`services.text_codec`), normalized for the editor."""
        text, _ = decode_text(self._read_bytes(ref))
        return normalize_song_text(text)

    def write_text(self, ref: DocumentRef, text: str) -> Optional[str]:
        """Write a song in the document's own encoding and line endings (a
        CRLF Windows-1252 file stays one); a new or empty document is UTF-8
        with LF.

        Returns:
            None, or the note that the text didn't fit the document's
            encoding and was written in UTF-8.
        """
        try:
            existing: Optional[bytes] = self._read_bytes(ref)
        except FileOperationError:
            existing = None
        data, note = encode_text(text, format_of(existing, TextFormat()))
        self._call(self._bridge.writeBytes, ref.id, data)
        return note

    def _read_bytes(self, ref: DocumentRef) -> bytes:
        """The document's bytes. Chaquopy's ``byte[]`` converts with
        ``bytes()``; a plain sequence of signed Java bytes is masked."""
        data = self._call(self._bridge.readBytes, ref.id)
        try:
            return bytes(data)
        except (TypeError, ValueError):
            return bytes(b & 0xFF for b in data)

    def write_bytes(self, ref: DocumentRef, data: bytes) -> None:
        """Write an export (Chaquopy passes ``bytes`` as a Java ``byte[]``)."""
        self._call(self._bridge.writeBytes, ref.id, bytes(data))

    def write_file(self, ref: DocumentRef, local_path: str) -> None:
        """Write an export from a local file (an audio export): the host streams
        it into the document, so it never crosses the bridge as one array.
        Called on the audio export's worker thread."""
        self._call(self._bridge.copyFromFile, ref.id, str(local_path))

    def is_available(self, ref: DocumentRef) -> bool:
        """Whether the grant is still held and the host has the document."""
        try:
            return bool(self._bridge.isAvailable(ref.id))
        except Exception as e:
            logger.warning("isAvailable(%s) failed: %s", ref.location, self.message_of(e))
            return False

    def recent(self) -> List[DocumentRef]:
        """The recent list (the host prunes unavailable documents)."""
        try:
            items = json.loads(str(self._bridge.recent()))
            return [_ref(item) for item in items]
        except Exception as e:
            logger.error("Couldn't read the recent list: %s", self.message_of(e))
            return []

    def add_recent(self, ref: DocumentRef) -> None:
        """Move ``ref`` to the front of the recent list."""
        self.sync_max_recent()
        self._call(self._bridge.addRecent, ref.id, ref.display_name, ref.location)

    def rename(self, ref: DocumentRef, display_name: str) -> DocumentRef:
        """Rename the document.

        The host may change the id and adjust the name (``song (1).txt``
        rather than replace another document) and moves the recent-list
        entry to the new ref.

        Raises:
            RenameNotSupported: The storage can't rename it.
            FileOperationError: Anything else, with the host's message.
        """
        try:
            data = self._bridge.rename(ref.id, display_name)
        except RenameNotSupported:
            raise
        except Exception as e:
            if self.is_rename_unsupported(e):
                raise RenameNotSupported(self.message_of(e)) from e
            raise FileOperationError(self.message_of(e)) from e
        return _ref(json.loads(str(data)))

    def _call(self, method: Callable[..., Any], *args: Any) -> Any:
        try:
            return method(*args)
        except FileOperationError:
            raise
        except Exception as e:
            raise FileOperationError(self.message_of(e)) from e
