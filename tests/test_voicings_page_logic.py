"""Headless unit tests for the pure inline-validation helper of the Voicings page.

Only the module-level pure function :func:`field_errors` (and the parsing
helpers it relies on) is exercised here -- no Tkinter widgets are constructed,
so these tests run without a display. The import is tk-safe: importing the
module only *defines* the widget class and the tooltip helpers, it never
instantiates a root window.

``field_errors`` runs on *collected* data (the output of a form's
``collect()``), where a valid note name has already become an int and only an
unparseable leftover stays a raw string. So the tests below feed ints for
valid pitches and raw strings for the deliberate parse failures.
"""

from ui.dialogs.voicings_page import field_errors


# ---------------------------------------------------------------------------
# Clean data yields no errors
# ---------------------------------------------------------------------------


def test_clean_fretboard_data_no_errors():
    data = {
        'model': 'fretboard',
        'tuning': [40, 45, 50, 55, 59, 64],
        'max_fret': 12,
        'fingers': 4,
        'max_span': 4,
        'relaxed_span': 5,
        'allow_barres': True,
        'weights': {
            'sounding_string_bonus': 1.2,
            'open_string_bonus': 0.5,
            'bass_note_bonus': 8.0,
            'barre_penalty': 1.0,
        },
    }
    assert field_errors(data) == {}


def test_minimal_fretboard_data_no_errors():
    # No physical params, no weights -- nothing to flag.
    assert field_errors({'model': 'fretboard', 'tuning': [40, 45, 50, 55, 59, 64]}) == {}


def test_clean_ensemble_data_no_errors():
    data = {
        'model': 'ensemble',
        'voices': [
            {'name': 'Soprano', 'range': [60, 79]},
            {'name': 'Alto', 'range': [53, 74]},
            {'name': 'Bass', 'range': [40, 60]},
        ],
        'max_spacing': [12, 19],
        'allow_unisons': True,
        'weights': {
            'movement': 0.4,
            'bass_movement': 0.15,
            'leap_penalty': 2.0,
            'doubling': {'root': 2.0, 'third': -2.0, 'fifth': 0.5},
            'omit': {'root': 4.0, 'third': 40.0},
            'inversion': {'root': 0.0, 'first': -1.5},
        },
    }
    assert field_errors(data) == {}


def test_movement_as_list_of_floats_no_errors():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [48, 60]}],
        'weights': {'movement': [0.4, 0.2]},
    }
    assert field_errors(data) == {}


def test_piano_data_no_errors():
    assert field_errors({'model': 'piano'}) == {}


def test_clean_full_piano_data_no_errors():
    data = {
        'model': 'piano',
        'lh_range': [24, 48],
        'rh_range': [48, 84],
        'bass_range': [36, 47],
        'rh_low_anchor': [48, 64],
        'rh_center': 63.0,
        'rh_low_interval_floor': 52,
        'hand_span': 14,
        'max_notes_per_hand': 5,
        'max_total_notes': 10,
        'hand_gap_floor': 2,
        'add_bass': True,
        'weights': {
            'rh_note_bonus': 0.6,
            'rh_center_penalty': -1.4,
            'movement_penalty': -0.35,
            'omit': {'root': -4.0, 'third': -40.0},
        },
    }
    assert field_errors(data) == {}


# ---------------------------------------------------------------------------
# Fretboard parse errors
# ---------------------------------------------------------------------------


def test_tuning_raw_string_flagged():
    errors = field_errors({'model': 'fretboard', 'tuning': 'H9'})
    assert 'tuning' in errors
    assert list(errors) == ['tuning']


def test_physical_param_non_int_flagged():
    errors = field_errors({
        'model': 'fretboard',
        'tuning': [40, 45, 50, 55, 59, 64],
        'max_fret': 'abc',
    })
    assert 'max_fret' in errors


def test_fretboard_weight_raw_string_flagged():
    data = {
        'model': 'fretboard',
        'tuning': [40, 45, 50, 55, 59, 64],
        'weights': {'barre_penalty': 'abc', 'span_penalty': 1.2},
    }
    errors = field_errors(data)
    assert errors == {'weight:barre_penalty': errors.get('weight:barre_penalty')}
    assert 'weight:barre_penalty' in errors


def test_bool_physical_param_flagged():
    # A bool is an int subclass but must not count as a whole number.
    errors = field_errors({
        'model': 'fretboard',
        'tuning': [40, 45, 50, 55, 59, 64],
        'fingers': True,
    })
    assert 'fingers' in errors


# ---------------------------------------------------------------------------
# Ensemble parse errors
# ---------------------------------------------------------------------------


def test_voice_low_raw_string_flagged():
    data = {
        'model': 'ensemble',
        'voices': [
            {'name': 'Lead', 'range': ['Q', 72]},
            {'name': 'Bass', 'range': [48, 60]},
        ],
    }
    errors = field_errors(data)
    assert 'voice:0:low' in errors
    assert 'voice:0:high' not in errors
    assert 'voice:1:low' not in errors


