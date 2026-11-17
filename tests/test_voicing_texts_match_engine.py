"""The voicings editor's help texts say what the engines do (todo #15).

Each check pins a fact the text used to get wrong; the engine code it
describes is named in the comment.
"""

from chordnotepad.settings_forms.voicing_texts import TOOLTIPS, nested_tooltip


def test_ensemble_octave_leap_is_more_than_an_octave_on_top_of_a_large_leap():
    # ensemble_voicer._score_transition: magnitude > 12, after the > 7 leap.
    text = TOOLTIPS['weight:octave_leap_penalty']
    assert "more than an octave" in text and "or more" not in text
    assert "large-leap" in text


def test_ensemble_upper_spacing_threshold_is_a_fifth():
    # ensemble_voicer: gaps above the bass beyond upper_spacing_threshold
    # cost upper_spacing_penalty per semitone; a fifth by default.
    from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES, DEFAULT_WEIGHTS
    assert DEFAULT_WEIGHTS['upper_spacing_threshold'] == 7
    assert BUILTIN_ENSEMBLES['quartet'].weight('upper_spacing_threshold') == 12
    assert "Upper spacing allowed" in TOOLTIPS['weight:upper_spacing_penalty']
    text = TOOLTIPS['weight:upper_spacing_threshold']
    assert "7 (a fifth)" in text and "12 (an octave)" in text and "semitones" in text


def test_ensemble_outer_leap_is_per_semitone_beyond_a_fifth_for_the_outer_voices():
    # ensemble_voicer._score_transition: b == 0 or n - 1, magnitude > 7.
    text = TOOLTIPS['weight:outer_leap_penalty']
    assert "top or bottom voice" in text and "fifth" in text and "per semitone" in text


def test_ensemble_middle_range_is_the_middle_half():
    # ensemble_voicer.__init__: a quarter of the range in from each end.
    from chordnotepad.audio.ensemble_voicer import _BAND_QUARTER
    assert _BAND_QUARTER == 4
    text = TOOLTIPS['weight:middle_range_penalty']
    assert "middle half" in text and "a quarter of the range" in text


def test_ensemble_hidden_perfects_spare_a_stepwise_top_voice():
    # ensemble_voicer._score_transition: abs(top delta) > _STEP (2).
    from chordnotepad.audio.ensemble_voicer import _STEP
    assert _STEP == 2
    assert "whole tone" in TOOLTIPS['weight:hidden_perfect_penalty']
    assert "by step is never charged" in TOOLTIPS['weight:hidden_perfect_penalty']


def test_ensemble_parallels_spare_a_doubled_bass_line_from_five_voices():
    # ensemble_voicer._score_transition: n >= _DOUBLED_BASS_MIN_VOICES.
    from chordnotepad.audio.ensemble_voicer import _DOUBLED_BASS_MIN_VOICES
    assert _DOUBLED_BASS_MIN_VOICES == 5
    assert "five voices or more" in TOOLTIPS['weight:parallel_perfect_penalty']


def test_every_ensemble_weight_has_a_label_and_help():
    from chordnotepad.models.ensemble_spec import DEFAULT_WEIGHTS, _NESTED_WEIGHT_KEYS
    from chordnotepad.settings_forms.voicing_texts import ENSEMBLE_WEIGHT_LABELS
    flat = {k for k in DEFAULT_WEIGHTS if k not in _NESTED_WEIGHT_KEYS}
    assert set(ENSEMBLE_WEIGHT_LABELS) == flat
    for key in flat:
        assert TOOLTIPS[f'weight:{key}']


def test_ensemble_common_tone_is_the_same_pitch():
    # delta == 0: the same note, not just the same pitch class.
    text = TOOLTIPS['weight:common_tone_bonus']
    assert "pitch class" not in text and "same note" in text


def test_ensemble_key_dependent_weights_say_they_need_a_key():
    for key in ('leading_tone_resolution_bonus', 'double_leading_tone_penalty'):
        assert "key" in TOOLTIPS[f'weight:{key}']


