"""Documents as opaque references, so the core never handles platform paths.

On desktop a document is a file path; on Android it will be a content URI that
only the platform can open. :class:`DocumentRef` carries what the core needs
(an id to hand back to the store, a name for titles, a location for messages)
and :class:`DocumentStore` does the reading and writing.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, Union

from utils.paths import display_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentRef:
    """A document the user picked.

    Attributes:
        id: Opaque to the core; only the store that made it interprets it
            (an absolute path on desktop, a content URI on Android).
        display_name: File name for titles and the Save As suggestion,
            e.g. ``"song.txt"``.
        location: User-facing place, for status and error messages.
    """

    id: str
    display_name: str
    location: str

    @property
    def stem(self) -> str:
        """The name without its extension (used as the MIDI title)."""
        return os.path.splitext(self.display_name)[0]


class DocumentStore(Protocol):
    """Reads and writes documents and keeps the recent-documents list.

    Reading and writing never touch the recent list: the session's document
    flows decide what joins it (opened and saved songs, not exports).
    """

    def ref_for(self, document_id: str) -> DocumentRef:
        """The reference for a document id, e.g. what a file picker returned
        (desktop: a path; Android: a content URI)."""
        ...

    def read_text(self, ref: DocumentRef) -> str:
        """Read a song, normalized for the editor.

        Raises:
            FileOperationError: With a user-facing reason.
        """
        ...

    def write_text(self, ref: DocumentRef, text: str) -> None:
        """Write a song.

        Raises:
            FileOperationError: With a user-facing reason.
        """
        ...

    def write_bytes(self, ref: DocumentRef, data: bytes) -> None:
        """Write an export.

        Raises:
            FileOperationError: With a user-facing reason.
        """
        ...

    def is_available(self, ref: DocumentRef) -> bool:
        """Whether the document can still be opened."""
        ...

    def recent(self) -> List[DocumentRef]:
        """Recently used documents that are still available, newest first.

        Documents that are no longer available are dropped from the list.
        """
        ...

    def add_recent(self, ref: DocumentRef) -> None:
        """Move ``ref`` to the front of the recent list (capped in length)."""
        ...


class FileSystemDocumentStore:
    """:class:`DocumentStore` over local files, delegating to ``FileService``.

    ``FileService`` keeps doing the work it did before: text normalization on
    read, pruning missing files from the recent list, and the error messages.
    """

    def __init__(self, file_service) -> None:
        """Create the store.

        Args:
            file_service: The ``FileService`` that does the file I/O.
        """
        self._files = file_service

    def ref_for_path(self, path: Union[str, "os.PathLike[str]"]) -> DocumentRef:
        """Make a reference to a local file, e.g. one a file picker returned.

        The id is the absolute path, not ``resolve()``-d: resolving would
        rewrite symlinks and mapped network drives in what the user sees.
        """
        absolute = os.path.abspath(os.fspath(path))
        return DocumentRef(
            id=absolute,
            display_name=os.path.basename(absolute),
            location=display_path(absolute),
        )

    def ref_for(self, document_id: str) -> DocumentRef:
        """:meth:`ref_for_path` for a path given as the id."""
        return self.ref_for_path(document_id)

    def read_text(self, ref: DocumentRef) -> str:
        """Read a song through ``FileService.open_file``."""
        return self._files.open_file(Path(ref.id))

    def write_text(self, ref: DocumentRef, text: str) -> None:
        """Write a song through ``FileService.save_file``."""
        self._files.save_file(Path(ref.id), text)

    def write_bytes(self, ref: DocumentRef, data: bytes) -> None:
        """Write an export through ``FileService.save_bytes``."""
        self._files.save_bytes(Path(ref.id), data)

    def is_available(self, ref: DocumentRef) -> bool:
        """Whether the file still exists."""
        return self._files.file_exists(Path(ref.id))

    def recent(self) -> List[DocumentRef]:
        """The recent-files list (missing files already pruned) as refs."""
        return [self.ref_for_path(p) for p in self._files.get_recent_files()]

    def add_recent(self, ref: DocumentRef) -> None:
        """Add the file to the front of the recent-files list."""
        self._files.add_recent_file(Path(ref.id))
