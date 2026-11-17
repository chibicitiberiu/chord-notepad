"""Headless tests for the voicings editor's form schemas and value conversion.

Covers :mod:`settings_forms.voicing_form`: the schemas are plain JSON, every
field round-trips spec -> values -> spec for every built-in voicing, the
schema, the values and the error ids agree, and the messages keep the
desktop's wording.
"""

import copy
import dataclasses
import json

import pytest

from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES, EnsembleSpec
from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec
from chordnotepad.models.piano_spec import BUILTIN_PIANOS, PianoSpec
from chordnotepad.settings_forms import voicing_form as vf

_SPEC_CLASSES = {'fretboard': FretboardSpec, 'ensemble': EnsembleSpec, 'piano': PianoSpec}

BUILTINS = (
    [('fretboard', spec) for spec in BUILTIN_FRETBOARDS.values()]
    + [('ensemble', spec) for spec in BUILTIN_ENSEMBLES.values()]
    + [('piano', spec) for spec in BUILTIN_PIANOS.values()]
)
BUILTIN_IDS = [f'{model}:{spec.name}' for model, spec in BUILTINS]


def _json_round_trip(obj):
    return json.loads(json.dumps(obj, allow_nan=False))


def _leaf_ids(model, values):
    """Every value key / error id the schema of ``model`` declares, for ``values``."""
    ids = set()
    for field in vf.iter_fields(vf.form_schema(model)):
        if field['kind'] == vf.KIND_RECORDS:
            for i, _ in enumerate(values[field['id']]):
                for column in field['columns']:
                    ids.add(field['error_path'].format(index=i, column=column['id']))
        else:
            ids.add(field['id'])
    return ids


# ---------------------------------------------------------------------------
# JSON purity
# ---------------------------------------------------------------------------


def test_editor_schema_is_plain_json():
    schema = vf.editor_schema()
    assert _json_round_trip(schema) == schema
    assert [m['value'] for m in schema['models']] == ['fretboard', 'ensemble', 'piano']
    assert set(schema['forms']) == set(vf.MODELS)


@pytest.mark.parametrize('model,spec', BUILTINS, ids=BUILTIN_IDS)
def test_values_and_errors_are_plain_json(model, spec):
    data = {'model': model, **spec.to_dict()}
    values = vf.values_from_voicing(model, data)
    assert _json_round_trip(values) == values
    assert _json_round_trip(vf.voicing_from_values(model, values)) == \
        vf.voicing_from_values(model, values)
    broken = {key: ('zzz' if isinstance(value, str) else value) for key, value in values.items()}
    result = vf.validate_form('x', model, broken)
    assert _json_round_trip(result) == result


def test_load_presets_are_plain_json():
    presets = vf.load_presets({'mine': {'model': 'piano'}})
    assert _json_round_trip(presets) == presets


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('model,spec', BUILTINS, ids=BUILTIN_IDS)
def test_builtin_round_trips_spec_values_spec(model, spec):
    data = {'model': model, **spec.to_dict()}
    values = vf.values_from_voicing(model, data)
    back = vf.voicing_from_values(model, values, label=spec.label)
    assert back['model'] == model
    rebuilt = _SPEC_CLASSES[model].from_dict(spec.name, back)
    if model == 'ensemble':
        # The form saves the movement weight as one value per voice.
        assert rebuilt.movement_per_voice() == spec.movement_per_voice()
        rebuilt = dataclasses.replace(rebuilt, weights=dict(spec.weights))
    assert rebuilt == spec
    assert vf.field_errors(model, values) == {}
    assert vf.cross_field_errors(spec.name, model, values, spec.label) == []


@pytest.mark.parametrize('model,spec', BUILTINS, ids=BUILTIN_IDS)
def test_values_round_trip_is_stable(model, spec):
    values = vf.values_from_voicing(model, {'model': model, **spec.to_dict()})
    again = vf.values_from_voicing(model, vf.voicing_from_values(model, values))
    assert again == values


