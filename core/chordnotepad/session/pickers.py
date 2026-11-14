"""The ▾ value pickers after a directive (the Qt editor), as plain data.

A picker offers the values a directive can take, list-driven and already
valid, the way the Tk Insert dialogs did: every value a picker gives passes
:func:`session.directives.check_directive` and parses as a valid directive.
:func:`picker_options` says what to show for a kind; the view composes the
value with :func:`tempo_value`, :func:`time_value` or :func:`loop_value`
(or takes a choice's ``value``) and sends it to
``AppSession.replace_directive_value``. ``AppSession.picker_at`` finds the
directive at the caret and builds the context.

========  =========================================================================
kind      what it offers
========  =========================================================================
``key``   the 30 keys with a signature (the Insert Key list), majors then minors,
          each in pitch order from C, an enharmonic twin beside its pair
          (natural, then flat, then sharp: D♭ before C♯, B before C♭)
``time``  presets (2/4 ... 12/8), and beats 1-16 over a unit of 1, 2, 4, 8 or 16
``tempo`` the forms (120, +10, −10, 50%, 2x, reset), each with its number's range
``capo``  a fret from 0 to 12 (0: no capo)
``loop``  the labels above the loop in song order, then ``@start``; a count 1-16
========  =========================================================================

Key values are spelled in the song's notation (``Reb``, ``Lam``); labels show
♯ and ♭. Directive keywords map to kinds by :data:`KIND_OF_KEYWORD` (``tempo``
is ``bpm``'s other name).
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from chordnotepad.constants import MAX_BEATS, MAX_BPM, MIN_BEATS, MIN_BPM, TIME_SIGNATURE_UNITS
from chordnotepad.models.notation import AMERICAN_DIRECTIVE_KEYS, Notation, directive_key_names
from chordnotepad.services.key_spelling import pitch_class
from chordnotepad.session.directives import LOOP_START, MAX_CAPO, MIN_CAPO

KEY = "key"
TIME = "time"
TEMPO = "tempo"
CAPO = "capo"
LOOP = "loop"
#: Every picker kind.
KINDS = (KEY, TIME, TEMPO, CAPO, LOOP)
#: The directive keywords with a picker, and its kind.
KIND_OF_KEYWORD = {"bpm": TEMPO, "tempo": TEMPO, "time": TIME, "key": KEY, "capo": CAPO,
                   "loop": LOOP}

#: The time signatures offered as chips (the mockup's presets).
TIME_PRESETS = ("2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8")

#: Loop counts the picker's box offers (a typed {loop} may say more).
MIN_LOOP_COUNT, MAX_LOOP_COUNT = 1, 16
#: The count a {loop} without one plays (the parser's default).
DEFAULT_LOOP_COUNT = 2

#: The labels a loop can name through check_directive (letters, digits, _).
_LABEL_RE = re.compile(r"^[a-zA-Z0-9_]+$")
_LOOP_COUNT_RE = re.compile(r"[+-]?\d+")

_EUROPEAN_ROOTS = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
_PRETTY_ACCIDENTAL = {"": "", "#": "♯", "b": "♭"}
#: Within one pitch class: the natural first, then the flat, then the sharp.
_ACCIDENTAL_ORDER = {"": 0, "b": 1, "#": 2}


@dataclass(frozen=True)
class PickerContext:
    """What a picker needs from the song.

    Attributes:
        notation: ``american`` or ``european`` (the song's): key names.
        labels: The labels above the directive, in song order (a loop can
            only repeat a section above it).
        current: The directive's value now, as typed.
    """

    notation: str = Notation.AMERICAN.value
    labels: Tuple[str, ...] = ()
    current: str = ""


@dataclass(frozen=True)
class PickerChoice:
    """A chip.

    Attributes:
        value: What goes into the directive (a key in the song's notation, a
            time, a tempo, a label).
        label: What the chip shows (♯ and ♭ for keys, − for a slower tempo).
        twin: Key chips: the enharmonic twin's ``value`` ("" when it has none).
        form: Tempo chips: the form the chip picks (``abs``, ``rel``, ...).
    """

    value: str
    label: str
    twin: str = ""
    form: str = ""


@dataclass(frozen=True)
class PickerGroup:
    """Chips under a caption ("Major", "Minor", "Section"; "" for none)."""

    title: str
    choices: Tuple[PickerChoice, ...]


@dataclass(frozen=True)
class NumberField:
    """A number box with a slider.

    Attributes:
        name: Which number: ``bpm``, ``change``, ``percent``, ``multiplier``,
            ``fret``, ``count`` or ``beats``.
        minimum: The smallest value.
        maximum: The largest value.
        step: The slider's step (and the box's).
        caption: The caption above it.
        suffix: After the box ("bpm", "%", "×"; "" for none).
    """

    name: str
    minimum: float
    maximum: float
    step: float
    caption: str
    suffix: str = ""

    def __contains__(self, value: float) -> bool:
        """Whether ``value`` is in range and on the step."""
        if not self.minimum <= value <= self.maximum:
            return False
        steps = (value - self.minimum) / self.step
        return abs(steps - round(steps)) < 1e-9


@dataclass(frozen=True)
class TempoForm:
    """A form of ``{bpm}``: ``abs`` (120), ``rel`` (+10, -10), ``pct``
    (50%), ``mul`` (2x) or ``reset``, with its number (None for reset)."""

    form: str
    number: Optional[NumberField]


@dataclass(frozen=True)
class PickerOptions:
    """What a picker shows.

    Attributes:
        kind: One of :data:`KINDS`.
        current: The directive's value now (a chip whose ``value`` equals
            it is the current one).
        groups: The chips.
        numbers: The number boxes (time: ``beats``; capo: ``fret``; loop:
            ``count``). Tempo's number depends on the form: see ``forms``.
        units: Time: the beat units to pick from.
        forms: Tempo: every form with its number.
    """

    kind: str
    current: str
    groups: Tuple[PickerGroup, ...] = ()
    numbers: Tuple[NumberField, ...] = ()
    units: Tuple[int, ...] = ()
    forms: Tuple[TempoForm, ...] = ()


@dataclass(frozen=True)
class DirectivePicker:
    """The picker for the directive at a place in the text
    (``AppSession.picker_at``).

    Attributes:
        kind: One of :data:`KINDS`.
        start: Where the directive starts (its ``{``); send ``(start, end)``
            to ``replace_directive_value``.
        end: Where it ends (after its ``}``).
        value_start: Where its value starts (the ▾ chip sits after the value).
        value_end: Where its value ends.
        options: What the picker shows.
    """

    kind: str
    start: int
    end: int
    value_start: int
    value_end: int
    options: PickerOptions


# -- keys -----------------------------------------------------------------------------


def _parts(american_key: str) -> Tuple[str, str, bool]:
    """``(letter, accidental, minor)`` of an American key name."""
    minor = american_key.endswith("m")
    root = american_key[:-1] if minor else american_key
    return root[0], root[1:], minor


def _pitch(american_key: str) -> int:
    letter, accidental, _ = _parts(american_key)
    return pitch_class(letter + accidental)


def key_label(american_key: str, notation: str) -> str:
    """A key as a chip shows it: ``D♭``, ``C♯m``; ``Re♭``, ``Do♯m`` in European."""
    letter, accidental, minor = _parts(american_key)
    root = _EUROPEAN_ROOTS[letter] if Notation(notation) is Notation.EUROPEAN else letter
    return root + _PRETTY_ACCIDENTAL[accidental] + ("m" if minor else "")


def key_groups(notation: str) -> Tuple[PickerGroup, ...]:
    """The key chips: "Major" then "Minor", each in pitch order from C with
    enharmonic twins side by side; values spelled in ``notation``."""
    names = directive_key_names(notation)  # index-aligned with the American ones
    groups = []
    for title, minor in (("Major", False), ("Minor", True)):
        keys = [(i, key) for i, key in enumerate(AMERICAN_DIRECTIVE_KEYS)
                if key.endswith("m") == minor]
        keys.sort(key=lambda item: (_pitch(item[1]), _ACCIDENTAL_ORDER[_parts(item[1])[1]]))
        choices = []
        for i, key in keys:
            twin = next((names[j] for j, other in keys
                         if j != i and _pitch(other) == _pitch(key)), "")
            choices.append(PickerChoice(names[i], key_label(key, notation), twin=twin))
        groups.append(PickerGroup(title, tuple(choices)))
    return tuple(groups)


# -- tempo ------------------------------------------------------------------------------


TEMPO_NUMBERS = {
    "abs": NumberField("bpm", MIN_BPM, MAX_BPM, 1, "Beats per minute", "bpm"),
    "rel": NumberField("change", -100, 100, 1, "Change, in bpm", "bpm"),
    "pct": NumberField("percent", 1, 400, 1, "Percent of the tempo", "%"),
    "mul": NumberField("multiplier", 0.25, 4, 0.25, "Multiplier", "×"),
}
TEMPO_CHIPS = (
    PickerChoice("120", "120", form="abs"),
    PickerChoice("+10", "+10", form="rel"),
    PickerChoice("-10", "−10", form="rel"),
    PickerChoice("50%", "50%", form="pct"),
    PickerChoice("2x", "2x", form="mul"),
    PickerChoice("reset", "reset", form="reset"),
)


def tempo_form(value: str) -> Tuple[str, float]:
    """A ``{bpm}`` value's form and number: ``("pct", 50.0)`` for ``50%``,
    ``("reset", 0.0)`` for ``reset``/``original``, ``("abs", n)`` otherwise
    (0 when it isn't a number)."""
    text = value.strip()
    if text.lower() in ("reset", "original"):
        return "reset", 0.0
    for form, suffix in (("pct", "%"), ("mul", "x")):
        if text.endswith(suffix):
            return form, _number(text[:-1])
    if text.startswith(("+", "-")):
        return "rel", _number(text)
    return "abs", _number(text)


def tempo_value(form: str, number: float = 0) -> str:
    """The ``{bpm}`` value for a form and its number: ``"120"``, ``"+10"``,
    ``"-10"``, ``"50%"``, ``"0.25x"``, ``"reset"``.

    Raises:
        ValueError: For an unknown form, or a number outside the form's range
            or off its step.
    """
    if form == "reset":
        return "reset"
    field = TEMPO_NUMBERS.get(form)
    if field is None:
        raise ValueError(f"unknown tempo form {form!r}")
    if number not in field:
        raise ValueError(f"{field.caption} must be {field.minimum:g}-{field.maximum:g} "
                         f"in steps of {field.step:g}, not {number!r}")
    if form == "mul":
        return f"{number:g}x"
    whole = int(round(number))
    if form == "pct":
        return f"{whole}%"
    if form == "rel":
        return f"{whole:+d}"
    return str(whole)


def _number(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


# -- time, loop -----------------------------------------------------------------------------


BEATS = NumberField("beats", MIN_BEATS, MAX_BEATS, 1, "Beats per bar")
FRET = NumberField("fret", MIN_CAPO, MAX_CAPO, 1, "Capo fret (0 = none)")
LOOP_COUNT = NumberField("count", MIN_LOOP_COUNT, MAX_LOOP_COUNT, 1, "Times")


def time_value(beats: int, unit: int) -> str:
    """``"3/4"``.

    Raises:
        ValueError: For beats outside 1-16 or a unit not 1, 2, 4, 8 or 16.
    """
    if beats not in BEATS or unit not in TIME_SIGNATURE_UNITS:
        raise ValueError(f"no time signature {beats!r}/{unit!r}")
    return f"{int(beats)}/{int(unit)}"


def loop_parts(value: str) -> Tuple[str, int]:
    """A ``{loop}`` value's label and count, as the parser reads it: the
    count is the last word when it is a whole number, else
    :data:`DEFAULT_LOOP_COUNT` (``{loop: verse}`` plays the section twice)."""
    stripped = value.strip()
    parts = stripped.rsplit(None, 1)
    if len(parts) == 2 and _LOOP_COUNT_RE.fullmatch(parts[1]):
        return parts[0], int(parts[1])
    return stripped, DEFAULT_LOOP_COUNT


def loop_value(label: str, count: int) -> str:
    """``"chorus 3"``: always with the count, so it plays as many times as
    picked (without one, a loop plays twice).

    Raises:
        ValueError: For a count outside 1-16 or an empty label.
    """
    if not label.strip() or count not in LOOP_COUNT:
        raise ValueError(f"no loop {label!r} {count!r}")
    return f"{label.strip()} {int(count)}"


def loop_labels(labels: Tuple[str, ...]) -> Tuple[str, ...]:
    """What a loop picker offers: the labels above it in song order that a
    ``{loop}`` can name (letters, digits and underscores; once each), then
    ``@start``."""
    seen = []
    for label in labels:
        if label != LOOP_START and _LABEL_RE.match(label) and label not in seen:
            seen.append(label)
    return tuple(seen) + (LOOP_START,)


# -- the picker -------------------------------------------------------------------------------


def song_key_options(notation: str, current: str = "") -> PickerOptions:
    """The Qt player bar's key picker: the toolbar's keys
    (``toolbar.key_options``: roots only, a roman numeral's case says major
    or minor), in ``notation``, with ♯ and ♭ on the chips. Not a directive:
    the pick goes to ``AppSession.set_key``."""
    from chordnotepad.session import toolbar
    choices = tuple(PickerChoice(key, key_label(toolbar.convert_key(key, Notation.AMERICAN.value),
                                                notation))
                    for key in toolbar.key_options(notation))
    return PickerOptions(KEY, current.strip(), groups=(PickerGroup("", choices),))


def picker_options(kind: str, ctx: PickerContext = PickerContext()) -> PickerOptions:
    """What the picker of ``kind`` shows in ``ctx``.

    Raises:
        ValueError: For an unknown kind or notation.
    """
    current = ctx.current.strip()
    if kind == KEY:
        return PickerOptions(KEY, current, groups=key_groups(ctx.notation))
    if kind == TIME:
        chips = tuple(PickerChoice(t, t) for t in TIME_PRESETS)
        return PickerOptions(TIME, current, groups=(PickerGroup("", chips),),
                             numbers=(BEATS,), units=TIME_SIGNATURE_UNITS)
    if kind == TEMPO:
        forms = tuple(TempoForm(form, TEMPO_NUMBERS.get(form))
                      for form in ("abs", "rel", "pct", "mul", "reset"))
        return PickerOptions(TEMPO, current, groups=(PickerGroup("Form", TEMPO_CHIPS),),
                             forms=forms)
    if kind == CAPO:
        return PickerOptions(CAPO, current, numbers=(FRET,))
    if kind == LOOP:
        chips = tuple(PickerChoice(label, label) for label in loop_labels(ctx.labels))
        return PickerOptions(LOOP, current, groups=(PickerGroup("Section", chips),),
                             numbers=(LOOP_COUNT,))
    raise ValueError(f"no picker for {kind!r}; expected one of {KINDS}")

