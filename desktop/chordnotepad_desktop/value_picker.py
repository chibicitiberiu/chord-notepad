"""The ▾ value pickers after a directive (plan step D5): the Python side.

The chip and the popup are QML (``EditorPane.qml``, ``ValuePicker.qml``);
everything they decide with is here, over the core's
:mod:`chordnotepad.session.pickers` and the session:

* :meth:`ValuePickerModel.pickerAt` is the directive under the pointer
  (the chip follows the hover) and :attr:`ValuePickerModel.caretPicker` the
  one at the caret, both from the session's ``picker_at`` (a direct call):
  the kind, the directive's span and its value's, and what the picker shows
  (``PickerOptions`` as plain data), plus ``initial``: the numbers the boxes
  start from, read from the value as typed.
* :meth:`ValuePickerModel.valueFor` composes a value from what was picked
  (the core's ``tempo_value``, ``time_value``, ``loop_value``), or "" when
  it isn't one.
* :meth:`ValuePickerModel.tap` is a press of the tempo picker's Tap: the
  time from a monotonic clock, and the tempo tapped so far from the core's
  :func:`~chordnotepad.session.toolbar.tap_tempo`. Nothing is written until
  Apply, like a typed number.
* :meth:`ValuePickerModel.apply` sends it: ``replace_directive_value``, a
  bridge command, one undo step; the session checks it like the Tk Insert
  dialogs' values and puts the caret after the ``}``.

Positions in and out are Qt (UTF-16) positions; ``cpStart``/``cpEnd`` are
the session's code-point span. Lookups wait while a ``set_text`` is still
queued (the session's offsets would be the older text's).

Labels and comments have no picker (``picker_at`` is None there), and
neither does a read-only editor (QML hides the chip while playing and in
Play).
"""

import logging
import re
import time
from typing import Any, Callable, List, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from chordnotepad.constants import TIME_SIGNATURE_UNITS
from chordnotepad.session import pickers, toolbar
from chordnotepad.session.bridge import to_json_value

logger = logging.getLogger(__name__)

_TIME = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")


def _clamp(value: float, field: pickers.NumberField) -> float:
    """``value`` inside ``field``'s range, on its step."""
    value = min(max(value, field.minimum), field.maximum)
    steps = round((value - field.minimum) / field.step)
    return field.minimum + steps * field.step


def _number(value: float) -> Any:
    """A whole number as an int (QML shows ``3``, not ``3.0``)."""
    return int(value) if float(value).is_integer() else float(value)


def initial_values(picker: pickers.DirectivePicker) -> dict:
    """What the picker's boxes start from, read from the value as typed.

    * time: ``beats`` and ``unit`` (4/4 when the value isn't a time);
    * tempo: ``form`` and its ``number``, inside the form's range;
    * capo: ``fret`` (0 when it isn't one);
    * loop: ``label`` (only one the picker offers, else "") and ``count``
      (what the loop plays now: 2 without a count).
    """
    options = picker.options
    current = options.current
    if picker.kind == pickers.TIME:
        match = _TIME.match(current)
        beats, unit = (int(match.group(1)), int(match.group(2))) if match else (4, 4)
        if beats not in pickers.BEATS or unit not in TIME_SIGNATURE_UNITS:
            beats, unit = 4, 4
        return {"beats": beats, "unit": unit}
    if picker.kind == pickers.TEMPO:
        form, number = pickers.tempo_form(current)
        field = pickers.TEMPO_NUMBERS.get(form)
        return {"form": form, "number": _number(_clamp(number, field)) if field else 0}
    if picker.kind == pickers.CAPO:
        try:
            fret = int(current)
        except ValueError:
            fret = 0
        return {"fret": int(_clamp(fret, pickers.FRET))}
    if picker.kind == pickers.LOOP:
        label, count = pickers.loop_parts(current)
        offered = [c.value for group in options.groups for c in group.choices]
        return {"label": label if label in offered else "",
                "count": int(_clamp(count, pickers.LOOP_COUNT))}
    return {}


def compose_value(kind: str, parts: dict) -> str:
    """The directive value for what was picked, or "" when it isn't one.

    ``parts``: ``value`` (a chip: a key, a time preset), ``beats`` and
    ``unit`` (time), ``form`` and ``number`` (tempo), ``fret`` (capo),
    ``label`` and ``count`` (loop).
    """
    try:
        if kind == pickers.KEY:
            return str(parts.get("value") or "")
        if kind == pickers.TIME:
            if parts.get("value"):
                return str(parts["value"])
            return pickers.time_value(int(parts["beats"]), int(parts["unit"]))
        if kind == pickers.TEMPO:
            return pickers.tempo_value(str(parts["form"]), float(parts.get("number") or 0))
        if kind == pickers.CAPO:
            fret = float(parts["fret"])
            return str(int(fret)) if fret in pickers.FRET else ""
        if kind == pickers.LOOP:
            return pickers.loop_value(str(parts.get("label") or ""), int(parts["count"]))
    except (KeyError, TypeError, ValueError) as e:
        logger.debug("No %s value from %r: %s", kind, parts, e)
    return ""


