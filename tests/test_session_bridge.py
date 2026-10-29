"""The session over the bridge: encode, decode, dispatch, the schema.

The flows at the bottom run the way Android runs: a ThreadedHost session
thread, the core built by ``session.bootstrap``, and only strings in
(``SessionBridge.submit(command, args_json)``) and out (``sink(type_name,
json)``), with a silent FakePlayer and an in-memory document store.
"""

import dataclasses
import inspect
import json
import re
import threading
from enum import Enum
from pathlib import Path

import pytest

from services.appdata_service import AppDataService
from session import bridge, errors
from session.bootstrap import build_core_services, create_session
from session.bridge import (
    BridgeError, ErrorEvents, SessionBridge, decode_args, dispatch, encode, schema_json,
)
from session.documents import DocumentRef
from session.events import (
    CloseApproved, ConfirmDiscardRequest, DiscardChoice, PickDocumentRequest, PickMode,
    TextEdited, UndoPolicy, UnexpectedError,
)
from session.host import HostDispatch
from session.session import AppSession
from session.settings import SettingsValues
from session.state import (
    DocumentState, HighlightState, MenuItem, PlaybackState, PlaybackStatus, Span, SpanKind,
    VoicingMenuState,
)
from session.testing import FakePlayer, InMemoryDocumentStore
from session.threaded_host import ThreadedHost

ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "android" / "bridge_schema.json"
KOTLIN_COMMANDS = (ROOT / "android" / "app" / "src" / "main" / "kotlin" / "io" / "github"
                   / "chibicitiberiu" / "chordnotepad" / "bridge" / "SessionCommands.kt")

SONG = "{bpm: 90}\n{time: 3/4}\n{key: G}\nG D Em C\n"


# -- encode ------------------------------------------------------------------------


def test_encode_states_with_enums_tuples_and_nested_dtos():
    state = HighlightState(3, 7, (Span(0, 1, SpanKind.CHORD), Span(2, 4, SpanKind.COMMENT)))
    name, payload = encode(state)
    assert name == "HighlightState"
    assert json.loads(payload) == {
        "text_revision": 3, "client_token": 7,
        "spans": [{"start": 0, "end": 1, "kind": "chord"},
                  {"start": 2, "end": 4, "kind": "comment"}]}

    name, payload = encode(VoicingMenuState("piano", ((MenuItem("Piano", "piano"),), ())))
    assert json.loads(payload) == {"selected": "piano",
                                   "groups": [[{"label": "Piano", "value": "piano"}], []]}
    assert json.loads(encode(PlaybackState(PlaybackStatus.IDLE))[1])["playing_span"] is None


def test_encode_events_and_requests():
    assert encode(CloseApproved()) == ("CloseApproved", "{}")
    assert json.loads(encode(TextEdited(2, 0, 3, "é😀", UndoPolicy.GROUP, 2))[1]) == {
        "text_revision": 2, "start": 0, "end": 3, "replacement": "é😀", "undo": "group",
        "cursor": 2}
    assert json.loads(encode(PickDocumentRequest(4, PickMode.EXPORT_MIDI, "a.mid"))[1]) == {
        "request_id": 4, "mode": "export_midi", "suggested_name": "a.mid"}
    assert json.loads(encode(UnexpectedError("boom"))[1]) == {"message": "boom", "context": None}
    ref = DocumentRef("content://x/1", "a.txt", "Downloads/a.txt")
    state = DocumentState("a.txt", "Downloads/a.txt", True, "a.txt* - Chord Notepad",
                          "content://x/1")
    assert json.loads(encode(state)[1])["document_id"] == ref.id


def test_encode_refuses_live_objects_and_unknown_types():
    with pytest.raises(TypeError):
        encode(object())
    with pytest.raises(TypeError):
        encode(DocumentRef("a", "b", "c"))  # a value type, never an output on its own
    with pytest.raises(TypeError):
        encode(HighlightState(0, 0, (object(),)))
    with pytest.raises(TypeError):
        encode(PlaybackState(PlaybackStatus.IDLE, bar=float("nan")))


# -- decode ------------------------------------------------------------------------


