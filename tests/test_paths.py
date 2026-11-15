"""chordnotepad.utils.paths: the extension rule and the names of portal paths.

The Qt file pickers (``chordnotepad_desktop/files.py``) and the document
store (``session/documents.py``) use these. They were tested through the Tk
file dialogs' re-exports until the Tk front end went.
"""

import os
from pathlib import Path

import pytest

from chordnotepad.utils import paths


@pytest.mark.parametrize(
    "path, ext, expected",
    [
        ("/home/me/song", ".txt", "/home/me/song.txt"),
        ("/home/me/song", "txt", "/home/me/song.txt"),
        ("/home/me/song.cho", ".txt", "/home/me/song.cho"),
        ("/home/me/song.mid", ".mid", "/home/me/song.mid"),
        ("/home/my.dir/song", ".txt", "/home/my.dir/song.txt"),
        ("/home/me/song", "", "/home/me/song"),
        ("", ".txt", ""),
    ],
)
def test_apply_default_extension(path, ext, expected):
    assert paths.apply_default_extension(path, ext) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/run/user/1000/doc/3f2a91bc/My Song.txt",
        "/run/flatpak/doc/3f2a91bc/My Song.txt",
        Path("/run/user/1000/doc/3f2a91bc/My Song.txt"),
    ],
)
def test_document_portal_paths_show_their_file_name(path):
    assert paths.is_document_portal_path(path)
    assert paths.display_path(path) == "My Song.txt"


@pytest.mark.parametrize("path", ["/home/me/My Song.txt", "relative/song.txt",
                                  "/run/user/1000/other/x.txt"])
def test_other_paths_are_shown_as_they_are(path):
    assert not paths.is_document_portal_path(path)
    assert paths.display_path(path) == path
    assert paths.display_path(Path(path)) == str(Path(path))
    assert paths.display_path(os.path.join("home", "a.txt")) == os.path.join("home", "a.txt")
