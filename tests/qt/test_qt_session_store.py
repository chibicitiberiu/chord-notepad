"""SessionStore: the session for QML over the bridge (plan step C3).

Most tests drive a real session on a ManualHost, so what is posted (the
commands, the deferred requests) runs only when the test says so. The last
ones check the allow-list of direct calls: nothing in the Qt package calls
the session except through it.
"""

import ast
import json
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

import dataclasses  # noqa: E402

from PySide6.QtCore import QMetaMethod  # noqa: E402

from chordnotepad.services.appdata_service import AppDataService  # noqa: E402
from chordnotepad.session.bootstrap import build_core_services, create_session  # noqa: E402
from chordnotepad.session.bridge import STATE_TYPES  # noqa: E402
from chordnotepad.session.formatting import CONFIRM_DISCARD_MESSAGE, CONFIRM_DISCARD_TITLE  # noqa: E402
from chordnotepad.session.host import HostDispatch  # noqa: E402
from chordnotepad.session.platform import DESKTOP_QT  # noqa: E402
from chordnotepad.session.testing import FakePlayer, InMemoryDocumentStore, ManualHost  # noqa: E402
from chordnotepad_desktop import session_store  # noqa: E402
from chordnotepad_desktop.session_store import DIRECT_CALLS, SessionStore  # noqa: E402

PACKAGE = Path(session_store.__file__).resolve().parent
SONG = "{bpm: 90}\nC   G   Am  F\nOne two three four\n"


class Env:
    """A session on a ManualHost with a store over it."""

    def __init__(self, tmp_path):
        self.host = ManualHost()
        core = build_core_services(AppDataService(root=tmp_path), HostDispatch(self.host),
                                   player=FakePlayer())
        self.session = create_session(self.host, core, InMemoryDocumentStore(),
                                      chord_sheet=False, platform=DESKTOP_QT)
        self.session.start()
        self.store = SessionStore(self.host, self.session)
        self.events = []
        self.requests = []
        self.store.event.connect(lambda name, data: self.events.append((name, data)))
        self.store.request.connect(lambda name, data: self.requests.append((name, data)))

    def run(self, seconds=1.0):
        """Run what was posted, and the timers due within ``seconds``."""
        self.host.run_pending()
        self.host.advance(seconds)
        self.host.run_pending()

    def state(self, name):
        mapping = self.store.state(name)
        return {key: mapping.value(key) for key in mapping.keys()}


@pytest.fixture
def env(qapp, tmp_path):
    e = Env(tmp_path)
    yield e
    e.store.close()
    e.session.shutdown()


def test_every_state_has_a_map_with_every_field_from_the_start(env):
    states = env.store.property("states")
    assert sorted(states.keys()) == sorted(t.__name__ for t in STATE_TYPES)
    for state_type in STATE_TYPES:
        assert sorted(env.store.state(state_type.__name__).keys()) == sorted(
            f.name for f in dataclasses.fields(state_type))
    # Not published on the desktop until app_started: there, but null.
    assert env.state("StartupState") == {"screen": None}


def test_the_states_are_replayed_into_the_maps(env):
    assert env.state("DocumentState")["title"] == "Untitled - Chord Notepad"
    assert env.state("DocumentState")["is_modified"] is False
    assert env.state("StatusState")["text"] == "Ready"
    assert env.state("PlaybackState")["status"] == "idle"


def test_submit_goes_through_the_bridge_and_updates_the_maps(env, qtbot):
    with qtbot.waitSignal(env.store.stateChanged, timeout=1000,
                          check_params_cb=lambda name: name == "DocumentState"):
        env.store.submit("set_text", {"text": SONG, "client_token": 1})
        assert env.state("DocumentState")["is_modified"] is False   # queued, not run yet
        env.run()
    assert env.state("DocumentState")["is_modified"] is True
    assert env.state("DocumentState")["title"] == "Untitled* - Chord Notepad"
    env.store.submit("set_word_wrap", {"on": True})
    env.run()
    assert env.state("EditorState")["word_wrap"] is True