def test_decode_args_by_parameter_type():
    assert decode_args("set_text", '{"text": "C", "client_token": 4}') == {
        "text": "C", "client_token": 4}
    assert decode_args("transpose", '{"semitones": -2, "selection": [1, 5]}') == {
        "semitones": -2, "selection": (1, 5)}
    assert decode_args("transpose", '{"semitones": 1, "selection": null}')["selection"] is None
    assert decode_args("set_bpm", '{"bpm": 120.0}') == {"bpm": 120.0}
    assert decode_args("set_bpm", '{"bpm": 120}') == {"bpm": 120.0}
    assert decode_args("play_pause", '{"from_offset": null}') == {"from_offset": None}
    assert decode_args("set_key", '{"key": null}') == {"key": None}
    assert decode_args("stop", "{}") == {}
    assert decode_args("stop", "") == {}
    ref = {"id": "content://a", "display_name": "a.txt", "location": "a"}
    assert decode_args("open_document", json.dumps({"ref": ref})) == {
        "ref": DocumentRef("content://a", "a.txt", "a")}
    assert decode_args("open_document", '{"ref": null}') == {"ref": None}
    assert decode_args("restore_draft", json.dumps(
        {"text": "C", "document": None, "modified": True})) == {
        "text": "C", "document": None, "modified": True}


def test_decode_args_leaves_out_parameters_that_have_defaults():
    assert decode_args("set_text", '{"text": "C"}') == {"text": "C"}
    assert decode_args("play_pause", "{}") == {}


@pytest.mark.parametrize("command,args,problem", [
    ("no_such_command", "{}", "unknown command"),
    ("subscribe", "{}", "unknown command"),            # not a bridge command
    ("shutdown", "{}", "unknown command"),
    ("set_text", "[1]", "must be a JSON object"),
    ("set_text", "{nope", "aren't JSON"),
    ("set_text", '{"text": "C", "colour": 1}', "unknown arguments"),
    ("insert_text", '{"text": "C"}', "missing argument 'at'"),
    ("insert_text", '{"at": "3", "text": "C"}', "expected an integer"),
    ("insert_text", '{"at": 1.5, "text": "C"}', "expected an integer"),
    ("tap_chord_at", '{"offset": true}', "expected an integer"),
    ("set_chord_sheet_visible", '{"visible": 1}', "expected true or false"),
    ("set_bpm", '{"bpm": "fast"}', "expected a number"),
    ("transpose", '{"semitones": 1, "selection": [1]}', "expected [start, end]"),
    ("open_recent", '{"ref": null}', "expected a DocumentRef object"),
    ("open_recent", '{"ref": {"id": "a"}}', "missing ['display_name', 'location']"),
    ("open_recent", '{"ref": {"id": "a", "display_name": "b", "location": "c", "x": 1}}',
     "unknown ['x']"),
])
def test_decode_args_rejects_bad_input(command, args, problem):
    with pytest.raises(BridgeError, match=re.escape(problem)):
        decode_args(command, args)


def test_command_tables_match_the_session_methods():
    for name, params in bridge.SESSION_COMMANDS.items():
        method = getattr(AppSession, name)
        signature = list(inspect.signature(method).parameters)[1:]
        assert signature == list(params), name
    assert not set(bridge.HOST_COMMANDS) & set(bridge.SESSION_COMMANDS)


def test_every_command_kotlin_sends_is_known():
    source = KOTLIN_COMMANDS.read_text(encoding="utf-8")
    kotlin = set(re.findall(r'const val [A-Z_]+ = "([a-z_]+)"', source))
    assert len(kotlin) >= 30
    assert kotlin <= set(json.loads(schema_json())["commands"])


# -- the schema ---------------------------------------------------------------------


def test_committed_schema_is_current():
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_json(), (
        "android/bridge_schema.json is stale; regenerate it with "
        "`cd src && python -m session.bridge --schema > ../android/bridge_schema.json`")


