"""Renaming the open document (Android's title → Rename), and Save As a name.

The session over an InMemoryDocumentStore, plus the desktop file store's
rename on real files.
"""

import os

import pytest

from exceptions import FileOperationError
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session.documents import FileSystemDocumentStore
from session.events import PickDocumentRequest, RenameFailed
from session.host import HostDispatch
from session.session import AppSession
from session.state import DocumentState, RecentDocumentsState, StatusState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


class FakeConfig:
    def __init__(self, **values):
        self._values = dict(values)

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class Env:
    def __init__(self, documents=None):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        config = FakeConfig()
        audio = PlaybackService(config, player=FakePlayer(auto_play=False), application=dispatch)
        self.store = InMemoryDocumentStore(
            {"song.txt": "C G"} if documents is None else documents)
        parser = SongParserService()
        self.main = MainWindowViewModel(config, audio, self.store, parser, dispatch)
        self.session = AppSession(self.host, main_window_viewmodel=self.main,
                                  text_editor_viewmodel=TextEditorViewModel(parser))
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()

    def open(self, name="song.txt"):
        self.session.open_document(InMemoryDocumentStore.ref(name))
        self.recorder.clear()

    def document(self):
        return self.recorder.last(DocumentState)

    def failure(self):
        return self.recorder.last(RenameFailed)


def test_rename_keeps_the_extension_and_follows_the_document():
    env = Env()
    env.open()
    env.session.set_text("C G Am")  # unsaved changes survive a rename
    env.session.rename_document("  My song ")
    assert "memory:My song.txt" in env.store.contents
    assert "memory:song.txt" not in env.store.contents
    state = env.document()
    assert (state.display_name, state.document_id, state.is_modified) == (
        "My song.txt", "memory:My song.txt", True)
    assert state.title == "My song.txt* - Chord Notepad"
    recent = env.recorder.last(RecentDocumentsState).items
    assert [r.display_name for r in recent] == ["My song.txt"]
    assert env.recorder.last(StatusState).text == "Renamed to My song.txt"
    # Saving writes the renamed document.
    env.session.save()
    assert env.store.contents["memory:My song.txt"] == "C G Am"


def test_a_name_that_already_ends_with_the_extension_isnt_doubled():
    env = Env()
    env.open()
    env.session.rename_document("Other.TXT")
    assert env.document().display_name == "Other.TXT"


def test_renaming_to_the_same_name_does_nothing():
    env = Env()
    env.open()
    env.session.rename_document("song")
    assert env.recorder.items == []


@pytest.mark.parametrize("name, reason", [
    ("", "Please enter a name."),
    ("   ", "Please enter a name."),
    ("a/b", "A name can't contain / or \\."),
    ("a\\b", "A name can't contain / or \\."),
    ("..", "That name isn't allowed."),
    ("a\tb", "A name can't contain control characters."),
    ("x" * 300, "That name is too long."),
])
def test_invalid_names_are_refused_without_save_as(name, reason):
    env = Env()
    env.open()
    env.session.rename_document(name)
    assert env.failure() == RenameFailed(name, reason, False)
    assert env.document() is None  # nothing changed


def test_a_name_in_use_is_refused_with_save_as_offered():
    env = Env({"song.txt": "C", "taken.txt": "G"})
    env.open()
    env.session.rename_document("taken")
    assert env.failure() == RenameFailed(
        "taken", "A file named taken.txt already exists there.", True)
    assert env.store.contents["memory:taken.txt"] == "G"


def test_storage_that_cant_rename_offers_save_as_under_the_name():
    env = Env()
    env.open()
    env.store.can_rename = False
    env.session.rename_document("New name")
    assert env.failure() == RenameFailed(
        "New name", "This storage can't rename documents.", True)
    env.session.save_as("New name")
    request = env.recorder.last(PickDocumentRequest)
    assert request.suggested_name == "New name.txt"
    env.session.respond(request.request_id, InMemoryDocumentStore.ref("New name.txt"))
    assert env.document().display_name == "New name.txt"


def test_save_as_refuses_a_bad_name():
    env = Env()
    with pytest.raises(ValueError):
        env.session.save_as("a/b")


def test_an_untitled_document_takes_the_name_when_first_saved():
    env = Env(documents={})
    env.session.rename_document("Draft")
    state = env.document()
    assert (state.display_name, state.document_id, state.title) == (
        "Draft.txt", None, "Draft.txt - Chord Notepad")
    assert env.recorder.last(StatusState).text == "Renamed to Draft.txt"
    env.session.save()
    request = env.recorder.last(PickDocumentRequest)
    assert request.suggested_name == "Draft.txt"
    env.session.respond(request.request_id, InMemoryDocumentStore.ref("Draft.txt"))
    # Saved: the name is the document's now; New forgets it.
    assert env.session._pending_name is None
    env.session.new_document()
    assert env.document().display_name == "Untitled"


def test_new_document_forgets_a_pending_name():
    env = Env(documents={})
    env.session.rename_document("Draft")
    env.session.new_document()
    assert env.document().display_name == "Untitled"
    env.session.save()
    assert env.recorder.last(PickDocumentRequest).suggested_name == "Untitled.txt"


# -- the desktop file store ---------------------------------------------------------


@pytest.fixture
def files(tmp_path):
    from services.file_service import FileService

    return FileSystemDocumentStore(FileService(FakeConfig()))


def test_file_store_renames_in_place(files, tmp_path):
    path = tmp_path / "song.txt"
    path.write_text("C G")
    ref = files.ref_for_path(path)
    new = files.rename(ref, "tune.txt")
    assert new == files.ref_for_path(tmp_path / "tune.txt")
    assert (tmp_path / "tune.txt").read_text() == "C G"
    assert not path.exists()


def test_file_store_refuses_to_replace_a_file(files, tmp_path):
    (tmp_path / "song.txt").write_text("C")
    (tmp_path / "tune.txt").write_text("G")
    with pytest.raises(FileOperationError, match="A file named tune.txt already exists"):
        files.rename(files.ref_for_path(tmp_path / "song.txt"), "tune.txt")
    assert (tmp_path / "tune.txt").read_text() == "G"


def test_file_store_case_only_rename(files, tmp_path):
    (tmp_path / "song.txt").write_text("C")
    new = files.rename(files.ref_for_path(tmp_path / "song.txt"), "Song.txt")
    assert os.listdir(tmp_path) == ["Song.txt"]
    assert new.display_name == "Song.txt"


def test_file_store_missing_file(files, tmp_path):
    with pytest.raises(FileOperationError, match="File not found"):
        files.rename(files.ref_for_path(tmp_path / "gone.txt"), "x.txt")