@pytest.mark.parametrize('model', vf.MODELS)
def test_schema_values_and_ids_agree(model):
    values = vf.default_values(model)
    schema_ids = {field['id'] for field in vf.iter_fields(vf.form_schema(model))}
    assert set(values) == schema_ids


@pytest.mark.parametrize('model', vf.MODELS)
def test_schema_defaults_are_the_default_values(model):
    values = vf.default_values(model)
    for field in vf.iter_fields(vf.form_schema(model)):
        assert field['default'] == values[field['id']], field['id']


@pytest.mark.parametrize('model', vf.MODELS)
def test_default_voicing_is_valid(model):
    values = vf.default_values(model)
    assert vf.validate_form('New voicing', model, values) == {'fields': {}, 'form': []}


@pytest.mark.parametrize('model', vf.MODELS)
def test_missing_values_fall_back_to_defaults(model):
    assert vf.voicing_from_values(model, {}) == \
        vf.voicing_from_values(model, vf.default_values(model))


def test_unknown_model_gets_the_piano_form():
    assert vf.form_schema('weird')['model'] == 'piano'
    assert vf.voicing_from_values('weird', {})['model'] == 'piano'


def test_bare_piano_shows_engine_defaults():
    values = vf.values_from_voicing('piano', {'model': 'piano'})
    assert values['range:lh_range:low'] == 'C1'
    assert values['rh_center'] == '63.0'
    assert values['nested:omit:third'] == '-40.0'


def test_broken_piano_keeps_raw_values_visible():
    values = vf.values_from_voicing('piano', {
        'model': 'piano', 'lh_range': ['Q9', 48], 'hand_span': 'abc',
        'weights': {'omit': {'third': 'bad'}},
    })
    assert values['range:lh_range:low'] == 'Q9'
    assert values['range:lh_range:high'] == 'C3'
    assert values['hand_span'] == 'abc'
    assert values['nested:omit:third'] == 'bad'
    assert values['nested:omit:root'] == '-4.0'


def test_label_is_carried_over():
    values = vf.default_values('fretboard')
    assert vf.voicing_from_values('fretboard', values, label='Mine')['label'] == 'Mine'
    assert 'label' not in vf.voicing_from_values('fretboard', values)


# ---------------------------------------------------------------------------
# Field errors through values (same ids and wording as the desktop)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('model', vf.MODELS)
def test_every_parseable_field_reports_with_a_schema_id(model):
    values = vf.default_values(model)
    broken = {}
    for key, value in values.items():
        if key == 'voices':
            broken[key] = [{**row, 'low': 'zz', 'high': 'zz', 'staff': 'alto', 'gap': 'zz', 'movement': 'zz'}
                           for row in value]
        elif isinstance(value, str):
            broken[key] = 'zz'
        else:
            broken[key] = value
    errors = vf.field_errors(model, broken)
    # The bottom voice's gap is never saved, so never wrong.
    last_gap = f"voice:{len(broken.get('voices', [])) - 1}:gap"
    expected = {
        fid for fid in _leaf_ids(model, broken)
        if not fid.endswith(':name') and fid != last_gap
        and fid not in ('allow_barres', 'allow_unisons', 'add_bass')
    }
    assert set(errors) == expected


def test_error_wording_per_kind():
    fret = {**vf.default_values('fretboard'), 'tuning': 'H9', 'max_fret': 'x',
            'weight:barre_penalty': 'q'}
    assert vf.field_errors('fretboard', fret) == {
        'tuning': 'Not a valid note name',
        'max_fret': 'Must be a whole number',
        'weight:barre_penalty': 'Must be a number',
    }
    ens = vf.default_values('ensemble')
    ens['voices'][0] = {**ens['voices'][0], 'low': 'Q', 'staff': 'alto', 'gap': 'x',
                        'movement': 'a'}
    ens.update({'nested:doubling:third': 'bad'})
    assert vf.field_errors('ensemble', ens) == {
        'voice:0:low': 'Not a valid note name',
        'voice:0:staff': "Must be 'treble', 'bass', or omitted",
        'voice:0:gap': 'Must be a whole number',
        'voice:0:movement': 'Must be a number',
        'nested:doubling:third': 'Must be a number',
    }
    piano = {**vf.default_values('piano'), 'range:rh_range:high': 'Q9', 'rh_center': 'x',
             'hand_span': '1.5'}
    assert vf.field_errors('piano', piano) == {
        'range:rh_range:high': 'Not a valid note name',
        'rh_center': 'Must be a number',
        'hand_span': 'Must be a whole number',
    }


