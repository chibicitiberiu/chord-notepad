"""The voicings editor as data: form schemas, value conversion and validation.

Each voicing model (fretboard, ensemble, piano) has a declarative *form
schema*: ordered sections of fields, each field with an id, a label, help
text, a kind, constraints and a default. A view renders the schema and holds
the user's *values*; everything else (formatting a stored voicing for the
form, parsing the form back into a voicing, which fields are invalid, the
cross-field error, the "Load config" presets) lives here, so the desktop
Settings window and the Android editor behave the same.

Everything a function here returns is plain JSON data (dict, list, str,
number, bool, None), so the bridge can carry it unchanged.

Values
------
A form's values are a flat dict keyed by field id. Text-like fields hold the
string the user sees (``'E2 A2 D3 G3 B3 E4'``, ``'12'``, ``'-1.2'``), bool
fields hold a bool, a choice field holds the chosen ``value``, and a records
field (the ensemble's voices) holds a list of dicts keyed by column id. Field
ids double as error keys: ``field_errors`` reports ``{'max_fret': ...}`` for
the ``max_fret`` field and ``'voice:<i>:<column>'`` for a cell of row ``i``.

Parsing is forgiving, as on the desktop: a value that doesn't parse stays a
raw string in the voicing dict, so the user can keep typing. Two error
classes come out of that:

* **field errors** (:func:`field_errors`): a value left as a raw string where
  a number, note name or list was expected, marked on the field itself;
* **cross-field errors** (:func:`cross_field_errors`): whatever the model's
  spec rejects (relaxed span below the stretch, a voice's low above its high,
  a wrong ``max_spacing`` length, an out-of-range value, ...), shown once for
  the whole form.
"""

import copy
import logging
import re
from typing import Any, Dict, List, Mapping, Optional

from exceptions import ConfigurationError
from models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    DEFAULT_WEIGHTS as ENSEMBLE_DEFAULT_WEIGHTS,
    EnsembleSpec,
    _NESTED_WEIGHT_KEYS,
    midi_to_note_name,
    parse_note_name,
)
from models.fretboard_spec import (
    BUILTIN_FRETBOARDS,
    DEFAULT_WEIGHTS as FRETBOARD_DEFAULT_WEIGHTS,
    FretboardSpec,
)
from models.piano_spec import (
    DEFAULT_PIANO,
    DEFAULT_WEIGHTS as PIANO_DEFAULT_WEIGHTS,
    PianoSpec,
)
from settings_forms.voicing_texts import (
    ANDROID_TOOLTIPS,
    EDITOR_TEXTS,
    ENSEMBLE_WEIGHT_LABELS,
    FRETBOARD_WEIGHT_LABELS,
    MODEL_LABELS,
    NESTED_WEIGHT_TITLES,
    PIANO_WEIGHT_LABELS,
    ROLE_LABELS,
    STAFF_LABELS,
    TOOLTIPS,
    WEIGHTS_BLURB,
    nested_tooltip,
    piano_weight_tooltip,
)

logger = logging.getLogger(__name__)

#: Bumped when the shape of the schema changes incompatibly.
SCHEMA_VERSION = 1

#: The voicing models, in the order the model selector lists them.
MODELS = ('fretboard', 'ensemble', 'piano')

#: Group order of the voicings list (tree) and the "Load config" menu.
TREE_GROUPS = ('fretboard', 'piano', 'ensemble')

# Field kinds. Text-like kinds hold a string value; see the module docstring.
KIND_TEXT = 'text'                    # free text, never invalid
KIND_INT = 'int'                      # a whole number
KIND_FLOAT = 'float'                  # a number
KIND_BOOL = 'bool'                    # a checkbox
KIND_CHOICE = 'choice'                # one of ``choices`` (by value)
KIND_PITCH = 'pitch'                  # a note name or MIDI number
KIND_PITCH_LIST = 'pitch_list'        # pitches separated by spaces or commas
KIND_INT_LIST = 'int_list'            # comma-separated whole numbers
KIND_FLOAT_OR_LIST = 'float_or_list'  # a number, or comma-separated numbers
KIND_RECORDS = 'records'              # a list of rows, each a dict of ``columns``

# Section kinds (presentation hints shared by every view).
SECTION_STACK = 'stack'              # fields one under another
SECTION_GRID = 'grid'                # number fields in a two-column grid
SECTION_TABLE = 'table'              # one records field shown as a table
SECTION_RANGE_TABLE = 'range_table'  # labelled rows of (low, high) pitch fields
SECTION_GROUPS = 'groups'            # titled sub-sections side by side

#: Spinner range of every weight.
_WEIGHT_MIN, _WEIGHT_MAX, _WEIGHT_STEP = -100.0, 100.0, 0.1