def test_a_command_without_arguments(env):
    env.store.submit("toggle_metronome")
    env.run()
    assert env.state("ToolbarState")["metronome"] is True


def test_a_bad_command_becomes_an_unexpected_error_event(env):
    env.store.submit("no_such_command", {})
    env.store.submit("set_word_wrap", {"on": "yes"})
    env.run()
    names = [(name, data["context"]) for name, data in env.events]
    assert names == [("UnexpectedError", "bridge"), ("UnexpectedError", "bridge")]
    assert "unknown command 'no_such_command'" in env.events[0][1]["message"]


def during_delivery(env):
    """A list that is non-empty while the store is handed an output."""
    inside = []
    receive = env.store._bridge._sink

    def wrapped(type_name, payload):
        inside.append(type_name)
        try:
            receive(type_name, payload)
        finally:
            inside.pop()

    env.store._bridge._sink = wrapped
    return inside


def test_requests_come_after_delivery(env):
    inside = during_delivery(env)
    seen = []
    env.store.request.connect(lambda name, data: seen.append(list(inside)))
    env.store.submit("set_text", {"text": SONG, "client_token": 1})
    env.store.submit("request_close")
    env.run()
    assert [name for name, _ in env.requests] == ["ConfirmDiscardRequest"]
    assert seen == [[]]
    request_id = env.requests[0][1]["request_id"]
    assert request_id == env.session.pending_request.request_id

    closed = []
    env.store.closeApproved.connect(lambda: closed.append(list(inside)))
    env.store.submit("respond", {"request_id": request_id, "value": "discard"})
    env.run()
    assert closed == [[]]          # CloseApproved is deferred too
    assert not [name for name, _ in env.events if name == "CloseApproved"]


def test_states_and_events_come_during_delivery(env):
    inside = during_delivery(env)
    seen = []
    env.store.stateChanged.connect(lambda name: seen.append(list(inside)))
    env.store.event.connect(lambda name, data: seen.append(list(inside)))
    env.store.submit("set_word_wrap", {"on": True})
    env.store.submit("no_such_command")
    env.run()
    assert ["EditorState"] in seen and ["UnexpectedError"] in seen


def test_cancel_keeps_the_window(env):
    env.store.submit("set_text", {"text": SONG, "client_token": 1})
    env.store.submit("request_close")
    env.run()
    closed = []
    env.store.closeApproved.connect(lambda: closed.append(True))
    env.store.submit("respond", {"request_id": env.requests[-1][1]["request_id"], "value": "cancel"})
    env.run()
    assert closed == [] and env.session.pending_request is None


def test_events_arrive_in_order_with_their_fields(env):
    env.store.submit("request_quick_start")
    env.run()
    name, data = env.events[-1]
    assert name == "QuickStartContent"
    assert data["show_on_startup"] is True
    assert data["pages"] and {"title", "blocks"} <= set(data["pages"][0])


def test_the_direct_calls(env):
    env.store.submit("set_text", {"text": SONG, "client_token": 1})
    env.run()
    c = SONG.index("C ")
    assert env.store.chordAt(c) == {"start": c, "end": c + 1, "kind": "chord", "message": ""}
    assert env.store.chordAt(SONG.index("One")) is None
    hint = env.store.directiveHintAt(3)
    assert hint["keyword"] == "bpm" and hint["start"] == 0 and hint["syntax"]
    values = env.store.direct("settings_values")
    assert values.bpm == 120
    catalog = env.store.direct("licence_catalog", Path(__file__).resolve().parents[2]
                               / "resources" / "licenses")
    assert catalog is not None
    assert env.store.direct("picker_at", 3).kind == "tempo"
    assert env.store.direct("picker_at", SONG.index("One")) is None


def test_anything_else_is_refused_as_a_direct_call(env):
    with pytest.raises(ValueError, match="not a direct call"):
        env.store.direct("save")


