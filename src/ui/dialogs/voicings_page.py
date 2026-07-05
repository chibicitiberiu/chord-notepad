"""The Voicings page of the Settings window.

A two-pane editor for the ``voicings`` registry: a grouped tree of voicings on
the left (with add/remove buttons), and a model-specific parameter form on the
right. All state lives in the injected
:class:`~viewmodels.settings_viewmodel.SettingsViewModel`; this widget renders
it and forwards edits.

The form stays deliberately forgiving while the user types: an unparseable
field keeps its raw string in the working copy rather than being rejected
mid-edit. What changed is that this raw state is now *shown* inline instead of
hidden. Two error classes surface:

* **Parse errors** -- a value that stayed a raw string where a number, note
  name or list was expected. These are detected by the pure, headless-testable
  :func:`field_errors` and marked red on the offending control as you type.
* **Semantic / cross-field errors** (relaxed span < span, voice low >= high, a
  wrong ``max_spacing`` length, an out-of-range value, ...) are left to the
  spec: after each edit ``viewmodel.validate_voicing`` runs and its message is
  shown in a red banner at the top of the form.

The dialog's Save button is still the hard gate (it runs
``viewmodel.validate_all`` and jumps to the first bad voicing); the inline
feedback here is additive.
"""

import logging
import re
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable, Dict, List, Optional

from exceptions import ConfigurationError
from models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    DEFAULT_WEIGHTS as ENSEMBLE_DEFAULT_WEIGHTS,
    _NESTED_WEIGHT_KEYS,
    midi_to_note_name,
    parse_note_name,
)
from models.fretboard_spec import (
    BUILTIN_FRETBOARDS,
    DEFAULT_WEIGHTS as FRETBOARD_DEFAULT_WEIGHTS,
)
from models.piano_spec import (
    DEFAULT_PIANO,
    DEFAULT_WEIGHTS as PIANO_DEFAULT_WEIGHTS,
    PianoSpec,
)
from ui.base.tooltip import add_tooltip, ensure_field_error_styles, mark_field
from viewmodels.settings_viewmodel import SettingsViewModel

logger = logging.getLogger(__name__)


# Human-readable labels, taken verbatim from help/fretted.rst and
# help/ensembles.rst, keyed by the weight's config key.
FRETBOARD_WEIGHT_LABELS: Dict[str, str] = {
    'sounding_string_bonus': 'Sounding string',
    'open_string_bonus': 'Open string',
    'bass_note_bonus': 'Correct bass note',
    'slash_bass_bonus': 'Correct slash bass',
    'span_penalty': 'Wide stretch',
    'stretch_penalty': 'Compact shape',
    'awkward_stretch_penalty': 'Awkward stretch',
    'position_penalty': 'High neck position',
    'fretted_finger_penalty': 'Fretted finger',
    'barre_penalty': 'Barre',
    'interior_mute_penalty': 'Muted inner string',
    'movement_penalty': 'Hand movement',
    'kept_finger_bonus': 'Kept finger',
}

ENSEMBLE_WEIGHT_LABELS: Dict[str, str] = {
    'movement': 'Voice movement',
    'bass_movement': 'Bass movement',
    'leap_penalty': 'Large leap',
    'octave_leap_penalty': 'Octave leap',
    'tritone_leap_penalty': 'Tritone leap',
    'common_tone_bonus': 'Common tone held',
    'parallel_perfect_penalty': 'Parallel fifths/octaves',
    'contrary_motion_bonus': 'Contrary motion',
    'seventh_resolution_bonus': 'Seventh resolves down',
    'leading_tone_resolution_bonus': 'Leading tone resolves',
    'double_leading_tone_penalty': 'Doubled leading tone',
    'range_comfort_penalty': 'Out-of-comfort range',
    'unison_penalty': 'Unison between voices',
    'upper_spacing_penalty': 'Wide upper spacing',
}

PIANO_WEIGHT_LABELS: Dict[str, str] = {
    'rh_note_bonus': 'Right-hand note',
    'rh_center_penalty': 'Right-hand center',
    'lh_below_bass_penalty': 'Bass below range',
    'lh_above_bass_penalty': 'Bass above range',
    'lh_double_penalty': 'Doubled bass',
    'lh_double_low_penalty': 'Doubled bass low',
    'rh_low_interval_penalty': 'Muddy low interval',
    'rh_wide_gap_penalty': 'Wide right-hand gap',
    'muddy_gap_penalty': 'Hands too close',
    'common_tone_bonus': 'Common tone held',
    'movement_penalty': 'Voice movement',
}

# Two piano weight keys collide by name with an existing fretboard/ensemble
# weight key ('movement_penalty', 'common_tone_bonus'); a shared TOOLTIPS dict
# keyed by bare 'weight:<key>' can't hold two different texts for the same
# key, so those two get a piano-prefixed tooltip key instead. See
# _piano_weight_tooltip below.
_PIANO_WEIGHT_TOOLTIP_OVERRIDES: Dict[str, str] = {
    'movement_penalty': 'weight:piano_movement_penalty',
    'common_tone_bonus': 'weight:piano_common_tone_bonus',
}

# Titles for the three nested-weight sub-frames.
NESTED_WEIGHT_TITLES: Dict[str, str] = {
    'doubling': 'Doubling',
    'omit': 'Omission',
    'inversion': 'Inversion',
}

# Human labels for the per-role sub-keys of the nested weights.
ROLE_LABELS: Dict[str, str] = {
    'root': 'Root',
    'third': 'Third',
    'fifth': 'Fifth',
    'seventh': 'Seventh',
    'color': 'Color',
    'extension': 'Extension',
    'first': 'First',
    'second': 'Second',
}

# Display names for the model combobox, and the mapping back to model keys.
_MODEL_DISPLAY = {'fretboard': 'Fretboard', 'ensemble': 'Ensemble', 'piano': 'Piano'}
_DISPLAY_MODEL = {display: model for model, display in _MODEL_DISPLAY.items()}

# Display names for a voice's staff selector, and the mapping back to the
# 'staff' dict value ('Auto' <-> absent/None key).
_STAFF_DISPLAY = {None: 'Auto', 'treble': 'Treble', 'bass': 'Bass'}
_DISPLAY_TO_STAFF = {display: value for value, display in _STAFF_DISPLAY.items()}
_STAFF_COMBO_VALUES = ['Auto', 'Treble', 'Bass']
# Group node order in the tree.
_GROUP_ORDER = ('fretboard', 'piano', 'ensemble')
_GROUP_LABEL = {'fretboard': 'Fretboard', 'piano': 'Piano', 'ensemble': 'Ensemble'}

# Small grey introducing every 'Weights' section.
_WEIGHTS_BLURB = (
    "Each weight adds to a voicing's score, so a higher number always means "
    "more preferred. Positive values pull the picker toward a trait; negative "
    "values push it away. Zero is neutral. The defaults suit most music, so "
    "change these only if the results aren't to your taste."
)