#: Error message per field kind (the kinds that can fail to parse).
_KIND_ERRORS = {
    KIND_INT: 'Must be a whole number',
    KIND_FLOAT: 'Must be a number',
    KIND_PITCH: 'Not a valid note name',
    KIND_PITCH_LIST: 'Not a valid note name',
    KIND_INT_LIST: 'Must be whole numbers',
    KIND_FLOAT_OR_LIST: 'Must be a number or list of numbers',
    KIND_CHOICE: "Must be 'treble', 'bass', or omitted",
}

_PIANO_RANGE_KEYS = ('lh_range', 'rh_range', 'bass_range', 'rh_low_anchor')
_PIANO_INT_KEYS = ('rh_low_interval_floor', 'hand_span', 'max_notes_per_hand',
                   'max_total_notes', 'hand_gap_floor')
_FRETBOARD_INT_KEYS = ('max_fret', 'fingers', 'max_span', 'relaxed_span')


# ---------------------------------------------------------------------------
# Parsing and formatting (forgiving: keep the raw string when a value won't parse)
# ---------------------------------------------------------------------------


def pitch_to_text(value: Any) -> str:
    """Render a single pitch (MIDI int or already-a-string) as a note name."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return midi_to_note_name(value)
    return str(value)


def tuning_to_text(tuning: Any) -> str:
    """Render a tuning (list of pitches, or a raw in-progress string) for the entry."""
    if isinstance(tuning, str):
        return tuning
    if isinstance(tuning, (list, tuple)):
        return ' '.join(pitch_to_text(p) for p in tuning)
    return ''


def parse_pitch_token(token: str) -> Optional[int]:
    """Parse one pitch token to a MIDI int, or return None if unparseable."""
    token = token.strip()
    if re.fullmatch(r'-?\d+', token):
        return int(token)
    return parse_note_name(token)


def parse_pitch_list(text: str) -> Any:
    """Parse a whitespace/comma separated pitch list; return a list or the raw text."""
    tokens = [t for t in re.split(r'[,\s]+', text.strip()) if t]
    if not tokens:
        return []
    parsed = []
    for token in tokens:
        midi = parse_pitch_token(token)
        if midi is None:
            return text  # keep raw string for validation to pinpoint later
        parsed.append(midi)
    return parsed


def parse_pitch_or_raw(text: str) -> Any:
    """Parse a single pitch endpoint; return an int or the raw string."""
    midi = parse_pitch_token(text)
    return midi if midi is not None else text


def parse_int_or_raw(text: str) -> Any:
    """Parse a whole number; return an int or the raw string."""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return text


def parse_float_or_raw(text: str) -> Any:
    """Parse a number; return a float or the raw string."""
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        return text


def parse_int_list_or_raw(text: str) -> Any:
    """Parse a comma-separated int list; return a list or the raw string."""
    tokens = [t.strip() for t in text.split(',') if t.strip()]
    parsed = []
    for token in tokens:
        try:
            parsed.append(int(token))
        except ValueError:
            return text
    return parsed


def parse_scalar_or_list(text: str) -> Any:
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


def _join(value: Any) -> str:
    """Render a list as ``'a, b, c'`` and anything else with ``str``."""
    if isinstance(value, (list, tuple)):
        return ', '.join(str(x) for x in value)
    return str(value)


def _is_number(value: Any) -> bool:
    """True for a real int/float, excluding bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def form_model(model: Any) -> str:
    """The form a voicing of ``model`` is edited with (unknown models get the piano form)."""
    return model if model in ('fretboard', 'ensemble') else 'piano'


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def default_voicing(model: str) -> Dict[str, Any]:
    """Parameters for a brand-new voicing of ``model`` (also used on a model switch).

    Fretboard is a standard guitar, ensemble a minimal two-voice pair, piano
    the bare engine defaults.
    """
    if model == 'fretboard':
        return {'model': 'fretboard', 'tuning': [40, 45, 50, 55, 59, 64]}
    if model == 'ensemble':
        return {
            'model': 'ensemble',
            'voices': [
                {'name': 'Voice 1', 'range': ['C4', 'C5']},
                {'name': 'Voice 2', 'range': ['C3', 'C4']},
            ],
        }
    return {'model': 'piano'}


def default_values(model: str) -> Dict[str, Any]:
    """The form values of a brand-new voicing of ``model``."""
    return values_from_voicing(model, default_voicing(model))


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def _field(field_id: str, kind: str, label: str, help_text: str, default: Any,
           **extra: Any) -> Dict[str, Any]:
    """One field description; ``extra`` holds the optional keys (min, max, step, ...)."""
    out: Dict[str, Any] = {'id': field_id, 'kind': kind, 'label': label,
                           'help': help_text, 'default': default}
    out.update(extra)
    return out


def _weight_field(field_id: str, label: str, help_text: str, default: Any) -> Dict[str, Any]:
    return _field(field_id, KIND_FLOAT, label, help_text, str(default),
                  min=_WEIGHT_MIN, max=_WEIGHT_MAX, step=_WEIGHT_STEP)


