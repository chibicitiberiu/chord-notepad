"""The Android host module (``chordnotepad_android``) with Kotlin faked in Python.

``host.start`` is what Kotlin's PyHost calls through Chaquopy; here the
Kotlin ``DocumentStoreBridge`` and ``EventSink`` are plain Python objects with
the same method names, and a FakePlayer stands in for FluidSynth.
"""

import json
import sys
import threading
from pathlib import Path

import pytest

from exceptions import FileOperationError
from session import errors
from session.documents import DocumentRef

ANDROID_PYTHON = Path(__file__).parent.parent / "android" / "app" / "src" / "main" / "python"
sys.path.insert(0, str(ANDROID_PYTHON))

from chordnotepad_android import host as android_host  # noqa: E402
from chordnotepad_android.android_store import AndroidDocumentStore  # noqa: E402
from session.testing import FakePlayer  # noqa: E402


class DocumentStoreException(Exception):
    """Like a Java exception through Chaquopy: the message is getMessage()."""

    def __init__(self, message):
        super().__init__(f"io.github...DocumentStoreException: {message}")
        self._message = message

    def getMessage(self):
        return self._message


class FakeKotlinStore:
    """The Kotlin DocumentStoreBridge's methods, over a dict keyed by URI."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.recent_list = []
        self.max_recent = None
        self.calls = []

    def _ref(self, uri):
        name = uri.rsplit("/", 1)[-1]
        return {"id": uri, "display_name": name, "location": f"Documents/{name}"}

    def readText(self, uri):
        self.calls.append(("readText", uri))
        if uri not in self.docs:
            raise DocumentStoreException(f"File not found: {uri}")
        return self.docs[uri]

    def writeText(self, uri, text):
        if uri.endswith("readonly.txt"):
            raise DocumentStoreException("Permission denied: readonly.txt")
        self.docs[uri] = text

    def writeBytes(self, uri, data):
        assert isinstance(data, bytes)
        self.docs[uri] = data

    def isAvailable(self, uri):
        return uri in self.docs

    def recent(self):
        return json.dumps([self._ref(u) for u in self.recent_list if u in self.docs])

    def addRecent(self, uri, display_name, location):
        self.calls.append(("addRecent", uri, display_name, location))
        self.recent_list = [uri] + [u for u in self.recent_list if u != uri]
        del self.recent_list[self.max_recent or 10:]

    def setMaxRecent(self, count):
        self.max_recent = count

    def describe(self, uri):
        return json.dumps(self._ref(uri)) if uri in self.docs else None


class FakeSink:
    def __init__(self):
        self.events = []
        self.cond = threading.Condition()

    def onEvent(self, type_name, payload):
        with self.cond:
            self.events.append((type_name, json.loads(payload)))
            self.cond.notify_all()

    def wait_for(self, type_name, where=lambda d: True, timeout=15):
        def find():
            return next((d for n, d in self.events if n == type_name and where(d)), None)
        with self.cond:
            assert self.cond.wait_for(lambda: find() is not None, timeout), self.events
            return find()


URI = "content://com.android.providers.downloads/document/song.txt"


# -- AndroidDocumentStore --------------------------------------------------------------


def test_store_normalizes_reads_and_maps_java_failures():
    kotlin = FakeKotlinStore({URI: "C\r\nG Am\n"})
    store = AndroidDocumentStore(kotlin, max_recent=lambda: 7)
    assert kotlin.max_recent == 7
    ref = store.ref_for(URI)
    assert ref == DocumentRef(URI, "song.txt", "Documents/song.txt")
    assert store.read_text(ref) == "C\nG Am\n"
    with pytest.raises(FileOperationError, match=r"^File not found: content://x$"):
        store.read_text(DocumentRef("content://x", "x", "x"))
    with pytest.raises(FileOperationError, match=r"^Permission denied: readonly.txt$"):
        store.write_text(DocumentRef("content://readonly.txt", "readonly.txt", "r"), "C")
    assert store.ref_for("content://missing") is None


def test_store_writes_and_keeps_the_recent_list():
    kotlin = FakeKotlinStore({URI: "C"})
    limit = [2]
    store = AndroidDocumentStore(kotlin, max_recent=lambda: limit[0])
    ref = store.ref_for(URI)
    store.write_text(ref, "D")
    store.write_bytes(DocumentRef("content://x/a.mid", "a.mid", "a.mid"), b"MThd")
    assert kotlin.docs == {URI: "D", "content://x/a.mid": b"MThd"}
    assert store.is_available(ref)
    store.add_recent(ref)
    assert store.recent() == [ref]
    limit[0] = 5
    store.add_recent(ref)
    assert kotlin.max_recent == 5


def test_store_survives_a_broken_recent_list():
    kotlin = FakeKotlinStore()
    kotlin.recent = lambda: "not json"
    kotlin.isAvailable = lambda uri: (_ for _ in ()).throw(DocumentStoreException("gone"))
    store = AndroidDocumentStore(kotlin)
    assert store.recent() == []
    assert store.is_available(DocumentRef("a", "b", "c")) is False


# -- host.start ------------------------------------------------------------------------


@pytest.fixture
def started(tmp_path):
    kotlin = FakeKotlinStore({URI: "{bpm: 100}\nC G Am F\n"})
    sink = FakeSink()
    previous_handler = errors.get_handler()
    handle = android_host.start(
        str(tmp_path), "/data/app/lib", kotlin, sink,
        {"sample_rate": 48000, "frames_per_buffer": 192, "soundfont_path": ""},
        player=FakePlayer(), configure_logging=False)
    yield handle, kotlin, sink, tmp_path
    handle.shutdown()
    assert errors.get_handler() is previous_handler


def test_start_replays_the_states_and_runs_commands(started):
    handle, _, sink, tmp_path = started
    sink.wait_for("DocumentState")
    assert sink.events[0][0] == "HighlightState"
    handle.submit("set_text", json.dumps({"text": "C Am", "client_token": 5}))
    state = sink.wait_for("HighlightState", lambda d: d["client_token"] == 5 and d["spans"])
    assert [s["kind"] for s in state["spans"]] == ["chord", "chord"]
    assert (tmp_path / "config" / "chord-notepad").is_dir()
    assert (tmp_path / "data" / "chord-notepad").is_dir()


def test_open_a_content_uri_and_save(started):
    handle, kotlin, sink, _ = started
    ref = {"id": URI, "display_name": "song.txt", "location": "Documents/song.txt"}
    handle.submit("open_document", json.dumps({"ref": ref}))
    sink.wait_for("DocumentState", lambda d: d["document_id"] == URI)
    edit = sink.wait_for("TextEdited")
    assert edit["replacement"] == "{bpm: 100}\nC G Am F\n" and edit["undo"] == "reset"
    assert sink.wait_for("ToolbarState", lambda d: d["bpm"] == 100)
    assert ("addRecent", URI, "song.txt", "Documents/song.txt") in kotlin.calls
    handle.submit("insert_text", json.dumps({"at": 0, "text": "Dm "}))
    handle.submit("save", "{}")
    handle.host.call(lambda: None, timeout=15)  # everything submitted has run
    assert sink.events[-1][0] in ("DocumentState", "StatusState")
    assert [d for n, d in sink.events if n == "DocumentState"][-1]["is_modified"] is False
    assert kotlin.docs[URI] == "Dm {bpm: 100}\nC G Am F\n"


def test_failures_and_unknown_commands_are_events(started):
    handle, _, sink, _ = started
    ref = {"id": "content://gone", "display_name": "gone.txt", "location": "gone.txt"}
    handle.submit("open_document", json.dumps({"ref": ref}))
    error = sink.wait_for("UserError")
    assert "File not found: content://gone" in error["message"]
    handle.submit("frobnicate", "{}")
    assert sink.wait_for("UnexpectedError")["context"] == "bridge"


def test_errors_on_the_session_thread_reach_the_sink(started):
    handle, _, sink, _ = started

    def boom():
        raise RuntimeError("oops")

    handle.host.post(boom)
    error = sink.wait_for("UnexpectedError")
    assert error == {"message": "RuntimeError: oops", "context": "session thread callback"}


def test_lifecycle_commands(started):
    handle, _, sink, tmp_path = started
    handle.submit("set_bpm", json.dumps({"bpm": 133.0}))
    handle.submit("app_background", "{}")
    handle.submit("app_foreground", "{}")
    handle.submit("pause", "{}")
    handle.submit("restore_draft", json.dumps(
        {"text": "G D\n", "document": None, "modified": True}))
    sink.wait_for("DocumentState", lambda d: d["is_modified"] and d["document_id"] is None)
    config = json.loads((tmp_path / "config" / "chord-notepad" / "settings.json").read_text())
    assert config["bpm"] == 133
    assert not [e for e in sink.events if e[0] == "UnexpectedError"]


def test_shutdown_saves_the_config_and_stops_the_thread(tmp_path):
    sink = FakeSink()
    handle = android_host.start(str(tmp_path), "", FakeKotlinStore(), sink, {},
                                player=FakePlayer(), configure_logging=False)
    handle.submit("set_font", json.dumps({"family": "Serif", "size": 14}))
    sink.wait_for("EditorState", lambda d: d["font_size"] == 14)
    handle.shutdown()
    handle.shutdown()  # twice is fine
    assert not handle.host.is_running
    config = json.loads((tmp_path / "config" / "chord-notepad" / "settings.json").read_text())
    assert (config["font_family"], config["font_size"]) == ("Serif", 14)
    count = len(sink.events)
    handle.submit("stop", "{}")  # after shutdown: dropped
    assert len(sink.events) == count


def test_audio_options_from_kotlins_dict():
    options = android_host.audio_options_from(
        {"sample_rate": 48000, "frames_per_buffer": 192, "soundfont_path": "/x.sf2"})
    assert (options.sample_rate, options.period_size) == (48000, 192)
    assert options.settings["audio.oboe.performance-mode"] == "LowLatency"
    defaults = android_host.audio_options_from({})
    assert (defaults.sample_rate, defaults.period_size) == (None, None)


def test_chord_sheet_buffer_is_packed_on_the_callers_thread(started):
    from chord_sheet.pack import unpack

    handle, _, sink, _ = started
    assert handle.chord_sheet_buffer(120) is None  # nothing rendered yet
    handle.submit("set_chord_sheet_visible", json.dumps({"visible": True}))
    handle.submit("set_text", json.dumps({"text": "C G Am F", "client_token": 1}))
    sink.wait_for("ChordSheetState", lambda d: d["visible"] and d["song_revision"] > 0)
    data = handle.chord_sheet_buffer(120.0)
    assert isinstance(data, bytes) and data
    assert unpack(data) is not None
    # Another view, from the state's list.
    state = [d for n, d in sink.events if n == "ChordSheetState"][-1]
    other = next(v["view_id"] for v in state["views"]
                 if v["available"] and v["view_id"] != state["active_view"])
    handle.submit("set_chord_sheet_view", json.dumps({"view_id": other}))
    sink.wait_for("ChordSheetState", lambda d: d["active_view"] == other)
    assert handle.chord_sheet_buffer(120.0) != data


def test_chord_sheet_buffer_failures_are_reported_not_raised(started):
    handle, _, sink, _ = started
    handle.session._sheet_snapshot = (object(), "keyboard", 1.0, ())
    assert handle.chord_sheet_buffer(100) is None
    assert sink.wait_for("UnexpectedError")["context"] == "chord_sheet_buffer"