def test_cross_field_error_wording():
    values = {**vf.default_values('fretboard'), 'max_span': '5', 'relaxed_span': '3'}
    assert vf.cross_field_errors('Mine', 'fretboard', values) == [
        "Relaxed span (3) must be >= Max span (5)."]
    values = vf.default_values('ensemble')
    values['voices'][0] = {**values['voices'][0], 'low': 'C5', 'high': 'C4'}
    assert vf.cross_field_errors('Duo', 'ensemble', values) == [
        "Voice 'Voice 1' range must have low < high, got 72 >= 60."]


def test_cross_field_errors_name_fields_by_their_labels():
    # Not "Fretboard 'Piano': 'max_fret' must be ...": the form is the voicing's.
    values = {**vf.default_values('fretboard'), 'max_span': '5', 'relaxed_span': '3'}
    checked = vf.validate_form('Piano', 'fretboard', values)
    assert checked['fields'] == {}
    assert len(checked['form']) == 1 and checked['form'][0].startswith('Relaxed span')
    assert "'" not in checked['form'][0]
    # A number past its range is the field's error, not the form's.
    values = {**vf.default_values('fretboard'), 'max_fret': '999'}
    assert vf.validate_form('Piano', 'fretboard', values) == {
        'fields': {'max_fret': 'Must be from 5 to 24'}, 'form': []}
    assert vf.cross_field_errors('Piano', 'fretboard', values) == [
        'Max fret must be from 5 to 24.']


def test_form_errors_wait_for_the_fields():
    values = vf.default_values('ensemble')
    values['voices'][1] = {**values['voices'][1], 'low': 'Q'}
    checked = vf.validate_form('Duo', 'ensemble', values)
    assert checked == {'fields': {'voice:1:low': 'Not a valid note name'}, 'form': []}
    # The spec's own message is still there for a view that asks.
    assert vf.cross_field_errors('Duo', 'ensemble', values)


def test_voicing_error_unknown_model():
    assert vf.voicing_error('w', {'model': 'weird'}) == "Unknown voicing model: 'weird'"


# ---------------------------------------------------------------------------
# Hints, choices, records
# ---------------------------------------------------------------------------


def _voices_field():
    return next(f for f in vf.iter_fields(vf.form_schema('ensemble')) if f['id'] == 'voices')


def _gaps(values):
    return [row['gap'] for row in values['voices']]


def _names(values):
    return [row['name'] for row in values['voices']]


def _four(spacing=(12, 12, 19)):
    data = {'model': 'ensemble', 'max_spacing': list(spacing), 'voices': [
        {'name': name, 'range': [low, low + 12]}
        for name, low in (('S', 72), ('A', 64), ('T', 52), ('B', 40))]}
    return vf.values_from_voicing('ensemble', data)


def test_spacing_is_a_gap_per_voice_not_a_field():
    ids = {f['id'] for f in vf.iter_fields(vf.form_schema('ensemble'))}
    assert 'max_spacing' not in ids
    gap = next(c for c in _voices_field()['columns'] if c['id'] == 'gap')
    assert gap['kind'] == vf.KIND_INT and gap['label'] == 'Max gap to next voice'
    assert (gap['min'], gap['max'], gap['step']) == (1, 127, 1)
    assert gap['disabled_in_last_row'] is True
    assert not any(c.get('disabled_in_last_row') for c in _voices_field()['columns']
                   if c['id'] != 'gap')
    field = _voices_field()
    assert (field['move_up_help'], field['move_down_help']) == ('Move up', 'Move down')