def _nested_group(group: str, defaults: Mapping[str, Any],
                  model: str = 'ensemble') -> Dict[str, Any]:
    """A titled grid of per-role weights (doubling / omit / inversion)."""
    return {
        'id': f'nested:{group}',
        'kind': SECTION_GRID,
        'title': NESTED_WEIGHT_TITLES[group],
        'fields': [
            _weight_field(f'nested:{group}:{role}', ROLE_LABELS.get(role, role),
                          nested_tooltip(group, role, model), value)
            for role, value in defaults.items()
        ],
    }


def _fretboard_schema() -> Dict[str, Any]:
    defaults = values_from_voicing('fretboard', default_voicing('fretboard'))
    physical = (
        ('max_fret', 'Max fret', 5, 24),
        ('fingers', 'Fingers', 1, 5),
        ('max_span', 'Max span', 1, 8),
        ('relaxed_span', 'Relaxed span', 1, 10),
    )
    return {
        'model': 'fretboard',
        'title': MODEL_LABELS['fretboard'],
        'sections': [
            {'id': 'strings', 'kind': SECTION_STACK, 'title': None, 'fields': [
                _field('tuning', KIND_PITCH_LIST, 'Strings', TOOLTIPS['tuning'],
                       defaults['tuning'],
                       hint='(note names or MIDI numbers, e.g. E2 A2 D3 G3 B3 E4)',
                       min_items=3, max_items=12),
            ]},
            {'id': 'physical', 'kind': SECTION_GRID, 'title': None, 'fields': [
                _field(key, KIND_INT, label, TOOLTIPS[key], defaults[key],
                       min=lo, max=hi, step=1)
                for key, label, lo, hi in physical
            ]},
            {'id': 'options', 'kind': SECTION_STACK, 'title': None, 'fields': [
                _field('allow_barres', KIND_BOOL, 'Allow barre chords',
                       TOOLTIPS['allow_barres'], True),
            ]},
            {'id': 'weights', 'kind': SECTION_GRID, 'title': 'Weights', 'blurb': WEIGHTS_BLURB,
             'fields': [
                 _weight_field(f'weight:{key}', FRETBOARD_WEIGHT_LABELS.get(key, key),
                               TOOLTIPS.get(f'weight:{key}', key), value)
                 for key, value in FRETBOARD_DEFAULT_WEIGHTS.items()
             ]},
        ],
    }


def _ensemble_schema() -> Dict[str, Any]:
    defaults = values_from_voicing('ensemble', default_voicing('ensemble'))
    staff_choices = [{'value': value, 'label': label} for value, label in STAFF_LABELS]
    voices = _field(
        'voices', KIND_RECORDS, 'Voices', '', defaults['voices'],
        columns=[
            _field('name', KIND_TEXT, 'Name', TOOLTIPS['voice_name'], '', width=16),
            _field('low', KIND_PITCH, 'Low', TOOLTIPS['voice_low'], 'C3', width=8),
            _field('high', KIND_PITCH, 'High', TOOLTIPS['voice_high'], 'C4', width=8),
            _field('staff', KIND_CHOICE, 'Staff', TOOLTIPS['voice_staff'], None,
                   width=8, choices=staff_choices),
        ],
        error_path='voice:{index}:{column}',
        min_items=2, max_items=8,
        new_item={'name': 'Voice {n}', 'low': 'C3', 'high': 'C4', 'staff': None},
        add_label='Add voice', add_help=TOOLTIPS['add_voice'],
        remove_label='✕', remove_help=TOOLTIPS['remove_voice'],
    )
    flat_weights = [
        _field('movement', KIND_FLOAT_OR_LIST, ENSEMBLE_WEIGHT_LABELS['movement'],
               TOOLTIPS['weight:movement'], defaults['movement'], width=10),
    ]
    for key, value in ENSEMBLE_DEFAULT_WEIGHTS.items():
        if key == 'movement' or key in _NESTED_WEIGHT_KEYS:
            continue
        flat_weights.append(_weight_field(
            f'weight:{key}', ENSEMBLE_WEIGHT_LABELS.get(key, key),
            TOOLTIPS.get(f'weight:{key}', key), value))
    return {
        'model': 'ensemble',
        'title': MODEL_LABELS['ensemble'],
        'sections': [
            {'id': 'voices', 'kind': SECTION_TABLE, 'title': 'Voices', 'fields': [voices]},
            {'id': 'spacing', 'kind': SECTION_STACK, 'title': None, 'fields': [
                _field('max_spacing', KIND_INT_LIST, 'Max spacing', TOOLTIPS['max_spacing'],
                       defaults['max_spacing'],
                       hint='(comma-separated, {count} values expected)',
                       hint_count={'records': 'voices', 'offset': -1}),
                _field('allow_unisons', KIND_BOOL, 'Allow unisons',
                       TOOLTIPS['allow_unisons'], True),
            ]},
            {'id': 'weights', 'kind': SECTION_GRID, 'title': 'Weights', 'blurb': WEIGHTS_BLURB,
             'fields': flat_weights},
            {'id': 'nested', 'kind': SECTION_GROUPS, 'title': None, 'groups': [
                _nested_group(group, ENSEMBLE_DEFAULT_WEIGHTS[group])
                for group in _NESTED_WEIGHT_KEYS
            ]},
        ],
    }


