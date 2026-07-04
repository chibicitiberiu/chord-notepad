"""Configuration model for the fretboard voicing model (guitar, ukulele, banjo, ...).

A "voicing" is a named configuration made of a *model* (the engine that
renders it: fretboard, ensemble, piano) plus that model's parameters. This
module defines the parameters for a fretboard-model voicing: a
:class:`FretboardSpec` describes one fretted instrument's tuning and physical
limits (fret range, finger count, stretch), plus a set of tunable weights
that steer the fingering search (open/full voicings, low position, bass
correctness, hand movement, and so on).

This generalizes what used to be hard-coded on ``GuitarChordPicker`` (its
``TUNINGS`` dict and ``SCORE_*`` class constants) so that arbitrary fretted
instruments -- not just six-string guitar -- can be described as data. This
module only defines the *data*; the fingering-search engine itself (the
future generalized ``GuitarChordPicker``) lives elsewhere and is not part of
this module.

The tuning is given in **string order**, lowest string first (the string a
right-handed player would strike first / the thickest string), not sorted by
pitch: re-entrant tunings such as the ukulele's high-G ("my dog has fleas",
G4-C4-E4-A4, where the first string sounds *above* the second) are legal and
must be preserved in that order.
"""
from dataclasses import dataclass, field
import copy
import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from exceptions import ConfigurationError
from models.ensemble_spec import parse_note_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pitch resolution
# ---------------------------------------------------------------------------


def _resolve_string_pitch(value: Union[int, str], *, context: str) -> int:
    """Resolve one open-string tuning entry (MIDI int or note name) to a MIDI int.

    Used by :meth:`FretboardSpec.from_dict` to accept either representation
    for each entry of ``tuning``. ``context`` is a short human-readable label
    prefixed to any error, e.g. ``"Fretboard 'standard', string 0"``.
    """
    if isinstance(value, bool):
        raise ConfigurationError(
            f"{context}: pitch must be a MIDI int or note-name string, got bool"
        )
    if isinstance(value, int):
        midi: Optional[int] = value
    elif isinstance(value, str):
        midi = parse_note_name(value)
        if midi is None:
            raise ConfigurationError(f"{context}: invalid note name {value!r}")
    else:
        raise ConfigurationError(
            f"{context}: pitch must be a MIDI int or note-name string, got {type(value).__name__}"
        )
    if not (0 <= midi <= 127):
        raise ConfigurationError(f"{context}: MIDI note {midi} is out of range 0-127")
    return midi


# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

#: Default tunables for the fretboard voicing engine, tuned for standard
#: six-string guitar. A future Options -> Voices UI edits a copy of this (via
#: :meth:`FretboardSpec.from_dict`'s ``weights`` override), so keep the keys
#: stable.
#:
#: Every value here is a **positive magnitude** -- the picker decides whether
#: each one is a reward or a penalty and applies the sign itself, so that a
#: future weights UI can show every slider as "more = stronger effect"
#: without needing to know which weights used to be negative internally.
#: The comment on each entry names the ``GuitarChordPicker.SCORE_*`` class
#: constant it replaces (see ``src/audio/guitar_chord_picker.py``); entries
#: marked "sign flipped" were negative (penalties) on the old constant and
#: are now stored as their positive magnitude.
DEFAULT_WEIGHTS: Dict[str, float] = {
    'sounding_string_bonus': 1.2,     # was SCORE_PER_SOUNDING
    'open_string_bonus': 0.5,         # was SCORE_PER_OPEN
    'bass_note_bonus': 8.0,           # was SCORE_BASS
    'slash_bass_bonus': 12.0,         # was SCORE_SLASH_BASS
    'span_penalty': 1.2,              # was SCORE_PER_SPAN_FRET (sign flipped)
    'position_penalty': 0.6,          # was SCORE_PER_AVG_FRET (sign flipped)
    'fretted_finger_penalty': 0.5,    # was SCORE_PER_FRETTED (sign flipped)
    'barre_penalty': 1.0,             # was SCORE_BARRE (sign flipped)
    'interior_mute_penalty': 2.0,     # was SCORE_PER_INTERIOR_MUTE (sign flipped)
    'movement_penalty': 1.0,          # was SCORE_PER_MOVE_FRET (sign flipped)
    'kept_finger_bonus': 0.4,         # was SCORE_PER_KEPT_FINGER
}


