"""Recent files with the same name told apart by their folder (Q11, plan step B3).

The Tk menu shows names only (two song.txt look the same); the Qt menu uses
formatting.recent_file_labels.
"""

import pytest

from chordnotepad.session import formatting
from chordnotepad.session.documents import DocumentRef, FileSystemDocumentStore


def ref(location, name=None):
    name = name or location.replace("\\", "/").rsplit("/", 1)[-1]
    return DocumentRef(id=location, display_name=name, location=location)


def folders(*locations):
    return formatting.recent_file_folders([ref(loc) for loc in locations])


def test_unique_names_get_no_folder():
    assert folders("/home/t/a.txt", "/home/t/b.txt") == ("", "")
    assert formatting.recent_file_folders([]) == ()


def test_the_nearest_folder_that_differs():
    assert folders("/home/t/Music/Band/song.txt", "/home/t/Music/Solo/song.txt",
                   "/home/t/other.txt") == ("Band", "Solo", "")


def test_as_many_folders_as_it_takes_each():
    assert folders("/x/A/Band/song.txt", "/x/B/Band/song.txt", "/x/B/Solo/song.txt") == (
        "A/Band", "B/Band", "Solo")


def test_names_that_differ_only_in_case_look_the_same():
    assert folders("/a/song.txt", "/b/Song.TXT") == ("a", "b")


def test_a_folder_inside_the_other_and_the_root():
    assert folders("/home/song.txt", "/home/t/song.txt") == ("home", "t")
    assert folders("/song.txt", "/home/song.txt") == ("/", "home")


def test_windows_paths_keep_their_separator():
    assert folders("C:\\Users\\t\\Songs\\song.txt", "C:\\Users\\u\\Songs\\song.txt") == (
        "t\\Songs", "u\\Songs")
    assert folders("C:\\Users\\t\\song.txt", "D:\\song.txt") == ("t", "D:")


def test_home_shortened_locations():
    assert folders("~/Music/song.txt", "~/Downloads/song.txt") == ("Music", "Downloads")


def test_a_location_without_folders():
    refs = [DocumentRef("content://1", "song.txt", "song.txt"),
            DocumentRef("content://2", "song.txt", "Drive")]
    assert formatting.recent_file_folders(refs) == ("", "Drive")


def test_menu_labels():
    refs = [ref("/m/Band/song.txt"), ref("/m/Solo/song.txt"), ref("/m/x.txt")]
    assert formatting.recent_file_labels(refs) == (
        "song.txt — Band", "song.txt — Solo", "x.txt")
    assert formatting.NO_RECENT_FILES == "(No recent files)"


def test_with_the_desktop_store_refs(tmp_path):
    store = FileSystemDocumentStore.__new__(FileSystemDocumentStore)
    a = tmp_path / "live" / "set.txt"
    b = tmp_path / "studio" / "set.txt"
    labels = formatting.recent_file_labels([store.ref_for_path(a), store.ref_for_path(b)])
    assert labels == ("set.txt — live", "set.txt — studio")
