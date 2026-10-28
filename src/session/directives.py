"""Building and validating the directives the Insert menu adds.

The Tk dialogs (and later the Android sheets) only collect the raw field
values; the wording of a directive, the checks on it and their messages live
here so every UI inserts and rejects the same things. The session validates
again when the answer comes back, so a view that skips the live check can't
insert a broken directive.

A directive's fields arrive as a ``{field: value}`` mapping of strings (ints
are accepted too), so the bridge can pass them as a JSON object:

========  ===========================================
kind      fields
========  ===========================================
``bpm``   ``value``: ``110``, ``+20``, ``20%``, ``2x``, ``reset``
``time``  ``beats``, ``unit``
``key``   ``key``: one of the key options of the notation
``label`` ``label``: letters, digits and underscores
``loop``  ``label``: ``@start`` or a label, ``count``
========  ===========================================
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Tuple

from models.directive import DirectiveType
from models.notation import Notation
from session.toolbar import key_options

LOOP_START = "@start"
"""The loop target meaning "the beginning of the song"."""

INVALID_INPUT = "Invalid Input"
DUPLICATE_LABEL = "Duplicate Label"

_LABEL_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_UNITS = (1, 2, 4, 8, 16)


class DirectiveKind(str, Enum):
    """The directives the Insert menu offers."""

    BPM = "bpm"
    TIME = "time"
    KEY = "key"
    LABEL = "label"
    LOOP = "loop"


@dataclass(frozen=True)
class DirectiveProblem:
    """Why the values can't make a directive, worded for the user.

    Attributes:
        title: A short title (the error dialog's title on desktop).
        message: What to fix.
    """

    title: str
    message: str


class InvalidDirective(ValueError):
    """Raised by :func:`build_directive` for values that don't validate."""

    def __init__(self, problem: DirectiveProblem) -> None:
        """Wrap ``problem``; its message becomes the exception text."""
        super().__init__(problem.message)
        self.problem = problem


def existing_labels(lines: Iterable[Any]) -> Tuple[str, ...]:
    """The names of the ``{label: ...}`` directives in a detected song, sorted.

    Args:
        lines: Detected lines (``Line`` objects with ``directives``).
    """
    names = {d.label for line in lines for d in line.directives
             if d.type == DirectiveType.LABEL and d.label}
    return tuple(sorted(names))


def loop_label_choices(labels: Iterable[str]) -> Tuple[str, ...]:
    """What a loop can jump back to: the song's start, then the labels, sorted."""
    return (LOOP_START,) + tuple(sorted(set(labels) - {LOOP_START}))


def check_directive(kind: str, values: Mapping[str, Any], *,
                    existing_labels: Iterable[str] = (),
                    notation: str = Notation.AMERICAN.value) -> Optional[DirectiveProblem]:
    """Check the values for a directive.

    Args:
        kind: A :class:`DirectiveKind` value.
        values: The directive's fields (see the module docstring).
        existing_labels: Labels already in the song (a new label must not
            repeat one).
        notation: The notation the key options are in.

    Returns:
        None if the values make a valid directive, else what is wrong.

    Raises:
        ValueError: If ``kind`` is not a directive kind.
    """
    kind = DirectiveKind(kind)
    if kind is DirectiveKind.BPM:
        return _check_bpm(_field(values, "value"))
    if kind is DirectiveKind.TIME:
        return _check_time(_field(values, "beats"), _field(values, "unit"))
    if kind is DirectiveKind.KEY:
        key = _field(values, "key")
        if key not in key_options(notation):
            return _invalid("Please select a key.")
        return None
    if kind is DirectiveKind.LABEL:
        return _check_label(_field(values, "label"), set(existing_labels))
    return _check_loop(_field(values, "label"), _field(values, "count"))


def directive_text(kind: str, values: Mapping[str, Any]) -> str:
    """The directive for already-checked values, e.g. ``{loop: chorus 2}``.

    Raises:
        ValueError: If ``kind`` is not a directive kind.
    """
    kind = DirectiveKind(kind)
    if kind is DirectiveKind.BPM:
        return f"{{bpm: {_field(values, 'value')}}}"
    if kind is DirectiveKind.TIME:
        return f"{{time: {int(_field(values, 'beats'))}/{int(_field(values, 'unit'))}}}"
    if kind is DirectiveKind.KEY:
        return f"{{key: {_field(values, 'key')}}}"
    if kind is DirectiveKind.LABEL:
        return f"{{label: {_field(values, 'label')}}}"
    return f"{{loop: {_field(values, 'label')} {int(_field(values, 'count'))}}}"


def build_directive(kind: str, values: Mapping[str, Any], *,
                    existing_labels: Iterable[str] = (),
                    notation: str = Notation.AMERICAN.value) -> str:
    """Check the values and return the directive text.

    Raises:
        InvalidDirective: If the values don't validate (see
            :func:`check_directive`).
        ValueError: If ``kind`` is not a directive kind.
    """
    problem = check_directive(kind, values, existing_labels=existing_labels, notation=notation)
    if problem is not None:
        raise InvalidDirective(problem)
    return directive_text(kind, values)


# -- the checks --------------------------------------------------------------------


def _field(values: Mapping[str, Any], name: str) -> str:
    value = values.get(name)
    return "" if value is None else str(value).strip()


def _invalid(message: str) -> DirectiveProblem:
    return DirectiveProblem(INVALID_INPUT, message)


def _is_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _as_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except ValueError:
        return None


def _check_bpm(value: str) -> Optional[DirectiveProblem]:
    if not value:
        return _invalid("Please enter a BPM value.")
    if value.lower() in ("reset", "original"):
        return None
    if value.endswith("%"):
        return None if _is_float(value[:-1]) else _invalid("Invalid percentage value.")
    if value.endswith("x"):
        return None if _is_float(value[:-1]) else _invalid("Invalid multiplier value.")
    if value.startswith(("+", "-")):
        return None if _as_int(value) is not None else _invalid("Invalid relative BPM value.")
    bpm = _as_int(value)
    if bpm is None:
        return _invalid("Invalid BPM value.")
    if bpm < 20 or bpm > 300:
        return _invalid("BPM must be between 20 and 300.")
    return None


def _check_time(beats: str, unit: str) -> Optional[DirectiveProblem]:
    beats_n = _as_int(beats)
    if beats_n is None or not 1 <= beats_n <= 16:
        return _invalid("Beats must be between 1 and 16.")
    if _as_int(unit) not in _UNITS:
        return _invalid("Beat unit must be 1, 2, 4, 8, or 16.")
    return None


def _check_label(label: str, existing: set) -> Optional[DirectiveProblem]:
    if not label:
        return _invalid("Please enter a label name.")
    if not _LABEL_RE.match(label):
        return _invalid("Label name can only contain letters, numbers, and underscores.")
    if label in existing:
        return DirectiveProblem(
            DUPLICATE_LABEL,
            f"A label named '{label}' already exists. Please use a unique name.")
    return None


def _check_loop(label: str, count: str) -> Optional[DirectiveProblem]:
    if not label:
        return _invalid("Please select a label.")
    if label != LOOP_START and not _LABEL_RE.match(label):
        return _invalid("Please select a label.")
    count_n = _as_int(count)
    if count_n is None or count_n < 1:
        return _invalid("Loop count must be at least 1.")
    return None

