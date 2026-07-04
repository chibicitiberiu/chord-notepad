"""Configuration model for the piano voicing model (two-hand keyboard).

A "voicing" is a named configuration made of a *model* (the engine that
renders it: fretboard, ensemble, piano) plus that model's parameters. This
module defines the parameters for a piano-model voicing: a :class:`PianoSpec`
describes a pianist's two hands (their playable registers, reach and note
count), a handful of scoring reference points (where the ideal right-hand
register sits, how far the hands should clear each other), and a set of
tunable weights that steer the two-hand optimizer (completeness, register
centering, low-interval clarity, hand-crossing clearance, and voice leading).

This generalizes what used to be hard-coded on ``ChordNotePicker`` (its
``LH_*``/``RH_*`` register constants, ``HAND_*`` physical limits and
``SCORE_*``/``OMIT_PENALTY`` weights) so that a keyboard voicing can be
described as data and edited in the Voices settings UI. This module only
defines the *data*; the two-hand voicing engine itself lives in
``src/audio/chord_picker.py``.

Every weight is a **signed contribution** added directly to a voicing's
score: positive weights are rewards (more = more preferred), negative weights
are penalties (more negative = less preferred), and higher score always wins.
This matches the convention already used by :mod:`models.fretboard_spec` and
:mod:`models.ensemble_spec`, so a weights UI can present every value as a
signed number without knowing which sign the engine "means".
"""
from dataclasses import dataclass, field
import copy
import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from audio.chord_tones import DEFAULT_OMIT_PENALTY
from exceptions import ConfigurationError
from models.ensemble_spec import parse_note_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pitch resolution
# ---------------------------------------------------------------------------