def test_gaps_map_to_max_spacing_and_back():
    values = _four((10, 11, 19))
    assert _gaps(values) == ['10', '11', '19', '']
    assert vf.voicing_from_values('ensemble', values)['max_spacing'] == [10, 11, 19]
    # The bottom voice's gap is never saved.
    values['voices'][3]['gap'] = '7'
    assert vf.voicing_from_values('ensemble', values)['max_spacing'] == [10, 11, 19]
    assert vf.field_errors('ensemble', values) == {}


def test_missing_max_spacing_shows_the_spec_defaults():
    data = {'model': 'ensemble', 'voices': [
        {'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [52, 64]},
        {'name': 'C', 'range': [40, 52]}]}
    values = vf.values_from_voicing('ensemble', data)
    assert _gaps(values) == ['12', '19', '']
    saved = EnsembleSpec.from_dict('x', vf.voicing_from_values('ensemble', values))
    original = EnsembleSpec.from_dict('x', data)
    assert saved.movement_per_voice() == original.movement_per_voice()
    assert dataclasses.replace(saved, weights=original.weights) == original


def test_a_raw_spacing_list_shows_entry_by_entry():
    data = {'model': 'ensemble', 'max_spacing': '12, y', 'voices': [
        {'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [52, 64]},
        {'name': 'C', 'range': [40, 52]}]}
    values = vf.values_from_voicing('ensemble', data)
    assert _gaps(values) == ['12', 'y', '']
    assert vf.field_errors('ensemble', values) == {'voice:1:gap': 'Must be a whole number'}


def test_a_gap_must_be_a_whole_number_in_range():
    values = _four()
    for text, message in (('', 'Must be a whole number'), ('x', 'Must be a whole number'),
                          ('1.5', 'Must be a whole number'), ('0', 'Must be from 1 to 127'),
                          ('128', 'Must be from 1 to 127')):
        values['voices'][1]['gap'] = text
        assert vf.field_errors('ensemble', values) == {'voice:1:gap': message}, text
    values['voices'][1]['gap'] = '127'
    assert vf.validate_form('x', 'ensemble', values) == {'fields': {}, 'form': []}


def test_a_row_without_a_gap_cell_gets_the_default():
    values = _four()
    for row in values['voices']:
        del row['gap']
    assert vf.voicing_from_values('ensemble', values)['max_spacing'] == [12, 12, 12]


def test_add_gives_the_old_bottom_voice_an_octave():
    values = _four((10, 11, 19))
    added = vf.add_record('ensemble', values)
    assert _gaps(added) == ['10', '11', '19', '12', '']
    assert vf.voicing_from_values('ensemble', added)['max_spacing'] == [10, 11, 19, 12]


def test_new_voice_moved_to_the_top_keeps_the_gaps_with_their_voices():
    values = vf.add_record('ensemble', _four((10, 11, 19)))
    for _ in range(4):
        values = vf.move_record('ensemble', values, 4 - _, -1)
    assert _names(values) == ['Voice 5', 'S', 'A', 'T', 'B']
    # The new voice gets an octave to S; S..B keep theirs; B's moved-up gap stays.
    assert _gaps(values) == ['12', '10', '11', '19', '12']
    assert vf.voicing_from_values('ensemble', values)['max_spacing'] == [12, 10, 11, 19]


def test_moving_the_bottom_voice_up_and_back_restores_its_gap():
    values = _four((10, 11, 19))
    values['voices'][3]['gap'] = ''
    up = vf.move_record('ensemble', values, 3, -1)
    assert _names(up) == ['S', 'A', 'B', 'T']
    # B gains a voice below and had no gap: an octave. T is now last; its 19 is kept.
    assert _gaps(up) == ['10', '11', '12', '19']
    assert vf.voicing_from_values('ensemble', up)['max_spacing'] == [10, 11, 12]
    back = vf.move_record('ensemble', up, 2, 1)
    assert _names(back) == ['S', 'A', 'T', 'B']
    assert _gaps(back) == ['10', '11', '19', '12']
    assert vf.voicing_from_values('ensemble', back)['max_spacing'] == [10, 11, 19]


def test_move_out_of_range_is_a_no_op():
    values = _four()
    assert vf.move_record('ensemble', values, 0, -1) == values
    assert vf.move_record('ensemble', values, 3, 1) == values
    assert vf.move_record('ensemble', values, 9, -1) == values


def test_remove_takes_the_voice_gap_with_it():
    values = _four((10, 11, 19))
    removed = vf.remove_record('ensemble', values, 1)
    assert _names(removed) == ['S', 'T', 'B']
    assert _gaps(removed) == ['10', '19', '']
    # Removing the bottom voice: the new bottom one keeps its gap in the form only.
    removed = vf.remove_record('ensemble', values, 3)
    assert _gaps(removed) == ['10', '11', '19']
    assert vf.voicing_from_values('ensemble', removed)['max_spacing'] == [10, 11]


def test_staff_choice_labels_and_values():
    voices = next(f for f in vf.iter_fields(vf.form_schema('ensemble')) if f['id'] == 'voices')
    staff = next(c for c in voices['columns'] if c['id'] == 'staff')
    assert [vf.choice_label(staff, v) for v in (None, 'treble', 'bass', 'alto')] == \
        ['Auto', 'Treble', 'Bass', 'alto']
    assert [vf.choice_value(staff, v) for v in ('Auto', 'Treble', 'Bass', 'alto')] == \
        [None, 'treble', 'bass', 'alto']


def test_upper_clef_choice_labels_and_values():
    field = next(f for f in vf.iter_fields(vf.form_schema('ensemble'))
                 if f['id'] == 'upper_clef')
    assert field['kind'] == vf.KIND_CHOICE
    assert field['label'] == 'Upper staff'
    assert field['default'] == 'treble'
    assert [(c['value'], c['label']) for c in field['choices']] == [
        ('treble', 'Treble'), ('treble_8vb', 'Treble, octave lower (tenors)')]
    assert field['help']


def test_upper_clef_round_trips_through_the_form():
    ttbb = {'model': 'ensemble', **BUILTIN_ENSEMBLES['ttbb'].to_dict()}
    values = vf.values_from_voicing('ensemble', ttbb)
    assert values['upper_clef'] == 'treble_8vb'
    assert vf.voicing_from_values('ensemble', values)['upper_clef'] == 'treble_8vb'
    # Back to treble: the key is dropped, as for any voicing saved before it.
    plain = vf.voicing_from_values('ensemble', {**values, 'upper_clef': 'treble'})
    assert 'upper_clef' not in plain
    assert vf.values_from_voicing('ensemble', plain)['upper_clef'] == 'treble'
    assert EnsembleSpec.from_dict('t', plain).upper_clef == 'treble'


def test_bad_upper_clef_is_a_field_error():
    values = {**vf.default_values('ensemble'), 'upper_clef': 'alto'}
    assert vf.field_errors('ensemble', values) == {'upper_clef': 'Not one of the choices'}
    assert vf.cross_field_errors('Duo', 'ensemble', values) == [
        "Invalid Upper staff 'alto'; must be 'treble' or 'treble_8vb'."]


def test_load_presets_carry_the_male_choir_clef():
    presets = {p['label']: p['data'] for p in vf.load_presets()}
    assert presets['Male Choir (TTBB)']['upper_clef'] == 'treble_8vb'
    assert 'upper_clef' not in presets['Choir (SATB)']


def test_add_and_remove_record_normalise_like_the_desktop():
    values = vf.default_values('ensemble')
    values['voices'][0] = {**values['voices'][0], 'low': 'Db4'}
    added = vf.add_record('ensemble', values)
    assert [v['name'] for v in added['voices']] == ['Voice 1', 'Voice 2', 'Voice 3']
    assert added['voices'][2] == {'name': 'Voice 3', 'low': 'C3', 'high': 'C4', 'staff': None,
                                  'gap': '', 'movement': '-0.15'}
    assert added['voices'][0]['low'] == 'C#4'
    removed = vf.remove_record('ensemble', added, 0)
    assert [v['name'] for v in removed['voices']] == ['Voice 2', 'Voice 3']
    assert vf.remove_record('ensemble', removed, 9)['voices'] == removed['voices']


def test_record_helpers_on_voicing_data_copy():
    data = {'model': 'ensemble', 'voices': [{'name': 'A', 'range': [60, 72]}]}
    added = vf.voicing_with_record_added(data)
    assert added['voices'][-1] == {'name': 'Voice 2', 'range': ['C3', 'C4']}
    assert len(data['voices']) == 1
    assert vf.voicing_with_record_removed(added, 0)['voices'] == [added['voices'][1]]
    # An explicit spacing list follows the voices.
    data = {**added, 'max_spacing': [19]}
    assert vf.voicing_with_record_added(data)['max_spacing'] == [19, 12]
    assert vf.voicing_with_record_removed(data, 1)['max_spacing'] == []


# ---------------------------------------------------------------------------
# Texts and presets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('model', vf.MODELS)
def test_every_input_has_label_and_help(model):
    for field in vf.iter_fields(vf.form_schema(model)):
        assert field['label'], field['id']
        if field['kind'] == vf.KIND_RECORDS:
            for column in field['columns']:
                assert column['label'] and column['help'], column['id']
        else:
            assert field['help'], field['id']


#: The physical fields whose spec checks an upper limit too (the others only a
#: lower one, or none: the piano's RH center).
_SPEC_UPPER_LIMITS = {'max_fret', 'fingers'}


@pytest.mark.parametrize('model', ['fretboard', 'piano'])
def test_physical_ranges_agree_with_the_specs(model):
    """Every physical number field has a schema range (its tooltip shows it),
    the spec accepts both ends, and where the spec has a limit the range
    stops at it: one step past is refused."""
    section = next(s for s in vf.form_schema(model)['sections'] if s['id'] == 'physical')
    for field in section['fields']:
        assert field.get('min') is not None and field.get('max') is not None, field['id']

        def error(value):
            values = vf.default_values(model)
            values[field['id']] = str(value)
            # Relaxed span must not be under Max span: keep that rule out of it.
            if field['id'] == 'relaxed_span':
                values['max_span'] = '1'
            if field['id'] == 'max_span':
                values['relaxed_span'] = str(max(value, 1))
            return vf.voicing_error('t', vf.voicing_from_values(model, values))

        assert error(field['min']) is None, field['id']
        assert error(field['max']) is None, field['id']
        if field['kind'] == vf.KIND_INT:
            assert error(field['min'] - 1) is not None, field['id']
        if field['id'] in _SPEC_UPPER_LIMITS:
            assert error(field['max'] + 1) is not None, field['id']


def test_piano_weights_use_their_own_help_for_shared_keys():
    fields = {f['id']: f for f in vf.iter_fields(vf.form_schema('piano'))}
    assert fields['weight:movement_penalty']['help'].startswith(
        "How the picker treats a note's nearest-neighbour movement")
    ens = {f['id']: f for f in vf.iter_fields(vf.form_schema('ensemble'))}
    assert fields['weight:common_tone_bonus']['help'] != ens['weight:common_tone_bonus']['help']


def test_load_presets_order_and_groups():
    presets = vf.load_presets({'b': {'model': 'piano'}, 'a': {'model': 'fretboard'}})
    groups = [p['group'] for p in presets]
    n_fret, n_ens = len(BUILTIN_FRETBOARDS), len(BUILTIN_ENSEMBLES)
    assert groups == ['fretboard'] * n_fret + ['ensemble'] * n_ens + ['piano', 'custom', 'custom']
    assert [p['label'] for p in presets[-2:]] == ['a', 'b']
    assert presets[n_fret + n_ens]['label'] == 'Piano (default)'
    for preset in presets[:-2]:
        assert vf.voicing_error(preset['label'], preset['data']) is None


def test_load_presets_copy_custom_voicings():
    custom = {'a': {'model': 'piano', 'weights': {'omit': {'third': -3.0}}}}
    preset = vf.load_presets(custom)[-1]
    preset['data']['weights']['omit']['third'] = 0
    assert custom['a']['weights']['omit']['third'] == -3.0


def test_unparsed_tuning_error_names_the_bad_token():
    """A raw tuning string is judged per token, not per character."""
    from chordnotepad.settings_forms.voicing_form import voicing_error
    msg = voicing_error('t', {'model': 'fretboard', 'tuning': 'E2 A2 X9 G3'})
    assert msg is not None
    assert "'X9'" in msg and "string 2" in msg


def test_unparsed_tuning_error_counts_tokens_not_characters():
    from chordnotepad.settings_forms.voicing_form import voicing_error
    msg = voicing_error('t', {'model': 'fretboard', 'tuning': 'E2 A2'})
    assert msg is not None and 'got 2' in msg


# -- a number outside the schema's range is a field error ---------------------------------


def _number_fields():
    for model in ('fretboard', 'piano'):
        for field in vf.iter_fields(vf.form_schema(model)):
            if field['kind'] in (vf.KIND_INT, vf.KIND_FLOAT) and not field['id'].startswith(
                    ('weight:', 'nested:')):
                yield model, field


def test_a_number_outside_its_range_is_a_field_error_both_ends_are_in():
    seen = 0
    for model, field in _number_fields():
        seen += 1
        low, high = field['min'], field['max']

        def errors(value):
            values = vf.default_values(model)
            values[field['id']] = str(value)
            return vf.field_errors(model, values)

        text = f"Must be from {low:g} to {high:g}"
        assert errors(low).get(field['id']) is None, field['id']
        assert errors(high).get(field['id']) is None, field['id']
        assert errors(high + 1) == {field['id']: text}, field['id']
        assert errors(low - 1) == {field['id']: text}, field['id']
    assert seen == 10


def test_the_range_message_writes_numbers_like_the_tooltip():
    values = vf.default_values('fretboard')
    values['max_span'] = '20'
    assert vf.field_errors('fretboard', values) == {'max_span': 'Must be from 1 to 8'}
    piano = vf.default_values('piano')
    piano['rh_center'] = '200'
    assert vf.field_errors('piano', piano) == {'rh_center': 'Must be from 0 to 127'}
    piano['rh_center'] = '127.5'
    assert vf.field_errors('piano', piano) == {'rh_center': 'Must be from 0 to 127'}


def test_an_out_of_range_number_makes_the_voicing_invalid():
    for model, field in _number_fields():
        data = vf.default_voicing(model)
        data[field['id']] = field['max'] + 1
        message = vf.voicing_error('T', data)
        assert message and field['id'] in message, field['id']
        assert vf.spec_sentence(message, model).endswith(
            f"must be from {field['min']:g} to {field['max']:g}."), field['id']
    assert vf.voicing_error('T', vf.default_voicing('piano')) is None


def test_weights_have_no_range():
    values = vf.default_values('fretboard')
    values['weight:open_string_bonus'] = '5000'
    assert vf.field_errors('fretboard', values) == {}


def test_every_built_in_and_default_is_inside_its_ranges():
    data = [vf.voicing_from_values(m, vf.default_values(m)) for m in ('fretboard', 'ensemble', 'piano')]
    data += [vf.default_voicing(m) for m in ('fretboard', 'ensemble', 'piano')]
    data += [preset['data'] for preset in vf.load_presets()]
    assert len(data) > 5
    for item in data:
        assert vf.range_errors(item) == {}, item
        assert vf.voicing_error('T', item) is None, item


# ---------------------------------------------------------------------------
# The movement column
# ---------------------------------------------------------------------------


def _quartet():
    return next(p['data'] for p in vf.load_presets() if p['label'] == 'String Quartet')


def _cells(values):
    return [row['movement'] for row in values['voices']]


def test_movement_is_a_column_of_the_voices_table_and_no_separate_field():
    ids = {f['id'] for f in vf.iter_fields(vf.form_schema('ensemble'))}
    assert 'movement' not in ids and 'weight:bass_movement' not in ids
    column = next(c for c in _voices_field()['columns'] if c['id'] == 'movement')
    assert column['label'] == 'Movement cost'
    assert 'calmer' in column['help']


def test_scalar_movement_loads_as_cells_with_the_bass_value_last():
    data = {'model': 'ensemble', 'weights': {'movement': -0.4, 'bass_movement': -0.1},
            'voices': [{'name': n, 'range': r} for n, r in
                       (('A', [60, 72]), ('B', [52, 64]), ('C', [40, 52]))]}
    values = vf.values_from_voicing('ensemble', data)
    assert _cells(values) == ['-0.4', '-0.4', '-0.1']
    assert vf.voicing_from_values('ensemble', values)['weights']['movement'] == [-0.4, -0.4, -0.1]
    assert 'bass_movement' not in vf.voicing_from_values('ensemble', values)['weights']


def test_list_movement_loads_verbatim_and_a_wrong_length_adapted():
    values = vf.values_from_voicing('ensemble', _quartet())
    assert _cells(values) == ['-0.8', '-0.4', '-0.4', '-0.15']
    tibi = copy.deepcopy(_quartet())
    tibi['voices'] += [{'name': 'Solo', 'range': ['B1', 'D4']},
                       {'name': 'Double Bass', 'range': ['E1', 'G2']}]
    tibi['max_spacing'] += [12, 12]
    values = vf.values_from_voicing('ensemble', tibi)
    assert _cells(values) == ['-0.8', '-0.4', '-0.4', '-0.4', '-0.4', '-0.15']
    assert vf.field_errors('ensemble', values) == {}


def test_movement_cells_travel_with_their_voice():
    values = vf.values_from_voicing('ensemble', _quartet())
    names = [r['name'] for r in values['voices']]
    moved = vf.move_record('ensemble', values, 0, 2)
    assert [r['name'] for r in moved['voices']] == [names[1], names[2], names[0], names[3]]
    assert _cells(moved) == ['-0.4', '-0.4', '-0.8', '-0.15']
    removed = vf.remove_record('ensemble', values, 1)
    assert _cells(removed) == ['-0.8', '-0.4', '-0.15']


def test_a_voice_added_at_the_bottom_takes_the_bottom_value_and_the_old_bottom_an_inner_one():
    values = vf.values_from_voicing('ensemble', _quartet())
    added = vf.add_record('ensemble', values)
    assert _cells(added) == ['-0.8', '-0.4', '-0.4', '-0.4', '-0.15']
    # With no inner voice the old bottom keeps its own.
    two = vf.default_values('ensemble')
    assert _cells(vf.add_record('ensemble', two)) == ['-0.4', '-0.15', '-0.15']
    assert vf.voicing_with_record_added(_quartet())['weights']['movement'] == \
        [-0.8, -0.4, -0.4, -0.4, -0.15]
    assert vf.voicing_with_record_removed(_quartet(), 0)['weights']['movement'] == \
        [-0.4, -0.4, -0.15]


def test_duplicating_a_voice_copies_the_row_below_it_with_a_new_name():
    values = vf.values_from_voicing('ensemble', _quartet())
    values['voices'][1]['gap'] = '14'
    copied = vf.duplicate_record('ensemble', values, 1)
    names = [r['name'] for r in copied['voices']]
    assert names == [values['voices'][0]['name'], 'Violin II', 'Violin II 2',
                     values['voices'][2]['name'], values['voices'][3]['name']]
    assert {k: v for k, v in copied['voices'][2].items() if k != 'name'} == \
        {k: v for k, v in copied['voices'][1].items() if k != 'name'}
    assert copied['voices'][2]['gap'] == '14'
    assert _cells(copied) == ['-0.8', '-0.4', '-0.4', '-0.4', '-0.15']
    # Again: the next free number; the original is unchanged by it.
    again = vf.duplicate_record('ensemble', copied, 1)
    assert [r['name'] for r in again['voices']][:4] == [
        values['voices'][0]['name'], 'Violin II', 'Violin II 3', 'Violin II 2']
    # The bottom voice: the original gains a voice below and so a gap.
    bottom = vf.duplicate_record('ensemble', values, 3)
    assert bottom['voices'][3]['gap'] != '' and _cells(bottom)[-2:] == ['-0.15', '-0.15']
    assert vf.duplicate_record('ensemble', values, 9)['voices'] == values['voices']
