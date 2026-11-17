"""The version and preset link of a saved voicing, and its migrations.

Every voicing the user saves carries:

* ``version``: how many of :data:`MIGRATIONS` it has been through. A voicing
  without one is version 0 (everything saved before 0.6).
* ``based_on``: the built-in it was copied from, when it was: ``guitar:<slug>``
  (a ``BUILTIN_FRETBOARDS`` key), ``ensemble:<slug>`` (``BUILTIN_ENSEMBLES``)
  or ``piano``. Absent for a blank, a voicing made from scratch, or an
  origin that isn't known.

No screen shows either. Saved weights override a preset's, so a preset
tuned in a later release never reaches a copy of it by itself; the link lets
a migration move the values the user never changed.

Migration ``MIGRATIONS[i]`` moves a voicing from version ``i`` to ``i + 1``.
Each one is a pure function on the voicing dict that returns whether it
changed anything; it changes a value only while that value is one the user
never touched, and it never toggles, so running it twice, or on a dict a
newer release already moved, changes nothing.

ConfigService runs :func:`migrate_voicing` on every voicing at load (and the
Android staging file on what it keeps); a file it changes is backed up first.
"""

import copy
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Tuple

from chordnotepad.exceptions import ConfigurationError

#: The ``based_on`` of a copy of the built-in piano.
PIANO_ID = "piano"


def fretboard_id(slug: str) -> str:
    """The ``based_on`` of a copy of built-in fretboard ``slug``."""
    return f"guitar:{slug}"


