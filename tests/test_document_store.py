"""DocumentRef / DocumentStore: the file-system store, the in-memory test
store, and MainWindowViewModel working on refs instead of paths."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from exceptions import FileOperationError
from services.config_service import ConfigService
from services.file_service import FileService
from services.song_parser_service import SongParserService
from session.documents import DocumentRef, FileSystemDocumentStore
from session.testing import InMemoryDocumentStore


class FakeConfig:
    def __init__(self, **values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def _fs(tmp_path, max_recent=10):
    config = FakeConfig(recent_files=[], max_recent_files=max_recent)
    return FileSystemDocumentStore(FileService(config)), config


# --------------------------------------------------------------------------
# DocumentRef
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name, stem", [
    ("song.txt", "song"),
    ("song", "song"),
    ("my.song.txt", "my.song"),
    (".hidden", ".hidden"),
])
def test_stem_matches_path_stem(name, stem):
    assert DocumentRef(id="x", display_name=name, location="x").stem == stem
    assert Path(name).stem == stem


def test_refs_are_frozen_and_compare_by_value():
    a = DocumentRef("id", "a.txt", "/a.txt")
    assert a == DocumentRef("id", "a.txt", "/a.txt")
    with pytest.raises(Exception):
        a.id = "other"


# --------------------------------------------------------------------------
# FileSystemDocumentStore
# --------------------------------------------------------------------------


def test_ref_for_path_is_absolute_with_name_and_location(tmp_path, monkeypatch):
    store, _ = _fs(tmp_path)
    monkeypatch.chdir(tmp_path)
    ref = store.ref_for_path("song.txt")
    assert ref.id == str(tmp_path / "song.txt")
    assert ref.display_name == "song.txt"
    assert ref.location == str(tmp_path / "song.txt")


def test_portal_paths_show_only_the_name():
    store = FileSystemDocumentStore(FileService(FakeConfig()))
    ref = store.ref_for_path("/run/user/1000/doc/abc123/My Song.txt")
    assert ref.location == "My Song.txt"
    assert ref.id == "/run/user/1000/doc/abc123/My Song.txt"


def test_text_round_trip_is_normalized_and_leaves_the_recent_list_alone(tmp_path):
    # The session's document flows keep the recent list, not reads and writes.
    store, config = _fs(tmp_path)
    ref = store.ref_for_path(tmp_path / "song.txt")
    store.write_text(ref, "C G\n")
    assert store.is_available(ref)
    assert store.read_text(ref) == "C G\n"   # non-breaking space cleaned up
    assert store.recent() == []
    store.add_recent(ref)
    assert store.recent() == [ref]
    assert config.values["recent_files"] == [str((tmp_path / "song.txt").resolve())]


def test_write_bytes_writes_exactly_and_is_not_recent(tmp_path):
    store, _ = _fs(tmp_path)
    ref = store.ref_for_path(tmp_path / "out.mid")
    store.write_bytes(ref, b"MThd\x00\x01")
    assert (tmp_path / "out.mid").read_bytes() == b"MThd\x00\x01"
    assert store.recent() == []


def test_missing_file_reason(tmp_path):
    store, _ = _fs(tmp_path)
    ref = store.ref_for_path(tmp_path / "nope.txt")
    assert not store.is_available(ref)
    with pytest.raises(FileOperationError, match="File not found.*nope.txt"):
        store.read_text(ref)


def test_write_bytes_failure_reason(tmp_path):
    store, _ = _fs(tmp_path)
    ref = store.ref_for_path(tmp_path / "missing-dir" / "out.mid")
    with pytest.raises(FileOperationError, match="Failed to write file"):
        store.write_bytes(ref, b"x")


def test_recent_prunes_missing_files_and_caps_length(tmp_path):
    store, config = _fs(tmp_path, max_recent=2)
    refs = []
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("C\n", encoding="utf-8")
        refs.append(store.ref_for_path(tmp_path / name))
        store.add_recent(refs[-1])
    assert [r.display_name for r in store.recent()] == ["c.txt", "b.txt"]

    (tmp_path / "c.txt").unlink()
    assert [r.display_name for r in store.recent()] == ["b.txt"]
    assert len(config.values["recent_files"]) == 1


def test_add_recent_moves_an_existing_entry_to_the_front(tmp_path):
    store, _ = _fs(tmp_path)
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
        store.add_recent(store.ref_for_path(tmp_path / name))
    store.add_recent(store.ref_for_path(tmp_path / "a.txt"))
    assert [r.display_name for r in store.recent()] == ["a.txt", "b.txt"]


# --------------------------------------------------------------------------
# InMemoryDocumentStore behaves like the file-system store
# --------------------------------------------------------------------------


def test_memory_store_contract():
    store = InMemoryDocumentStore({"song.txt": "C G\n"}, max_recent=2)
    song = store.ref("song.txt")
    assert store.is_available(song)
    assert store.read_text(song) == "C G\n"
    assert store.recent() == []
    store.add_recent(song)
    assert store.recent() == [song]

    out = store.ref("out.mid")
    store.write_bytes(out, b"MIDI")
    assert store.contents[out.id] == b"MIDI"
    assert store.recent() == [song]
    with pytest.raises(FileOperationError):
        store.read_text(out)

    missing = store.ref("nope.txt")
    with pytest.raises(FileOperationError, match="File not found: nope.txt"):
        store.read_text(missing)

    for name in ("a.txt", "b.txt"):
        store.write_text(store.ref(name), "")
        store.add_recent(store.ref(name))
    assert [r.display_name for r in store.recent()] == ["b.txt", "a.txt"]

    del store.contents[store.ref("b.txt").id]
    assert [r.display_name for r in store.recent()] == ["a.txt"]


# --------------------------------------------------------------------------
# MainWindowViewModel on refs
# --------------------------------------------------------------------------


def _viewmodel(store):
    from viewmodels.main_window_viewmodel import MainWindowViewModel

    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: {"notation": "american"}.get(key, default)
    return MainWindowViewModel(
        config_service=config,
        audio_service=MagicMock(),
        documents=store,
        song_parser_service=SongParserService(),
        application=MagicMock(),
    )


def test_open_sets_the_document_text():
    store = InMemoryDocumentStore({"song.txt": "{bpm: 90}\nC G\n"})
    vm = _viewmodel(store)
    seen = []
    vm.observe("current_document", seen.append)

    ref = store.ref("song.txt")
    assert vm.open_file(ref) is True
    assert vm.current_document == ref
    assert seen == [ref]
    assert vm.current_text == "{bpm: 90}\nC G\n"
    assert vm.bpm == 90
    assert store.recent() == []   # the session's flows add it


def test_failed_open_keeps_the_current_document():
    store = InMemoryDocumentStore({"song.txt": "C\n"})
    vm = _viewmodel(store)
    vm.open_file(store.ref("song.txt"))
    assert vm.open_file(store.ref("nope.txt")) is False
    assert vm.current_document == store.ref("song.txt")
    assert "nope.txt" in vm.last_error


def test_save_writes_to_the_current_document_and_save_as_switches():
    store = InMemoryDocumentStore({"song.txt": "C\n"})
    vm = _viewmodel(store)
    vm.open_file(store.ref("song.txt"))
    vm.on_text_changed("C G\n")
    assert vm.is_modified

    assert vm.save_file() is True
    assert store.contents[store.ref("song.txt").id] == "C G\n"
    assert not vm.is_modified

    copy = store.ref("copy.txt")
    vm.on_text_changed("Am\n")
    assert vm.save_file_as(copy) is True
    assert vm.current_document == copy
    assert store.contents[copy.id] == "Am\n"


def test_new_file_clears_the_document():
    store = InMemoryDocumentStore({"song.txt": "C\n"})
    vm = _viewmodel(store)
    vm.open_file(store.ref("song.txt"))
    vm.new_file()
    assert vm.current_document is None


def test_ref_for_an_id_is_the_ref_for_that_document(tmp_path):
    store, _ = _fs(tmp_path)
    path = str(tmp_path / "song.txt")
    assert store.ref_for(path) == store.ref_for_path(path)
    memory = InMemoryDocumentStore()
    assert memory.ref_for(memory.ref("a.txt").id) == memory.ref("a.txt")
    assert memory.ref_for("a.txt") == memory.ref("a.txt")


# --------------------------------------------------------------------------
# MIDI bytes and paths
# --------------------------------------------------------------------------


def test_render_midi_bytes_matches_the_file_writer(tmp_path):
    from models.notation import Notation
    from services.midi_file_writer import render_midi_bytes, write_midi_file
    from services.playback_service import PlaybackService

    config = FakeConfig(bpm=120, voicing="piano")
    lines = SongParserService().detect_chords_in_text("C G Am F\n", Notation.AMERICAN)
    rendered = PlaybackService(config_service=config, player=None).render_song(lines, None)

    data = render_midi_bytes(rendered, program=5, title="song")
    assert data.startswith(b"MThd")
    path = tmp_path / "song.mid"
    write_midi_file(rendered, path, program=5, title="song")
    assert path.read_bytes() == data


def test_file_dialogs_reexports_the_moved_path_helpers():
    from utils import file_dialogs, paths

    assert file_dialogs.display_path is paths.display_path
    assert file_dialogs.is_document_portal_path is paths.is_document_portal_path
    assert paths.display_path("/run/flatpak/doc/x/a.txt") == "a.txt"
    assert paths.display_path(os.path.join("home", "a.txt")) == os.path.join("home", "a.txt")


# The window turning picker paths into refs and the Recent Files menu are
# tested with the flows (tests/test_session_documents.py).