def _resolve_pitch(value: Union[int, str], *, context: str) -> int:
    """Resolve a register endpoint (MIDI int or note name) to a MIDI int.

    Used by :meth:`PianoSpec.from_dict` to accept either representation for
    each range/anchor endpoint. ``context`` is a short human-readable label
    prefixed to any error, e.g. ``"Piano 'grand', 'lh_range' low"``.
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

#: Default tunables for the piano voicing engine. A Voices settings UI edits a
#: copy of this (via :meth:`PianoSpec.from_dict`'s ``weights`` override), so
#: keep the keys and shapes stable.
#:
#: - ``rh_note_bonus``: reward per note kept in the right hand (favours fuller
#:   voicings). Was ``SCORE_PER_RH_NOTE``.
#: - ``rh_center_penalty``: cost per semitone the right hand's mean pitch
#:   strays from :attr:`PianoSpec.rh_center`. Was ``SCORE_CENTER``.
#: - ``lh_below_bass_penalty`` / ``lh_above_bass_penalty``: cost per semitone
#:   the bass sits below/above the preferred bass range. Were
#:   ``SCORE_LH_BELOW_OCT2`` / ``SCORE_LH_ABOVE_OCT2``.
#: - ``lh_double_penalty``: cost applied once when the bass is octave-doubled.
#:   Was ``SCORE_LH_DOUBLE``.
#: - ``lh_double_low_penalty``: extra cost per semitone an octave-doubled bass
#:   sits below the preferred bass range. Was ``SCORE_LH_DOUBLE_LOW``.
#: - ``rh_low_interval_penalty``: cost per close (<= 4 semitone) right-hand
#:   interval sounding below :attr:`PianoSpec.rh_low_interval_floor` (muddy).
#:   Was ``SCORE_RH_LOW_INTERVAL``.
#: - ``rh_wide_gap_penalty``: cost per interior right-hand gap wider than an
#:   octave. Was ``SCORE_RH_WIDE_GAP``.
#: - ``muddy_gap_penalty``: cost per semitone the hands clear each other by
#:   less than :attr:`PianoSpec.hand_gap_floor`. Was ``SCORE_MUDDY_GAP``.
#: - ``common_tone_bonus``: reward per common tone held across a chord change
#:   (voice leading). Was ``SCORE_COMMON_TONE``.
#: - ``movement_penalty``: cost per semitone of nearest-neighbour movement
#:   across a chord change (voice leading). Was ``SCORE_PER_MOVE``.
#: - ``omit``: per-chord-tone-role penalty for omitting a tone entirely, keyed
#:   by the shared role taxonomy in :mod:`audio.chord_tones`. Was
#:   ``OMIT_PENALTY`` (stored positive-magnitude then subtracted; now stored
#:   negative and added, so migrated behaviour is identical).
DEFAULT_WEIGHTS: Dict[str, Any] = {
    'rh_note_bonus': 0.6,
    'rh_center_penalty': -1.4,
    'lh_below_bass_penalty': -1.5,
    'lh_above_bass_penalty': -1.5,
    'lh_double_penalty': -1.0,
    'lh_double_low_penalty': -1.0,
    'rh_low_interval_penalty': -2.0,
    'rh_wide_gap_penalty': -0.6,
    'muddy_gap_penalty': -1.5,
    'common_tone_bonus': 1.5,
    'movement_penalty': -0.35,
    'omit': {role: -penalty for role, penalty in DEFAULT_OMIT_PENALTY.items()},
}

#: Weight keys whose value is itself a per-role mapping rather than a scalar.
_NESTED_WEIGHT_KEYS = ('omit',)


def _is_plain_number(value: Any) -> bool:
    """True for int/float, explicitly excluding bool (a bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_weights(overrides: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Deep-merge a partial weights override onto a fresh copy of :data:`DEFAULT_WEIGHTS`.

    Flat weights are scalars; ``omit`` is a per-role mapping. Unknown top-level
    or nested keys are logged as a warning and ignored, so older configs stay
    loadable after new weights are added. Wrong-typed values raise
    :class:`ConfigurationError`.
    """
    merged: Dict[str, Any] = copy.deepcopy(DEFAULT_WEIGHTS)
    if not overrides:
        return merged

    for key, value in overrides.items():
        if key not in DEFAULT_WEIGHTS:
            logger.warning("Ignoring unknown piano weight key: %r", key)
            continue
        if key in _NESTED_WEIGHT_KEYS:
            if not isinstance(value, Mapping):
                raise ConfigurationError(
                    f"Weight {key!r} must be a mapping, got {type(value).__name__}"
                )
            for subkey, subval in value.items():
                if subkey not in merged[key]:
                    logger.warning("Ignoring unknown piano weight key: %r.%r", key, subkey)
                    continue
                if not _is_plain_number(subval):
                    raise ConfigurationError(
                        f"Weight {key!r}.{subkey!r} must be numeric, got {type(subval).__name__}"
                    )
                merged[key][subkey] = float(subval)
        else:
            if not _is_plain_number(value):
                raise ConfigurationError(
                    f"Weight {key!r} must be numeric, got {type(value).__name__}"
                )
            merged[key] = float(value)

    return merged


# ---------------------------------------------------------------------------
# Numeric validation helpers
# ---------------------------------------------------------------------------


def _validate_int_min(data: Mapping[str, Any], key: str, default: int, lo: int, name: str) -> int:
    """Fetch ``data[key]`` (or ``default``) and require it be an int ``>= lo``."""
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < lo:
        raise ConfigurationError(
            f"Piano {name!r}: {key!r} must be an integer >= {lo}, got {value!r}"
        )
    return value


def _resolve_range(data: Mapping[str, Any], key: str, default: Tuple[int, int], name: str) -> Tuple[int, int]:
    """Resolve a ``[low, high]`` range (MIDI ints or note names) with ``low < high``."""
    raw = data.get(key, default)
    if raw is None or len(raw) != 2:
        raise ConfigurationError(
            f"Piano {name!r}: {key!r} must be a 2-element [low, high] range"
        )
    low = _resolve_pitch(raw[0], context=f"Piano {name!r}, {key!r} low")
    high = _resolve_pitch(raw[1], context=f"Piano {name!r}, {key!r} high")
    if not low < high:
        raise ConfigurationError(
            f"Piano {name!r}: {key!r} must have low < high, got {low} >= {high}"
        )
    return (low, high)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PianoSpec:
    """A validated, immutable configuration for a two-hand keyboard voicing.

    Construct via :meth:`from_dict` (which validates and applies defaults);
    the bare dataclass constructor performs no validation and is intended for
    internal use (e.g. tests, or building a spec field-by-field once each
    field is already known-good).

    All defaults reproduce the original ``ChordNotePicker`` class constants
    exactly, so the default spec is behaviour-preserving.
    """

    name: str
    """Stable identifier/slug for this piano voicing, e.g. ``'grand'``."""

    label: str
    """Human-readable display name for a Voices settings UI, e.g. ``'Grand Piano'``."""

    lh_range: Tuple[int, int] = (24, 48)
    """Left-hand playable register as inclusive MIDI ``(low, high)`` (C1..C3)."""

    rh_range: Tuple[int, int] = (48, 84)
    """Right-hand playable register as inclusive MIDI ``(low, high)`` (C3..C6)."""

    bass_range: Tuple[int, int] = (36, 47)
    """Preferred bass register as inclusive MIDI ``(low, high)`` (C2..B2).

    The bass is not forced here; sitting outside this window costs
    ``lh_below_bass_penalty`` / ``lh_above_bass_penalty`` per semitone."""

    rh_low_anchor: Tuple[int, int] = (48, 64)
    """Window the lowest right-hand note is anchored within, MIDI ``(low, high)`` (C3..E4)."""

    rh_center: float = 63.0
    """Target for the right hand's mean pitch; drift costs ``rh_center_penalty``."""

    rh_low_interval_floor: int = 52
    """Right-hand close intervals below this MIDI note sound muddy (E3)."""

    hand_span: int = 14
    """Widest reach of one hand in semitones (a ninth)."""

    max_notes_per_hand: int = 5
    """Most notes one hand may play (five fingers)."""

    max_total_notes: int = 10
    """Most notes both hands may play together."""

    hand_gap_floor: int = 2
    """The right hand should clear the bass by more than this many semitones."""

    add_bass: bool = True
    """Whether to include the left-hand bass note at all."""

    weights: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_WEIGHTS))
    """Tunable voicing-engine weights; see :data:`DEFAULT_WEIGHTS` for the full set."""

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> 'PianoSpec':
        """Parse and validate a ``PianoSpec`` from a plain dict (e.g. from JSON config).

        Every key is optional: an empty ``data`` (or one carrying only
        ``'model'``) yields the behaviour-preserving default piano voicing.

        Args:
            name: Stable identifier/slug for this piano voicing (e.g. ``'grand'``).
            data: Mapping which may carry any of:

                - ``'lh_range'`` / ``'rh_range'`` / ``'bass_range'`` /
                  ``'rh_low_anchor'`` (optional): a ``[low, high]`` pair, each
                  endpoint a MIDI int (0-127) or a note name such as ``'C3'``.
                  ``low`` must be below ``high``.
                - ``'rh_center'`` (optional): a number (the ideal right-hand
                  mean pitch).
                - ``'rh_low_interval_floor'`` (optional): int >= 0.
                - ``'hand_span'`` / ``'max_notes_per_hand'`` /
                  ``'max_total_notes'`` / ``'hand_gap_floor'`` (optional):
                  ints >= 1 (``hand_gap_floor`` >= 0).
                - ``'add_bass'`` (optional): bool, default ``True``.
                - ``'weights'`` (optional): a partial dict deep-merged over
                  :data:`DEFAULT_WEIGHTS`. Unknown keys (top-level or nested)
                  are logged as a warning and ignored; wrong-typed values raise
                  :class:`ConfigurationError`.
                - ``'label'`` (optional): human-readable display name, defaults
                  to ``name`` when omitted.

        Returns:
            A validated, immutable ``PianoSpec``.

        Raises:
            ConfigurationError: if ``data`` is malformed (a non-increasing
                range, an unparseable/out-of-range pitch, a numeric field out
                of its bounds, or a wrong-typed value).
        """
        lh_range = _resolve_range(data, 'lh_range', (24, 48), name)
        rh_range = _resolve_range(data, 'rh_range', (48, 84), name)
        bass_range = _resolve_range(data, 'bass_range', (36, 47), name)
        rh_low_anchor = _resolve_range(data, 'rh_low_anchor', (48, 64), name)

        rh_center = data.get('rh_center', 63.0)
        if not _is_plain_number(rh_center):
            raise ConfigurationError(
                f"Piano {name!r}: 'rh_center' must be numeric, got {rh_center!r}"
            )

        rh_low_interval_floor = _validate_int_min(data, 'rh_low_interval_floor', 52, 0, name)
        hand_span = _validate_int_min(data, 'hand_span', 14, 1, name)
        max_notes_per_hand = _validate_int_min(data, 'max_notes_per_hand', 5, 1, name)
        max_total_notes = _validate_int_min(data, 'max_total_notes', 10, 1, name)
        hand_gap_floor = _validate_int_min(data, 'hand_gap_floor', 2, 0, name)

        add_bass = data.get('add_bass', True)
        if not isinstance(add_bass, bool):
            raise ConfigurationError(f"Piano {name!r}: 'add_bass' must be a bool")

        weights = _merge_weights(data.get('weights'))
        label = data.get('label', name)
        if not isinstance(label, str):
            raise ConfigurationError(f"Piano {name!r}: 'label' must be a string")

        return cls(
            name=name,
            label=label,
            lh_range=lh_range,
            rh_range=rh_range,
            bass_range=bass_range,
            rh_low_anchor=rh_low_anchor,
            rh_center=float(rh_center),
            rh_low_interval_floor=rh_low_interval_floor,
            hand_span=hand_span,
            max_notes_per_hand=max_notes_per_hand,
            max_total_notes=max_total_notes,
            hand_gap_floor=hand_gap_floor,
            add_bass=add_bass,
            weights=weights,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize back to the plain-dict shape accepted by :meth:`from_dict`.

        ``name`` itself is not part of the returned dict (it is passed
        separately to ``from_dict``); round-tripping is
        ``PianoSpec.from_dict(spec.name, spec.to_dict())``.
        """
        return {
            'label': self.label,
            'lh_range': list(self.lh_range),
            'rh_range': list(self.rh_range),
            'bass_range': list(self.bass_range),
            'rh_low_anchor': list(self.rh_low_anchor),
            'rh_center': self.rh_center,
            'rh_low_interval_floor': self.rh_low_interval_floor,
            'hand_span': self.hand_span,
            'max_notes_per_hand': self.max_notes_per_hand,
            'max_total_notes': self.max_total_notes,
            'hand_gap_floor': self.hand_gap_floor,
            'add_bass': self.add_bass,
            'weights': copy.deepcopy(dict(self.weights)),
        }

    def weight(self, key: str) -> Any:
        """Look up a single weight by top-level key (e.g. ``'rh_center_penalty'`` or ``'omit'``)."""
        return self.weights[key]


#: The default, behaviour-preserving piano voicing. Bare ``"piano"`` selection
#: and an empty ``{"model": "piano"}`` registry entry both resolve to this.
DEFAULT_PIANO = PianoSpec.from_dict('grand', {'label': 'Grand Piano'})

#: Built-in piano presets, keyed by slug. There is a single preset today (the
#: default grand); the Voices UI lets the user derive custom piano voicings
#: from it.
BUILTIN_PIANOS: Dict[str, PianoSpec] = {
    'grand': DEFAULT_PIANO,
}