def test_schema_describes_every_dto_and_command():
    data = json.loads(schema_json())
    assert data["version"] == bridge.SCHEMA_VERSION
    types = data["types"]
    kinds = {name: t["kind"] for name, t in types.items()}
    assert kinds["HighlightState"] == "state" and kinds["TextEdited"] == "event"
    assert kinds["PickDocumentRequest"] == "request" and kinds["DocumentRef"] == "value"
    assert types["DocumentRef"]["fields"] == {"id": "str", "display_name": "str",
                                              "location": "str"}
    assert types["PlaybackState"]["fields"]["playing_span"] == "Span|null"
    assert types["VoicingMenuState"]["fields"]["groups"] == "list[list[MenuItem]]"
    assert types["UnexpectedError"]["fields"] == {"message": "str", "context": "str|null"}
    assert types["DocumentState"]["fields"]["document_id"] == "str|null"
    assert data["enums"]["DiscardChoice"] == ["save", "discard", "cancel"]
    assert set(data["commands"]) == set(data["command_params"])
    # Every type name the schema uses is a primitive, an enum or a listed DTO.
    known = {"str", "int", "float", "bool", "any", "selection",
             "dict[str,str]"} | set(types) | set(data["enums"])
    used = [t for ty in types.values() for t in ty["fields"].values()]
    used += [t for params in data["command_params"].values() for t in params.values()]
    used += list(data["answers"].values())
    for type_name in used:
        base = type_name.removesuffix("|null")
        while base.startswith("list["):
            base = base[len("list["):-1]
        assert base in known, type_name


def test_module_prints_the_schema(capsys):
    assert bridge.main(["--schema"]) == 0
    assert capsys.readouterr().out == schema_json()
    assert bridge.main([]) == 2


# -- on a ThreadedHost, through strings only ------------------------------------------


class BridgeEnv:
    """A session as Android runs it, driven only through the bridge's strings."""

    def __init__(self, tmp_path, documents=None, chord_sheet=False, audio_works=True):
        self.host = ThreadedHost(name="test-session")
        self.host.start()
        self.player = FakePlayer()
        self.services = build_core_services(
            AppDataService(root=tmp_path), HostDispatch(self.host),
            player=self.player if audio_works else None)
        if not audio_works:
            playback = self.services.playback

            def fail(soundfont_path=None, audio_options=None):
                playback._init_error = "no audio driver"
                return False
            playback.initialize_player = fail
        self.store = InMemoryDocumentStore({"song.txt": SONG} if documents is None else documents)
        self.out = []
        self.dtos = []
        self._cond = threading.Condition()
        self.cursor = 0
        self.error_events = None

        def build():
            session = create_session(self.host, self.services, self.store,
                                     chord_sheet=chord_sheet, detection_delay_s=0.02)
            session.subscribe(self.dtos.append)
            b = SessionBridge(self.host, session, self._sink)
            session.start()
            return b

        self.bridge = self.host.call(build, timeout=60)
        self.session = self.bridge.session

    def _sink(self, type_name, payload):
        assert self.host.is_session_thread()
        with self._cond:
            self.out.append((type_name, json.loads(payload)))
            self._cond.notify_all()

    def send(self, command, **args):
        self.bridge.submit(command, json.dumps(args))

    def expect(self, type_name, where=lambda d: True, timeout=15):
        """The next output of ``type_name`` matching ``where`` (after the cursor)."""
        with self._cond:
            def find():
                for i in range(self.cursor, len(self.out)):
                    name, data = self.out[i]
                    if name == type_name and where(data):
                        return i
                return None
            found = self._cond.wait_for(lambda: find() is not None, timeout)
            assert found, f"no {type_name} matching; got {self.out[self.cursor:]}"
            index = find()
            self.cursor = index + 1
            return self.out[index][1]

    def settle(self):
        """Wait until everything submitted so far has run."""
        self.host.call(lambda: None, timeout=15)

    def since(self, mark):
        with self._cond:
            return list(self.out[mark:])

    def latest(self, type_name):
        with self._cond:
            for name, data in reversed(self.out):
                if name == type_name:
                    return data
        return None

    def close(self):
        if self.error_events is not None:
            self.error_events.uninstall()
        try:
            self.host.call(self.session.shutdown, timeout=10)
        finally:
            self.host.shutdown(timeout=5)
            self.services.playback.cleanup()


@pytest.fixture
def env(tmp_path):
    e = BridgeEnv(tmp_path)
    yield e
    e.close()


def ref_json(name):
    ref = InMemoryDocumentStore.ref(name)
    return {"id": ref.id, "display_name": ref.display_name, "location": ref.location}


def test_subscribing_replays_every_state_first(env):
    names = [name for name, _ in env.out[:10]]
    assert set(names) == {"HighlightState", "PlaybackState", "StatusState", "EditorState",
                          "ToolbarState", "VoicingMenuState", "InstrumentMenuState",
                          "DocumentState", "RecentDocumentsState"} | ({"ChordSheetState"}
                                                                        & set(names))
    assert env.out[0][0] == "HighlightState"
    assert env.latest("DocumentState") == {
        "display_name": "Untitled", "location": None, "is_modified": False,
        "title": "Untitled - Chord Notepad", "document_id": None}


