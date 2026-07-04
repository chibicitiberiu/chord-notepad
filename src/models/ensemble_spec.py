"""Configuration model for the ensemble voicer (N monophonic voices, e.g. SATB).

An :class:`EnsembleSpec` describes a fixed set of monophonic voices (soprano,
alto, tenor, bass, ...) that a future ``EnsembleVoicer`` service will use to
render a song as independent melodic lines instead of block chords: each
voice gets a comfortable range, a maximum leap to its neighbour, and a set of
tunable weights that steer voice-leading choices (parallel fifths/octaves,
doubling preference, leading-tone resolution, and so on).

This module only defines the *data*: parsing/validating a plain dict (as
loaded from JSON config) into a frozen, reusable spec, plus a handful of
built-in ensembles (SATB choir, TTBB, SSA, string quartet). The voicing
engine itself lives elsewhere and is not part of this module.

Voices are always ordered top-first (soprano..bass / highest..lowest), which
is also the order used for ``max_spacing`` (the maximum semitone gap allowed
between voices[i] and voices[i+1]) and for the per-voice weight tuples
returned by :meth:`EnsembleSpec.movement_per_voice`.
"""
from dataclasses import dataclass, field
import copy
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from chord.midi_converter import parse_note_to_semitone
from exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Note-name <-> MIDI conversion
# ---------------------------------------------------------------------------

# Matches a note letter, optional sharps/flats, and a (possibly negative)
# octave digit group, e.g. "C4", "F#3", "Bb2", "C##5", "C-1".
_NOTE_NAME_RE = re.compile(r'^\s*([A-Ga-g])([#b]*)(-?\d+)\s*$')


def parse_note_name(name: str) -> Optional[int]:
    """Convert a note name with octave (e.g. ``'C4'``, ``'F#3'``, ``'Bb2'``) to a MIDI note.

    Follows the same octave convention used throughout the rest of the
    codebase (see ``chord.midi_converter.ChordToMidiConverter``): middle C is
    ``C4`` = MIDI note 60, i.e. ``midi = pitch_class + (octave + 1) * 12``.

    Reuses :func:`chord.midi_converter.parse_note_to_semitone` for the
    letter/accidental part (so ``#``, ``b`` and multiple accidentals resolve
    exactly as they do for chord notes), then applies the octave.

    Returns ``None`` if the string isn't a recognisable note name, or if the
    resulting MIDI note falls outside the valid 0-127 range.
    """
    if not name:
        return None
    match = _NOTE_NAME_RE.match(name)
    if not match:
        return None
    letter, accidentals, octave_str = match.groups()
    pitch_class = parse_note_to_semitone(letter + accidentals)
    if pitch_class is None:
        return None
    midi = pitch_class + (int(octave_str) + 1) * 12
    if not (0 <= midi <= 127):
        return None
    return midi


#: Pitch-class names used by :func:`midi_to_note_name`, sharps convention.
_MIDI_PITCH_CLASS_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


def midi_to_note_name(midi: int) -> str:
    """Convert a MIDI note number to a note name with octave (e.g. ``60`` -> ``'C4'``).

    The inverse of :func:`parse_note_name`, using the sharps convention for
    accidentals (so MIDI 66 renders as ``'F#4'``, never ``'Gb4'``) and the
    same octave convention as the rest of the codebase (middle C is ``C4`` =
    MIDI note 60). The round-trip ``parse_note_name(midi_to_note_name(m))``
    reproduces ``m`` for every ``m`` in ``0..127``.

    Args:
        midi: A MIDI note number, expected in ``0..127``.

    Returns:
        The note name, e.g. ``'C4'`` or ``'F#3'``.
    """
    pitch_class = midi % 12
    octave = midi // 12 - 1
    return f"{_MIDI_PITCH_CLASS_NAMES[pitch_class]}{octave}"