def test_after_close_nothing_comes_or_goes(env):
    env.store.close()
    env.store.submit("toggle_metronome")
    env.run()
    assert env.session.pending_request is None
    assert env.state("ToolbarState")["metronome"] is False


def test_the_fixed_texts_are_the_sessions(env):
    texts = env.store.property("texts")
    assert texts["confirmDiscardTitle"] == CONFIRM_DISCARD_TITLE
    assert texts["confirmDiscardMessage"] == CONFIRM_DISCARD_MESSAGE


def test_arguments_that_are_not_json_are_reported(env):
    env.store.submit("set_word_wrap", {"on": float("nan")})
    env.run()
    assert env.events[-1][0] == "UnexpectedError"


# -- the allow-list guard ----------------------------------------------------------------

#: Session calls the plumbing makes besides the direct calls: the lifecycle
#: (application.py) and the window geometry in logical pixels
#: (window_geometry.py). The geometry is desktop-only (plan step B3), so it
#: isn't a bridge command; it is read before the window shows and saved after
#: the session approved closing.
PLUMBING = {"start", "shutdown", "stop"}
GEOMETRY = {"logical_window_geometry", "set_logical_window_geometry"}


def session_attributes(tree):
    """Attributes read on anything named session (``session.x``, ``self._session.x``)."""
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        owner = node.value
        name = owner.id if isinstance(owner, ast.Name) else \
            owner.attr if isinstance(owner, ast.Attribute) else None
        if name in ("session", "_session"):
            found.add(node.attr)
    return found


def test_the_direct_calls_are_the_plans_four_and_the_pickers_lookup():
    # picker_at: the ▾ value picker (D5; B4 listed it as a direct call).
    assert DIRECT_CALLS == {"directive_hint_at", "chord_at", "licence_catalog", "settings_values",
                            "picker_at"}


def test_nothing_in_the_qt_package_calls_the_session_outside_the_allow_list():
    used = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        for attr in session_attributes(ast.parse(path.read_text(encoding="utf-8"))):
            used.setdefault(attr, set()).add(path.name)
    allowed = DIRECT_CALLS | PLUMBING | GEOMETRY
    stray = {attr: files for attr, files in used.items() if attr not in allowed}
    assert stray == {}, f"call these through submit() (bridge commands): {stray}"
    # The direct calls themselves go through SessionStore.direct only.
    assert not any(attr in DIRECT_CALLS for attr in used), used
    geometry = {attr: files for attr, files in used.items() if attr in GEOMETRY}
    assert all(files == {"window_geometry.py"} for files in geometry.values()), geometry


def test_qml_can_call_only_submit_and_the_two_lookups():
    meta = SessionStore.staticMetaObject
    own = {meta.method(i).name().data().decode() for i in range(meta.methodOffset(), meta.methodCount())
           if meta.method(i).methodType() == QMetaMethod.MethodType.Slot}
    assert own == {"submit", "chordAt", "directiveHintAt"}


def test_the_guard_sees_session_calls():
    tree = ast.parse("self._session.save()\nsession.stop()\nx.session.window_geometry\n")
    assert session_attributes(tree) == {"save", "stop", "window_geometry"}


def test_the_qml_submits_only_bridge_commands():
    from chordnotepad.session.bridge import HOST_COMMANDS, SESSION_COMMANDS
    import re

    qml_dir = PACKAGE / "qml"
    names = set()
    for path in qml_dir.rglob("*.qml"):
        names |= set(re.findall(r'\bsubmit\("(\w+)"', path.read_text(encoding="utf-8")))
    assert names <= set(SESSION_COMMANDS) | set(HOST_COMMANDS), names - set(SESSION_COMMANDS)


def test_the_payload_is_json(env):
    # The store hands the bridge a JSON object; dispatch decodes it by type.
    sent = []
    env.store._bridge.submit = lambda command, payload: sent.append((command, json.loads(payload)))
    env.store.submit("set_key", {"key": None})
    env.store.submit("rewind")
    assert sent == [("set_key", {"key": None}), ("rewind", {})]
