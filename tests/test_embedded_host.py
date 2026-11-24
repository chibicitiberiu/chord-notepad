"""``session.embedded_host`` and ``session.callback_store`` as iOS's Swift host uses them.

The Swift side hands Python a plain callbacks object and an event sink; here
both are Python objects, and ``CN_TEST_FAKE_PLAYER`` stands in for FluidSynth.
Android's use of the same code is in ``test_android_host.py``.
"""

import json
import threading

import pytest

from chordnotepad.exceptions import FileOperationError, RenameNotSupported
from chordnotepad.session import embedded_host, errors
from chordnotepad.session.callback_store import CallbackDocumentStore
from chordnotepad.session.documents import DocumentRef
from chordnotepad.session.platform import ANDROID, IOS
from chordnotepad.session.testing import FakePlayer

DOC = "bookmark:song"


class SwiftStore:
    """The callbacks a Swift host provides, over a dict, raising plain Python errors."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.recent_ids = []
        self.max_recent = None

    @staticmethod
    def _ref(doc_id):
        name = doc_id.rsplit(":", 1)[-1] + ".txt"
        return {"id": doc_id, "display_name": name, "location": f"On My iPad/{name}"}

    def readBytes(self, doc_id):
        if doc_id not in self.docs:
            raise OSError(f"Couldn't open {doc_id}")
        return self.docs[doc_id]

    def writeBytes(self, doc_id, data):
        self.docs[doc_id] = data

    def copyFromFile(self, doc_id, path):
        with open(path, "rb") as f:
            self.docs[doc_id] = f.read()

    def isAvailable(self, doc_id):
        return doc_id in self.docs

    def describe(self, doc_id):
        return json.dumps(self._ref(doc_id)) if doc_id in self.docs else None

    def recent(self):
        return json.dumps([self._ref(d) for d in self.recent_ids if d in self.docs])

    def addRecent(self, doc_id, display_name, location):
        self.recent_ids = [doc_id] + [d for d in self.recent_ids if d != doc_id]

    def setMaxRecent(self, count):
        self.max_recent = count

    def rename(self, doc_id, display_name):
        if doc_id.endswith("locked"):
            raise RenameNotSupported("iCloud can't rename this one.")
        raise RuntimeError("Disk full")


class Sink:
    def __init__(self):
        self.events = []
        self.cond = threading.Condition()
        self.threads = set()

    def onEvent(self, type_name, payload):
        with self.cond:
            self.threads.add(threading.current_thread().name)
            self.events.append((type_name, json.loads(payload)))
            self.cond.notify_all()

    def wait_for(self, type_name, where=lambda d: True, timeout=15):
        def find():
            return next((d for n, d in self.events if n == type_name and where(d)), None)
        with self.cond:
            assert self.cond.wait_for(lambda: find() is not None, timeout), self.events
            return find()


# -- CallbackDocumentStore -----------------------------------------------------------


def test_callback_store_maps_python_failures_and_rename():
    store = CallbackDocumentStore(SwiftStore({DOC: b"C\r\nG\n", "locked": b""}), max_recent=lambda: 4)
    ref = store.ref_for(DOC)
    assert ref == DocumentRef(DOC, "song.txt", "On My iPad/song.txt")
    assert store.read_text(ref) == "C\nG\n"
    with pytest.raises(FileOperationError, match=r"^Couldn't open bookmark:gone$"):
        store.read_text(DocumentRef("bookmark:gone", "gone.txt", "gone"))
    with pytest.raises(RenameNotSupported, match="iCloud"):
        store.rename(store.ref_for("locked"), "x.txt")
    with pytest.raises(FileOperationError, match=r"^Disk full$") as raised:
        store.rename(ref, "x.txt")
    assert not isinstance(raised.value, RenameNotSupported)


# -- start(platform=IOS) -------------------------------------------------------------


@pytest.fixture
def ios(tmp_path):
    store, sink = SwiftStore({DOC: b"{bpm: 90}\nC G Am F\n"}), Sink()
    previous_handler = errors.get_handler()
    handle = embedded_host.start(
        platform=IOS, files_dir=str(tmp_path), document_store=store, event_sink=sink,
        player=FakePlayer(), configure_logging=False)
    yield handle, store, sink, tmp_path
    handle.shutdown()
    assert errors.get_handler() is previous_handler


def test_ios_session_reaches_its_first_state_and_runs_commands(ios):
    handle, store, sink, tmp_path = ios
    sink.wait_for("EditorState")
    assert sink.threads == {"python-session"}
    assert handle.session._platform == IOS
    assert handle.services.playback is not None  # the iOS self-test's audio status reads it
    handle.submit("set_text", json.dumps({"text": "C Am", "client_token": 3}))
    state = sink.wait_for("HighlightState", lambda d: d["client_token"] == 3 and d["spans"])
    assert [s["kind"] for s in state["spans"]] == ["chord", "chord"]
    assert (tmp_path / "config" / "chord-notepad").is_dir()


def test_ios_opens_and_saves_through_the_callbacks(ios):
    handle, store, sink, _ = ios
    ref = SwiftStore._ref(DOC)
    handle.submit("open_document", json.dumps({"ref": ref}))
    sink.wait_for("DocumentState", lambda d: d["document_id"] == DOC)
    assert sink.wait_for("ToolbarState", lambda d: d["bpm"] == 90)
    assert store.recent_ids == [DOC]
    handle.submit("insert_text", json.dumps({"at": 0, "text": "Dm "}))
    handle.submit("save", "{}")
    handle.host.call(lambda: None, timeout=15)
    assert store.docs[DOC] == b"Dm {bpm: 90}\nC G Am F\n"


def test_ios_player_status_is_the_position_like_androids(ios):
    handle, _, sink, _ = ios
    handle.submit("set_text", json.dumps({"text": "C G\nAm F", "client_token": 1}))
    sink.wait_for("PlaybackState", lambda d: d["playhead_offset"] == 0)
    # Desktop would say "Playing 2 chords..."; the mobile players say "Starting…".
    handle.submit("play_pause", "{}")
    assert sink.wait_for("StatusState", lambda d: d["text"] == "Starting…")


def test_a_plain_callable_works_as_the_sink_and_the_env_switch_gives_a_fake_player(
        tmp_path, monkeypatch):
    monkeypatch.setenv(embedded_host.FAKE_PLAYER_ENV, "1")
    seen = []
    cond = threading.Condition()

    def sink(type_name, payload):
        with cond:
            seen.append(type_name)
            cond.notify_all()

    handle = embedded_host.start(platform=IOS, files_dir=str(tmp_path), document_store=SwiftStore(),
                                 event_sink=sink, configure_logging=False)
    try:
        with cond:
            assert cond.wait_for(lambda: "EditorState" in seen, 15), seen
        assert isinstance(handle._services.playback._player, FakePlayer)
    finally:
        handle.shutdown()


def test_start_refuses_an_unknown_platform(tmp_path):
    with pytest.raises(ValueError):
        embedded_host.start(platform="unknown", files_dir=str(tmp_path), document_store=SwiftStore(),
                            event_sink=Sink(), player=FakePlayer(), configure_logging=False)


def test_android_wrapper_keeps_its_platform_and_options():
    from chordnotepad_android import host as android_host

    assert android_host.SessionHandle is embedded_host.SessionHandle
    assert android_host.OBOE_SETTINGS["audio.oboe.performance-mode"] == "LowLatency"
    assert ANDROID != IOS