def _resolve_pitch(value: Union[int, str], *, context: str) -> int:
    """Resolve a voice-range endpoint (MIDI int or note name) to a MIDI int.

    Used by :meth:`EnsembleSpec.from_dict` to accept either representation.
    ``context`` is a short human-readable label prefixed to any error, e.g.
    ``"Ensemble 'satb', voice 'Soprano' low"``.
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

#: Default tunables for the ensemble voicing engine, SATB-tuned. A future
#: Options -> Voices UI edits a copy of this (via :meth:`EnsembleSpec.from_dict`'s
#: ``weights`` override), so keep the keys and shapes stable.
#:
#: - ``movement`` / ``bass_movement``: cost per semitone of motion for an
#:   inner/upper voice vs. the bottom voice (``movement`` may also be given as
#:   a per-voice list top->bottom; see :meth:`EnsembleSpec.movement_per_voice`).
#: - ``leap_penalty`` / ``octave_leap_penalty`` / ``tritone_leap_penalty``:
#:   extra cost for a single voice leaping more than a fifth, more than an
#:   octave, or exactly a tritone (6 semitones).
#: - ``common_tone_bonus``: reward for a voice holding the same pitch class.
#: - ``parallel_perfect_penalty``: cost per pair of voices moving in parallel
#:   perfect fifths/octaves.
#: - ``contrary_motion_bonus``: reward for outer voices moving in contrary
#:   motion.
#: - ``seventh_resolution_bonus`` / ``leading_tone_resolution_bonus``: reward
#:   for resolving a chordal 7th down, or a leading tone up, by step.
#: - ``double_leading_tone_penalty``: cost for doubling the leading tone.
#: - ``doubling``: per-chord-tone-role bonus/penalty for which tone gets
#:   doubled when there are more voices than chord tones.
#: - ``omit``: per-role penalty for omitting a chord tone entirely.
#: - ``inversion``: per-inversion bonus/penalty for the chosen bass note.
#: - ``range_comfort_penalty``: cost per semitone a voice sits inside the
#:   outer 2 semitones of its configured range.
#: - ``unison_penalty``: cost per pair of adjacent voices sounding a unison.
#: - ``upper_spacing_penalty``: cost per semitone an upper-voice adjacent gap
#:   exceeds a perfect octave (12 semitones).
DEFAULT_WEIGHTS: Dict[str, Any] = {
    'movement': 0.4,
    'bass_movement': 0.15,
    'leap_penalty': 2.0,
    'octave_leap_penalty': 6.0,
    'tritone_leap_penalty': 3.0,
    'common_tone_bonus': 1.5,
    'parallel_perfect_penalty': 25.0,
    'contrary_motion_bonus': 0.8,
    'seventh_resolution_bonus': 1.5,
    'leading_tone_resolution_bonus': 1.5,
    'double_leading_tone_penalty': 8.0,
    'doubling': {
        'root': 2.0,
        'fifth': 0.5,
        'third': -2.0,
        'seventh': -6.0,
        'color': -6.0,
        'extension': -6.0,
    },
    'omit': {
        'root': 4.0,
        'third': 40.0,
        'fifth': 8.0,
        'seventh': 40.0,
        'color': 30.0,
        'extension': 7.0,
    },
    'inversion': {
        'root': 0.0,
        'first': -1.5,
        'second': -5.0,
        'third': -3.0,
    },
    'range_comfort_penalty': 0.5,
    'unison_penalty': 0.5,
    'upper_spacing_penalty': 0.15,
}

#: Weight keys whose value is itself a per-role mapping rather than a scalar.
_NESTED_WEIGHT_KEYS = ('doubling', 'omit', 'inversion')


def _is_plain_number(value: Any) -> bool:
    """True for int/float, explicitly excluding bool (a bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_weights(overrides: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Deep-merge a partial weights override onto a fresh copy of :data:`DEFAULT_WEIGHTS`.

    Unknown top-level or nested keys are logged as a warning and ignored,
    so that older configs stay loadable after new weights are added.
    Wrong-typed values raise :class:`ConfigurationError`.
    """
    merged: Dict[str, Any] = copy.deepcopy(DEFAULT_WEIGHTS)
    if not overrides:
        return merged

    for key, value in overrides.items():
        if key not in DEFAULT_WEIGHTS:
            logger.warning("Ignoring unknown ensemble weight key: %r", key)
            continue

        if key in _NESTED_WEIGHT_KEYS:
            if not isinstance(value, Mapping):
                raise ConfigurationError(
                    f"Weight {key!r} must be a mapping, got {type(value).__name__}"
                )
            for subkey, subval in value.items():
                if subkey not in merged[key]:
                    logger.warning("Ignoring unknown ensemble weight key: %r.%r", key, subkey)
                    continue
                if not _is_plain_number(subval):
                    raise ConfigurationError(
                        f"Weight {key!r}.{subkey!r} must be numeric, got {type(subval).__name__}"
                    )
                merged[key][subkey] = float(subval)
        elif key == 'movement':
            if isinstance(value, (list, tuple)):
                if not all(_is_plain_number(v) for v in value):
                    raise ConfigurationError("Weight 'movement' list entries must be numeric")
                merged[key] = [float(v) for v in value]
            elif _is_plain_number(value):
                merged[key] = float(value)
            else:
                raise ConfigurationError(
                    f"Weight 'movement' must be a number or list of numbers, got {type(value).__name__}"
                )
        else:
            if not _is_plain_number(value):
                raise ConfigurationError(
                    f"Weight {key!r} must be numeric, got {type(value).__name__}"
                )
            merged[key] = float(value)

    return merged


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceSpec:
    """A single monophonic voice's identity and comfortable pitch range.

    Represents one line of an ensemble (e.g. "Soprano"). ``low`` and
    ``high`` are inclusive MIDI note numbers.
    """

    name: str
    """Display name for this voice, e.g. ``'Soprano'`` or ``'Violin I'``."""

    low: int
    """Lowest MIDI note this voice may be assigned, inclusive."""

    high: int
    """Highest MIDI note this voice may be assigned, inclusive."""


@dataclass(frozen=True)
class EnsembleSpec:
    """A validated, immutable configuration for an N-voice ensemble.

    Construct via :meth:`from_dict` (which validates and applies defaults);
    the bare dataclass constructor performs no validation and is intended
    for internal use (e.g. tests, or building a spec field-by-field once
    each field is already known-good).
    """

    name: str
    """Stable identifier/slug for this ensemble, e.g. ``'satb'``."""

    label: str
    """Human-readable display name for a Voices settings UI, e.g. ``'Choir (SATB)'``."""

    voices: Tuple[VoiceSpec, ...]
    """Voices ordered top-first: soprano..bass (or equivalently highest..lowest)."""

    max_spacing: Tuple[int, ...]
    """Maximum semitone gap allowed between each pair of adjacent voices.

    Has ``len(voices) - 1`` entries; entry ``i`` bounds the gap between
    ``voices[i]`` and ``voices[i + 1]``.
    """

    allow_unisons: bool = True
    """Whether adjacent voices are permitted to sound the same pitch."""

    weights: Mapping[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_WEIGHTS))
    """Tunable voicing-engine weights; see :data:`DEFAULT_WEIGHTS` for the full set."""

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> 'EnsembleSpec':
        """Parse and validate an ``EnsembleSpec`` from a plain dict (e.g. from JSON config).

        Args:
            name: Stable identifier/slug for this ensemble (e.g. ``'satb'``).
            data: Mapping with keys:

                - ``'voices'`` (required): a list of 2 to 8 entries, each
                  ``{'name': str, 'range': [low, high]}``, ordered top voice
                  first. ``low``/``high`` are each either a MIDI int (0-127)
                  or a note name such as ``'C4'`` (may be mixed).
                - ``'max_spacing'`` (optional): a list of ``len(voices) - 1``
                  positive integers, one per adjacent-voice gap. Defaults to
                  12 semitones per gap, except the bottommost gap which
                  defaults to 19 (the octave-plus-a-fifth typically allowed
                  between tenor and bass).
                - ``'allow_unisons'`` (optional): bool, default ``True``.
                - ``'weights'`` (optional): a partial dict deep-merged over
                  :data:`DEFAULT_WEIGHTS`. Unknown keys (top-level or nested)
                  are logged as a warning and ignored; wrong-typed values
                  raise :class:`ConfigurationError`.
                - ``'label'`` (optional): human-readable display name,
                  defaults to ``name`` when omitted.

            Returns:
                A validated, immutable ``EnsembleSpec``.

            Raises:
                ConfigurationError: if ``data`` is malformed, listing the
                    specific problem (voice count out of ``[2, 8]``, a
                    non-increasing range, a ``max_spacing`` list whose length
                    doesn't match ``len(voices) - 1``, a non-positive spacing
                    entry, an unparseable note name, or a wrong-typed value).
        """
        raw_voices = data.get('voices')
        if not raw_voices:
            raise ConfigurationError(f"Ensemble {name!r}: 'voices' is required and must be non-empty")
        if not (2 <= len(raw_voices) <= 8):
            raise ConfigurationError(
                f"Ensemble {name!r}: must have between 2 and 8 voices, got {len(raw_voices)}"
            )

        voices: List[VoiceSpec] = []
        for i, raw_voice in enumerate(raw_voices):
            if not isinstance(raw_voice, Mapping):
                raise ConfigurationError(f"Ensemble {name!r}: voice[{i}] must be a mapping")
            voice_name = raw_voice.get('name')
            if not voice_name or not isinstance(voice_name, str):
                raise ConfigurationError(f"Ensemble {name!r}: voice[{i}] is missing a string 'name'")
            voice_range = raw_voice.get('range')
            if voice_range is None or len(voice_range) != 2:
                raise ConfigurationError(
                    f"Ensemble {name!r}: voice {voice_name!r} must have a 2-element 'range' [low, high]"
                )
            low = _resolve_pitch(
                voice_range[0], context=f"Ensemble {name!r}, voice {voice_name!r} low"
            )
            high = _resolve_pitch(
                voice_range[1], context=f"Ensemble {name!r}, voice {voice_name!r} high"
            )
            if not low < high:
                raise ConfigurationError(
                    f"Ensemble {name!r}: voice {voice_name!r} range must have low < high, "
                    f"got {low} >= {high}"
                )
            voices.append(VoiceSpec(name=voice_name, low=low, high=high))

        n_gaps = len(voices) - 1
        raw_spacing = data.get('max_spacing')
        if raw_spacing is None:
            max_spacing: Tuple[int, ...] = tuple([12] * (n_gaps - 1) + [19])
        else:
            if len(raw_spacing) != n_gaps:
                raise ConfigurationError(
                    f"Ensemble {name!r}: 'max_spacing' must have {n_gaps} entries "
                    f"(one per adjacent voice gap), got {len(raw_spacing)}"
                )
            for spacing_value in raw_spacing:
                if not isinstance(spacing_value, int) or isinstance(spacing_value, bool) or spacing_value <= 0:
                    raise ConfigurationError(
                        f"Ensemble {name!r}: 'max_spacing' entries must be positive integers, "
                        f"got {spacing_value!r}"
                    )
            max_spacing = tuple(raw_spacing)

        allow_unisons = data.get('allow_unisons', True)
        if not isinstance(allow_unisons, bool):
            raise ConfigurationError(f"Ensemble {name!r}: 'allow_unisons' must be a bool")

        weights = _merge_weights(data.get('weights'))
        label = data.get('label', name)
        if not isinstance(label, str):
            raise ConfigurationError(f"Ensemble {name!r}: 'label' must be a string")

        return cls(
            name=name,
            label=label,
            voices=tuple(voices),
            max_spacing=max_spacing,
            allow_unisons=allow_unisons,
            weights=weights,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize back to the plain-dict shape accepted by :meth:`from_dict`.

        Note that ``name`` itself is not part of the returned dict (it is
        passed separately to ``from_dict``, mirroring how it is supplied
        here); round-tripping is ``EnsembleSpec.from_dict(spec.name, spec.to_dict())``.
        """
        return {
            'label': self.label,
            'voices': [
                {'name': voice.name, 'range': [voice.low, voice.high]} for voice in self.voices
            ],
            'max_spacing': list(self.max_spacing),
            'allow_unisons': self.allow_unisons,
            'weights': copy.deepcopy(dict(self.weights)),
        }

    def weight(self, key: str) -> Any:
        """Look up a single weight by top-level key (e.g. ``'leap_penalty'`` or ``'doubling'``)."""
        return self.weights[key]

    def movement_per_voice(self) -> Tuple[float, ...]:
        """Return the per-voice movement weight, ordered top voice first.

        If ``weights['movement']`` is a scalar, it applies to every voice
        except the bottommost, which uses ``weights['bass_movement']``
        instead. If it is a list, it must have one entry per voice
        (top-first) and is used verbatim, overriding ``bass_movement`` for
        the bottom voice too.

        Raises:
            ConfigurationError: if a list-form ``movement`` weight's length
                doesn't match the number of voices.
        """
        n = len(self.voices)
        movement = self.weights.get('movement', DEFAULT_WEIGHTS['movement'])
        if isinstance(movement, (list, tuple)):
            if len(movement) != n:
                raise ConfigurationError(
                    f"Ensemble {self.name!r}: 'movement' list must have one entry per voice "
                    f"({n}), got {len(movement)}"
                )
            return tuple(float(v) for v in movement)
        bass_movement = float(self.weights.get('bass_movement', DEFAULT_WEIGHTS['bass_movement']))
        return tuple([float(movement)] * (n - 1) + [bass_movement])


def _builtin(name: str, label: str, voices: List[Tuple[str, str, str]], max_spacing: List[int]) -> EnsembleSpec:
    """Build one built-in :class:`EnsembleSpec` with default weights.

    ``voices`` is a list of ``(voice_name, low_note_name, high_note_name)``
    tuples, top voice first.
    """
    return EnsembleSpec.from_dict(name, {
        'label': label,
        'voices': [
            {'name': voice_name, 'range': [low, high]} for voice_name, low, high in voices
        ],
        'max_spacing': max_spacing,
    })


#: Built-in ensemble presets, keyed by a voicing-string slug. All use the
#: engine's default weights (:data:`DEFAULT_WEIGHTS`); a future Voices UI
#: will let the user override weights per-ensemble on top of these.
BUILTIN_ENSEMBLES: Dict[str, EnsembleSpec] = {
    'satb': _builtin(
        'satb', 'Choir (SATB)',
        [
            ('Soprano', 'C4', 'G5'),
            ('Alto', 'F3', 'D5'),
            ('Tenor', 'C3', 'G4'),
            ('Bass', 'E2', 'C4'),
        ],
        [12, 12, 19],
    ),
    'ttbb': _builtin(
        'ttbb', 'Male Choir (TTBB)',
        [
            ('Tenor 1', 'C3', 'A4'),
            ('Tenor 2', 'A2', 'F4'),
            ('Baritone', 'F2', 'D4'),
            ('Bass', 'E2', 'C4'),
        ],
        [12, 12, 12],
    ),
    'ssa': _builtin(
        'ssa', 'Treble Choir (SSA)',
        [
            ('Soprano 1', 'C4', 'A5'),
            ('Soprano 2', 'A3', 'F5'),
            ('Alto', 'F3', 'D5'),
        ],
        [12, 12],
    ),
    'quartet': _builtin(
        'quartet', 'String Quartet',
        [
            ('Violin I', 'G3', 'E6'),
            ('Violin II', 'G3', 'C6'),
            ('Viola', 'C3', 'E5'),
            ('Cello', 'C2', 'E4'),
        ],
        [14, 14, 24],
    ),
}