# ---------------------------------------------------------------------------
# Tooltip texts -- one concrete sentence per input, grounded in the parameter
# tables of help/fretted.rst and help/ensembles.rst. Kept here (module level)
# so the wording is maintainable in one place.
# ---------------------------------------------------------------------------
TOOLTIPS: Dict[str, str] = {
    # Header controls.
    'name': "The name of this voicing, shown in the Playback → Voicing menu.",
    'model': ("The engine that renders this voicing: fretboard (a fretted "
              "instrument), ensemble (independent voices), or piano."),
    'load': ("Replace this voicing's parameters with those of a built-in preset "
             "or another voicing. The name is kept."),
    'tree_add': "Add a new voicing.",
    'tree_remove': "Remove the selected voicing.",

    # Fretboard physical parameters.
    'tuning': ("Open-string pitches in string order, lowest string first "
               "(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4). Required."),
    'max_fret': "Highest fret the picker will reach; higher allows shapes further up the neck.",
    'fingers': "How many fretting fingers the hand has available.",
    'max_span': "Widest fret stretch the hand holds on a normal pass.",
    'relaxed_span': ("Widest stretch accepted as a last resort when nothing fits "
                     "the normal span; must be at least the stretch."),
    'allow_barres': ("Whether one finger flattened across several strings can stand "
                     "in for several fretted fingers at once."),

    # Fretboard weights.
    'weight:sounding_string_bonus': ("How the picker treats strings that actually sound. More "
                                     "positive favors fuller-sounding fingerings; negative would "
                                     "favor sparser ones."),
    'weight:open_string_bonus': ("How the picker treats open strings (fret 0), on top of the "
                                 "sounding-string weight. More positive favors open strings."),
    'weight:bass_note_bonus': ("How the picker treats the chord's root landing on the lowest "
                               "sounding string. More positive encourages it."),
    'weight:slash_bass_bonus': ("How the picker treats a slash chord's named bass note landing "
                                "in the bass (the G in C/G). More positive encourages it."),
    'weight:span_penalty': ("How the picker treats wide finger stretches. More negative avoids "
                            "them; positive would seek them out."),
    'weight:stretch_penalty': ("How the picker treats a shape's overall fret span beyond a "
                               "single fret. More negative favors compact shapes; a one-fret "
                               "span costs nothing."),
    'weight:awkward_stretch_penalty': ("How the picker treats a three-fret shape that isn't a "
                                       "clean index-to-pinky reach on an outer string -- one "
                                       "that would force an inner finger to make the stretch. "
                                       "Set strongly negative to reject shapes no hand can hold."),
    'weight:position_penalty': ("How the picker treats fingerings further up the neck. More "
                                "negative keeps fingerings closer to the nut."),
    'weight:fretted_finger_penalty': ("How the picker treats fretted fingers. More negative "
                                      "favors shapes that leave more strings open or muted."),
    'weight:barre_penalty': ("How the picker treats fingerings that need a barre, on top of the "
                             "fretted-finger weight. More negative avoids barres."),
    'weight:interior_mute_penalty': ("How the picker treats a muted string buried between two "
                                     "sounding strings. More negative avoids that shape."),
    'weight:movement_penalty': ("How the picker treats the hand shifting from the previous "
                                "chord, across the whole song. More negative steadies the hand."),
    'weight:kept_finger_bonus': ("How the picker treats a finger staying on the same string and "
                                 "fret between chords. More positive rewards keeping it there."),

    # Ensemble voices / spacing / unisons.
    'voice_name': "Name of this voice, e.g. Soprano. Free text.",
    'voice_low': "Lowest note this voice may sing, inclusive (note name or MIDI number).",
    'voice_high': "Highest note this voice may sing, inclusive (note name or MIDI number).",
    'voice_staff': ("Which staff of a grand-staff chord sheet this voice is drawn on. Auto "
                    "picks treble or bass from the voice's range; Treble/Bass pins it."),
    'add_voice': "Add another voice to the ensemble (2 to 8 voices).",
    'remove_voice': "Remove this voice from the ensemble.",
    'max_spacing': ("Maximum semitone gap allowed between each pair of neighbouring voices; "
                    "comma-separated, one value per gap."),
    'allow_unisons': "Whether two neighbouring voices may land on the same pitch.",

    # Ensemble weights.
    'weight:movement': ("How the picker treats an inner or upper voice moving between chords "
                        "(a single number, or one per voice). More negative discourages "
                        "movement; positive would encourage it."),
    'weight:bass_movement': ("How the picker treats the bottom voice moving between chords, "
                             "normally set less negative than the inner-voice movement weight."),
    'weight:leap_penalty': ("How the picker treats a voice jumping more than a fifth between "
                            "chords. More negative avoids large leaps."),
    'weight:octave_leap_penalty': ("How the picker treats a voice jumping a full octave or more. "
                                   "More negative avoids octave leaps."),
    'weight:tritone_leap_penalty': ("How the picker treats a voice leaping exactly a tritone (six "
                                    "semitones). More negative avoids tritone leaps."),
    'weight:common_tone_bonus': ("How the picker treats a voice holding the pitch class it just "
                                 "sang. More positive rewards holding common tones."),
    'weight:parallel_perfect_penalty': ("How the picker treats a pair of voices moving in "
                                        "parallel fifths or octaves. More negative avoids them; "
                                        "set strongly negative by default."),
    'weight:contrary_motion_bonus': ("How the picker treats the outer two voices moving in "
                                     "opposite directions. More positive encourages it."),
    'weight:seventh_resolution_bonus': ("How the picker treats a chordal seventh resolving down "
                                        "by step. More positive encourages that resolution."),
    'weight:leading_tone_resolution_bonus': ("How the picker treats the leading tone resolving up "
                                             "to the tonic. More positive encourages it."),
    'weight:double_leading_tone_penalty': ("How the picker treats two voices doubling the leading "
                                           "tone. More negative avoids doubling it."),
    'weight:range_comfort_penalty': ("How the picker treats a voice sitting in the outer 2 "
                                     "semitones of its range. More negative keeps voices off "
                                     "their extremes."),
    'weight:unison_penalty': ("How the picker treats a pair of neighbouring voices on the same "
                              "pitch, when unisons are allowed. More negative avoids unisons."),
    'weight:upper_spacing_penalty': ("How the picker treats an upper-voice gap exceeding an "
                                     "octave. More negative favors closer spacing above the "
                                     "bass."),

    # Piano hands & range.
    'lh_range_low': "Lowest note the left hand may play (note name or MIDI number).",
    'lh_range_high': "Highest note the left hand may play (note name or MIDI number).",
    'rh_range_low': "Lowest note the right hand may play (note name or MIDI number).",
    'rh_range_high': "Highest note the right hand may play (note name or MIDI number).",
    'bass_range_low': ("Lowest note of the preferred bass register. Sitting below it costs "
                       "the bass-below-range weight per semitone."),
    'bass_range_high': ("Highest note of the preferred bass register. Sitting above it costs "
                        "the bass-above-range weight per semitone."),
    'rh_low_anchor_low': "Lowest note the right hand's lowest note is anchored within.",
    'rh_low_anchor_high': "Highest note the right hand's lowest note is anchored within.",
    'rh_center': ("Target for the right hand's mean pitch. Drifting from it costs the "
                 "right-hand center weight per semitone."),
    'rh_low_interval_floor': ("Right-hand close intervals sounding below this note are "
                             "considered muddy and cost the muddy-low-interval weight."),
    'hand_span': "Widest reach of one hand, in semitones (a ninth by default).",
    'max_notes_per_hand': "Most notes one hand may play at once.",
    'max_total_notes': "Most notes both hands may play together.",
    'hand_gap_floor': ("The right hand should clear the bass by more than this many "
                       "semitones, or it costs the hands-too-close weight."),
    'add_bass': "Whether to include the left-hand bass note at all.",

    # Piano weights.
    'weight:rh_note_bonus': ("How the picker treats a note kept in the right hand. More "
                             "positive favors fuller voicings; negative would favor sparser "
                             "ones."),
    'weight:rh_center_penalty': ("How the picker treats the right hand's mean pitch straying "
                                 "from its target center. More negative keeps it closer to "
                                 "center."),
    'weight:lh_below_bass_penalty': ("How the picker treats the bass sitting below the "
                                     "preferred bass range. More negative discourages a bass "
                                     "that's too low."),
    'weight:lh_above_bass_penalty': ("How the picker treats the bass sitting above the "
                                     "preferred bass range. More negative discourages a bass "
                                     "that's too high."),
    'weight:lh_double_penalty': ("How the picker treats octave-doubling the bass note. More "
                                 "negative avoids doubling it."),
    'weight:lh_double_low_penalty': ("How the picker treats an octave-doubled bass sitting "
                                     "below the preferred bass range, on top of the doubling "
                                     "weight. More negative avoids it."),
    'weight:rh_low_interval_penalty': ("How the picker treats a close right-hand interval "
                                       "sounding below the muddy-interval floor. More negative "
                                       "avoids muddy low intervals."),
    'weight:rh_wide_gap_penalty': ("How the picker treats an interior right-hand gap wider "
                                   "than an octave. More negative avoids wide gaps."),
    'weight:muddy_gap_penalty': ("How the picker treats the hands clearing each other by less "
                                 "than the hand gap floor. More negative keeps the hands "
                                 "apart."),
    'weight:piano_common_tone_bonus': ("How the picker treats a note holding the same pitch "
                                       "across a chord change. More positive rewards holding "
                                       "common tones."),
    'weight:piano_movement_penalty': ("How the picker treats a note's nearest-neighbour "
                                      "movement across a chord change, across the whole song. "
                                      "More negative steadies the voicing."),
}