def test_typing_comes_back_as_highlight_spans(env):
    env.send("set_text", text="C Am\n// a comment", client_token=7)
    state = env.expect("HighlightState", lambda d: d["client_token"] == 7 and d["spans"])
    assert state["spans"] == [
        {"start": 5, "end": 17, "kind": "comment"},
        {"start": 0, "end": 1, "kind": "chord"},
        {"start": 2, "end": 4, "kind": "chord"},
    ]
    assert env.latest("DocumentState")["is_modified"] is True


def test_play_reports_playing_chords_then_finishes(env):
    env.send("set_text", text="C G Am F", client_token=1)
    env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
    env.send("play_pause", from_offset=None)
    env.expect("PlaybackState", lambda d: d["status"] == "playing")
    spans = []
    while True:
        state = env.expect("PlaybackState")
        if state["status"] == "idle":
            break
        if state["playing_span"] is not None:
            spans.append((state["playing_span"]["start"], state["chord_index"]))
    assert spans[0] == (0, 0)
    assert [s for s, _ in spans] == sorted(s for s, _ in spans)
    assert len(spans) >= 2
    assert "start" in env.player.calls
    editor = env.latest("EditorState")
    assert editor["read_only"] is False
    assert env.latest("ToolbarState")["play_action"] == "play"


def test_open_through_the_picker_with_a_ref_object(env):
    env.send("open_document", ref=None)
    request = env.expect("PickDocumentRequest")
    assert request["mode"] == "open" and request["suggested_name"] == ""
    env.send("respond", request_id=request["request_id"], value=ref_json("song.txt"))
    edit = env.expect("TextEdited")
    assert (edit["start"], edit["end"], edit["replacement"], edit["undo"]) == (
        0, 0, SONG, "reset")
    highlight = env.expect("HighlightState")
    assert highlight["text_revision"] == edit["text_revision"]
    env.settle()
    assert env.latest("DocumentState") == {
        "display_name": "song.txt", "location": "song.txt", "is_modified": False,
        "title": "song.txt - Chord Notepad", "document_id": "memory:song.txt"}
    toolbar = env.latest("ToolbarState")
    assert (toolbar["bpm"], toolbar["beats"], toolbar["unit"], toolbar["key"]) == (90, 3, 4, "G")
    assert env.latest("RecentDocumentsState") == {"items": [ref_json("song.txt")]}


def test_unsaved_changes_question_answered_with_a_string(env):
    env.send("set_text", text="C D", client_token=1)
    env.send("new_document")
    request = env.expect("ConfirmDiscardRequest")
    env.send("respond", request_id=request["request_id"], value="discard")
    edit = env.expect("TextEdited")
    assert (edit["replacement"], edit["undo"]) == ("", "plain")
    env.settle()
    assert env.latest("DocumentState")["is_modified"] is False


def test_transpose_is_one_grouped_edit(env):
    env.send("set_text", text="{key: G}\nG D Em C\n", client_token=1)
    env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
    env.send("transpose", semitones=2, selection=None)
    edit = env.expect("TextEdited")
    assert edit["undo"] == "group" and edit["start"] == 0
    assert edit["replacement"] == "{key: A}\nA E F#m D\n"
    assert edit["cursor"] == len(edit["replacement"])
    env.expect("HighlightState", lambda d: d["text_revision"] == edit["text_revision"])


def test_save_as_and_export_through_pickers(env):
    env.send("set_text", text="C G", client_token=1)
    env.send("save_as")
    request = env.expect("PickDocumentRequest")
    assert (request["mode"], request["suggested_name"]) == ("save", "Untitled.txt")
    env.send("respond", request_id=request["request_id"], value=ref_json("new.txt"))
    env.settle()
    assert env.store.contents["memory:new.txt"] == "C G"
    assert env.latest("DocumentState")["document_id"] == "memory:new.txt"

    env.send("export_midi")
    request = env.expect("PickDocumentRequest", lambda d: d["mode"] == "export_midi")
    assert request["suggested_name"] == "new.mid"
    env.send("respond", request_id=request["request_id"], value=ref_json("new.mid"))
    env.expect("StatusState", lambda d: d["text"].startswith("Exported MIDI"))
    assert env.store.contents["memory:new.mid"][:4] == b"MThd"