def _piano_schema() -> Dict[str, Any]:
    defaults = values_from_voicing('piano', default_voicing('piano'))
    ranges = (
        ('lh_range', 'Left hand', 'lh_range_low', 'lh_range_high'),
        ('rh_range', 'Right hand', 'rh_range_low', 'rh_range_high'),
        ('bass_range', 'Bass (preferred)', 'bass_range_low', 'bass_range_high'),
        ('rh_low_anchor', 'RH lowest-note anchor', 'rh_low_anchor_low', 'rh_low_anchor_high'),
    )
    physical = (
        ('rh_center', KIND_FLOAT, 'RH center', 0, 127, 0.5),
        ('rh_low_interval_floor', KIND_INT, 'Muddy floor', 0, 127, 1),
        ('hand_span', KIND_INT, 'Hand span', 1, 24, 1),
        ('max_notes_per_hand', KIND_INT, 'Max notes/hand', 1, 10, 1),
        ('max_total_notes', KIND_INT, 'Max total notes', 1, 20, 1),
        ('hand_gap_floor', KIND_INT, 'Hand gap floor', 0, 24, 1),
    )
    rows = []
    for key, label, low_tip, high_tip in ranges:
        low_id, high_id = f'range:{key}:low', f'range:{key}:high'
        rows.append({
            'id': key, 'label': label, 'help': TOOLTIPS[low_tip],
            'fields': [
                _field(low_id, KIND_PITCH, 'Low', TOOLTIPS[low_tip], defaults[low_id], width=8),
                _field(high_id, KIND_PITCH, 'High', TOOLTIPS[high_tip], defaults[high_id],
                       width=8),
            ],
        })
    flat_weights = [
        _weight_field(f'weight:{key}', PIANO_WEIGHT_LABELS.get(key, key),
                      piano_weight_tooltip(key), value)
        for key, value in PIANO_DEFAULT_WEIGHTS.items() if key != 'omit'
    ]
    return {
        'model': 'piano',
        'title': MODEL_LABELS['piano'],
        'sections': [
            {'id': 'ranges', 'kind': SECTION_RANGE_TABLE, 'title': 'Hands & range',
             'columns': ['Low', 'High'], 'rows': rows},
            {'id': 'physical', 'kind': SECTION_GRID, 'title': None, 'fields': [
                _field(key, kind, label, TOOLTIPS[key], defaults[key], min=lo, max=hi, step=step)
                for key, kind, label, lo, hi, step in physical
            ]},
            {'id': 'options', 'kind': SECTION_STACK, 'title': None, 'fields': [
                _field('add_bass', KIND_BOOL, 'Add bass note', TOOLTIPS['add_bass'], True),
            ]},
            {'id': 'weights', 'kind': SECTION_GRID, 'title': 'Weights', 'blurb': WEIGHTS_BLURB,
             'fields': flat_weights,
             'groups': [_nested_group('omit', PIANO_DEFAULT_WEIGHTS['omit'], 'piano')]},
        ],
    }


def form_schema(model: str) -> Dict[str, Any]:
    """The form schema of one model (unknown models get the piano form).

    Shape::

        {'model': 'fretboard', 'title': 'Fretboard', 'sections': [
            {'id': 'physical', 'kind': 'grid', 'title': None, 'fields': [
                {'id': 'max_fret', 'kind': 'int', 'label': 'Max fret',
                 'help': '...', 'default': '12', 'min': 5, 'max': 24, 'step': 1},
                ...]},
            ...]}

    A section has an ``id``, a ``kind`` (``stack``, ``grid``, ``table``,
    ``range_table`` or ``groups``), a ``title`` (or None) and optionally a
    ``blurb``; its inputs are in ``fields``, except a ``range_table`` (labelled
    ``rows``, each with two pitch ``fields``) and a ``groups`` section (titled
    ``grid`` sub-sections in ``groups``). A ``grid`` may also carry ``groups``,
    shown under its own fields. ``min``/``max``/``step`` are the spinner's
    range; the spec's own limits surface as the cross-field error.
    """
    model = form_model(model)
    if model == 'fretboard':
        return _fretboard_schema()
    if model == 'ensemble':
        return _ensemble_schema()
    return _piano_schema()


