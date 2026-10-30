"""The voicings editor's help texts say what the engines do (todo #15).

Each check pins a fact the text used to get wrong; the engine code it
describes is named in the comment.
"""

from audio import ensemble_voicer
from settings_forms.voicing_texts import TOOLTIPS, nested_tooltip


def test_ensemble_octave_leap_is_more_than_an_octave_on_top_of_a_large_leap():
    # ensemble_voicer._score_transition: magnitude > 12, after the > 7 leap.
    text = TOOLTIPS['weight:octave_leap_penalty']
    assert "more than an octave" in text and "or more" not in text
    assert "large-leap" in text


def test_ensemble_upper_spacing_threshold_is_a_fifth():
    assert ensemble_voicer._UPPER_SPACING_THRESHOLD == 7
    text = TOOLTIPS['weight:upper_spacing_penalty']
    assert "fifth" in text and "octave" not in text


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
    assert "exactly three frets" in TOOLTIPS['weight:awkward_stretch_penalty']
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