def _nested_tooltip(group: str, role: str) -> str:
    """Build a per-role tooltip for a nested-weight spinbox."""
    role_label = ROLE_LABELS.get(role, role).lower()
    if group == 'doubling':
        return (f"How much to favor doubling the {role_label} when there are more voices "
                f"than chord tones. Positive encourages it, negative avoids it.")
    if group == 'omit':
        return (f"How reluctant the picker is to drop the {role_label} when there are fewer "
                f"voices than chord tones. More negative keeps it; nearer zero allows "
                f"dropping it.")
    if group == 'inversion':
        return (f"How much to favor putting the {role_label} in the bass. Higher is more "
                f"preferred; 0 is neutral.")
    return f"{group} {role_label}"


# ---------------------------------------------------------------------------
# Parsing helpers (forgiving: keep the raw string when a value won't parse)
# ---------------------------------------------------------------------------


def _default_fretboard_data() -> dict:
    """Parameters for a brand-new fretboard voicing (standard guitar)."""
    return {'model': 'fretboard', 'tuning': [40, 45, 50, 55, 59, 64]}


def _default_ensemble_data() -> dict:
    """Parameters for a brand-new ensemble voicing (a minimal two-voice pair)."""
    return {
        'model': 'ensemble',
        'voices': [
            {'name': 'Voice 1', 'range': ['C4', 'C5']},
            {'name': 'Voice 2', 'range': ['C3', 'C4']},
        ],
    }


def _default_piano_data() -> dict:
    return {'model': 'piano'}


def _default_data_for_model(model: str) -> dict:
    if model == 'fretboard':
        return _default_fretboard_data()
    if model == 'ensemble':
        return _default_ensemble_data()
    return _default_piano_data()


def _pitch_to_text(value: Any) -> str:
    """Render a single pitch (MIDI int or already-a-string) as a note name."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return midi_to_note_name(value)
    return str(value)


def _tuning_to_text(tuning: Any) -> str:
    """Render a tuning (list of pitches, or a raw in-progress string) for the entry."""
    if isinstance(tuning, str):
        return tuning
    if isinstance(tuning, (list, tuple)):
        return ' '.join(_pitch_to_text(p) for p in tuning)
    return ''


def _parse_pitch_token(token: str):
    """Parse one pitch token to a MIDI int, or return None if unparseable."""
    token = token.strip()
    if re.fullmatch(r'-?\d+', token):
        return int(token)
    return parse_note_name(token)


def _parse_pitch_list(text: str):
    """Parse a whitespace/comma separated pitch list; return a list or the raw text."""
    tokens = [t for t in re.split(r'[,\s]+', text.strip()) if t]
    if not tokens:
        return []
    parsed = []
    for token in tokens:
        midi = _parse_pitch_token(token)
        if midi is None:
            return text  # keep raw string for validation to pinpoint later
        parsed.append(midi)
    return parsed


def _parse_pitch_or_raw(text: str):
    """Parse a single pitch endpoint; return an int or the raw string."""
    midi = _parse_pitch_token(text)
    return midi if midi is not None else text


def _parse_int_or_raw(text: str):
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return text


def _parse_float_or_raw(text: str):
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        return text


def _parse_int_list_or_raw(text: str):
    """Parse a comma-separated int list; return a list or the raw string."""
    tokens = [t.strip() for t in text.split(',') if t.strip()]
    parsed = []
    for token in tokens:
        try:
            parsed.append(int(token))
        except ValueError:
            return text
    return parsed


def _parse_scalar_or_list(text: str):
    """Parse ``movement`` as a single float or a comma-separated list of floats."""
    text = text.strip()
    if ',' in text:
        tokens = [t.strip() for t in text.split(',') if t.strip()]
        parsed = []
        for token in tokens:
            try:
                parsed.append(float(token))
            except ValueError:
                return text
        return parsed
    try:
        return float(text)
    except ValueError:
        return text


# ---------------------------------------------------------------------------
# Inline validation (pure, headless-testable)
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    """True for a real int/float, excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def field_errors(data: dict) -> Dict[str, str]:
    """Map each bad field-id in a *collected* voicing dict to a short message.

    This detects only **parse** errors -- values that the forgiving collectors
    left as a raw ``str`` where a number, note name or list was expected. It
    runs on the output of the form's ``collect()`` (so a valid note name like
    ``'C4'`` has already become the int ``60`` and is *not* flagged; only an
    unparseable leftover string is). Semantic and cross-field problems
    (``relaxed_span < max_span``, ``low >= high``, wrong ``max_spacing``
    length, out-of-range values, too few/many voices/strings) are deliberately
    left to the spec's validation and the red banner -- this function never
    reports them.

    Field-ids:

    * ``'tuning'`` -- fretboard strings still a raw string.
    * ``'max_fret'`` / ``'fingers'`` / ``'max_span'`` / ``'relaxed_span'`` --
      a physical-param spinbox value that isn't a whole number.
    * ``'weight:<key>'`` -- a flat weight value that isn't a number.
    * ``'movement'`` -- the ensemble ``movement`` weight still a raw string.
    * ``'nested:<group>:<role>'`` -- a doubling/omit/inversion role that isn't
      a number.
    * ``'voice:<i>:low'`` / ``'voice:<i>:high'`` -- a voice range endpoint
      still a raw string (voice *names* are free text and are never flagged).
    * ``'voice:<i>:staff'`` -- a voice's ``staff`` value that isn't
      ``'treble'``, ``'bass'``, or absent/``None`` (e.g. hand-edited to some
      other string in the config file).
    * ``'max_spacing'`` -- the ensemble spacing list still a raw string.
    * ``'range:<key>:low'`` / ``'range:<key>:high'`` -- a piano range
      (``lh_range``/``rh_range``/``bass_range``/``rh_low_anchor``) endpoint
      still a raw string.
    * ``'rh_center'`` / ``'rh_low_interval_floor'`` / ``'hand_span'`` /
      ``'max_notes_per_hand'`` / ``'max_total_notes'`` / ``'hand_gap_floor'``
      -- a piano physical-param spinbox value that isn't a number
      (``rh_center`` accepts a float; the rest must be whole numbers).
    * ``'nested:omit:<role>'`` -- a piano omission-weight role that isn't a
      number (shares the ``nested:<group>:<role>`` scheme with ensemble).

    Args:
        data: A collected voicing dict (must carry a ``'model'`` key).

    Returns:
        A ``{field_id: message}`` dict; empty when every value parsed.
    """
    errors: Dict[str, str] = {}
    model = data.get('model')

    if model == 'fretboard':
        if isinstance(data.get('tuning'), str):
            errors['tuning'] = 'Not a valid note name'
        for key in ('max_fret', 'fingers', 'max_span', 'relaxed_span'):
            if key in data and not _is_number(data[key]):
                errors[key] = 'Must be a whole number'
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if not _is_number(value):
                errors[f'weight:{key}'] = 'Must be a number'

    elif model == 'ensemble':
        for i, voice in enumerate(data.get('voices') or []):
            vrange = voice.get('range', []) if isinstance(voice, dict) else []
            low = vrange[0] if len(vrange) > 0 else None
            high = vrange[1] if len(vrange) > 1 else None
            if isinstance(low, str):
                errors[f'voice:{i}:low'] = 'Not a valid note name'
            if isinstance(high, str):
                errors[f'voice:{i}:high'] = 'Not a valid note name'
            raw_staff = voice.get('staff') if isinstance(voice, dict) else None
            if raw_staff is not None and raw_staff not in ('treble', 'bass'):
                errors[f'voice:{i}:staff'] = "Must be 'treble', 'bass', or omitted"
        if isinstance(data.get('max_spacing'), str):
            errors['max_spacing'] = 'Must be whole numbers'
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if key == 'movement':
                if isinstance(value, str):
                    errors['movement'] = 'Must be a number or list of numbers'
            elif key in _NESTED_WEIGHT_KEYS:
                for role, role_value in (value or {}).items():
                    if not _is_number(role_value):
                        errors[f'nested:{key}:{role}'] = 'Must be a number'
            else:
                if not _is_number(value):
                    errors[f'weight:{key}'] = 'Must be a number'

    elif model == 'piano':
        for range_key in ('lh_range', 'rh_range', 'bass_range', 'rh_low_anchor'):
            rng = data.get(range_key)
            if isinstance(rng, (list, tuple)):
                low = rng[0] if len(rng) > 0 else None
                high = rng[1] if len(rng) > 1 else None
                if isinstance(low, str):
                    errors[f'range:{range_key}:low'] = 'Not a valid note name'
                if isinstance(high, str):
                    errors[f'range:{range_key}:high'] = 'Not a valid note name'
        for key in ('rh_low_interval_floor', 'hand_span', 'max_notes_per_hand',
                    'max_total_notes', 'hand_gap_floor'):
            if key in data and not _is_number(data[key]):
                errors[key] = 'Must be a whole number'
        if 'rh_center' in data and not _is_number(data['rh_center']):
            errors['rh_center'] = 'Must be a number'
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if key == 'omit':
                for role, role_value in (value or {}).items():
                    if not _is_number(role_value):
                        errors[f'nested:omit:{role}'] = 'Must be a number'
            else:
                if not _is_number(value):
                    errors[f'weight:{key}'] = 'Must be a number'

    return errors


