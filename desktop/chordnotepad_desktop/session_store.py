"""The session as QML sees it: states as property maps, outputs as signals.

:class:`SessionStore` sits on the same bridge Android uses
(``chordnotepad.session.bridge``): a :class:`~chordnotepad.session.bridge.SessionBridge`
subscribes to the session and hands every output over as ``(type_name,
json)``, and every command goes back through ``bridge.dispatch`` (decoded
by the command's parameter types; a bad command or one that raises becomes
an ``UnexpectedError`` event instead of an exception). So QML works with
exactly the data and the commands Kotlin does, and a command name or
argument it gets wrong fails the same way.

* **States** (``DocumentState``, ``PlaybackState``, ...): one
  ``QQmlPropertyMap`` per type in :attr:`SessionStore.states`, keyed by the
  type's name, each holding the DTO's fields by their Python names::

      title: win.store.states.DocumentState.title

  Every map and every field exists from the start (null until the session
  publishes the state), because a QML binding to a key that is inserted
  later is never re-evaluated. A changed field is updated in place, so only
  the bindings that read it run again. :attr:`SessionStore.stateChanged`
  names the type after each update.
* **Events** (``UserError``, ``TextEdited``, ...): :attr:`SessionStore.event`
  with the type name and the fields, in delivery order with the states.
  ``CloseApproved`` is the exception: it tears the window down, so it comes
  as :attr:`SessionStore.closeApproved`, after delivery (as Tk's
  ``after_idle``).
* **Requests** (``ConfirmDiscardRequest``, ...): :attr:`SessionStore.request`,
  also after delivery: a dialog opened from inside delivery would see the
  session half-way through a command. Answer with
  ``submit("respond", {request_id, value})``.
* **Commands:** ``submit(name)`` / ``submit(name, args)``, args a JS object
  of the command's keyword arguments. Queued for the session thread (the GUI
  thread, through the host) and run after the caller returns, as on Android.

A few session methods return a value at once instead of publishing one:
they are the **direct calls**, :data:`DIRECT_CALLS`, and nothing else in
this package calls the session (``tests/qt/test_qt_session_store.py`` keeps
it that way). QML reaches two of them as slots (:meth:`SessionStore.chordAt`,
:meth:`SessionStore.directiveHintAt`), Python code all of them
(:meth:`SessionStore.direct`).
"""

import dataclasses
import json
import logging
import warnings
from typing import Any, Dict, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import QQmlPropertyMap

from chordnotepad.session import formatting
from chordnotepad.session.bridge import (
    EVENT_TYPES, REQUEST_TYPES, SESSION_COMMANDS, STATE_TYPES, SessionBridge, to_json_value,
)
from chordnotepad.session.host import Host

logger = logging.getLogger(__name__)

#: The session methods called directly, for the value they return. Every
#: other session method is a bridge command (``submit``). ``picker_at`` is
#: the ▾ value picker's lookup (plan step D5, value_picker.py).
#: The player bar's (plan step E, player_bar.py): ``timeline_offset`` (is
#: there anywhere to seek to; the seek is the ``seek_to_bar`` command),
#: ``timeline_position``, ``setting_directive_start``, and ``volume``,
#: ``muted`` and ``metronome_volume``, which are properties (read, not called).
#: The chrome's (plan step F, chrome.py and files.py): ``ui_scale`` and
#: ``menu_bar_shown`` (properties) and ``document_ref``, the picked file's
#: reference.
#: The chord sheet's (plan step E4, chord_sheet.py): ``chord_sheet_buffer``
#: (the packed view; called off the GUI thread, as Android does) and
#: ``logical_chord_sheet_height`` (the Edit panel's saved height, B3).
#: The rail's (plan step F5, sidebars.py): ``sidebar`` and ``sidebar_width``,
#: properties (the open sidebar and its width, kept in the config).
#: ``dismissed_notices``, a property: the notices dismissed for good (the
#: staff's rhythm notice, chord_sheet.py).
DIRECT_CALLS = frozenset({"directive_hint_at", "chord_at", "licence_catalog", "settings_values",
                          "picker_at", "timeline_offset", "timeline_position",
                          "setting_directive_start", "volume", "muted", "metronome_volume",
                          "ui_scale", "menu_bar_shown", "document_ref",
                          "chord_sheet_buffer", "logical_chord_sheet_height",
                          "sidebar", "sidebar_width", "dismissed_notices"})

_STATE_NAMES = frozenset(t.__name__ for t in STATE_TYPES)
_EVENT_NAMES = frozenset(t.__name__ for t in EVENT_TYPES)
_REQUEST_NAMES = frozenset(t.__name__ for t in REQUEST_TYPES)
#: Shown after delivery, like the requests (see the module docstring).
_CLOSE_APPROVED = "CloseApproved"

#: Texts the window shows that the session has as constants, not as states.
TEXTS = {
    "appName": "Chord Notepad",
    "confirmDiscardTitle": formatting.CONFIRM_DISCARD_TITLE,
    "confirmDiscardMessage": formatting.CONFIRM_DISCARD_MESSAGE,
    # The empty editor's placeholder, the Tk window's.
    "editorPlaceholder": "Type or paste a song here",
}