def editor_schema(platform: str = 'desktop') -> Dict[str, Any]:
    """Everything a view needs to build the voicings editor, as plain data.

    Args:
        platform: ``desktop`` or ``android`` (``session.platform``): the
            header help that names a menu is worded for it.

    Returns:
        ``{'version', 'models': [{'value', 'label'}], 'tree_groups': [{'model',
        'label'}], 'texts': {...}, 'help': {...}, 'forms': {model: schema}}``.
        ``texts`` holds the editor's fixed strings (button and dialog texts;
        ``remove_confirm`` takes a ``{name}``), ``help`` the help texts of the
        header controls (``name``, ``model``, ``load``, ``tree_add``,
        ``tree_remove``).
    """
    return {
        'version': SCHEMA_VERSION,
        'models': [{'value': m, 'label': MODEL_LABELS[m]} for m in MODELS],
        'tree_groups': [{'model': m, 'label': MODEL_LABELS[m]} for m in TREE_GROUPS],
        'texts': dict(EDITOR_TEXTS),
        'help': {key: (ANDROID_TOOLTIPS.get(key, TOOLTIPS[key]) if platform == 'android'
                       else TOOLTIPS[key])
                 for key in ('name', 'model', 'load', 'tree_add', 'tree_remove')},
        'forms': {m: form_schema(m) for m in MODELS},
    }