def test_a_cancelled_picker_and_close(env):
    env.send("set_text", text="C", client_token=1)
    env.send("request_close")
    request = env.expect("ConfirmDiscardRequest")
    env.send("respond", request_id=request["request_id"], value=None)
    env.settle()
    assert not any(name == "CloseApproved" for name, _ in env.out)
    env.send("request_close")
    request = env.expect("ConfirmDiscardRequest")
    env.send("respond", request_id=request["request_id"], value="discard")
    assert env.expect("CloseApproved") == {}


def test_bad_commands_become_unexpected_errors_and_the_session_goes_on(env):
    env.send("no_such_command")
    error = env.expect("UnexpectedError")
    assert error == {"message": "unknown command 'no_such_command'", "context": "bridge"}

    env.bridge.submit("set_text", "not json")
    assert env.expect("UnexpectedError")["context"] == "bridge"

    # Decoded fine, but the session refuses it: the command's name is the context.
    env.send("insert_text", at=999, text="C")
    error = env.expect("UnexpectedError")
    assert error["context"] == "insert_text" and error["message"].startswith("ValueError")

    env.send("set_voicing", voicing="nope")
    assert env.expect("UnexpectedError")["context"] == "set_voicing"

    env.send("set_text", text="Am", client_token=3)
    assert env.expect("HighlightState", lambda d: d["client_token"] == 3)["spans"]


def test_respond_is_decoded_by_the_pending_request(env):
    env.send("set_text", text="C", client_token=1)
    env.send("open_document", ref=None)
    request = env.expect("ConfirmDiscardRequest")
    # Not a DiscardChoice: rejected, and the question is still pending.
    env.send("respond", request_id=request["request_id"], value="maybe")
    assert "save, discard, cancel" in env.expect("UnexpectedError")["message"]
    env.send("respond", request_id=request["request_id"], value="discard")
    pick = env.expect("PickDocumentRequest")
    # A string isn't a ref.
    env.send("respond", request_id=pick["request_id"], value="memory:song.txt")
    assert env.expect("UnexpectedError")["context"] == "bridge"
    env.send("respond", request_id=pick["request_id"], value=ref_json("song.txt"))
    assert env.expect("TextEdited")["undo"] == "reset"
    # An answer to a request that's gone is ignored, whatever its value.
    mark = len(env.out)
    env.send("respond", request_id=pick["request_id"], value={"bogus": True})
    env.settle()
    assert not any(name == "UnexpectedError" for name, _ in env.since(mark))


def test_insert_directive_answer_is_a_dict_of_strings(env):
    env.send("set_text", text="C G\n", client_token=1)
    env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
    env.send("request_insert_directive", kind="bpm", at=0)
    request = env.expect("InsertDirectiveRequest")
    assert request["kind"] == "bpm" and request["existing_labels"] == []
    env.send("respond", request_id=request["request_id"], value={"value": 3})
    assert "object of strings" in env.expect("UnexpectedError")["message"]
    env.send("respond", request_id=request["request_id"], value={"value": "100"})
    edit = env.expect("TextEdited")
    assert edit["replacement"] == "{bpm: 100} " and edit["undo"] == "plain"


def test_capo_choice_answer_is_an_option_value(env):
    env.send("set_text", text="F Bb C Dm\n", client_token=1)
    env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
    env.send("request_suggest_capo", selection=None)
    request = env.expect("CapoChoiceRequest")
    values = [o["value"] for o in request["options"]]
    assert request["default"] in values
    env.send("respond", request_id=request["request_id"], value=request["default"])
    env.expect("StatusState", lambda d: "capo" in d["text"].lower()
               and not d["text"].startswith("Finding"))


def test_restore_draft_resets_the_text_and_takes_the_document(env):
    env.send("restore_draft", text="G Em\n", document=ref_json("song.txt"), modified=True)
    edit = env.expect("TextEdited")
    assert (edit["start"], edit["end"], edit["replacement"], edit["undo"]) == (
        0, 0, "G Em\n", "reset")
    env.expect("HighlightState", lambda d: d["text_revision"] == edit["text_revision"]
               and len(d["spans"]) == 2)
    env.settle()
    assert env.latest("DocumentState") == {
        "display_name": "song.txt", "location": "song.txt", "is_modified": True,
        "title": "song.txt* - Chord Notepad", "document_id": "memory:song.txt"}
    # The stored document wasn't read (or written).
    assert env.store.contents["memory:song.txt"] == SONG
    # Save goes to that document.
    env.send("save")
    env.settle()
    assert env.store.contents["memory:song.txt"] == "G Em\n"


