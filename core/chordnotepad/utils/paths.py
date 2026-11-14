"""User-facing forms of file paths (Tk-free; shared by the core and the UI)."""

import os
import re
from typing import Union

# Where the XDG document portal mounts files it hands to a Flatpak.
_DOC_PORTAL_PATH_RE = re.compile(r"^/run/(?:user/\d+|flatpak)/doc/")


def display_path(path: Union[str, "os.PathLike[str]"]) -> str:
    """Return a user-facing form of a file path.

    Files handed to a Flatpak through the document portal live under
    ``/run/user/<uid>/doc/<id>/``, which means nothing to the user, so those
    are shown by file name only. Any other path is returned unchanged.

    Args:
        path: File path.

    Returns:
        The file name for document-portal paths, otherwise ``str(path)``.
    """
    text = os.fspath(path)
    if is_document_portal_path(text):
        return os.path.basename(text)
    return text


def is_document_portal_path(path: Union[str, "os.PathLike[str]"]) -> bool:
    """Check whether a path points into the document portal's FUSE mount.

    Args:
        path: File path.

    Returns:
        True for ``/run/user/<uid>/doc/...`` and ``/run/flatpak/doc/...`` paths.
    """
    return bool(_DOC_PORTAL_PATH_RE.match(os.fspath(path)))