def iter_fields(schema: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Every input field of a form schema, in display order (records fields included)."""
    out: List[Dict[str, Any]] = []

    def walk(section: Mapping[str, Any]) -> None:
        out.extend(section.get('fields', []))
        for row in section.get('rows', []):
            out.extend(row['fields'])
        for group in section.get('groups', []):
            walk(group)

    for section in schema['sections']:
        walk(section)
    return out


def field_hint(field: Mapping[str, Any], values: Mapping[str, Any]) -> str:
    """The grey hint under a field, with any ``{count}`` filled in from ``values``."""
    hint = field.get('hint', '')
    count_rule = field.get('hint_count')
    if count_rule:
        count = max(len(values.get(count_rule['records']) or []) + count_rule['offset'], 0)
        hint = hint.format(count=count)
    return hint


def choice_label(field: Mapping[str, Any], value: Any) -> str:
    """The label shown for a choice value (an unknown value is shown as is)."""
    for choice in field['choices']:
        if choice['value'] == value:
            return choice['label']
    return str(value)


def choice_value(field: Mapping[str, Any], label: str) -> Any:
    """The value of a choice label (an unknown label is its own value)."""
    for choice in field['choices']:
        if choice['label'] == label:
            return choice['value']
    return label


# ---------------------------------------------------------------------------
# Voicing dict <-> form values
# ---------------------------------------------------------------------------


def _piano_render_data(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Fully populate a piano data dict for rendering, defaults and all.

    Runs ``data`` through :meth:`PianoSpec.from_dict` so a bare
    ``{'model': 'piano'}`` entry (or any partial one) renders every real
    default value instead of blanks. If ``data`` currently carries
    unparseable values (left over from a forgiving commit, or mid-edit),
    ``from_dict`` raises; fall back to the defaults with ``data``'s own raw
    values overlaid, so the user still sees -- and can fix -- whatever is
    wrong instead of the form silently discarding it.
    """
    try:
        return PianoSpec.from_dict('piano', data).to_dict()
    except ConfigurationError:
        populated = DEFAULT_PIANO.to_dict()
        for key, value in data.items():
            if key in ('model', 'weights'):
                continue
            if key in _PIANO_RANGE_KEYS:
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


def _weights_of(data: Mapping[str, Any]) -> Mapping[str, Any]:
    weights = data.get('weights')
    return weights if isinstance(weights, Mapping) else {}


def values_from_voicing(model: str, data: Mapping[str, Any]) -> Dict[str, Any]:
    """Format a stored voicing dict as form values (missing keys get their defaults).

    Args:
        model: The model whose form shows ``data`` (normally ``data['model']``).
        data: A voicing dict as stored in the config (may hold raw strings
            left by an earlier forgiving edit; they are shown as typed).

    Returns:
        The form values, keyed by field id.
    """
    model = form_model(model)
    values: Dict[str, Any] = {}

    if model == 'fretboard':
        weights = dict(FRETBOARD_DEFAULT_WEIGHTS)
        weights.update(_weights_of(data))
        values['tuning'] = tuning_to_text(data.get('tuning', []))
        for key, default in zip(_FRETBOARD_INT_KEYS, (12, 4, 4, 5)):
            values[key] = str(data.get(key, default))
        values['allow_barres'] = bool(data.get('allow_barres', True))
        for key in FRETBOARD_DEFAULT_WEIGHTS:
            values[f'weight:{key}'] = str(weights.get(key))
        return values

    if model == 'ensemble':
        rows = []
        for voice in list(data.get('voices', []) or []):
            is_dict = isinstance(voice, Mapping)
            vrange = voice.get('range', [None, None]) if is_dict else [None, None]
            if not isinstance(vrange, (list, tuple)):
                vrange = [None, None]
            low = vrange[0] if len(vrange) > 0 else None
            high = vrange[1] if len(vrange) > 1 else None
            rows.append({
                'name': str(voice.get('name', '')) if is_dict else '',
                'low': pitch_to_text(low) if low is not None else '',
                'high': pitch_to_text(high) if high is not None else '',
                'staff': voice.get('staff') if is_dict else None,
            })
        values['voices'] = rows
        spacing = data.get('max_spacing')
        values['max_spacing'] = str(
            ', '.join(str(s) for s in spacing) if isinstance(spacing, (list, tuple))
            else (spacing or ''))
        values['allow_unisons'] = bool(data.get('allow_unisons', True))
        weights = _weights_of(data)
        values['movement'] = _join(weights.get('movement', ENSEMBLE_DEFAULT_WEIGHTS['movement']))
        for key, default in ENSEMBLE_DEFAULT_WEIGHTS.items():
            if key == 'movement' or key in _NESTED_WEIGHT_KEYS:
                continue
            values[f'weight:{key}'] = str(weights.get(key, default))
        for group in _NESTED_WEIGHT_KEYS:
            current = weights.get(group, {}) or {}
            for role, default in ENSEMBLE_DEFAULT_WEIGHTS[group].items():
                values[f'nested:{group}:{role}'] = str(current.get(role, default))
        return values

    populated = _piano_render_data(data)
    for key in _PIANO_RANGE_KEYS:
        low, high = populated.get(key, (0, 0))
        values[f'range:{key}:low'] = pitch_to_text(low)
        values[f'range:{key}:high'] = pitch_to_text(high)
    for key in ('rh_center',) + _PIANO_INT_KEYS:
        values[key] = str(populated.get(key))
    values['add_bass'] = bool(populated.get('add_bass', True))
    weights = populated.get('weights', {}) or {}
    for key, default in PIANO_DEFAULT_WEIGHTS.items():
        if key != 'omit':
            values[f'weight:{key}'] = str(weights.get(key, default))
    omit = weights.get('omit', {}) or {}
    for role, default in PIANO_DEFAULT_WEIGHTS['omit'].items():
        values[f'nested:omit:{role}'] = str(omit.get(role, default))
    return values


def voicing_from_values(model: str, values: Mapping[str, Any],
                        label: Optional[str] = None) -> Dict[str, Any]:
    """Parse form values back into a voicing dict, forgivingly.

    A value that doesn't parse stays a raw string in the result (see
    :func:`field_errors`). A missing value counts as the field's default.

    Args:
        model: The form's model.
        values: The form values, keyed by field id.
        label: The voicing's display label to carry over, if it has one.

    Returns:
        A voicing dict including ``'model'``, ready for ``set_voicing_data``.
    """
    model = form_model(model)
    defaults = default_values(model)

    def text(key: str) -> str:
        value = values.get(key, defaults.get(key, ''))
        return '' if value is None else str(value)

    def flag(key: str) -> bool:
        return bool(values.get(key, defaults.get(key, True)))

    out: Dict[str, Any] = {'model': model}
    if model == 'fretboard':
        out['tuning'] = parse_pitch_list(text('tuning'))
        for key in _FRETBOARD_INT_KEYS:
            out[key] = parse_int_or_raw(text(key))
        out['allow_barres'] = flag('allow_barres')
        out['weights'] = {key: parse_float_or_raw(text(f'weight:{key}'))
                          for key in FRETBOARD_DEFAULT_WEIGHTS}

    elif model == 'ensemble':
        voices = []
        for row in values.get('voices', defaults.get('voices')) or []:
            voice: Dict[str, Any] = {
                'name': str(row.get('name', '')).strip(),
                'range': [parse_pitch_or_raw(str(row.get('low', ''))),
                          parse_pitch_or_raw(str(row.get('high', '')))],
            }
            if row.get('staff') is not None:
                voice['staff'] = row['staff']
            voices.append(voice)
        out['voices'] = voices
        spacing = text('max_spacing').strip()
        if spacing:
            out['max_spacing'] = parse_int_list_or_raw(spacing)
        out['allow_unisons'] = flag('allow_unisons')
        weights: Dict[str, Any] = {
            key: parse_float_or_raw(text(f'weight:{key}'))
            for key in ENSEMBLE_DEFAULT_WEIGHTS
            if key != 'movement' and key not in _NESTED_WEIGHT_KEYS
        }
        weights['movement'] = parse_scalar_or_list(text('movement'))
        for group in _NESTED_WEIGHT_KEYS:
            weights[group] = {role: parse_float_or_raw(text(f'nested:{group}:{role}'))
                              for role in ENSEMBLE_DEFAULT_WEIGHTS[group]}
        out['weights'] = weights

    else:
        for key in _PIANO_RANGE_KEYS:
            out[key] = [parse_pitch_or_raw(text(f'range:{key}:low')),
                        parse_pitch_or_raw(text(f'range:{key}:high'))]
        out['rh_center'] = parse_float_or_raw(text('rh_center'))
        for key in _PIANO_INT_KEYS:
            out[key] = parse_int_or_raw(text(key))
        out['add_bass'] = flag('add_bass')
        weights = {key: parse_float_or_raw(text(f'weight:{key}'))
                   for key in PIANO_DEFAULT_WEIGHTS if key != 'omit'}
        weights['omit'] = {role: parse_float_or_raw(text(f'nested:omit:{role}'))
                           for role in PIANO_DEFAULT_WEIGHTS['omit']}
        out['weights'] = weights

    if label:
        out['label'] = label
    return out


# ---------------------------------------------------------------------------
# Records (the ensemble's voices)
# ---------------------------------------------------------------------------


def voicing_with_record_added(data: Mapping[str, Any], field_id: str = 'voices') -> Dict[str, Any]:
    """A copy of ``data`` with one new row appended to its records field."""
    out = copy.deepcopy(dict(data))
    rows = out.setdefault(field_id, [])
    rows.append({'name': f'Voice {len(rows) + 1}', 'range': ['C3', 'C4']})
    return out


def voicing_with_record_removed(data: Mapping[str, Any], index: int,
                                field_id: str = 'voices') -> Dict[str, Any]:
    """A copy of ``data`` without row ``index`` of its records field (no-op if out of range)."""
    out = copy.deepcopy(dict(data))
    rows = out.get(field_id, [])
    if 0 <= index < len(rows):
        del rows[index]
    return out


def add_record(model: str, values: Mapping[str, Any], field_id: str = 'voices') -> Dict[str, Any]:
    """Form values with a new row appended to a records field.

    Goes through the voicing dict, so the other values come back normalised
    exactly as after the desktop's add (``'Db4'`` becomes ``'C#4'``).
    """
    data = voicing_with_record_added(voicing_from_values(model, values), field_id)
    return values_from_voicing(model, data)


def remove_record(model: str, values: Mapping[str, Any], index: int,
                  field_id: str = 'voices') -> Dict[str, Any]:
    """Form values without row ``index`` of a records field (normalised like :func:`add_record`)."""
    data = voicing_with_record_removed(voicing_from_values(model, values), index, field_id)
    return values_from_voicing(model, data)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def collected_field_errors(data: Mapping[str, Any]) -> Dict[str, str]:
    """Map each bad field id in a parsed voicing dict to a short message.

    This detects only **parse** errors: values that the forgiving parsers
    left as a raw ``str`` where a number, note name or list was expected. It
    runs on the output of :func:`voicing_from_values` (so a valid note name
    like ``'C4'`` has already become the int ``60`` and is *not* flagged).
    Semantic and cross-field problems are left to :func:`voicing_error`.

    Field ids:

    * ``'tuning'``, ``'max_fret'``, ``'fingers'``, ``'max_span'``,
      ``'relaxed_span'``: fretboard strings / physical parameters.
    * ``'weight:<key>'``: a flat weight that isn't a number.
    * ``'movement'``: the ensemble ``movement`` weight still a raw string.
    * ``'nested:<group>:<role>'``: a doubling/omit/inversion role that isn't
      a number (ensemble, and the piano's ``omit``).
    * ``'voice:<i>:low'`` / ``'voice:<i>:high'``: a voice range endpoint
      still a raw string (voice *names* are free text and never flagged).
    * ``'voice:<i>:staff'``: a ``staff`` that isn't ``'treble'``, ``'bass'``
      or absent/``None``.
    * ``'max_spacing'``: the ensemble spacing list still a raw string.
    * ``'range:<key>:low'`` / ``'range:<key>:high'``: a piano range endpoint
      still a raw string.
    * ``'rh_center'`` (a number) and ``'rh_low_interval_floor'``,
      ``'hand_span'``, ``'max_notes_per_hand'``, ``'max_total_notes'``,
      ``'hand_gap_floor'`` (whole numbers): piano physical parameters.

    Args:
        data: A parsed voicing dict (must carry a ``'model'`` key).

    Returns:
        A ``{field_id: message}`` dict; empty when every value parsed.
    """
    errors: Dict[str, str] = {}
    model = data.get('model')

    if model == 'fretboard':
        if isinstance(data.get('tuning'), str):
            errors['tuning'] = _KIND_ERRORS[KIND_PITCH_LIST]
        for key in _FRETBOARD_INT_KEYS:
            if key in data and not _is_number(data[key]):
                errors[key] = _KIND_ERRORS[KIND_INT]
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if not _is_number(value):
                errors[f'weight:{key}'] = _KIND_ERRORS[KIND_FLOAT]

    elif model == 'ensemble':
        for i, voice in enumerate(data.get('voices') or []):
            vrange = voice.get('range', []) if isinstance(voice, dict) else []
            low = vrange[0] if len(vrange) > 0 else None
            high = vrange[1] if len(vrange) > 1 else None
            if isinstance(low, str):
                errors[f'voice:{i}:low'] = _KIND_ERRORS[KIND_PITCH]
            if isinstance(high, str):
                errors[f'voice:{i}:high'] = _KIND_ERRORS[KIND_PITCH]
            raw_staff = voice.get('staff') if isinstance(voice, dict) else None
            if raw_staff is not None and raw_staff not in ('treble', 'bass'):
                errors[f'voice:{i}:staff'] = _KIND_ERRORS[KIND_CHOICE]
        if isinstance(data.get('max_spacing'), str):
            errors['max_spacing'] = _KIND_ERRORS[KIND_INT_LIST]
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if key == 'movement':
                if isinstance(value, str):
                    errors['movement'] = _KIND_ERRORS[KIND_FLOAT_OR_LIST]
            elif key in _NESTED_WEIGHT_KEYS:
                for role, role_value in (value or {}).items():
                    if not _is_number(role_value):
                        errors[f'nested:{key}:{role}'] = _KIND_ERRORS[KIND_FLOAT]
            else:
                if not _is_number(value):
                    errors[f'weight:{key}'] = _KIND_ERRORS[KIND_FLOAT]

    elif model == 'piano':
        for range_key in _PIANO_RANGE_KEYS:
            rng = data.get(range_key)
            if isinstance(rng, (list, tuple)):
                low = rng[0] if len(rng) > 0 else None
                high = rng[1] if len(rng) > 1 else None
                if isinstance(low, str):
                    errors[f'range:{range_key}:low'] = _KIND_ERRORS[KIND_PITCH]
                if isinstance(high, str):
                    errors[f'range:{range_key}:high'] = _KIND_ERRORS[KIND_PITCH]
        for key in _PIANO_INT_KEYS:
            if key in data and not _is_number(data[key]):
                errors[key] = _KIND_ERRORS[KIND_INT]
        if 'rh_center' in data and not _is_number(data['rh_center']):
            errors['rh_center'] = _KIND_ERRORS[KIND_FLOAT]
        weights = data.get('weights') or {}
        for key, value in weights.items():
            if key == 'omit':
                for role, role_value in (value or {}).items():
                    if not _is_number(role_value):
                        errors[f'nested:omit:{role}'] = _KIND_ERRORS[KIND_FLOAT]
            else:
                if not _is_number(value):
                    errors[f'weight:{key}'] = _KIND_ERRORS[KIND_FLOAT]

    return errors


def field_errors(model: str, values: Mapping[str, Any]) -> Dict[str, str]:
    """The fields of a form whose value doesn't parse, ``{field_id: message}``."""
    return collected_field_errors(voicing_from_values(model, values))


def voicing_error(name: str, data: Mapping[str, Any]) -> Optional[str]:
    """Validate one voicing dict; return the spec's error message, or ``None`` if valid.

    A ``'fretboard'``/``'ensemble'``/``'piano'`` model is parsed through its
    spec's ``from_dict`` and any error message is returned verbatim. An
    unknown model returns a descriptive message.
    """
    model = data.get('model')
    try:
        if model == 'fretboard':
            FretboardSpec.from_dict(name, data)
        elif model == 'ensemble':
            EnsembleSpec.from_dict(name, data)
        elif model == 'piano':
            PianoSpec.from_dict(name, data)
        else:
            return f"Unknown voicing model: {model!r}"
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as text
        return str(exc)
    return None


def cross_field_errors(name: str, model: str, values: Mapping[str, Any],
                       label: Optional[str] = None) -> List[str]:
    """The form-level errors of a form (at most one today: the spec's message)."""
    message = voicing_error(name, voicing_from_values(model, values, label))
    return [message] if message else []


def validate_form(name: str, model: str, values: Mapping[str, Any],
                  label: Optional[str] = None) -> Dict[str, Any]:
    """Both error classes of a form at once: ``{'fields': {...}, 'form': [...]}``."""
    return {'fields': field_errors(model, values),
            'form': cross_field_errors(name, model, values, label)}


# ---------------------------------------------------------------------------
# "Load config" presets
# ---------------------------------------------------------------------------


def load_presets(custom_voicings: Optional[Mapping[str, Mapping[str, Any]]] = None
                 ) -> List[Dict[str, Any]]:
    """The entries of the "Load config" menu, in menu order.

    Every built-in fretboard, then every built-in ensemble, then a single
    piano entry, then the user's own voicings sorted by name. Each entry is
    ``{'label', 'group', 'data'}``: ``group`` is ``'fretboard'``,
    ``'ensemble'``, ``'piano'`` or ``'custom'`` (a view separates the
    groups), ``data`` a complete voicing dict including ``'model'``.
    """
    presets: List[Dict[str, Any]] = []
    for fretboard in BUILTIN_FRETBOARDS.values():
        presets.append({'label': fretboard.label, 'group': 'fretboard',
                        'data': {'model': 'fretboard', **fretboard.to_dict()}})
    for ensemble in BUILTIN_ENSEMBLES.values():
        presets.append({'label': ensemble.label, 'group': 'ensemble',
                        'data': {'model': 'ensemble', **ensemble.to_dict()}})
    presets.append({'label': 'Piano (default)', 'group': 'piano',
                    'data': {'model': 'piano', **DEFAULT_PIANO.to_dict()}})
    for name in sorted(custom_voicings or {}):
        presets.append({'label': name, 'group': 'custom',
                        'data': copy.deepcopy(dict(custom_voicings[name]))})
    return presets