def _is_plain_number(value: Any) -> bool:
    """True for int/float, explicitly excluding bool (a bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_weights(overrides: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    """Deep-merge a partial weights override onto a fresh copy of :data:`DEFAULT_WEIGHTS`.

    All fretboard weights are flat scalars (unlike the ensemble engine's
    nested ``doubling``/``omit``/``inversion`` weights), so this is a simple
    key-by-key merge. Unknown keys are logged as a warning and ignored, so
    that older configs stay loadable after new weights are added. Wrong-typed
    values raise :class:`ConfigurationError`.
    """
    merged: Dict[str, float] = dict(DEFAULT_WEIGHTS)
    if not overrides:
        return merged

    for key, value in overrides.items():
        if key not in DEFAULT_WEIGHTS:
            logger.warning("Ignoring unknown fretboard weight key: %r", key)
            continue
        if not _is_plain_number(value):
            raise ConfigurationError(
                f"Weight {key!r} must be numeric, got {type(value).__name__}"
            )
        merged[key] = float(value)

    return merged


# ---------------------------------------------------------------------------
# Integer bound validation helpers
# ---------------------------------------------------------------------------


def _validate_int_range(data: Mapping[str, Any], key: str, default: int, lo: int, hi: int, name: str) -> int:
    """Fetch ``data[key]`` (or ``default``) and require it be an int in ``[lo, hi]``."""
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not (lo <= value <= hi):
        raise ConfigurationError(
            f"Fretboard {name!r}: {key!r} must be an integer between {lo} and {hi}, got {value!r}"
        )
    return value


def _validate_int_min(data: Mapping[str, Any], key: str, default: int, lo: int, name: str) -> int:
    """Fetch ``data[key]`` (or ``default``) and require it be an int ``>= lo``."""
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < lo:
        raise ConfigurationError(
            f"Fretboard {name!r}: {key!r} must be an integer >= {lo}, got {value!r}"
        )
    return value


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FretboardSpec:
    """A validated, immutable configuration for a fretted-instrument voicing.

    Construct via :meth:`from_dict` (which validates and applies defaults);
    the bare dataclass constructor performs no validation and is intended
    for internal use (e.g. tests, or building a spec field-by-field once
    each field is already known-good).
    """

    name: str
    """Stable identifier/slug for this fretboard, e.g. ``'standard'``."""

    label: str
    """Human-readable display name for a Voices settings UI, e.g. ``'Guitar (Standard - EADGBE)'``."""

    tuning: Tuple[int, ...]
    """Open-string MIDI pitches, in **string order** (lowest string first).

    Not necessarily ascending: re-entrant tunings (e.g. ukulele's high-G) are
    legal and preserve their natural string order rather than being sorted
    by pitch.
    """

    max_fret: int = 12
    """Highest fret considered when enumerating fingerings (5-24 inclusive)."""

    fingers: int = 4
    """Number of fretting fingers available (1-5 inclusive)."""

    max_span: int = 4
    """Widest fret stretch the fretting hand can hold on a normal pass (>= 1)."""

    relaxed_span: int = 5
    """Widest fret stretch allowed by the relaxation ladder when no fingering
    fits within :attr:`max_span` (>= :attr:`max_span`)."""

    allow_barres: bool = True
    """Whether barre fingerings (one finger covering multiple strings) are permitted."""

    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    """Tunable voicing-engine weights; see :data:`DEFAULT_WEIGHTS` for the full set."""

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> 'FretboardSpec':
        """Parse and validate a ``FretboardSpec`` from a plain dict (e.g. from JSON config).

        Args:
            name: Stable identifier/slug for this fretboard (e.g. ``'standard'``).
            data: Mapping with keys:

                - ``'tuning'`` (required): a list of 3 to 12 entries, in
                  string order (lowest string first), each either a MIDI int
                  (0-127) or a note name such as ``'E2'`` (may be mixed).
                  Re-entrant tunings (an entry higher in pitch than the one
                  before it) are legal and are not reordered.
                - ``'max_fret'`` (optional): int, 5-24, default 12.
                - ``'fingers'`` (optional): int, 1-5, default 4.
                - ``'max_span'`` (optional): int, >= 1, default 4.
                - ``'relaxed_span'`` (optional): int, >= ``max_span``, default 5.
                - ``'allow_barres'`` (optional): bool, default ``True``.
                - ``'weights'`` (optional): a partial dict merged over
                  :data:`DEFAULT_WEIGHTS`. Unknown keys are logged as a
                  warning and ignored; wrong-typed values raise
                  :class:`ConfigurationError`.
                - ``'label'`` (optional): human-readable display name,
                  defaults to ``name`` when omitted.

        Returns:
            A validated, immutable ``FretboardSpec``.

        Raises:
            ConfigurationError: if ``data`` is malformed, listing the
                specific problem (string count out of ``[3, 12]``, an
                unparseable/out-of-range tuning entry, a numeric field out
                of its bounds, ``relaxed_span < max_span``, or a wrong-typed
                value).
        """
        raw_tuning = data.get('tuning')
        if not raw_tuning:
            raise ConfigurationError(f"Fretboard {name!r}: 'tuning' is required and must be non-empty")
        if not (3 <= len(raw_tuning) <= 12):
            raise ConfigurationError(
                f"Fretboard {name!r}: must have between 3 and 12 strings, got {len(raw_tuning)}"
            )
        tuning: Tuple[int, ...] = tuple(
            _resolve_string_pitch(value, context=f"Fretboard {name!r}, string {i}")
            for i, value in enumerate(raw_tuning)
        )

        max_fret = _validate_int_range(data, 'max_fret', 12, 5, 24, name)
        fingers = _validate_int_range(data, 'fingers', 4, 1, 5, name)
        max_span = _validate_int_min(data, 'max_span', 4, 1, name)
        relaxed_span = _validate_int_min(data, 'relaxed_span', 5, 1, name)
        if relaxed_span < max_span:
            raise ConfigurationError(
                f"Fretboard {name!r}: 'relaxed_span' ({relaxed_span}) must be >= "
                f"'max_span' ({max_span})"
            )

        allow_barres = data.get('allow_barres', True)
        if not isinstance(allow_barres, bool):
            raise ConfigurationError(f"Fretboard {name!r}: 'allow_barres' must be a bool")

        weights = _merge_weights(data.get('weights'))
        label = data.get('label', name)
        if not isinstance(label, str):
            raise ConfigurationError(f"Fretboard {name!r}: 'label' must be a string")

        return cls(
            name=name,
            label=label,
            tuning=tuning,
            max_fret=max_fret,
            fingers=fingers,
            max_span=max_span,
            relaxed_span=relaxed_span,
            allow_barres=allow_barres,
            weights=weights,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize back to the plain-dict shape accepted by :meth:`from_dict`.

        Note that ``name`` itself is not part of the returned dict (it is
        passed separately to ``from_dict``, mirroring how it is supplied
        here); round-tripping is ``FretboardSpec.from_dict(spec.name, spec.to_dict())``.
        """
        return {
            'label': self.label,
            'tuning': list(self.tuning),
            'max_fret': self.max_fret,
            'fingers': self.fingers,
            'max_span': self.max_span,
            'relaxed_span': self.relaxed_span,
            'allow_barres': self.allow_barres,
            'weights': copy.deepcopy(dict(self.weights)),
        }

    def weight(self, key: str) -> float:
        """Look up a single weight by key (e.g. ``'span_penalty'``)."""
        return self.weights[key]


def _builtin(name: str, label: str, tuning: List[Union[int, str]],
             weights: Optional[Dict[str, float]] = None) -> FretboardSpec:
    """Build one built-in :class:`FretboardSpec` with all other fields at default."""
    data: Dict[str, Any] = {'label': label, 'tuning': tuning}
    if weights:
        data['weights'] = weights
    return FretboardSpec.from_dict(name, data)


#: Built-in fretboard presets, keyed by the existing ``guitar:<key>`` voicing-string
#: slug used throughout the codebase (see ``src/ui/main_window.py``'s Voicing menu
#: and ``GuitarChordPicker.TUNINGS``, which this data supersedes). All use the
#: engine's default physical limits (``max_fret=12``, ``fingers=4``,
#: ``max_span=4``, ``relaxed_span=5``, ``allow_barres=True``). The guitars use
#: :data:`DEFAULT_WEIGHTS` unchanged; the ukulele overrides two weights (see
#: its comment below). A future Voices UI will let the user override any of
#: these per-voicing.
BUILTIN_FRETBOARDS: Dict[str, FretboardSpec] = {
    'standard': _builtin('standard', 'Guitar (Standard - EADGBE)', [40, 45, 50, 55, 59, 64]),
    'drop_d': _builtin('drop_d', 'Guitar (Drop D)', [38, 45, 50, 55, 59, 64]),
    'dadgad': _builtin('dadgad', 'Guitar (DADGAD)', [38, 45, 50, 55, 57, 62]),
    'open_g': _builtin('open_g', 'Guitar (Open G)', [38, 43, 50, 55, 59, 62]),
    # Re-entrant: G4 (67) sounds higher than the C4 (60) next to it. This is
    # the standard ukulele "my dog has fleas" tuning and is intentionally not
    # sorted into pitch order. The weight overrides account for re-entrancy:
    # everything sounds within one octave, so chasing a root bass (a guitar
    # instinct) drags shapes up the neck for no audible gain, while every one
    # of the four strings ringing matters much more than on a six-string.
    # With these values the picker chooses the standard chord-book shapes
    # (C=0003, G=0232, G7=0212, F=2010, Bb=3211).
    'ukulele': _builtin('ukulele', 'Ukulele', ['G4', 'C4', 'E4', 'A4'],
                        weights={'bass_note_bonus': 1.0, 'sounding_string_bonus': 2.5}),
}
