"""The session's DocumentStore over Kotlin's SafDocumentStore.

Kotlin's ``DocumentStoreBridge`` (``bridge/BridgeContract.kt``) does the
Storage Access Framework I/O and keeps the recent list; this wrapper gives it
the shape of ``session.documents.DocumentStore``. Text normalization stays in
Python. A failure arrives as a Java ``DocumentStoreException`` whose message
is user-facing; it is raised again as ``FileOperationError`` with that
message, like ``FileService`` does on desktop; Kotlin's
``RenameUnsupportedException`` (a provider that can't rename) becomes
``RenameNotSupported``. Called on the session thread only.
"""

import json
import logging
from typing import Any, Callable, List, Optional

from exceptions import FileOperationError, RenameNotSupported
from session.documents import DocumentRef
from utils.text_normalization import normalize_song_text

logger = logging.getLogger(__name__)


def _message(exc: BaseException) -> str:
    """The user-facing message of a Java exception (or a Python one)."""
    get_message = getattr(exc, "getMessage", None)
    if callable(get_message):
        try:
            message = get_message()
        except Exception:
            message = None
        if message:
            return str(message)
    return str(exc) or type(exc).__name__


#: Kotlin's exception for a provider without rename support (simple class name).
RENAME_UNSUPPORTED = "RenameUnsupportedException"


def _java_name(exc: BaseException) -> str:
    """The simple class name of a Java exception (Chaquopy), else the Python one."""
    get_class = getattr(exc, "getClass", None)
    if callable(get_class):
        try:
            return str(get_class().getSimpleName())
        except Exception:
            pass
    return type(exc).__name__


def _ref(data: Any) -> DocumentRef:
    return DocumentRef(id=str(data["id"]), display_name=str(data["display_name"]),
                       location=str(data["location"]))


class AndroidDocumentStore:
    """:class:`session.documents.DocumentStore` backed by Kotlin's store."""

    def __init__(self, bridge: Any, max_recent: Callable[[], int] = lambda: 10) -> None:
        """Wrap ``bridge``.

        Args:
            bridge: The Kotlin ``DocumentStoreBridge``.
            max_recent: The configured recent-list length (read again before
                each ``add_recent``, so a Settings change takes effect).
        """
        self._bridge = bridge
        self._max_recent = max_recent
        self._sent_max: Optional[int] = None
        self.sync_max_recent()

    def sync_max_recent(self) -> None:
        """Tell Kotlin the recent list's cap if it changed."""
        try:
            count = int(self._max_recent())
        except Exception:
            logger.exception("Couldn't read max_recent_files")
            return
        if count != self._sent_max:
            self._call(self._bridge.setMaxRecent, count)
            self._sent_max = count

    def ref_for(self, document_id: str) -> Optional[DocumentRef]:
        """The ref for a content URI, or None if it can't be reached."""
        data = self._call(self._bridge.describe, document_id)
        return _ref(json.loads(str(data))) if data is not None else None

    def read_text(self, ref: DocumentRef) -> str:
        """Read a song, normalized for the editor."""
        return normalize_song_text(str(self._call(self._bridge.readText, ref.id)))

    def write_text(self, ref: DocumentRef, text: str) -> None:
        """Write a song."""
        self._call(self._bridge.writeText, ref.id, text)

    def write_bytes(self, ref: DocumentRef, data: bytes) -> None:
        """Write an export (Chaquopy passes ``bytes`` as a Java ``byte[]``)."""
        self._call(self._bridge.writeBytes, ref.id, bytes(data))

    def is_available(self, ref: DocumentRef) -> bool:
        """Whether the grant is still held and the provider has the document."""
        try:
            return bool(self._bridge.isAvailable(ref.id))
        except Exception as e:
            logger.warning("isAvailable(%s) failed: %s", ref.location, _message(e))
            return False

    def recent(self) -> List[DocumentRef]:
        """The recent list (Kotlin prunes unavailable documents)."""
        try:
            items = json.loads(str(self._bridge.recent()))
            return [_ref(item) for item in items]
        except Exception as e:
            logger.error("Couldn't read the recent list: %s", _message(e))
            return []

    def add_recent(self, ref: DocumentRef) -> None:
        """Move ``ref`` to the front of the recent list."""
        self.sync_max_recent()
        self._call(self._bridge.addRecent, ref.id, ref.display_name, ref.location)

    def rename(self, ref: DocumentRef, display_name: str) -> DocumentRef:
        """Rename the document (``DocumentsContract.renameDocument``).

        The provider may change the id and adjust the name (``song (1).txt``
        rather than replace another document); Kotlin moves the recent-list
        entry to the new ref.

        Raises:
            RenameNotSupported: The provider can't rename it.
            FileOperationError: Anything else, with Kotlin's message.
        """
        try:
            data = self._bridge.rename(ref.id, display_name)
        except Exception as e:
            if _java_name(e) == RENAME_UNSUPPORTED:
                raise RenameNotSupported(_message(e)) from e
            raise FileOperationError(_message(e)) from e
        return _ref(json.loads(str(data)))

    @staticmethod
    def _call(method: Callable[..., Any], *args: Any) -> Any:
        try:
            return method(*args)
        except FileOperationError:
            raise
        except Exception as e:
            raise FileOperationError(_message(e)) from e
