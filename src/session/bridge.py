"""The session over a string-only bridge (Android: Kotlin through Chaquopy).

Outbound, :func:`encode` turns every state, event and request into
``(type_name, json)``: the DTO's class name and its fields as a JSON object
(enums as their values, tuples as arrays, nested DTOs as objects, None as
null; a field typed ``Any`` is plain JSON data, schema type ``json``). Inbound, :func:`dispatch` takes a command name and its keyword
arguments as a JSON object, decodes them by the command's parameter types and
calls the session. :class:`SessionBridge` puts the two on a host: commands
are posted to the session thread, output goes to a sink.

Nothing the bridge is handed can crash the session thread: an unknown
command, a bad argument or a command that raises becomes an
:class:`~session.events.UnexpectedError` (``context="bridge"`` for what
couldn't be decoded, the command's name for what it raised).

``python -m session.bridge --schema`` prints the contract both sides test
against (committed as ``android/bridge_schema.json``; see docs/ANDROID.md,
"Bridge contract"): every DTO with its fields and JSON types, the enums and
every command with its parameters.
"""

import dataclasses
import inspect
import json
import logging
import math
import sys
import threading
import traceback
import types
import typing
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from session import errors
from session.documents import DocumentRef
from session.events import (
    AudioUnavailable, CapoChoiceRequest, CloseApproved, ConfirmDiscardRequest, DiscardChoice,
    InsertDirectiveRequest, PickDocumentRequest, PickMode, QuickStartBlock, QuickStartContent,
    DirectiveCheck, DirectiveHint, QuickStartPage, RenameFailed, TextEdited, UndoPolicy,
    UnexpectedError,
    UserError, VoicingEditorSchema,
)
from session.host import Host
from session.settings import SettingsValues
from session.state import (
    ChordSheetState, ChordSheetView, DocumentState, EditorState, HighlightState,
    IdentifierNote, IdentifierState, InstrumentFamily, InstrumentMenuState, MenuItem, PlayAction,
    PlaybackState, PlaybackStatus, RecentDocumentsState, SettingsState, SongDefault,
    SongDefaultsState, Span, SpanKind, StartupScreen, StartupState, StatusState, ToolbarState,
    VoicingEditorState, VoicingGroup, VoicingMenuState, VoicingPreset,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: The ``context`` of an UnexpectedError for input the bridge couldn't use.
BRIDGE_CONTEXT = "bridge"

# -- the DTOs -----------------------------------------------------------------

STATE_TYPES: Tuple[type, ...] = (
    DocumentState, EditorState, HighlightState, PlaybackState, ToolbarState, StatusState,
    VoicingMenuState, InstrumentMenuState, RecentDocumentsState, ChordSheetState,
    IdentifierState, SettingsState, VoicingEditorState, SongDefaultsState, StartupState,
)
EVENT_TYPES: Tuple[type, ...] = (
    TextEdited, UserError, AudioUnavailable, UnexpectedError, CloseApproved,
    VoicingEditorSchema, QuickStartContent, DirectiveCheck, RenameFailed, DirectiveHint,
)
REQUEST_TYPES: Tuple[type, ...] = (
    ConfirmDiscardRequest, PickDocumentRequest, CapoChoiceRequest, InsertDirectiveRequest,
)
#: Nested in outputs, or sent in commands.
VALUE_TYPES: Tuple[type, ...] = (
    Span, MenuItem, InstrumentFamily, ChordSheetView, DocumentRef, SettingsValues,
    IdentifierNote, VoicingGroup, VoicingPreset, QuickStartPage, QuickStartBlock, SongDefault,
)
ENUM_TYPES: Tuple[Type[Enum], ...] = (
    SpanKind, PlaybackStatus, PlayAction, UndoPolicy, DiscardChoice, PickMode, StartupScreen,
)

_KINDS: Dict[type, str] = {
    **{t: "state" for t in STATE_TYPES},
    **{t: "event" for t in EVENT_TYPES},
    **{t: "request" for t in REQUEST_TYPES},
    **{t: "value" for t in VALUE_TYPES},
}


class BridgeError(ValueError):
    """A command the bridge can't run as given (unknown, or bad arguments)."""


def to_json_value(value: Any) -> Any:
    """``value`` as plain JSON data (dicts, lists, str, int, float, bool, None).

    Raises:
        TypeError: For anything else (a live object must never cross).
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value.value if isinstance(value, Enum) else value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"non-finite float {value!r} can't cross the bridge")
        return value
    if isinstance(value, Enum):
        return to_json_value(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json_value(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (tuple, list)):
        return [to_json_value(v) for v in value]
    if isinstance(value, dict):
        # Only in fields typed Any (plain JSON data, e.g. the voicing form).
        if not all(isinstance(k, str) for k in value):
            raise TypeError(f"JSON objects need str keys: {value!r}")
        return {k: to_json_value(v) for k, v in value.items()}
    raise TypeError(f"{type(value).__name__} can't cross the bridge: {value!r}")


def encode(dto: Any) -> Tuple[str, str]:
    """A session output as ``(type_name, json)``.

    Raises:
        TypeError: If ``dto`` isn't a state, event or request type, or holds
            something that isn't plain data.
    """
    if _KINDS.get(type(dto)) not in ("state", "event", "request"):
        raise TypeError(f"{type(dto).__name__} is not a session output")
    return type(dto).__name__, json.dumps(to_json_value(dto), ensure_ascii=False,
                                          allow_nan=False, separators=(",", ":"))


# -- argument types -------------------------------------------------------------
#
# A parameter type is a small string, the same one the schema shows:
# "int", "float", "str", "bool", "selection" ([start, end] or null),
# "DocumentRef", "SettingsValues", "any" (respond's value, decoded later),
# "json" (any JSON value, passed on as is), and "<type>|null".

_Decoder = Callable[[Any], Any]


def _decode_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BridgeError(f"expected an integer, got {value!r}")
    return value


def _decode_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BridgeError(f"expected a number, got {value!r}")
    return float(value)


def _decode_str(value: Any) -> str:
    if not isinstance(value, str):
        raise BridgeError(f"expected a string, got {value!r}")
    return value


def _decode_bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise BridgeError(f"expected true or false, got {value!r}")
    return value


def _decode_selection(value: Any) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise BridgeError(f"expected [start, end] or null, got {value!r}")
    return (_decode_int(value[0]), _decode_int(value[1]))


def _decode_dataclass(cls: type) -> _Decoder:
    names = [f.name for f in dataclasses.fields(cls)]
    hints = typing.get_type_hints(cls)

    def decode(value: Any) -> Any:
        if not isinstance(value, dict):
            raise BridgeError(f"expected a {cls.__name__} object, got {value!r}")
        missing = [n for n in names if n not in value]
        extra = sorted(set(value) - set(names))
        if missing or extra:
            raise BridgeError(f"{cls.__name__} needs exactly {names}; "
                              f"missing {missing}, unknown {extra}")
        kwargs = {n: _DECODERS[_type_name(hints[n])](value[n]) for n in names}
        return cls(**kwargs)

    return decode


_DECODERS: Dict[str, _Decoder] = {
    "int": _decode_int,
    "float": _decode_float,
    "str": _decode_str,
    "bool": _decode_bool,
    "selection": _decode_selection,
    "any": lambda value: value,
    "json": lambda value: value,
}
_DECODERS["DocumentRef"] = _decode_dataclass(DocumentRef)
_DECODERS["SettingsValues"] = _decode_dataclass(SettingsValues)


def _decoder(type_name: str) -> _Decoder:
    if type_name.endswith("|null"):
        inner = _DECODERS[type_name[:-len("|null")]]
        return lambda value: None if value is None else inner(value)
    return _DECODERS[type_name]


# -- commands -------------------------------------------------------------------

#: Session commands: public AppSession methods a bridge view may call, with
#: their parameters' types. Parameter names are the methods' (a test checks).
SESSION_COMMANDS: Dict[str, Dict[str, str]] = {
    # editing
    "set_text": {"text": "str", "client_token": "int"},
    "insert_text": {"at": "int", "text": "str"},
    "insert_chord": {"at": "int", "chord": "str"},
    "request_insert_directive": {"kind": "str", "at": "int"},
    "check_directive": {"kind": "str", "fields": "json", "request_id": "int"},
    "request_directive_hint": {"offset": "int"},
    "transpose": {"semitones": "int", "selection": "selection"},
    "request_suggest_capo": {"selection": "selection"},
    "convert_notation": {"target": "str"},
    "write_song_defaults": {},
    # playback and toolbar
    "play_pause": {"from_offset": "int|null"},
    "stop": {},
    "pause": {},
    "rewind": {},
    "set_playhead": {"offset": "int"},
    "tap_chord_at": {"offset": "int"},
    "set_bpm": {"bpm": "float"},
    "set_multiplier_pct": {"pct": "float"},
    "set_bpm_text": {"text": "str"},
    "set_multiplier_text": {"text": "str"},
    "reset_bpm": {},
    "reset_multiplier": {},
    "set_key": {"key": "str|null"},
    "set_time_signature": {"beats": "int", "unit": "int"},
    "toggle_metronome": {},
    "set_voicing": {"voicing": "str"},
    "set_instrument": {"program": "int"},
    "set_notation": {"notation": "str"},
    "set_font": {"family": "str", "size": "int"},
    "step_font_size": {"delta": "int"},
    "reset_font_size": {},
    # chord sheet
    "set_chord_sheet_visible": {"visible": "bool"},
    "set_chord_sheet_height": {"px": "int"},
    "set_chord_sheet_view": {"view_id": "str"},
    "chord_sheet_zoom": {"step": "int"},
    "audition": {"index": "int"},
    # chord identifier
    "identifier_toggle_note": {"note": "str", "octave": "int"},
    "identifier_set_notes_text": {"text": "str"},
    "identifier_clear": {},
    "play_note": {"note": "str", "octave": "int"},
    "play_identified_chord": {"chord": "str"},
    # documents and requests
    "new_document": {},
    "open_document": {"ref": "DocumentRef|null", "read_only": "bool"},
    "open_recent": {"ref": "DocumentRef"},
    "save": {},
    "save_as": {"name": "str|null"},
    "rename_document": {"name": "str"},
    "export_midi": {},
    "request_close": {},
    "respond": {"request_id": "int", "value": "any"},
    "restore_draft": {"text": "str", "document": "DocumentRef|null", "modified": "bool",
                      "read_only": "bool"},
    # settings and preferences
    "apply_settings": {"changes": "SettingsValues"},
    "set_show_quick_start_on_startup": {"show": "bool"},
    "request_quick_start": {},
    # the startup screen (Android)
    "app_started": {"launch_kind": "str", "today": "str", "installed_on": "str",
                    "can_ask_for_support": "bool"},
    "dismiss_startup_screen": {},
    # the Settings screen's working copy and its voicings editor
    "begin_settings_edit": {},
    "cancel_settings_edit": {},
    "save_settings": {"values": "SettingsValues|null"},
    "request_voicing_editor_schema": {},
    "select_voicing": {"name": "str"},
    "add_voicing": {},
    "remove_voicing": {"name": "str"},
    "rename_voicing": {"old": "str", "new": "str"},
    "set_voicing_values": {"values": "json"},
    "set_voicing_model": {"model": "str"},
    "add_voicing_record": {"field_id": "str"},
    "remove_voicing_record": {"index": "int", "field_id": "str"},
    "load_voicing_preset": {"group": "str", "label": "str"},
}

#: Host commands: the app's lifecycle, run on the session's primitives.
HOST_COMMANDS: Dict[str, Dict[str, str]] = {
    "app_background": {},
    "app_foreground": {},
}

#: respond()'s value, by the type of the request it answers (null cancels).
ANSWER_TYPES: Dict[type, str] = {
    PickDocumentRequest: "DocumentRef|null",
    ConfirmDiscardRequest: "DiscardChoice|null",
    CapoChoiceRequest: "str|null",
    InsertDirectiveRequest: "dict[str,str]|null",
}


def _decode_answer(request: Any, value: Any) -> Any:
    """Decode an answer to ``request`` (the pending one)."""
    if isinstance(request, ConfirmDiscardRequest):
        choice = _decoder("str|null")(value)
        if choice is None:
            return None
        try:
            return DiscardChoice(choice)
        except ValueError:
            raise BridgeError(f"expected save, discard, cancel or null, got {choice!r}")
    if isinstance(request, InsertDirectiveRequest):
        if value is None:
            return None
        if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise BridgeError(f"expected an object of strings or null, got {value!r}")
        return dict(value)
    if isinstance(request, PickDocumentRequest):
        return _decoder("DocumentRef|null")(value)
    if isinstance(request, CapoChoiceRequest):
        return _decoder("str|null")(value)
    raise BridgeError(f"no answer decoding for {type(request).__name__}")


#: Commands that can change a persisted setting. After one of them runs, a
#: bridge with autosave on writes the config shortly after (debounced).
CONFIG_COMMANDS = frozenset({
    "set_bpm", "set_multiplier_pct", "set_bpm_text", "set_multiplier_text",
    "reset_bpm", "reset_multiplier", "set_key", "set_time_signature",
    "toggle_metronome", "set_voicing", "set_instrument", "set_notation",
    "set_font", "step_font_size", "reset_font_size", "set_chord_sheet_visible",
    "set_chord_sheet_height", "set_chord_sheet_view", "chord_sheet_zoom",
    "convert_notation", "apply_settings", "save_settings",
    "set_show_quick_start_on_startup", "open_document", "open_recent", "save", "save_as",
    "rename_document",
})


def _session_call(session: Any, command: str, kwargs: Dict[str, Any]) -> None:
    if command == "respond":
        request = session.pending_request
        if request is None or request.request_id != kwargs["request_id"]:
            # Stale or unknown: the session ignores it (and logs); the value
            # isn't looked at.
            kwargs["value"] = None
        else:
            kwargs["value"] = _decode_answer(request, kwargs["value"])
    getattr(session, command)(**kwargs)


def _app_background(session: Any) -> None:
    """The app left the screen and may be killed: pause, keep the settings,
    release the audio output (refused while a song plays or renders)."""
    session.pause()
    session.save_config()
    session.suspend_audio()


def _app_foreground(session: Any) -> None:
    """The app is back on screen: reopen the audio output. A failure isn't
    reported here; the next play reports AudioUnavailable."""
    session.resume_audio()


_HOST_HANDLERS: Dict[str, Callable[[Any], None]] = {
    "app_background": _app_background,
    "app_foreground": _app_foreground,
}


def decode_args(command: str, args_json: str) -> Dict[str, Any]:
    """The keyword arguments of ``command``, decoded from ``args_json``.

    ``respond``'s value is left as JSON (it is decoded against the pending
    request when the command runs).

    Raises:
        BridgeError: For an unknown command, JSON that isn't an object, an
            unknown or missing argument, or an argument of the wrong type.
    """
    spec = SESSION_COMMANDS.get(command)
    if spec is None:
        spec = HOST_COMMANDS.get(command)
    if spec is None:
        raise BridgeError(f"unknown command {command!r}")
    try:
        raw = json.loads(args_json) if args_json else {}
    except (TypeError, ValueError) as e:
        raise BridgeError(f"{command}: arguments aren't JSON: {e}")
    if not isinstance(raw, dict):
        raise BridgeError(f"{command}: arguments must be a JSON object, got {raw!r}")
    unknown = sorted(set(raw) - set(spec))
    if unknown:
        raise BridgeError(f"{command}: unknown arguments {unknown}")
    optional = _optional_params(command)
    kwargs: Dict[str, Any] = {}
    for name, type_name in spec.items():
        if name not in raw:
            if name in optional:
                continue
            raise BridgeError(f"{command}: missing argument {name!r}")
        try:
            kwargs[name] = _decoder(type_name)(raw[name])
        except BridgeError as e:
            raise BridgeError(f"{command}: {name}: {e}")
    return kwargs


def dispatch(session: Any, command: str, args_json: str) -> bool:
    """Run one command on the session thread; never raises.

    A command the bridge can't decode emits ``UnexpectedError(context=
    "bridge")``; one that raises emits ``UnexpectedError(context=command)``
    (with the traceback in the log).

    Args:
        session: The :class:`~session.session.AppSession`.
        command: A session or host command name.
        args_json: Its keyword arguments as a JSON object.

    Returns:
        True if the command ran without raising.
    """
    try:
        kwargs = decode_args(command, args_json)
        handler = _HOST_HANDLERS.get(command)
        if handler is not None:
            handler(session, **kwargs)
        else:
            _session_call(session, command, kwargs)
        return True
    except BridgeError as e:
        logger.error("Bridge: %s", e)
        _report(session, str(e), BRIDGE_CONTEXT)
    except Exception as e:
        logger.error("Bridge command %s failed", command, exc_info=True)
        _report(session, f"{type(e).__name__}: {e}", command)
    return False


def _report(session: Any, message: str, context: str) -> None:
    try:
        session.report_unexpected(message, context)
    except Exception:
        logger.exception("Couldn't report a bridge failure")


_signature_cache: Dict[str, frozenset] = {}


def _optional_params(command: str) -> frozenset:
    """The parameters of a session command that have a default."""
    if command not in _signature_cache:
        optional: frozenset = frozenset()
        if command in SESSION_COMMANDS:
            from session.session import AppSession
            params = inspect.signature(getattr(AppSession, command)).parameters
            optional = frozenset(n for n, p in params.items()
                                 if p.default is not inspect.Parameter.empty)
        _signature_cache[command] = optional
    return _signature_cache[command]


# -- on a host ------------------------------------------------------------------

Sink = Callable[[str, str], None]


class SessionBridge:
    """A session behind the bridge: commands in as strings, output out as strings.

    Create it on the session thread (it subscribes to the session); then
    :meth:`submit` from any thread. Every output reaches ``sink(type_name,
    json)`` on the session thread, in delivery order, starting with the
    replay of every state.
    """

    def __init__(self, host: Host, session: Any, sink: Sink,
                 autosave_s: Optional[float] = None) -> None:
        """Subscribe ``sink`` to ``session``'s output.

        Args:
            host: The session's host.
            session: The session (already built on ``host``'s thread).
            sink: Gets each output as ``(type_name, json)``.
            autosave_s: If set, the config is saved this many seconds after the
                last command that may change a setting (a process kill then
                loses at most that). None leaves saving to the caller.
        """
        self._autosave_s = autosave_s
        self._autosave_timer: Any = None
        self._host = host
        self._session = session
        self._sink = sink
        self._subscription = session.subscribe(self._forward)

    @property
    def session(self) -> Any:
        """The session."""
        return self._session

    def submit(self, command: str, args_json: str) -> None:
        """Queue a command for the session thread and return at once."""
        self._host.post(lambda: self._run(command, args_json))

    def _run(self, command: str, args_json: str) -> None:
        dispatch(self._session, command, args_json)
        if self._autosave_s is not None and command in CONFIG_COMMANDS:
            self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if self._autosave_timer is not None:
            self._autosave_timer.cancel()
        self._autosave_timer = self._host.call_later(self._autosave_s, self._autosave)

    def _autosave(self) -> None:
        self._autosave_timer = None
        try:
            self._session.save_config()
        except Exception:
            logger.exception("Autosaving the config failed")

    def close(self) -> None:
        """Stop forwarding output and drop a pending autosave (on the session thread)."""
        if self._autosave_timer is not None:
            self._autosave_timer.cancel()
            self._autosave_timer = None
        self._subscription.cancel()

    def _forward(self, dto: Any) -> None:
        type_name, payload = encode(dto)
        self._sink(type_name, payload)


class ErrorEvents:
    """A ``session.errors`` handler that reports through the session, throttled.

    Each unexpected error becomes an ``UnexpectedError`` event, posted to
    the session thread. The same message from the same context is reported
    once per ``repeat_s``, and at most ``burst`` errors per ``window_s``;
    the rest are only logged.
    """

    def __init__(self, host: Host, session: Any, *, repeat_s: float = 30.0,
                 burst: int = 5, window_s: float = 60.0) -> None:
        """Create the handler (install it with :meth:`install`)."""
        self._host = host
        self._session = session
        self._repeat_s = repeat_s
        self._burst = burst
        self._window_s = window_s
        self._lock = threading.Lock()
        self._last_seen: Dict[Tuple[str, str], float] = {}
        self._recent: List[float] = []
        self._previous: Optional[errors.ErrorHandler] = None

    def install(self) -> None:
        """Make this the session error handler."""
        self._previous = errors.set_handler(self)

    def uninstall(self) -> None:
        """Put the handler installed before back."""
        if errors.get_handler() is self:
            errors.set_handler(self._previous)

    def __call__(self, exc_info: errors.ExcInfo, context: str) -> None:
        """Report one error (any thread)."""
        logger.error("Unexpected error in %s", context, exc_info=exc_info)
        exc = exc_info[1]
        message = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        if not self._admit(message, context):
            return
        session = self._session
        self._host.post(lambda: session.report_unexpected(message, context))

    def _admit(self, message: str, context: str) -> bool:
        now = self._host.monotonic()
        with self._lock:
            key = (context, message)
            last = self._last_seen.get(key)
            if last is not None and now - last < self._repeat_s:
                return False
            self._recent = [t for t in self._recent if now - t < self._window_s]
            if len(self._recent) >= self._burst:
                return False
            self._last_seen[key] = now
            self._recent.append(now)
            return True


# -- the schema -------------------------------------------------------------------

def _type_name(hint: Any) -> str:
    """A field's type annotation in the schema's notation."""
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        inner = [a for a in args if a is not type(None)]
        if len(inner) == 1 and len(args) == 2:
            return f"{_type_name(inner[0])}|null"
        raise TypeError(f"unsupported union {hint!r}")
    if origin in (tuple, list):
        if origin is tuple and not (len(args) == 2 and args[1] is Ellipsis):
            raise TypeError(f"only Tuple[X, ...] crosses the bridge, not {hint!r}")
        return f"list[{_type_name(args[0])}]"
    if hint in (str, int, float, bool):
        return hint.__name__
    if hint is typing.Any:
        return "json"
    if isinstance(hint, type) and (issubclass(hint, Enum) or dataclasses.is_dataclass(hint)):
        return hint.__name__
    raise TypeError(f"{hint!r} can't cross the bridge")


def schema() -> Dict[str, Any]:
    """The bridge contract: DTO types, enums and commands (JSON data)."""
    types: Dict[str, Any] = {}
    for cls, kind in _KINDS.items():
        hints = typing.get_type_hints(cls)
        types[cls.__name__] = {
            "kind": kind,
            "fields": {f.name: _type_name(hints[f.name]) for f in dataclasses.fields(cls)},
        }
    commands = {**SESSION_COMMANDS, **HOST_COMMANDS}
    return {
        "version": SCHEMA_VERSION,
        "types": types,
        "enums": {e.__name__: [m.value for m in e] for e in ENUM_TYPES},
        "commands": sorted(commands),
        "command_params": {name: dict(params) for name, params in sorted(commands.items())},
        "answers": {req.__name__: answer for req, answer in ANSWER_TYPES.items()},
    }


def schema_json() -> str:
    """:func:`schema` as the text committed in ``android/bridge_schema.json``."""
    return json.dumps(schema(), indent=2, sort_keys=True) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    """``python -m session.bridge --schema``: print the schema."""
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--schema"]:
        print("usage: python -m session.bridge --schema", file=sys.stderr)
        return 2
    sys.stdout.write(schema_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