def test_inversion_tooltips_name_the_inversion_not_a_tone():
    assert "third in the bass" in nested_tooltip('inversion', 'first')
    assert "fifth in the bass" in nested_tooltip('inversion', 'second')
    assert "7th in the bass" in nested_tooltip('inversion', 'third')
    assert "root in the bass" in nested_tooltip('inversion', 'root')


def test_piano_omission_isnt_about_voices():
    text = nested_tooltip('omit', 'fifth', model='piano')
    assert "voices" not in text and "hands" in text
    assert "voices" in nested_tooltip('omit', 'fifth')


def test_fretboard_texts():
    # guitar_chord_picker._score_fingering
    assert "subtracted" in TOOLTIPS['weight:bass_note_bonus']
    assert "pitch" in TOOLTIPS['weight:bass_note_bonus']
    assert "subtracted" in TOOLTIPS['weight:slash_bass_bonus']
    assert "fretted string" in TOOLTIPS['weight:fretted_finger_penalty']
    assert "more strings than" in TOOLTIPS['weight:barre_penalty']
    # _score_quality charges it from a three-fret span; _enumerate_candidates
    # drops such shapes from four frets.
    assert "three frets or more" in TOOLTIPS['weight:awkward_stretch_penalty']
    assert "four frets or more" in TOOLTIPS['weight:awkward_stretch_penalty']
    assert "Max span" in TOOLTIPS['relaxed_span']
    assert "lowest string first" not in TOOLTIPS['tuning']


def test_piano_texts():
    # chord_picker: hand span and notes per hand bind the right hand only;
    # the hand gap is measured from the left hand's top note.
    assert "right hand" in TOOLTIPS['hand_span']
    assert "right hand" in TOOLTIPS['max_notes_per_hand']
    assert "left hand's top note" in TOOLTIPS['hand_gap_floor']
    assert "left hand's top note" in TOOLTIPS['weight:muddy_gap_penalty']
    assert "4 semitones" in TOOLTIPS['rh_low_interval_floor']
    assert "4 semitones" in TOOLTIPS['weight:rh_low_interval_penalty']
    assert "fallback" in TOOLTIPS['rh_range_low']
    assert "slash" in TOOLTIPS['add_bass']


def test_ensemble_same_bass_text_names_the_case():
    # ensemble_voicer._score_transition: same chord, other written bass, same
    # lowest pitch class.
    from chordnotepad.settings_forms.voicing_texts import ENSEMBLE_WEIGHT_LABELS
    assert ENSEMBLE_WEIGHT_LABELS['same_bass_penalty'] == 'Same chord, same bass'
    text = TOOLTIPS['weight:same_bass_penalty']
    assert "C/E" in text and "lowest note" in text


def test_every_fretboard_weight_has_a_label_and_help():
    from chordnotepad.models.fretboard_spec import DEFAULT_WEIGHTS
    from chordnotepad.settings_forms.voicing_texts import FRETBOARD_WEIGHT_LABELS
    assert set(FRETBOARD_WEIGHT_LABELS) == set(DEFAULT_WEIGHTS)
    for key in DEFAULT_WEIGHTS:
        assert TOOLTIPS[f'weight:{key}']


def test_acoustic_tuning_texts():
    # guitar_chord_picker: _full_strum_strings is all strings but two, at
    # least three; the register term only for a bass on the upper half of
    # the strings; low mud below G2 / C3; the thumb only for a cramped grip.
    assert "4 of 6" in TOOLTIPS['weight:thin_shape_penalty']
    assert "two-note" in TOOLTIPS['weight:thin_shape_penalty']
    assert "upper half" in TOOLTIPS['weight:bass_register_penalty']
    assert "G2" in TOOLTIPS['weight:low_interval_penalty']
    assert "C3" in TOOLTIPS['weight:low_interval_penalty']
    assert "four-note" in TOOLTIPS['weight:omitted_fifth_penalty']
    assert "fretted bass" in TOOLTIPS['weight:damped_mute_penalty']
    assert "thumb" in TOOLTIPS['weight:awkward_stretch_penalty']