def test_restore_draft_of_a_new_document_with_the_same_text(env):
    env.send("restore_draft", text="", document=None, modified=False)
    edit = env.expect("TextEdited")
    assert (edit["replacement"], edit["undo"]) == ("", "reset")


def test_pause_only_pauses_a_playing_song(tmp_path):
    env = BridgeEnv(tmp_path)
    try:
        env.player.auto_play = False
        env.send("pause")
        env.settle()
        assert env.player.calls == []
        env.send("set_text", text="C G Am F", client_token=1)
        env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
        env.send("play_pause", from_offset=None)
        env.expect("PlaybackState", lambda d: d["status"] == "playing")
        env.send("pause")
        env.expect("PlaybackState", lambda d: d["status"] == "paused")
        env.send("pause")  # already paused: not resumed
        env.settle()
        assert [c for c in env.player.calls if c != "stop"] == ["start", "pause"]
        env.send("stop")
        env.expect("PlaybackState", lambda d: d["status"] == "idle")
    finally:
        env.close()


def test_app_background_pauses_and_saves_the_config_atomically(tmp_path):
    env = BridgeEnv(tmp_path)
    try:
        env.player.auto_play = False
        config_file = env.services.appdata.get_config_file_path()
        assert config_file.parent == tmp_path / "config" / "chord-notepad"
        env.send("set_bpm", bpm=150)
        env.send("set_text", text="C G", client_token=1)
        env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
        env.send("play_pause", from_offset=None)
        env.expect("PlaybackState", lambda d: d["status"] == "playing")
        env.send("app_background")
        env.expect("PlaybackState", lambda d: d["status"] == "paused")
        env.settle()
        assert json.loads(config_file.read_text())["bpm"] == 150
        assert not list(config_file.parent.glob("*.tmp"))
        env.send("app_foreground")
        env.settle()
        assert env.latest("PlaybackState")["status"] == "paused"
    finally:
        env.close()


def test_background_suspends_the_audio_and_foreground_resumes_it(tmp_path):
    env = BridgeEnv(tmp_path)
    try:
        env.send("set_text", text="C G", client_token=1)
        env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
        env.send("tap_chord_at", offset=0)  # creates the player lazily
        env.settle()
        env.send("app_background")
        env.settle()
        assert env.player.audio_suspended
        env.send("app_foreground")
        env.settle()
        assert not env.player.audio_suspended
        assert env.player.audio_calls == ["suspend", "resume"]
    finally:
        env.close()


def test_play_after_background_without_foreground_reopens_lazily(tmp_path):
    env = BridgeEnv(tmp_path)
    try:
        env.send("set_text", text="C G", client_token=1)
        env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
        env.send("tap_chord_at", offset=0)
        env.settle()
        env.send("app_background")
        env.settle()
        assert env.player.audio_suspended
        env.send("play_pause", from_offset=None)
        env.expect("PlaybackState", lambda d: d["status"] in ("playing", "idle") and
                   not env.player.audio_suspended)
        assert not env.player.audio_suspended
    finally:
        env.close()


def test_typed_bpm_and_multiplier(env):
    env.send("set_bpm_text", text="133")
    env.expect("ToolbarState", lambda d: d["bpm"] == 133)
    env.send("set_multiplier_text", text="1.5x")
    env.expect("ToolbarState", lambda d: d["multiplier_pct"] == 150)
    env.send("set_multiplier_text", text="75%")
    env.expect("ToolbarState", lambda d: d["multiplier_pct"] == 75)
    # Bad input leaves the values alone and reports nothing.
    env.send("set_bpm_text", text="fast")
    env.send("set_multiplier_text", text="")
    env.settle()
    toolbar = env.latest("ToolbarState")
    assert toolbar["bpm"] == 133 and toolbar["multiplier_pct"] == 75
    assert not [o for o in env.out if o[0] == "UnexpectedError"]
    env.send("reset_bpm")
    env.expect("ToolbarState", lambda d: d["bpm"] == 120)
    env.send("reset_multiplier")
    env.expect("ToolbarState", lambda d: d["multiplier_pct"] == 100)