def ensemble_id(slug: str) -> str:
    """The ``based_on`` of a copy of built-in ensemble ``slug``."""
    return f"ensemble:{slug}"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _equal(a: Any, b: Any) -> bool:
    """``a == b`` for saved JSON values, where a bool is never a number
    (``True == 1`` in Python) and 3 equals 3.0."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if _is_number(a) or _is_number(b):
        return _is_number(a) and _is_number(b) and float(a) == float(b)
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


# -- 0 -> 1: the link, and the sign repair --------------------------------------------

#: The penalty keys the old v1 config migration negated (services/config_service
#: ``_negate_signed_weights``): it ran on every config saved as version 1, which
#: 0.3.0 to 0.5.4 did for a new config whose voicings were already signed.
FRETBOARD_NEGATED_KEYS = (
    'span_penalty', 'position_penalty', 'fretted_finger_penalty',
    'barre_penalty', 'interior_mute_penalty', 'movement_penalty',
)
ENSEMBLE_NEGATED_FLAT_KEYS = (
    'movement', 'bass_movement', 'leap_penalty', 'octave_leap_penalty',
    'tritone_leap_penalty', 'parallel_perfect_penalty',
    'double_leading_tone_penalty', 'range_comfort_penalty',
    'unison_penalty', 'upper_spacing_penalty',
)


def _infer_based_on(entry: Mapping[str, Any]) -> Optional[str]:
    """The built-in a voicing of 0.5.4 or before was copied from, from its
    label (copies kept the built-in's): an ensemble by its label, a fretboard
    by its label and its tuning (copies of the Standard guitar re-tuned for
    seven strings keep its label), the piano by "Grand Piano". None when it
    can't be told."""
    from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES
    from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec
    from chordnotepad.models.piano_spec import DEFAULT_PIANO

    label = entry.get('label')
    if not isinstance(label, str) or not label:
        return None
    model = entry.get('model')
    if model == 'ensemble':
        for slug, spec in BUILTIN_ENSEMBLES.items():
            if spec.label == label:
                return ensemble_id(slug)
    elif model == 'fretboard':
        try:
            tuning = FretboardSpec.from_dict('copy', {'tuning': entry.get('tuning')}).tuning
        except Exception:  # noqa: BLE001 - a tuning that doesn't parse links to nothing
            return None
        for slug, spec in BUILTIN_FRETBOARDS.items():
            if spec.label == label and tuple(spec.tuning) == tuple(tuning):
                return fretboard_id(slug)
    elif model == 'piano' and label == DEFAULT_PIANO.label:
        return PIANO_ID
    return None


def _flipped(values: List[Any]) -> bool:
    """Every value a number of at least 0, and at least one above 0: what the
    old flip left of penalties that were all at or below 0."""
    return (all(_is_number(value) and value >= 0 for value in values)
            and any(value > 0 for value in values))


def _repair_flipped_signs(entry: MutableMapping[str, Any]) -> bool:
    """Negate back the penalties the old v1 migration turned into rewards.

    A fretboard is repaired only when all six negated keys are there, none
    below 0 and at least one above 0; an ensemble only when its ``omit``
    values are the same (no one rewards dropping the third). Then each of
    those penalties above 0 goes back below 0 (a 0 stays 0). Anything mixed
    is a user's own setting and stays.

    An ensemble repaired back to the omission order 0.3.0 to 0.4.1 used
    (``PREVIOUS_ENSEMBLE_OMIT_WEIGHTS``, exactly) then takes the ensemble
    order, as config v4 moved every undamaged one.
    """
    from chordnotepad.models.ensemble_spec import (
        ENSEMBLE_OMIT_WEIGHTS, PREVIOUS_ENSEMBLE_OMIT_WEIGHTS,
    )

    weights = entry.get('weights')
    if not isinstance(weights, dict):
        return False
    model = entry.get('model')
    if model == 'fretboard':
        if not all(key in weights for key in FRETBOARD_NEGATED_KEYS) or not _flipped(
                [weights[key] for key in FRETBOARD_NEGATED_KEYS]):
            return False
        for key in FRETBOARD_NEGATED_KEYS:
            if weights[key] > 0:
                weights[key] = -weights[key]
        return True
    if model == 'ensemble':
        omit = weights.get('omit')
        if not isinstance(omit, dict) or not omit or not _flipped(list(omit.values())):
            return False
        for role in omit:
            if omit[role] > 0:
                omit[role] = -omit[role]
        for key in ENSEMBLE_NEGATED_FLAT_KEYS:
            value = weights.get(key)
            if _is_number(value) and value > 0:
                weights[key] = -value
            elif isinstance(value, list):
                weights[key] = [-v if _is_number(v) and v > 0 else v for v in value]
        if _equal(omit, PREVIOUS_ENSEMBLE_OMIT_WEIGHTS):
            weights['omit'] = dict(ENSEMBLE_OMIT_WEIGHTS)
        return True
    return False


def _migrate_0_to_1(entry: MutableMapping[str, Any]) -> bool:
    """Infer ``based_on`` (a voicing that has one keeps it) and repair the
    signs the old v1 config migration flipped."""
    changed = False
    if 'based_on' not in entry:
        based_on = _infer_based_on(entry)
        if based_on is not None:
            entry['based_on'] = based_on
            changed = True
    return _repair_flipped_signs(entry) or changed


# -- 1 -> 2: the preset tuning since 0.5.4 reaches copies ------------------------------

#: The 0.5.4 ensemble defaults every built-in ensemble used (``git show
#: v0.5.4:src/models/ensemble_spec.py``), with ``omit`` as config v4 left it.
_V054_INVERSION = {'root': 0.0, 'first': -1.5, 'second': -5.0, 'third': -3.0}
_V054_DOUBLING = {'root': 2.0, 'fifth': 0.5, 'third': -2.0, 'seventh': -6.0,
                  'color': -6.0, 'extension': -6.0}
_V054_OMIT = {'root': -20.0, 'third': -40.0, 'fifth': -3.0, 'seventh': -40.0,
              'color': -30.0, 'extension': -6.0}


def _choir_untouched() -> Dict[str, List[Any]]:
    """The values of a choir copy (SATB, TTBB, SSA) its user never changed:
    the 0.5.4 default, then the default each later key was added with."""
    return {
        'allow_unisons': [True],
        'movement': [-0.4],
        'bass_movement': [-0.15],
        'leap_penalty': [-2.0],
        'octave_leap_penalty': [-6.0],
        'tritone_leap_penalty': [-3.0],
        'common_tone_bonus': [1.5],
        'parallel_perfect_penalty': [-25.0],
        'contrary_motion_bonus': [0.8],
        'seventh_resolution_bonus': [1.5],
        'leading_tone_resolution_bonus': [1.5],
        'double_leading_tone_penalty': [-8.0],
        'doubling': [_V054_DOUBLING],
        'omit': [_V054_OMIT],
        'inversion': [_V054_INVERSION],
        'range_comfort_penalty': [-0.5],
        'unison_penalty': [-0.5],
        'upper_spacing_penalty': [-0.15],
        # Added after 0.5.4:
        'same_bass_penalty': [-5.0, -8.0],             # ffc6b61, then 140149a
        'upper_spacing_threshold': [7.0],              # c569762
        'outer_leap_penalty': [0.0],                   # c25a76a
        'middle_range_penalty': [0.0],                 # 8e650db
        'hidden_perfect_penalty': [-2.0],              # b3d4c24
        'low_interval_limit_penalty': [-2.0],          # 60a1a60
        'augmented_second_penalty': [-4.0],            # engine review E1
        'voice_overlap_penalty': [-1.0],               # engine review E5
    }


def _quartet_untouched() -> Dict[str, List[Any]]:
    """The values of a String Quartet copy its user never changed: the 0.5.4
    default, the default each later key was added with, and the quartet's
    own values in the builds between (a1ea4b5 to 8ecfe61)."""
    return {
        'allow_unisons': [True],
        # The scalar 0.5.4 saved (with bass_movement), and the quartet's list
        # since a1ea4b5; a list the current form saves for the scalar
        # ([-0.4] * (n - 1) + [-0.15]) is the same per-voice weights.
        'movement': [-0.4, [-0.8, -0.4, -0.4, -0.15]],
        'bass_movement': [-0.15],
        'leap_penalty': [-2.0],
        'octave_leap_penalty': [-6.0],
        'tritone_leap_penalty': [-3.0],
        'common_tone_bonus': [1.5],
        'parallel_perfect_penalty': [-25.0],
        'contrary_motion_bonus': [0.8],
        'seventh_resolution_bonus': [1.5],
        'leading_tone_resolution_bonus': [1.5, 3.0],   # 3.0: a1ea4b5 to 8ecfe61
        'double_leading_tone_penalty': [-8.0],
        'doubling': [_V054_DOUBLING],
        'omit': [_V054_OMIT],
        'inversion': [_V054_INVERSION],
        'range_comfort_penalty': [-0.5],
        'unison_penalty': [-0.5],
        'upper_spacing_penalty': [-0.15],
        # Added after 0.5.4:
        'same_bass_penalty': [-5.0, -8.0],             # ffc6b61, then 140149a
        'upper_spacing_threshold': [7.0],              # c569762
        'outer_leap_penalty': [0.0],                   # c25a76a
        'middle_range_penalty': [0.0],                 # 8e650db
        'hidden_perfect_penalty': [-2.0],              # b3d4c24
        'low_interval_limit_penalty': [-2.0],          # 60a1a60
        'augmented_second_penalty': [-4.0],            # engine review E1
        'voice_overlap_penalty': [-1.0],               # engine review E5
    }


#: For each built-in ensemble migration 1->2 updates copies of, the values a
#: copy may hold for each key while its user never changed it (a key the copy
#: doesn't have counts as untouched too). A key that holds one of them takes
#: the preset's current value (``BUILTIN_ENSEMBLES``, read at run time). When
#: a preset's value changes, its previous value goes into that key's list.
#: ``allow_unisons`` is the voicing's own key, the rest are weights; the nested
#: weights (``doubling``, ``omit``, ``inversion``) move all or nothing.
UNTOUCHED_PRESET_VALUES: Dict[str, Dict[str, List[Any]]] = {
    'quartet': _quartet_untouched(),
    'satb': _choir_untouched(),
    'ttbb': _choir_untouched(),
    'ssa': _choir_untouched(),
}

#: Defaults changed since 0.5.4, per model: ``{key: [(old, new), ...]}``.
#: Migration 1->2 moves a saved flat weight still holding ``old`` to ``new``,
#: in every voicing of that model, preset copy or not (a voicing edited in
#: Settings saves its whole weight dict, so it holds the old default
#: explicitly). A key a voicing doesn't have already reads the new default.
DEFAULT_MOVES: Dict[str, Dict[str, List[Tuple[Any, Any]]]] = {
    'ensemble': {
        # With augmented seconds priced at -4.0, a tritone at -3.0 was the
        # cheaper way out of VI-V in minor (F4 to B3).
        'tritone_leap_penalty': [(-3.0, -4.5)],
    },
}

#: The voicing's own keys among the untouched values (the rest are weights).
_TOP_LEVEL_KEYS = ('allow_unisons',)
#: Weights moved together with ``movement``.
_MOVEMENT_KEYS = ('movement', 'bass_movement')

_ABSENT = object()


def _per_voice(movement: Any, bass_movement: Any, n: int) -> Optional[Tuple[float, ...]]:
    from chordnotepad.models.ensemble_spec import expand_movement
    try:
        return expand_movement(movement, bass_movement, n)
    except (ConfigurationError, TypeError, ValueError):
        return None


def _move_movement(weights: Dict[str, Any], untouched: Mapping[str, List[Any]],
                   target: Mapping[str, Any], defaults: Mapping[str, Any], n: int) -> bool:
    """Move the per-voice movement to the preset's, adapted to ``n`` voices,
    when what the copy plays (its ``movement`` with its ``bass_movement``) is
    one of the untouched shapes for ``n`` voices."""
    saved = _per_voice(weights.get('movement', defaults['movement']),
                       weights.get('bass_movement', defaults['bass_movement']), n)
    if saved is None:
        return False
    shapes = [_per_voice(movement, bass, n)
              for movement in untouched.get('movement', [])
              for bass in untouched.get('bass_movement', [])]
    new = _per_voice(target['movement'], target['bass_movement'], n)
    if new is None or not any(_equal(saved, shape) for shape in shapes if shape is not None):
        return False
    if _equal(saved, new):
        return False
    weights['movement'] = list(new)
    weights.pop('bass_movement', None)
    return True


def _move_nested(weights: Dict[str, Any], key: str, values: List[Any],
                 target: Mapping[str, Any], defaults: Mapping[str, Any]) -> bool:
    """All or nothing: a nested weight moves to the preset's only when every
    role it has holds one untouched mapping's value."""
    saved = weights.get(key, _ABSENT)
    roles = {} if saved is _ABSENT else saved
    if not isinstance(roles, Mapping):
        return False
    untouched = any(isinstance(value, Mapping) and all(
        role in value and _equal(roles[role], value[role]) for role in roles)
        for value in values)
    if not untouched:
        return False
    effective = {**defaults.get(key, {}), **roles}
    if _equal(effective, target[key]):
        return False
    weights[key] = copy.deepcopy(dict(target[key]))
    return True


def _move_defaults(entry: MutableMapping[str, Any]) -> bool:
    """Move each saved flat weight still on a default changed since 0.5.4 to
    the new default (:data:`DEFAULT_MOVES`), in any voicing of that model."""
    moves = DEFAULT_MOVES.get(entry.get('model'), {})
    weights = entry.get('weights')
    if not moves or not isinstance(weights, dict):
        return False
    changed = False
    for key, pairs in moves.items():
        if key not in weights:
            continue
        for old, new in pairs:
            if _equal(weights[key], old):
                weights[key] = copy.deepcopy(new)
                changed = True
                break
    return changed


def _migrate_1_to_2(entry: MutableMapping[str, Any]) -> bool:
    """Copies of the String Quartet and the choirs take the preset values
    tuned since 0.5.4, key by key, where the copy still holds a value its
    user never changed (:data:`UNTOUCHED_PRESET_VALUES`); then every voicing
    takes the defaults changed since 0.5.4 where it still holds the old one
    (:data:`DEFAULT_MOVES`). Fretboard and piano presets only gained keys
    since 0.5.4, which a copy already takes from the defaults."""
    changed = _migrate_preset_copy(entry)
    return _move_defaults(entry) or changed


def _migrate_preset_copy(entry: MutableMapping[str, Any]) -> bool:
    """The preset half of :func:`_migrate_1_to_2`."""
    from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES, DEFAULT_WEIGHTS

    based_on = entry.get('based_on')
    if entry.get('model') != 'ensemble' or not isinstance(based_on, str):
        return False
    slug = based_on.partition(':')[2] if based_on.startswith('ensemble:') else None
    if slug not in UNTOUCHED_PRESET_VALUES or slug not in BUILTIN_ENSEMBLES:
        return False
    untouched = UNTOUCHED_PRESET_VALUES[slug]
    preset = BUILTIN_ENSEMBLES[slug]
    weights = entry.get('weights', _ABSENT)
    if weights is _ABSENT:
        weights = {}
    if not isinstance(weights, dict):
        return False
    target = preset.weights
    changed = False

    for key in _TOP_LEVEL_KEYS:
        if key not in untouched:
            continue
        saved = entry.get(key, _ABSENT)
        wanted = getattr(preset, key)
        if saved is _ABSENT:
            # A key a voicing lacks reads as the spec's default (True).
            saved = True
        if any(_equal(saved, value) for value in untouched[key]) and not _equal(saved, wanted):
            entry[key] = wanted
            changed = True

    voices = entry.get('voices')
    if isinstance(voices, list) and voices and 'movement' in untouched:
        changed = _move_movement(weights, untouched, target, DEFAULT_WEIGHTS, len(voices)) \
            or changed

    for key, values in untouched.items():
        if key in _TOP_LEVEL_KEYS or key in _MOVEMENT_KEYS or key not in target:
            continue
        if isinstance(target[key], Mapping):
            changed = _move_nested(weights, key, values, target, DEFAULT_WEIGHTS) or changed
            continue
        saved = weights.get(key, _ABSENT)
        effective = DEFAULT_WEIGHTS.get(key) if saved is _ABSENT else saved
        if saved is not _ABSENT and not any(_equal(saved, value) for value in values):
            continue
        if _equal(effective, target[key]):
            continue
        weights[key] = copy.deepcopy(target[key])
        changed = True

    if changed and 'weights' not in entry:
        entry['weights'] = weights
    return changed


def _migrate_2_to_3(entry: MutableMapping[str, Any]) -> bool:
    """Run :func:`_migrate_1_to_2` again. Development builds stamped voicings
    at version 2 before the choir presets were retuned and before the
    tritone default moved (:data:`DEFAULT_MOVES`); both halves only move a
    value still on an old default, so running them twice changes nothing
    for a voicing that already had them."""
    return _migrate_1_to_2(entry)


#: ``MIGRATIONS[i]`` moves a voicing dict from version ``i`` to ``i + 1``,
#: in place, and returns whether it changed it.
MIGRATIONS: Tuple[Callable[[MutableMapping[str, Any]], bool], ...] = (
    _migrate_0_to_1,
    _migrate_1_to_2,
    _migrate_2_to_3,
)

#: The version a voicing saved by this release has.
VOICING_VERSION = len(MIGRATIONS)


def voicing_version(entry: Mapping[str, Any]) -> int:
    """The saved ``version`` of a voicing dict: a whole number of at least 0,
    else 0 (missing, or junk: a string, a float, a bool)."""
    raw = entry.get("version")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return 0
    return raw


def stamp(entry: MutableMapping[str, Any], based_on: Optional[str] = None) -> MutableMapping[str, Any]:
    """Give ``entry`` this release's ``version`` (a higher one, from a newer
    release, is kept) and, if given, the ``based_on`` link. In place; returns
    ``entry``."""
    entry["version"] = max(voicing_version(entry), VOICING_VERSION)
    if based_on is not None:
        entry["based_on"] = based_on
    return entry


def stamp_new(entry: MutableMapping[str, Any], based_on: Optional[str] = None) -> MutableMapping[str, Any]:
    """Like :func:`stamp`, but a ``version`` the entry has is kept as it is:
    a copy of a voicing whose migration failed keeps its lower version, so
    the next load tries again. For dicts that may come from the working copy
    (presets of the user's own voicings); a fresh dict gets this release's."""
    if "version" not in entry:
        entry["version"] = VOICING_VERSION
    if based_on is not None:
        entry["based_on"] = based_on
    return entry


def migrated_copy(entry: Mapping[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """A deep copy of ``entry`` brought up to :data:`VOICING_VERSION`, and
    whether that worked; if a migration fails, the untouched copy and False
    (its version stays below the current one)."""
    out = copy.deepcopy(dict(entry))
    try:
        migrate_voicing(out)
    except Exception:  # noqa: BLE001 - a failed migration keeps the voicing as it was
        return copy.deepcopy(dict(entry)), False
    return out, True


def migrate_voicing(entry: MutableMapping[str, Any]) -> bool:
    """Run the migrations ``entry`` hasn't been through, in place, and stamp it.

    An entry already at or above :data:`VOICING_VERSION` (with a valid
    ``version``) is left exactly as it is.

    Returns:
        Whether the dict changed (a value moved, or the version was written).
    """
    before = entry.get("version")
    current = voicing_version(entry)
    if current >= VOICING_VERSION and before == current and type(before) is int:
        return False
    changed = False
    for migration in MIGRATIONS[current:]:
        changed = migration(entry) or changed
    stamp(entry)
    return changed or type(before) is not int or entry["version"] != before