def test_voice_high_raw_string_flagged():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'Lead', 'range': [60, 'zz']}],
    }
    errors = field_errors(data)
    assert 'voice:0:high' in errors


def test_max_spacing_raw_string_flagged():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [48, 60]}],
        'max_spacing': 'x',
    }
    errors = field_errors(data)
    assert 'max_spacing' in errors


def test_movement_raw_string_flagged():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [48, 60]}],
        'weights': {'movement': 'a,b'},
    }
    errors = field_errors(data)
    assert 'movement' in errors


def test_nested_role_raw_string_flagged():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [48, 60]}],
        'weights': {'doubling': {'root': 2.0, 'third': 'bad'}},
    }
    errors = field_errors(data)
    assert 'nested:doubling:third' in errors
    assert 'nested:doubling:root' not in errors


def test_multiple_ensemble_errors_reported_together():
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': ['Q', 72]}, {'name': 'B', 'range': [48, 60]}],
        'max_spacing': 'x',
        'weights': {'leap_penalty': 'nope', 'omit': {'third': 'huge'}},
    }
    errors = field_errors(data)
    assert 'voice:0:low' in errors
    assert 'max_spacing' in errors
    assert 'weight:leap_penalty' in errors
    assert 'nested:omit:third' in errors


# ---------------------------------------------------------------------------
# Piano parse errors
# ---------------------------------------------------------------------------


def test_piano_range_endpoint_raw_string_flagged():
    data = {
        'model': 'piano',
        'lh_range': ['Q9', 48],
        'rh_range': [48, 84],
    }
    errors = field_errors(data)
    assert 'range:lh_range:low' in errors
    assert 'range:lh_range:high' not in errors
    assert 'range:rh_range:low' not in errors


def test_piano_scalar_non_number_flagged():
    errors = field_errors({'model': 'piano', 'hand_span': 'abc'})
    assert 'hand_span' in errors


def test_piano_rh_center_non_number_flagged():
    errors = field_errors({'model': 'piano', 'rh_center': 'abc'})
    assert errors == {'rh_center': errors.get('rh_center')}
    assert 'rh_center' in errors


def test_piano_weight_raw_string_flagged():
    data = {
        'model': 'piano',
        'weights': {'rh_note_bonus': 'nope', 'rh_center_penalty': -1.4},
    }
    errors = field_errors(data)
    assert errors == {'weight:rh_note_bonus': errors.get('weight:rh_note_bonus')}
    assert 'weight:rh_note_bonus' in errors


def test_piano_omit_role_raw_string_flagged():
    data = {
        'model': 'piano',
        'weights': {'omit': {'root': -4.0, 'third': 'bad'}},
    }
    errors = field_errors(data)
    assert 'nested:omit:third' in errors
    assert 'nested:omit:root' not in errors


def test_multiple_piano_errors_reported_together():
    data = {
        'model': 'piano',
        'lh_range': ['Q9', 48],
        'hand_span': 'abc',
        'weights': {'rh_note_bonus': 'nope', 'omit': {'third': 'huge'}},
    }
    errors = field_errors(data)
    assert 'range:lh_range:low' in errors
    assert 'hand_span' in errors
    assert 'weight:rh_note_bonus' in errors
    assert 'nested:omit:third' in errors


# ---------------------------------------------------------------------------
# Semantic / cross-field cases are NOT the job of field_errors
# ---------------------------------------------------------------------------


def test_relaxed_span_less_than_max_span_not_flagged():
    # Both parse fine; the relaxed < max rule is the spec's / banner's job.
    data = {
        'model': 'fretboard',
        'tuning': [40, 45, 50, 55, 59, 64],
        'max_span': 5,
        'relaxed_span': 3,
    }
    assert field_errors(data) == {}


def test_voice_low_ge_high_not_flagged():
    # low >= high is semantic; both endpoints parse to ints, so no parse error.
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [72, 60]}, {'name': 'B', 'range': [48, 60]}],
    }
    assert field_errors(data) == {}


def test_voice_name_never_flagged():
    # Names are free text; even an odd name yields no field error.
    data = {
        'model': 'ensemble',
        'voices': [{'name': '', 'range': [60, 72]}, {'name': '123', 'range': [48, 60]}],
    }
    assert field_errors(data) == {}


def test_wrong_max_spacing_length_not_flagged():
    # A parseable list of the wrong length is semantic -- left to the spec.
    data = {
        'model': 'ensemble',
        'voices': [{'name': 'A', 'range': [60, 72]}, {'name': 'B', 'range': [48, 60]}],
        'max_spacing': [12, 19, 7],
    }
    assert field_errors(data) == {}