def test_settings_round_trip_as_values(env):
    values = env.host.call(env.session.settings_values)
    assert isinstance(values, SettingsValues)
    changed = dataclasses.replace(values, font_size=20, max_recent_files=3, bpm=100)
    env.send("apply_settings", changes=bridge.to_json_value(changed))
    env.expect("EditorState", lambda d: d["font_size"] == 20)
    env.settle()
    config = env.services.config.config
    assert (config.font_size, config.max_recent_files, config.bpm) == (20, 3, 100)
    saved = json.loads(env.services.appdata.get_config_file_path().read_text())
    assert saved["font_size"] == 20

    bad = bridge.to_json_value(dataclasses.replace(values, font_size=200))
    env.send("apply_settings", changes=bad)
    error = env.expect("UnexpectedError")
    assert error["context"] == "apply_settings" and "font_size" in error["message"]
    assert env.services.config.config.font_size == 20


def test_unexpected_errors_from_any_thread_become_events_throttled(env):
    env.error_events = ErrorEvents(env.host, env.session, repeat_s=60, burst=3, window_s=60)
    env.error_events.install()

    def boom():
        raise RuntimeError("callback broke")

    for _ in range(3):
        env.host.post(boom)
    error = env.expect("UnexpectedError")
    assert error == {"message": "RuntimeError: callback broke",
                     "context": "session thread callback"}
    # From another thread too; the burst cap holds the rest back.
    for i in range(5):
        errors.report_from_any_thread((KeyError, KeyError(i), None), f"worker {i}")
    env.settle()
    env.settle()
    reported = [d for name, d in env.out if name == "UnexpectedError"]
    assert len(reported) == 3


def test_every_output_type_crosses_the_bridge_as_plain_values(tmp_path):
    """DTO purity over a session that emits every output type at least once."""
    env = BridgeEnv(tmp_path, chord_sheet=True, audio_works=False)
    try:
        env.send("set_text", text="{label: a}\nC G\n// note\n", client_token=1)
        env.expect("HighlightState", lambda d: d["client_token"] == 1 and d["spans"])
        env.send("tap_chord_at", offset=11)                      # AudioUnavailable
        env.send("play_pause", from_offset=None)                 # AudioUnavailable again
        env.send("request_insert_directive", kind="label", at=0)
        request = env.expect("InsertDirectiveRequest")
        env.send("respond", request_id=request["request_id"], value={"label": "a"})  # UserError
        env.send("request_suggest_capo", selection=None)
        request = env.expect("CapoChoiceRequest")
        env.send("respond", request_id=request["request_id"], value=None)
        env.send("transpose", semitones=1, selection=[11, 14])   # TextEdited
        env.send("bogus")                                       # UnexpectedError
        env.send("save")
        request = env.expect("PickDocumentRequest")
        env.send("respond", request_id=request["request_id"], value=None)
        env.send("request_close")
        request = env.expect("ConfirmDiscardRequest")
        env.send("respond", request_id=request["request_id"], value="discard")
        env.expect("CloseApproved")
        env.settle()

        outputs = set(bridge.STATE_TYPES + bridge.EVENT_TYPES + bridge.REQUEST_TYPES)
        seen = {type(dto) for dto in env.dtos}
        assert seen == outputs, f"never emitted: {outputs - seen}"
        assert {name for name, _ in env.out} == {t.__name__ for t in outputs}
        for dto in env.dtos:
            _assert_plain(dto)
        unexpected = [d for name, d in env.out if name == "UnexpectedError"]
        assert [d["context"] for d in unexpected] == ["bridge"]
    finally:
        env.close()


_DTO_TYPES = set(bridge.STATE_TYPES + bridge.EVENT_TYPES + bridge.REQUEST_TYPES
                 + bridge.VALUE_TYPES)


def _assert_plain(value, path="dto"):
    """Only str/int/float/bool/None, tuples, str enums and bridge DTOs."""
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, Enum):
            assert type(value) in bridge.ENUM_TYPES, path
        return
    if isinstance(value, tuple):
        for i, item in enumerate(value):
            _assert_plain(item, f"{path}[{i}]")
        return
    assert type(value) in _DTO_TYPES, f"{path}: {type(value).__name__}"
    assert dataclasses.is_dataclass(value) and value.__dataclass_params__.frozen, path
    for f in dataclasses.fields(value):
        _assert_plain(getattr(value, f.name), f"{path}.{f.name}")