class VoicingsPage(ttk.Frame):
    """Left tree + right parameter-form editor for the voicings registry."""

    def __init__(self, parent, viewmodel: SettingsViewModel) -> None:
        """Build the page.

        Args:
            parent: The parent widget (the Settings dialog's page container).
            viewmodel: The shared settings view model to read from and edit.
        """
        super().__init__(parent, padding=10)

        self._vm = viewmodel
        self._current_name: Optional[str] = None
        self._current_label: Optional[str] = None
        self._dirty = False
        self._suppress_tree_event = False
        self._loading_form = False
        # Per-model form state, populated by _build_*_form.
        self._collect: Optional[Callable[[], dict]] = None
        # field-id -> control, tooltip, and base tooltip text (for inline marks).
        self._field_widgets: Dict[str, tk.Widget] = {}
        self._field_tooltips: Dict[str, Any] = {}
        self._field_base_tips: Dict[str, str] = {}

        ensure_field_error_styles()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left_pane()
        self._build_right_pane()

        self.refresh()
        self._clear_editor()

    # -- Left pane -----------------------------------------------------------

    def _build_left_pane(self) -> None:
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        left.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(left, show='tree', height=10, selectmode='browse')
        self._tree.grid(row=0, column=0, sticky='ns')
        scroll = ttk.Scrollbar(left, orient='vertical', command=self._tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.tag_configure('group', font=('TkDefaultFont', 9, 'bold'))
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        buttons = ttk.Frame(left)
        buttons.grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))
        add_btn = ttk.Button(buttons, text='+', width=3, command=self._on_add)
        add_btn.pack(side=tk.LEFT)
        remove_btn = ttk.Button(buttons, text='−', width=3, command=self._on_remove)
        remove_btn.pack(side=tk.LEFT, padx=(4, 0))
        add_tooltip(add_btn, TOOLTIPS['tree_add'])
        add_tooltip(remove_btn, TOOLTIPS['tree_remove'])

    def refresh(self) -> None:
        """Re-read the view model and rebuild the voicings tree."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        for model in _GROUP_ORDER:
            self._tree.insert('', 'end', iid=f'g:{model}', text=_GROUP_LABEL[model],
                              open=True, tags=('group',))

        voicings = self._vm.get_voicings()
        for name in sorted(voicings):
            model = voicings[name].get('model', 'piano')
            group = model if model in _GROUP_ORDER else 'piano'
            self._tree.insert(f'g:{group}', 'end', iid=f'v:{name}', text=name)

    def _select_in_tree(self, name: str) -> None:
        """Highlight ``name`` in the tree without triggering a form reload."""
        iid = f'v:{name}'
        if not self._tree.exists(iid):
            return
        self._suppress_tree_event = True
        try:
            self._tree.selection_set(iid)
            self._tree.see(iid)
            self._tree.focus(iid)
        finally:
            self._suppress_tree_event = False

    def _on_tree_select(self, event=None) -> None:
        if self._suppress_tree_event:
            return
        selection = self._tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith('g:'):
            return  # selecting a group is a no-op
        name = iid[2:]
        if name in self._vm.get_voicings():
            self._load_editor(name)

    def _on_add(self) -> None:
        name = self._vm.add_voicing()
        self.refresh()
        self._load_editor(name)
        self._select_in_tree(name)

    def _on_remove(self) -> None:
        selection = self._tree.selection()
        if not selection or selection[0].startswith('g:'):
            return
        name = selection[0][2:]
        if not messagebox.askyesno('Remove Voicing', f"Remove voicing '{name}'?", parent=self):
            return
        self._vm.remove_voicing(name)
        if self._current_name == name:
            self._current_name = None
        self.refresh()
        if self._current_name is None:
            self._clear_editor()

    # -- Right pane ----------------------------------------------------------

    def _build_right_pane(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(5, weight=1)
        self._right = right

        # Row 0: Load config menubutton (the Menubutton draws its own indicator,
        # so the text is plain 'Load config' with no manual arrow glyph).
        self._load_button = ttk.Menubutton(right, text='Load config')
        self._load_menu = tk.Menu(self._load_button, tearoff=0)
        self._load_button['menu'] = self._load_menu
        self._load_button.grid(row=0, column=0, sticky='w', pady=(0, 6))
        add_tooltip(self._load_button, TOOLTIPS['load'])

        # Row 1: Name.
        name_frame = ttk.Frame(right)
        name_frame.grid(row=1, column=0, sticky='ew', pady=(0, 4))
        name_frame.columnconfigure(1, weight=1)
        self._tip_label(name_frame, 'Name:', TOOLTIPS['name'],
                        row=0, column=0, sticky='w', padx=(0, 6))
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(name_frame, textvariable=self._name_var)
        self._name_entry.grid(row=0, column=1, sticky='ew')
        self._name_entry.bind('<FocusOut>', self._on_name_commit)
        self._name_entry.bind('<Return>', self._on_name_commit)
        add_tooltip(self._name_entry, TOOLTIPS['name'])

        # Row 2: Model.
        model_frame = ttk.Frame(right)
        model_frame.grid(row=2, column=0, sticky='ew', pady=(0, 4))
        model_label = ttk.Label(model_frame, text='Model:')
        model_label.pack(side=tk.LEFT, padx=(0, 6))
        add_tooltip(model_label, TOOLTIPS['model'])
        self._model_var = tk.StringVar()
        self._model_combo = ttk.Combobox(
            model_frame, textvariable=self._model_var, state='readonly',
            values=[_MODEL_DISPLAY[m] for m in ('fretboard', 'ensemble', 'piano')],
            width=14,
        )
        self._model_combo.pack(side=tk.LEFT)
        self._model_combo.bind('<<ComboboxSelected>>', self._on_model_changed)
        add_tooltip(self._model_combo, TOOLTIPS['model'])

        ttk.Separator(right, orient='horizontal').grid(row=3, column=0, sticky='ew', pady=6)

        # Row 4: the semantic/cross-field error banner (hidden until needed).
        self._banner = tk.Label(
            right, anchor='w', justify=tk.LEFT, wraplength=420,
            background='#ffdddd', foreground='#8b0000', padx=8, pady=5,
        )
        self._banner.grid(row=4, column=0, sticky='ew', pady=(0, 6))
        self._banner.grid_remove()

        # Row 5: the model parameter form host (scrollable content per model).
        self._form_host = ttk.Frame(right)
        self._form_host.grid(row=5, column=0, sticky='nsew')
        self._form_host.columnconfigure(0, weight=1)
        self._form_host.rowconfigure(0, weight=1)

    def _rebuild_load_menu(self) -> None:
        self._load_menu.delete(0, 'end')
        sources = self._vm.get_load_sources()
        n_fret = len(BUILTIN_FRETBOARDS)
        n_ens = len(BUILTIN_ENSEMBLES)
        groups = [
            sources[0:n_fret],
            sources[n_fret:n_fret + n_ens],
            sources[n_fret + n_ens:n_fret + n_ens + 1],
            sources[n_fret + n_ens + 1:],
        ]
        first = True
        for group in groups:
            if not group:
                continue
            if not first:
                self._load_menu.add_separator()
            first = False
            for label, params in group:
                self._load_menu.add_command(
                    label=label,
                    command=lambda p=params: self._on_load_source(p),
                )

    def _on_load_source(self, params: dict) -> None:
        if self._current_name is None:
            return
        if not messagebox.askyesno(
            'Load configuration',
            'Loading a configuration replaces all parameters of this voicing. Continue?',
            parent=self,
        ):
            return
        import copy
        data = copy.deepcopy(params)
        self._current_label = data.get('label')
        self._vm.set_voicing_data(self._current_name, data)
        self._model_var.set(_MODEL_DISPLAY.get(data.get('model', 'piano'), 'Piano'))
        self._build_form(data)
        self._dirty = True

    def _on_name_commit(self, event=None) -> None:
        if self._current_name is None:
            return
        new = self._name_var.get().strip()
        if new == self._current_name:
            return
        try:
            self._vm.rename_voicing(self._current_name, new)
        except ValueError as exc:
            messagebox.showerror('Rename Voicing', str(exc), parent=self)
            self._name_var.set(self._current_name)
            return
        self._current_name = new
        self.refresh()
        self._select_in_tree(new)

    def _on_model_changed(self, event=None) -> None:
        if self._current_name is None:
            return
        new_model = _DISPLAY_MODEL.get(self._model_var.get())
        current = self._vm.get_voicings().get(self._current_name, {})
        if new_model == current.get('model'):
            return
        if self._dirty and not messagebox.askyesno(
            'Change Model',
            'Switching model will replace the current parameters with defaults. Continue?',
            parent=self,
        ):
            self._model_var.set(_MODEL_DISPLAY.get(current.get('model', 'piano'), 'Piano'))
            return
        data = _default_data_for_model(new_model)
        self._current_label = None
        self._vm.set_voicing_data(self._current_name, data)
        self._build_form(data)
        self._dirty = True

    # -- Editor load / clear -------------------------------------------------

    def select_voicing(self, name: str) -> None:
        """Select ``name`` in the tree and load it into the editor."""
        if name in self._vm.get_voicings():
            self._load_editor(name)
            self._select_in_tree(name)

    def _load_editor(self, name: str) -> None:
        self._current_name = name
        data = self._vm.get_voicings()[name]
        self._current_label = data.get('label')
        self._dirty = False

        self._set_editor_enabled(True)
        self._rebuild_load_menu()
        self._name_var.set(name)
        self._model_var.set(_MODEL_DISPLAY.get(data.get('model', 'piano'), 'Piano'))
        self._build_form(data)

    def _clear_editor(self) -> None:
        self._current_name = None
        self._current_label = None
        self._collect = None
        self._reset_fields()
        self._hide_banner()
        self._name_var.set('')
        self._model_var.set('')
        for child in self._form_host.winfo_children():
            child.destroy()
        placeholder = ttk.Label(
            self._form_host, text='Select a voicing to edit, or add one with "+".',
            foreground='#666666',
        )
        placeholder.grid(row=0, column=0, sticky='nw')
        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self._name_entry.configure(state=state)
        self._load_button.configure(state=state)
        self._model_combo.configure(state='readonly' if enabled else 'disabled')

    # -- Inline validation plumbing -----------------------------------------

    def _reset_fields(self) -> None:
        """Forget the previous form's registered controls (they were destroyed)."""
        self._field_widgets = {}
        self._field_tooltips = {}
        self._field_base_tips = {}

    def _register_field(self, field_id: str, widget: tk.Widget, tip_text: str) -> None:
        """Track a validatable control: tooltip it, and re-mark it live as it's typed."""
        self._field_base_tips[field_id] = tip_text
        self._field_tooltips[field_id] = add_tooltip(widget, tip_text)
        self._field_widgets[field_id] = widget
        widget.bind('<KeyRelease>',
                    lambda _e, fid=field_id: self._live_mark(fid), add='+')

    @staticmethod
    def _tip_label(parent, text: str, tip: str, **grid_kwargs) -> ttk.Label:
        """Create a form label, grid it, and give it its control's tooltip.

        Mirroring the tooltip onto the label (not just the input) means hovering
        the caption also reveals the help, which aids discoverability.
        """
        label = ttk.Label(parent, text=text)
        label.grid(**grid_kwargs)
        if tip:
            add_tooltip(label, tip)
        return label

    def _apply_field_mark(self, field_id: str, message: Optional[str]) -> None:
        """Red-mark (or clear) one control and fold ``message`` into its tooltip."""
        widget = self._field_widgets.get(field_id)
        if widget is None:
            return
        mark_field(widget, message is not None)
        tooltip = self._field_tooltips.get(field_id)
        if tooltip is not None:
            base = self._field_base_tips.get(field_id, '')
            tooltip.set_text(f"{base}\n\n⚠ {message}" if message else base)

    def _live_mark(self, field_id: str) -> None:
        """Lightweight per-keystroke re-mark of a single field (no vm/banner touch)."""
        if self._collect is None:
            return
        errors = field_errors(self._collect())
        self._apply_field_mark(field_id, errors.get(field_id))

    def _refresh_validation(self) -> None:
        """Re-mark every field from :func:`field_errors` and refresh the banner."""
        if self._current_name is None or self._collect is None:
            self._hide_banner()
            return
        errors = field_errors(self._collect())
        for field_id in self._field_widgets:
            self._apply_field_mark(field_id, errors.get(field_id))
        message = self._vm.validate_voicing(self._current_name)
        if message:
            self._show_banner(message)
        else:
            self._hide_banner()

    def _show_banner(self, message: str) -> None:
        self._banner.configure(text=message)
        self._banner.grid()

    def _hide_banner(self) -> None:
        self._banner.grid_remove()

    # -- Scrollable form scaffolding ----------------------------------------

    def _new_scroll_area(self) -> ttk.Frame:
        """Clear the form host and return a fresh scrollable inner frame.

        The inner frame carries a right padding so its controls never sit
        underneath the vertical scrollbar.
        """
        for child in self._form_host.winfo_children():
            child.destroy()

        canvas = tk.Canvas(self._form_host, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar = ttk.Scrollbar(self._form_host, orient='vertical', command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=scrollbar.set)

        # padding right = 16 keeps content clear of the scrollbar gutter.
        inner = ttk.Frame(canvas, padding=(2, 2, 16, 2))
        window = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', _on_configure)

        def _on_canvas_configure(event):
            canvas.itemconfigure(window, width=event.width)
        canvas.bind('<Configure>', _on_canvas_configure)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                canvas.yview_scroll(1, 'units')
            else:
                canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')

        for widget in (canvas, inner):
            widget.bind('<MouseWheel>', _on_mousewheel)
            widget.bind('<Button-4>', _on_mousewheel)
            widget.bind('<Button-5>', _on_mousewheel)

        inner.columnconfigure(1, weight=1)
        return inner

    def _build_form(self, data: dict) -> None:
        self._reset_fields()
        self._loading_form = True
        try:
            model = data.get('model', 'piano')
            if model == 'fretboard':
                self._build_fretboard_form(data)
            elif model == 'ensemble':
                self._build_ensemble_form(data)
            else:
                self._build_piano_form(data)
        finally:
            self._loading_form = False
        # Reflect the freshly-built form's current error state immediately.
        self._refresh_validation()

    def _commit_form(self, event=None) -> None:
        if self._loading_form or self._current_name is None or self._collect is None:
            return
        data = self._collect()
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._refresh_validation()

    def _bind_commit(self, widget, *, is_entry=False) -> None:
        """Wire a widget so leaving/changing it commits the form."""
        if is_entry:
            widget.bind('<FocusOut>', self._commit_form)
            widget.bind('<Return>', self._commit_form)

    # -- Shared weight-grid helper ------------------------------------------

    def _build_weight_grid(self, frame: ttk.Frame,
                           entries: List) -> None:
        """Lay a list of weight spinboxes out in a 2-column (label, spin) grid.

        Args:
            frame: The parent frame; columns 0/2 hold labels, 1/3 hold spins.
            entries: ``(field_id, label, var, lo, hi, increment, tip)`` tuples.
        """
        for idx, (field_id, label, var, lo, hi, inc, tip) in enumerate(entries):
            r, c = divmod(idx, 2)
            c *= 2
            self._tip_label(frame, label, tip, row=r, column=c, sticky='w',
                            padx=(0, 6), pady=2)
            spin = ttk.Spinbox(frame, from_=lo, to=hi, increment=inc,
                               textvariable=var, width=8, command=self._commit_form)
            spin.grid(row=r, column=c + 1, sticky='w', padx=(0, 18), pady=2)
            self._bind_commit(spin, is_entry=True)
            self._register_field(field_id, spin, tip)

    # -- Fretboard form ------------------------------------------------------

    def _build_fretboard_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        weights = dict(FRETBOARD_DEFAULT_WEIGHTS)
        weights.update(data.get('weights', {}) or {})
        row = 0

        # Strings.
        self._tip_label(inner, 'Strings:', TOOLTIPS['tuning'],
                        row=row, column=0, sticky='w', pady=2)
        strings_var = tk.StringVar(value=_tuning_to_text(data.get('tuning', [])))
        strings_entry = ttk.Entry(inner, textvariable=strings_var)
        strings_entry.grid(row=row, column=1, sticky='ew', pady=2)
        self._bind_commit(strings_entry, is_entry=True)
        self._register_field('tuning', strings_entry, TOOLTIPS['tuning'])
        row += 1
        ttk.Label(inner, text='(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4)',
                  foreground='#666666').grid(row=row, column=1, sticky='w')
        row += 1

        # Physical parameters, two (label, spinbox) pairs per row.
        phys_frame = ttk.Frame(inner)
        phys_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        row += 1
        spin_vars: Dict[str, tk.StringVar] = {}
        phys_params = (
            ('max_fret', 'Max fret:', 5, 24, 12),
            ('fingers', 'Fingers:', 1, 5, 4),
            ('max_span', 'Max span:', 1, 8, 4),
            ('relaxed_span', 'Relaxed span:', 1, 10, 5),
        )
        for idx, (key, text, lo, hi, default) in enumerate(phys_params):
            r, c = divmod(idx, 2)
            c *= 2
            self._tip_label(phys_frame, text, TOOLTIPS[key],
                            row=r, column=c, sticky='w', padx=(0, 6), pady=2)
            var = tk.StringVar(value=str(data.get(key, default)))
            spin = ttk.Spinbox(phys_frame, from_=lo, to=hi, textvariable=var, width=8,
                               command=self._commit_form)
            spin.grid(row=r, column=c + 1, sticky='w', padx=(0, 18), pady=2)
            self._bind_commit(spin, is_entry=True)
            self._register_field(key, spin, TOOLTIPS[key])
            spin_vars[key] = var

        barre_var = tk.BooleanVar(value=bool(data.get('allow_barres', True)))
        barre_check = ttk.Checkbutton(inner, text='Allow barre chords', variable=barre_var,
                                      command=self._commit_form)
        barre_check.grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 2))
        add_tooltip(barre_check, TOOLTIPS['allow_barres'])
        row += 1

        # Weights.
        weights_frame = ttk.LabelFrame(inner, text='Weights', padding=8)
        weights_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        row += 1
        ttk.Label(weights_frame, text=_WEIGHTS_BLURB, foreground='#666666',
                  wraplength=440, justify=tk.LEFT).grid(
            row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
        grid_frame = ttk.Frame(weights_frame)
        grid_frame.grid(row=1, column=0, columnspan=4, sticky='ew')
        weight_vars: Dict[str, tk.StringVar] = {}
        weight_entries = []
        for key in FRETBOARD_DEFAULT_WEIGHTS:
            var = tk.StringVar(value=str(weights.get(key)))
            weight_vars[key] = var
            weight_entries.append((
                f'weight:{key}', FRETBOARD_WEIGHT_LABELS.get(key, key), var,
                -100.0, 100.0, 0.1, TOOLTIPS.get(f'weight:{key}', key),
            ))
        self._build_weight_grid(grid_frame, weight_entries)

        def collect() -> dict:
            out: dict = {'model': 'fretboard'}
            out['tuning'] = _parse_pitch_list(strings_var.get())
            for key, var in spin_vars.items():
                out[key] = _parse_int_or_raw(var.get())
            out['allow_barres'] = bool(barre_var.get())
            out['weights'] = {k: _parse_float_or_raw(v.get()) for k, v in weight_vars.items()}
            return out

        self._collect = collect

    # -- Ensemble form -------------------------------------------------------

    def _build_ensemble_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        voices = list(data.get('voices', []) or [])
        row = 0

        # Voices: an editable table with a header row and one row of aligned
        # Entry cells per voice. All columns are fixed-width and left-aligned
        # (no expanding middle column), so 'High' and the remove button stay
        # snug against 'Name' instead of being shoved to the right edge.
        voices_frame = ttk.LabelFrame(inner, text='Voices', padding=8)
        voices_frame.grid(row=row, column=0, columnspan=2, sticky='ew')
        row += 1

        name_w, range_w = 16, 8
        header_font = ('TkDefaultFont', 9, 'bold')
        for col, (htext, htip) in enumerate((
            ('Name', TOOLTIPS['voice_name']),
            ('Low', TOOLTIPS['voice_low']),
            ('High', TOOLTIPS['voice_high']),
            ('Staff', TOOLTIPS['voice_staff']),
        )):
            header = ttk.Label(voices_frame, text=htext, font=header_font)
            header.grid(row=0, column=col, sticky='w', padx=(0, 6))
            add_tooltip(header, htip)
        ttk.Separator(voices_frame, orient='horizontal').grid(
            row=1, column=0, columnspan=4, sticky='ew', pady=(2, 4))

        voice_rows: List[Dict[str, tk.StringVar]] = []
        for i, voice in enumerate(voices):
            vrange = voice.get('range', [None, None]) if isinstance(voice, dict) else [None, None]
            low = vrange[0] if len(vrange) > 0 else None
            high = vrange[1] if len(vrange) > 1 else None
            name_var = tk.StringVar(
                value=str(voice.get('name', '')) if isinstance(voice, dict) else '')
            low_var = tk.StringVar(value=_pitch_to_text(low) if low is not None else '')
            high_var = tk.StringVar(value=_pitch_to_text(high) if high is not None else '')
            raw_staff = voice.get('staff') if isinstance(voice, dict) else None
            staff_var = tk.StringVar(value=_STAFF_DISPLAY.get(raw_staff, str(raw_staff)))
            grid_row = i + 2

            name_e = ttk.Entry(voices_frame, textvariable=name_var, width=name_w)
            name_e.grid(row=grid_row, column=0, sticky='w', padx=(0, 6), pady=1)
            low_e = ttk.Entry(voices_frame, textvariable=low_var, width=range_w)
            low_e.grid(row=grid_row, column=1, sticky='w', padx=(0, 6), pady=1)
            high_e = ttk.Entry(voices_frame, textvariable=high_var, width=range_w)
            high_e.grid(row=grid_row, column=2, sticky='w', padx=(0, 6), pady=1)
            staff_cb = ttk.Combobox(voices_frame, textvariable=staff_var, width=range_w,
                                    state='readonly', values=_STAFF_COMBO_VALUES)
            staff_cb.grid(row=grid_row, column=3, sticky='w', padx=(0, 6), pady=1)
            staff_cb.bind('<<ComboboxSelected>>', self._commit_form)

            for entry in (name_e, low_e, high_e):
                self._bind_commit(entry, is_entry=True)
            add_tooltip(name_e, TOOLTIPS['voice_name'])
            self._register_field(f'voice:{i}:low', low_e, TOOLTIPS['voice_low'])
            self._register_field(f'voice:{i}:high', high_e, TOOLTIPS['voice_high'])
            self._register_field(f'voice:{i}:staff', staff_cb, TOOLTIPS['voice_staff'])

            remove_btn = ttk.Button(voices_frame, text='✕', width=3,
                                    command=lambda idx=i: self._remove_voice(idx))
            remove_btn.grid(row=grid_row, column=4, sticky='w', padx=(2, 0), pady=1)
            add_tooltip(remove_btn, TOOLTIPS['remove_voice'])
            voice_rows.append({
                'name': name_var, 'low': low_var, 'high': high_var, 'staff': staff_var,
            })

        add_btn = ttk.Button(voices_frame, text='Add voice', command=self._add_voice)
        add_btn.grid(row=len(voices) + 2, column=0, columnspan=2, sticky='w', pady=(6, 0))
        add_tooltip(add_btn, TOOLTIPS['add_voice'])

        # Max spacing.
        self._tip_label(inner, 'Max spacing:', TOOLTIPS['max_spacing'],
                        row=row, column=0, sticky='w', pady=(8, 2))
        spacing_val = data.get('max_spacing')
        spacing_text = (
            ', '.join(str(s) for s in spacing_val)
            if isinstance(spacing_val, (list, tuple)) else (spacing_val or '')
        )
        spacing_var = tk.StringVar(value=str(spacing_text))
        spacing_entry = ttk.Entry(inner, textvariable=spacing_var)
        spacing_entry.grid(row=row, column=1, sticky='ew', pady=(8, 2))
        self._bind_commit(spacing_entry, is_entry=True)
        self._register_field('max_spacing', spacing_entry, TOOLTIPS['max_spacing'])
        row += 1
        ttk.Label(inner, text=f'(comma-separated, {max(len(voices) - 1, 0)} values expected)',
                  foreground='#666666').grid(row=row, column=1, sticky='w')
        row += 1

        unison_var = tk.BooleanVar(value=bool(data.get('allow_unisons', True)))
        unison_check = ttk.Checkbutton(inner, text='Allow unisons', variable=unison_var,
                                       command=self._commit_form)
        unison_check.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        add_tooltip(unison_check, TOOLTIPS['allow_unisons'])
        row += 1

        weights = data.get('weights', {}) or {}
        weight_vars: Dict[str, tk.StringVar] = {}
        movement_var = tk.StringVar()
        nested_vars: Dict[str, Dict[str, tk.StringVar]] = {}

        # Flat weights (plus the special movement entry) in a 2-column grid.
        weights_frame = ttk.LabelFrame(inner, text='Weights', padding=8)
        weights_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        row += 1
        ttk.Label(weights_frame, text=_WEIGHTS_BLURB, foreground='#666666',
                  wraplength=440, justify=tk.LEFT).grid(
            row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))

        grid_frame = ttk.Frame(weights_frame)
        grid_frame.grid(row=1, column=0, columnspan=4, sticky='ew')

        mv = weights.get('movement', ENSEMBLE_DEFAULT_WEIGHTS['movement'])
        movement_var.set(
            ', '.join(str(x) for x in mv) if isinstance(mv, (list, tuple)) else str(mv))
        # Movement is a free-form entry (scalar or list), placed first.
        self._tip_label(grid_frame, ENSEMBLE_WEIGHT_LABELS['movement'],
                        TOOLTIPS['weight:movement'],
                        row=0, column=0, sticky='w', padx=(0, 6), pady=2)
        mv_entry = ttk.Entry(grid_frame, textvariable=movement_var, width=10)
        mv_entry.grid(row=0, column=1, sticky='w', padx=(0, 18), pady=2)
        self._bind_commit(mv_entry, is_entry=True)
        self._register_field('movement', mv_entry, TOOLTIPS['weight:movement'])

        flat_entries = []
        idx = 1  # movement occupies grid slot 0
        for key, default in ENSEMBLE_DEFAULT_WEIGHTS.items():
            if key == 'movement' or key in _NESTED_WEIGHT_KEYS:
                continue
            var = tk.StringVar(value=str(weights.get(key, default)))
            weight_vars[key] = var
            flat_entries.append((idx, key, var))
            idx += 1
        for slot, key, var in flat_entries:
            r, c = divmod(slot, 2)
            c *= 2
            self._tip_label(grid_frame, ENSEMBLE_WEIGHT_LABELS.get(key, key),
                            TOOLTIPS.get(f'weight:{key}', key),
                            row=r, column=c, sticky='w', padx=(0, 6), pady=2)
            spin = ttk.Spinbox(grid_frame, from_=-100.0, to=100.0, increment=0.1,
                               textvariable=var, width=8, command=self._commit_form)
            spin.grid(row=r, column=c + 1, sticky='w', padx=(0, 18), pady=2)
            self._bind_commit(spin, is_entry=True)
            self._register_field(f'weight:{key}', spin, TOOLTIPS.get(f'weight:{key}', key))

        # Nested-weight groups: three LabelFrames laid out to use horizontal
        # space (doubling + omit side by side, inversion below), each rendering
        # its role rows in two columns.
        nested_container = ttk.Frame(inner)
        nested_container.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        nested_container.columnconfigure(0, weight=1, uniform='nested')
        nested_container.columnconfigure(1, weight=1, uniform='nested')
        row += 1
        nested_positions = {'doubling': (0, 0), 'omit': (0, 1), 'inversion': (1, 0)}
        for nested_key in _NESTED_WEIGHT_KEYS:
            sub_default = ENSEMBLE_DEFAULT_WEIGHTS[nested_key]
            sub_current = weights.get(nested_key, {}) or {}
            gr, gc = nested_positions[nested_key]
            sub_frame = ttk.LabelFrame(nested_container, text=NESTED_WEIGHT_TITLES[nested_key],
                                       padding=6)
            sub_frame.grid(row=gr, column=gc, sticky='new', padx=(0, 8), pady=(0, 8))
            nested_vars[nested_key] = {}
            role_entries = []
            for subkey, subdefault in sub_default.items():
                var = tk.StringVar(value=str(sub_current.get(subkey, subdefault)))
                nested_vars[nested_key][subkey] = var
                role_entries.append((
                    f'nested:{nested_key}:{subkey}', ROLE_LABELS.get(subkey, subkey),
                    var, -100.0, 100.0, 0.1, _nested_tooltip(nested_key, subkey),
                ))
            self._build_weight_grid(sub_frame, role_entries)

        def collect() -> dict:
            out: dict = {'model': 'ensemble'}
            out_voices = []
            for vr in voice_rows:
                voice_dict: Dict[str, Any] = {
                    'name': vr['name'].get().strip(),
                    'range': [_parse_pitch_or_raw(vr['low'].get()),
                              _parse_pitch_or_raw(vr['high'].get())],
                }
                staff_display = vr['staff'].get()
                staff_value = _DISPLAY_TO_STAFF.get(staff_display, staff_display)
                if staff_value is not None:
                    voice_dict['staff'] = staff_value
                out_voices.append(voice_dict)
            out['voices'] = out_voices
            spacing_raw = spacing_var.get().strip()
            if spacing_raw:
                out['max_spacing'] = _parse_int_list_or_raw(spacing_raw)
            out['allow_unisons'] = bool(unison_var.get())
            weights_out: dict = {k: _parse_float_or_raw(v.get()) for k, v in weight_vars.items()}
            weights_out['movement'] = _parse_scalar_or_list(movement_var.get())
            for nested_key, sub in nested_vars.items():
                weights_out[nested_key] = {sk: _parse_float_or_raw(sv.get())
                                           for sk, sv in sub.items()}
            out['weights'] = weights_out
            return out

        self._collect = collect

    def _add_voice(self) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = self._collect()
        data.setdefault('voices', [])
        data['voices'].append({'name': f"Voice {len(data['voices']) + 1}", 'range': ['C3', 'C4']})
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)

    def _remove_voice(self, index: int) -> None:
        if self._current_name is None or self._collect is None:
            return
        data = self._collect()
        voices = data.get('voices', [])
        if 0 <= index < len(voices):
            del voices[index]
        if self._current_label:
            data['label'] = self._current_label
        self._vm.set_voicing_data(self._current_name, data)
        self._dirty = True
        self._build_form(data)

    # -- Piano form ----------------------------------------------------------

    _PIANO_RANGE_KEYS = ('lh_range', 'rh_range', 'bass_range', 'rh_low_anchor')
    _PIANO_SCALAR_KEYS = ('rh_low_interval_floor', 'hand_span', 'max_notes_per_hand',
                          'max_total_notes', 'hand_gap_floor')

    def _piano_render_data(self, data: dict) -> dict:
        """Fully populate a piano data dict for rendering, defaults and all.

        Runs ``data`` through :meth:`PianoSpec.from_dict` so a bare
        ``{'model': 'piano'}`` entry (or any partial one) renders every real
        default value instead of blanks. If ``data`` currently carries
        unparseable values (e.g. left over from a previous forgiving commit,
        or mid-edit), ``from_dict`` raises; fall back to the defaults with
        ``data``'s own raw values overlaid on top, so the user still sees --
        and can fix -- whatever is wrong instead of the form silently
        discarding it.
        """
        name = self._current_name or 'piano'
        try:
            return PianoSpec.from_dict(name, data).to_dict()
        except ConfigurationError:
            populated = DEFAULT_PIANO.to_dict()
            for key, value in data.items():
                if key in ('model', 'weights'):
                    continue
                if key in self._PIANO_RANGE_KEYS:
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        populated[key] = list(value)
                    continue
                populated[key] = value
            weights = dict(PIANO_DEFAULT_WEIGHTS)
            weights['omit'] = dict(PIANO_DEFAULT_WEIGHTS['omit'])
            raw_weights = data.get('weights')
            if isinstance(raw_weights, dict):
                for key, value in raw_weights.items():
                    if key == 'omit' and isinstance(value, dict):
                        weights['omit'].update(value)
                    else:
                        weights[key] = value
            populated['weights'] = weights
            return populated

    @staticmethod
    def _piano_weight_tooltip(key: str) -> str:
        tip_key = _PIANO_WEIGHT_TOOLTIP_OVERRIDES.get(key, f'weight:{key}')
        return TOOLTIPS.get(tip_key, key)

    def _build_piano_form(self, data: dict) -> None:
        inner = self._new_scroll_area()
        populated = self._piano_render_data(data)
        row = 0

        # Hands & range: four pitch ranges as (Low, High) note-name entries,
        # the same idiom as the ensemble form's voice-range table.
        range_frame = ttk.LabelFrame(inner, text='Hands & range', padding=8)
        range_frame.grid(row=row, column=0, columnspan=2, sticky='ew')
        row += 1

        header_font = ('TkDefaultFont', 9, 'bold')
        for col, htext in ((1, 'Low'), (2, 'High')):
            header = ttk.Label(range_frame, text=htext, font=header_font)
            header.grid(row=0, column=col, sticky='w', padx=(0, 6))
        ttk.Separator(range_frame, orient='horizontal').grid(
            row=1, column=0, columnspan=3, sticky='ew', pady=(2, 4))

        range_specs = (
            ('lh_range', 'Left hand', 'lh_range_low', 'lh_range_high'),
            ('rh_range', 'Right hand', 'rh_range_low', 'rh_range_high'),
            ('bass_range', 'Bass (preferred)', 'bass_range_low', 'bass_range_high'),
            ('rh_low_anchor', 'RH lowest-note anchor', 'rh_low_anchor_low', 'rh_low_anchor_high'),
        )
        range_vars: Dict[str, Dict[str, tk.StringVar]] = {}
        for i, (key, label, low_tip_key, high_tip_key) in enumerate(range_specs):
            grid_row = i + 2
            lo, hi = populated.get(key, (0, 0))
            row_label = ttk.Label(range_frame, text=label)
            row_label.grid(row=grid_row, column=0, sticky='w', padx=(0, 6), pady=1)
            low_var = tk.StringVar(value=_pitch_to_text(lo))
            high_var = tk.StringVar(value=_pitch_to_text(hi))
            low_e = ttk.Entry(range_frame, textvariable=low_var, width=8)
            low_e.grid(row=grid_row, column=1, sticky='w', padx=(0, 6), pady=1)
            high_e = ttk.Entry(range_frame, textvariable=high_var, width=8)
            high_e.grid(row=grid_row, column=2, sticky='w', pady=1)
            self._bind_commit(low_e, is_entry=True)
            self._bind_commit(high_e, is_entry=True)
            add_tooltip(row_label, TOOLTIPS[low_tip_key])
            self._register_field(f'range:{key}:low', low_e, TOOLTIPS[low_tip_key])
            self._register_field(f'range:{key}:high', high_e, TOOLTIPS[high_tip_key])
            range_vars[key] = {'low': low_var, 'high': high_var}

        # Physical scalars, two (label, spinbox) pairs per row.
        phys_frame = ttk.Frame(inner)
        phys_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        row += 1
        spin_vars: Dict[str, tk.StringVar] = {}
        phys_params = (
            ('rh_center', 'RH center:', 0, 127, 0.5),
            ('rh_low_interval_floor', 'Muddy floor:', 0, 127, 1),
            ('hand_span', 'Hand span:', 1, 24, 1),
            ('max_notes_per_hand', 'Max notes/hand:', 1, 10, 1),
            ('max_total_notes', 'Max total notes:', 1, 20, 1),
            ('hand_gap_floor', 'Hand gap floor:', 0, 24, 1),
        )
        for idx, (key, text, lo, hi, inc) in enumerate(phys_params):
            r, c = divmod(idx, 2)
            c *= 2
            self._tip_label(phys_frame, text, TOOLTIPS[key],
                            row=r, column=c, sticky='w', padx=(0, 6), pady=2)
            var = tk.StringVar(value=str(populated.get(key)))
            spin = ttk.Spinbox(phys_frame, from_=lo, to=hi, increment=inc,
                               textvariable=var, width=8, command=self._commit_form)
            spin.grid(row=r, column=c + 1, sticky='w', padx=(0, 18), pady=2)
            self._bind_commit(spin, is_entry=True)
            self._register_field(key, spin, TOOLTIPS[key])
            spin_vars[key] = var

        add_bass_var = tk.BooleanVar(value=bool(populated.get('add_bass', True)))
        add_bass_check = ttk.Checkbutton(inner, text='Add bass note', variable=add_bass_var,
                                         command=self._commit_form)
        add_bass_check.grid(row=row, column=0, columnspan=2, sticky='w', pady=(4, 2))
        add_tooltip(add_bass_check, TOOLTIPS['add_bass'])
        row += 1

        # Weights.
        weights = populated.get('weights', {}) or {}
        weights_frame = ttk.LabelFrame(inner, text='Weights', padding=8)
        weights_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        row += 1
        ttk.Label(weights_frame, text=_WEIGHTS_BLURB, foreground='#666666',
                  wraplength=440, justify=tk.LEFT).grid(
            row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
        grid_frame = ttk.Frame(weights_frame)
        grid_frame.grid(row=1, column=0, columnspan=4, sticky='ew')
        weight_vars: Dict[str, tk.StringVar] = {}
        weight_entries = []
        for key, default in PIANO_DEFAULT_WEIGHTS.items():
            if key == 'omit':
                continue
            var = tk.StringVar(value=str(weights.get(key, default)))
            weight_vars[key] = var
            weight_entries.append((
                f'weight:{key}', PIANO_WEIGHT_LABELS.get(key, key), var,
                -100.0, 100.0, 0.1, self._piano_weight_tooltip(key),
            ))
        self._build_weight_grid(grid_frame, weight_entries)

        # Omission (nested per-role weights), the same idiom as the ensemble
        # form's nested-weight sub-frames.
        omit_frame = ttk.LabelFrame(weights_frame, text=NESTED_WEIGHT_TITLES['omit'], padding=6)
        omit_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=(8, 0))
        omit_default = PIANO_DEFAULT_WEIGHTS['omit']
        omit_current = weights.get('omit', {}) or {}
        omit_vars: Dict[str, tk.StringVar] = {}
        omit_entries = []
        for subkey, subdefault in omit_default.items():
            var = tk.StringVar(value=str(omit_current.get(subkey, subdefault)))
            omit_vars[subkey] = var
            omit_entries.append((
                f'nested:omit:{subkey}', ROLE_LABELS.get(subkey, subkey),
                var, -100.0, 100.0, 0.1, _nested_tooltip('omit', subkey),
            ))
        self._build_weight_grid(omit_frame, omit_entries)

        def collect() -> dict:
            out: dict = {'model': 'piano'}
            for key, vars_ in range_vars.items():
                out[key] = [
                    _parse_pitch_or_raw(vars_['low'].get()),
                    _parse_pitch_or_raw(vars_['high'].get()),
                ]
            out['rh_center'] = _parse_float_or_raw(spin_vars['rh_center'].get())
            for key in self._PIANO_SCALAR_KEYS:
                out[key] = _parse_int_or_raw(spin_vars[key].get())
            out['add_bass'] = bool(add_bass_var.get())
            weights_out: dict = {k: _parse_float_or_raw(v.get()) for k, v in weight_vars.items()}
            weights_out['omit'] = {k: _parse_float_or_raw(v.get()) for k, v in omit_vars.items()}
            out['weights'] = weights_out
            return out

        self._collect = collect