def _whole_numbers(command: str, args: Any) -> Any:
    """``args`` with QML's numbers made ints where the command takes an int.

    A JavaScript number is a double, so QML's ``{ program: 24 }`` arrives as
    24.0, which the bridge refuses for an ``int`` parameter. Whole numbers
    for those become ints; anything else is left for the bridge to judge.
    """
    spec = SESSION_COMMANDS.get(str(command))
    if not spec or not isinstance(args, dict):
        return args
    fixed = dict(args)
    for name, kind in spec.items():
        value = fixed.get(name)
        if kind.split("|")[0] == "int" and isinstance(value, float) and value.is_integer():
            fixed[name] = int(value)
    return fixed


def _property_map(parent: QObject) -> QQmlPropertyMap:
    # PySide6 6.12 only binds QQmlPropertyMap's plain constructor, which Qt
    # deprecated in favour of a C++-only template; it works as before.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        mapping = QQmlPropertyMap()
    mapping.setParent(parent)
    return mapping


class SessionStore(QObject):
    """A session's output for QML, and its commands.

    Create it on the session thread (the GUI thread): it subscribes to the
    session at once, and the session replays every state into the maps.

    Args:
        host: The session's host (posts commands and the deferred outputs).
        session: The :class:`~chordnotepad.session.session.AppSession`.
    """

    #: A state's map was updated (its type name).
    stateChanged = Signal(str)
    #: An event (its type name and fields), in delivery order.
    event = Signal(str, "QVariant")
    #: A request (its type name and fields), after delivery.
    request = Signal(str, "QVariant")
    #: The session approved closing the window (after delivery).
    closeApproved = Signal()

    def __init__(self, host: Host, session: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._host = host
        self._session = session
        self._closed = False
        self._states = _property_map(self)
        self._maps: Dict[str, QQmlPropertyMap] = {}
        for state_type in STATE_TYPES:
            mapping = _property_map(self)
            for field in dataclasses.fields(state_type):
                mapping.insert(field.name, None)
            self._maps[state_type.__name__] = mapping
            self._states.insert(state_type.__name__, mapping)
        self._bridge = SessionBridge(host, session, self._receive)

    # -- for QML ------------------------------------------------------------------

    def _get_states(self) -> QObject:
        return self._states

    #: The state maps by type name (see the module docstring).
    states = Property(QObject, _get_states, constant=True)

    def _get_texts(self) -> dict:
        return dict(TEXTS)

    #: Fixed texts (:data:`TEXTS`).
    texts = Property("QVariantMap", _get_texts, constant=True)

    @Slot(str)
    @Slot(str, "QVariant")
    def submit(self, command: str, args: Any = None) -> None:
        """Queue ``command`` with ``args`` (its keyword arguments) for the session.

        Ignored once the store is closed (the window is going away).
        """
        if self._closed:
            logger.debug("Command %s after the store closed; ignored", command)
            return
        args = _whole_numbers(command, args)
        try:
            payload = json.dumps(args if args is not None else {}, ensure_ascii=False,
                                 allow_nan=False)
        except (TypeError, ValueError):
            # Passed on as it is: dispatch reports it as an UnexpectedError.
            payload = repr(args)
        self._bridge.submit(str(command), payload)

    @Slot(int, result="QVariant")
    def chordAt(self, offset: int) -> Any:  # noqa: N802 (Qt)
        """The chord span at code-point ``offset`` (``{start, end, kind, ...}``), or null."""
        return to_json_value(self.direct("chord_at", int(offset)))

    @Slot(int, result="QVariant")
    def directiveHintAt(self, offset: int) -> Any:  # noqa: N802 (Qt)
        """The directive hint at code-point ``offset`` (a ``DirectiveHint``'s fields)."""
        return to_json_value(self.direct("directive_hint_at", int(offset)))

    # -- for Python -------------------------------------------------------------

    def direct(self, name: str, *args: Any) -> Any:
        """Call one of the :data:`DIRECT_CALLS` and return its value.

        Raises:
            ValueError: For any other name.
        """
        if name not in DIRECT_CALLS:
            raise ValueError(f"{name!r} is not a direct call; submit it as a command")
        value = getattr(self._session, name)
        return value(*args) if callable(value) else value

    def after_commands(self, callback) -> None:
        """Run ``callback`` once the session has run every command submitted
        so far (commands and this run in order on the host)."""
        self._host.post(callback)

    def state(self, type_name: str) -> QQmlPropertyMap:
        """The map of one state type (KeyError for a name that isn't one)."""
        return self._maps[type_name]

    @property
    def closed(self) -> bool:
        """Whether :meth:`close` was called (the window is going away)."""
        return self._closed

    def close(self) -> None:
        """Stop forwarding output and taking commands (on the session thread)."""
        if self._closed:
            return
        self._closed = True
        self._bridge.close()

    # -- from the bridge ----------------------------------------------------------

    def _receive(self, type_name: str, payload: str) -> None:
        """One output, on the session thread, during delivery."""
        if self._closed:
            return
        data = json.loads(payload)
        if type_name in _STATE_NAMES:
            mapping = self._maps[type_name]
            for key, value in data.items():
                if mapping.value(key) != value:
                    mapping.insert(key, value)
            self.stateChanged.emit(type_name)
        elif type_name == _CLOSE_APPROVED:
            self._host.post(self._emit_close_approved)
        elif type_name in _REQUEST_NAMES:
            self._host.post(lambda: self._emit_request(type_name, data))
        elif type_name in _EVENT_NAMES:
            self.event.emit(type_name, data)
        else:
            logger.warning("Session output of unknown type %s dropped", type_name)

    def _emit_request(self, type_name: str, data: dict) -> None:
        if not self._closed:
            self.request.emit(type_name, data)

    def _emit_close_approved(self) -> None:
        if not self._closed:
            self.closeApproved.emit()