class ValuePickerModel(QObject):
    """The pickers' lookups and the pick (see the module docstring).

    Args:
        store: The window's SessionStore (``picker_at``, the command).
        editor: The EditorBridge (the caret, offsets).
        clock: The Tap button's time source, in seconds (tests pass a fake).
    """

    #: :attr:`caretPicker` changed.
    caretPickerChanged = Signal()
    #: :attr:`tapCount` changed.
    tapsChanged = Signal()

    #: The tap times kept: enough for any count's last intervals.
    _TAPS_KEPT = 64

    def __init__(self, store: Any, editor: Any, parent: Optional[QObject] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self._clock = clock
        self._taps: List[float] = []
        self._caret: dict = {}
        self._caret_due = False
        # The caret's picker was for the old text: gone until it is looked up again.
        editor.textChanged.connect(self._forget_caret)

    # -- lookups ----------------------------------------------------------------------

    def _picker(self, offset: int) -> dict:
        """The picker at code-point ``offset`` for QML, or {}."""
        picker = self._store.direct("picker_at", offset)
        if picker is None:
            return {}
        to_utf16 = self._editor.to_utf16
        return {
            "kind": picker.kind,
            "start": to_utf16(picker.start), "end": to_utf16(picker.end),
            "valueStart": to_utf16(picker.value_start), "valueEnd": to_utf16(picker.value_end),
            "cpStart": picker.start, "cpEnd": picker.end,
            "current": picker.options.current,
            "options": to_json_value(picker.options),
            "initial": initial_values(picker),
        }

    @Slot(int, result="QVariantMap")
    def pickerAt(self, position: int) -> dict:  # noqa: N802 (Qt)
        """The picker of the directive the character at Qt ``position`` is
        in (the pointer is over it), or {}: none there, past a line's end, or
        the session hasn't got the text shown yet."""
        offset = self._editor.char_offset(position)
        if offset is None or self._store.closed or not self._editor.in_step:
            return {}
        found = self._picker(offset)
        if found and not found["cpStart"] <= offset < found["cpEnd"]:
            return {}
        return found

    def _get_caret_picker(self) -> dict:
        return self._caret

    #: The picker of the directive at the caret (in it, or just after its
    #: ``}``), or {} (Alt+Down opens it; the chip shows for it).
    caretPicker = Property("QVariantMap", _get_caret_picker, notify=caretPickerChanged)

    @Slot()
    def refreshCaret(self) -> None:  # noqa: N802 (Qt)
        """Look the caret's picker up once the session has run the commands
        queued so far (the caret moved; typing sends the text first)."""
        if self._caret_due:
            return
        self._caret_due = True
        self._store.after_commands(self._update_caret)

    def _forget_caret(self) -> None:
        if self._caret:
            self._caret = {}
            self.caretPickerChanged.emit()
        self.refreshCaret()

    def _update_caret(self) -> None:
        self._caret_due = False
        if self._store.closed:
            return
        if not self._editor.in_step:
            self.refreshCaret()     # more typing came in: after that
            return
        cursor = self._editor.cursor_position()
        found = {} if cursor is None else self._picker(self._editor.to_code_point(cursor))
        if found != self._caret:
            self._caret = found
            self.caretPickerChanged.emit()

    # -- tap tempo --------------------------------------------------------------------

    @Slot(result=int)
    def tap(self) -> int:
        """A press of Tap: the tempo tapped so far, or 0 before the count's
        second tap (a pause starts a new count: :func:`toolbar.tap_tempo`)."""
        self._taps.append(float(self._clock()))
        del self._taps[:-self._TAPS_KEPT]
        self.tapsChanged.emit()
        return toolbar.tap_tempo(self._taps) or 0

    @Slot()
    def resetTaps(self) -> None:  # noqa: N802 (Qt)
        """Forget the taps (the picker opened again)."""
        if self._taps:
            self._taps = []
            self.tapsChanged.emit()

    def _get_tap_count(self) -> int:
        return toolbar.tap_count(self._taps)

    #: The taps in the current count (0 before the first).
    tapCount = Property(int, _get_tap_count, notify=tapsChanged)

    # -- the pick ---------------------------------------------------------------------

    @Slot(str, "QVariantMap", result=str)
    def valueFor(self, kind: str, parts: dict) -> str:  # noqa: N802 (Qt)
        """The value for what was picked (:func:`compose_value`)."""
        return compose_value(kind, dict(parts))

    @Slot("QVariantMap", str, result=bool)
    def apply(self, picker: dict, value: str) -> bool:
        """Give ``picker``'s directive the value ``value`` (one undo step).

        False, and nothing sent, when ``value`` is empty or the directive
        isn't there any more (the text changed while the picker was open).
        """
        if not value or not picker or self._store.closed or not self._editor.in_step:
            return False
        start, end = int(picker["cpStart"]), int(picker["cpEnd"])
        now = self._store.direct("picker_at", start)
        if now is None or (now.start, now.end) != (start, end):
            logger.info("The directive at %d-%d changed while its picker was open", start, end)
            return False
        if value == now.options.current:
            return True             # nothing to change: no empty undo step
        self._store.submit("replace_directive_value", {"span": [start, end], "value": value})
        return True
