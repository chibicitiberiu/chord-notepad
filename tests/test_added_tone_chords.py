"""Added-tone chords: the identifier offers them, and songs can use them.

music21 names a set of notes from the one root that stacks in thirds, so
E G# B C only came out as Caugmaj7/E, though it's heard as E major with an
added b6. The identifier now also tries every note as the root and names
what's left over a triad, sixth or seventh chord as added tones (Eaddb6,
Cadd#11, Cmaddb9). The same spellings work in a song: detected in every
notation, resolved to the right notes and register, transposed and
converted to European notation and back.
"""

import pytest

from audio.chord_picker import ChordNotePicker
from chord.detector import ChordDetector
from chord.helper import ChordHelper
from chord.midi_converter import parse_note_to_semitone
from services.song_parser_service import SongParserService
from services.transpose_service import transpose_chord_token, transpose_text
from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel, normalize_note_name


@pytest.fixture(scope="module")
def vm():
    return ChordIdentifierViewModel(SongParserService())


@pytest.fixture(scope="module")
def helper():
    return ChordHelper()


@pytest.fixture(scope="module")
def parser():
    return SongParserService()


def typed(vm, text):
    vm.set_notes_from_string(text)
    return vm.candidates


def pitch_classes(helper, name):
    return {parse_note_to_semitone(n) for n in helper.compute_chord_notes(name).notes}


# --- The identifier ---------------------------------------------------------

def test_e_major_with_an_added_flat_six_comes_before_the_slash_chord(vm):
    # E is the bass: E's own reading, then the inversion that says so, then
    # the plain C chord, then the reading whose bass is its added tone.
    assert typed(vm, "E3 G#3 B3 C4") == [
        'Eaddb6', 'Caugmaj7/E', 'Caugmaj7', 'G#augadd#9/E', 'G#augadd#9']


def test_piano_keys_give_the_same_added_tone_reading(vm):
    vm.set_notes([("E", 3), ("G#", 3), ("B", 3), ("C", 4)])
    assert vm.candidates[0] == 'Eaddb6'


def test_a_sharp_eleven_over_a_major_triad(vm):
    assert typed(vm, "C4 E4 G4 F#4") == ['Cadd#11']


def test_a_flat_nine_over_a_minor_triad(vm):
    assert typed(vm, "C4 Eb4 G4 Db4") == ['Cmaddb9']


def test_two_added_tones(vm):
    assert typed(vm, "C4 E4 G4 D5 F#5")[0] == 'Cadd9add#11'


def test_an_added_tone_over_a_seventh_is_a_thirteenth(vm):
    assert 'Em7addb13' in typed(vm, "E3 G3 B3 D4 C5")


def test_a_major_sixth_stays_a_six_chord(vm):
    found = typed(vm, "C4 E4 G4 A4")
    assert found == ['C6', 'Am7/C', 'Am7']
    assert not any('add13' in name for name in found)


def test_a_reading_on_another_root_is_offered_as_a_slash_chord(vm):
    # Nothing is rooted on E: the slash form, which says E is the bass, first.
    assert typed(vm, "E4 G4 C5 F#5") == ['Cadd#11/E', 'Cadd#11']


def test_a_reading_with_an_added_tone_in_the_bass_comes_last(vm):
    # Bb7: D diminished with an added b6 is the same four notes, but its
    # bass would be the added tone.
    assert typed(vm, "Bb4 D5 F5 Ab5") == ['Bb7', 'Ddimaddb6/Bb', 'Ddimaddb6']


def test_plain_chords_are_unchanged(vm):
    assert typed(vm, "C4 E4 G4") == ['C']
    assert typed(vm, "E3 G3 C4") == ['C/E', 'C']
    # Other readings follow (Emaddb6/C), but the plain chord leads.
    assert typed(vm, "C4 E4 G4 B4")[0] == 'Cmaj7'
    assert typed(vm, "C4 E4 G4 D5")[0] == 'Cadd9'


def test_a_cluster_is_still_no_chord(vm):
    assert typed(vm, "C4 C#4 D4") == []


def test_a_common_inversion_beats_a_rare_root_position(vm):
    # Cmaj7 in first inversion is likelier than E minor with an added b6.
    assert typed(vm, "E3 G3 B3 C4") == ['Cmaj7/E', 'Cmaj7', 'Emaddb6']
    # A dim7 chord on the lowest note leads the four equal-length names.
    assert typed(vm, "C4 Eb4 Gb4 A4")[0] == 'Cdim7'


@pytest.mark.parametrize("notes", [
    "E G# B C", "C E G F#", "C Eb G Db", "C E G A", "C E G D F#",
    "E G B D C", "C F G D", "Eb G Bb Cb", "Bb Db F Cb",
])
def test_every_root_reading_has_exactly_the_notes(helper, notes):
    names = notes.split()
    wanted = {parse_note_to_semitone(n) for n in names}
    readings = helper.identify_by_root(names)
    assert readings
    for root, name in readings:
        assert name.startswith(root)
        assert pitch_classes(helper, name) == wanted, name


def test_flat_roots_get_added_tones(helper):
    assert ('Eb', 'Ebaddb6') in helper.identify_by_root(['Eb', 'G', 'Bb', 'Cb'])
    assert ('Bb', 'Bbmaddb9') in helper.identify_by_root(['Bb', 'Db', 'F', 'Cb'])


# --- Resolving the spellings to notes ---------------------------------------

@pytest.mark.parametrize("name,notes,intervals", [
    ('Eaddb6', ['E', 'G#', 'B', 'C'], [0, 4, 7, 8]),
    ('Eaddb13', ['E', 'G#', 'B', 'C'], [0, 4, 7, 20]),
    ('E(addb6)', ['E', 'G#', 'B', 'C'], [0, 4, 7, 8]),
    ('E(addb13)', ['E', 'G#', 'B', 'C'], [0, 4, 7, 20]),
    ('Cadd#11', ['C', 'E', 'G', 'F#'], [0, 4, 7, 18]),
    ('C(add#11)', ['C', 'E', 'G', 'F#'], [0, 4, 7, 18]),
    ('Cmaddb9', ['C', 'Eb', 'G', 'Db'], [0, 3, 7, 13]),
    ('Cm(addb9)', ['C', 'Eb', 'G', 'Db'], [0, 3, 7, 13]),
    ('Cadd#9', ['C', 'E', 'G', 'D#'], [0, 4, 7, 15]),
    ('Cadd9add#11', ['C', 'E', 'G', 'D', 'F#'], [0, 4, 7, 14, 18]),
    ('Em7addb13', ['E', 'G', 'B', 'D', 'C'], [0, 3, 7, 10, 20]),
])
def test_spellings_resolve_to_notes_in_their_register(helper, name, notes, intervals):
    chord_notes = helper.compute_chord_notes(name)
    assert chord_notes.notes == notes
    assert chord_notes.intervals == intervals


def test_flat_root_spellings_resolve(helper):
    chord_notes = helper.compute_chord_notes('Ebaddb6')
    assert chord_notes.root == 'Eb'
    assert {parse_note_to_semitone(n) for n in chord_notes.notes} == {3, 7, 10, 11}
    assert helper.compute_chord_notes('Bbmaddb9/D').bass_note == 'D'


def test_a_flat_straight_after_the_root_is_still_the_root(helper):
    chord_notes = helper.compute_chord_notes('Eb6')
    assert chord_notes.root == 'Eb' and chord_notes.notes == ['Eb', 'G', 'Bb', 'C']


def test_identifier_plays_the_flat_six_inside_the_octave(vm):
    assert vm.get_chord_midi_notes('Eaddb6') == [52, 56, 59, 60]       # E3 G#3 B3 C4
    assert vm.get_chord_midi_notes('Cmaddb9') == [48, 51, 55, 61]      # Db above the octave
    assert vm.get_chord_midi_notes('Cadd#11') == [48, 52, 55, 66]


def test_playback_voices_b6_inside_the_chord_and_b13_on_top(helper):
    def voiced(name):
        return ChordNotePicker().chord_to_midi(helper.compute_chord_notes(name))
    b6 = voiced('Eaddb6')
    b13 = voiced('Eaddb13')
    # The C sits under the third (G#) as a b6, and above it as a b13.
    assert max(m for m in b6 if m % 12 == 0) < max(m for m in b6 if m % 12 == 8)
    assert max(m for m in b13 if m % 12 == 0) > max(m for m in b13 if m % 12 == 8)


# --- Songs ------------------------------------------------------------------

def _chords(parser, text, notation):
    return [(c.chord, c.is_valid) for line in parser.detect_chords_in_text(text, notation)
            if line.is_chord_line() for c in line.chords]


def test_detected_in_american_songs(parser):
    text = "Eaddb6 E(addb13) Cadd#11 Cmaddb9 eaddb6 Faddb6 Ebaddb6 Bbmaddb9/D"
    found = _chords(parser, text, 'american')
    assert found == [(name, True) for name in text.split()]


def test_detected_in_european_songs(parser):
    text = "Miaddb6 miaddb6 Faaddb6 Doadd#11 domaddb9 Mi(addb13) Sibaddb6"
    found = _chords(parser, text, 'european')
    assert found == [(name, True) for name in text.split()]


def test_detected_as_roman_numerals(parser):
    found = _chords(parser, "{key: C}\nIaddb6 iiaddb9 V7addb13 IVadd#11", 'american')
    assert found == [('Iaddb6', True), ('iiaddb9', True), ('V7addb13', True), ('IVadd#11', True)]


def test_roman_added_tones_resolve(helper):
    assert helper.compute_chord_notes('Iaddb6', key='C', is_relative=True).notes == ['C', 'E', 'G', 'Ab']
    assert helper.compute_chord_notes('iiaddb9', key='C', is_relative=True).notes == ['D', 'F', 'A', 'Eb']


def test_patterns_take_the_accidental_after_add():
    for pattern, token in ((ChordDetector.CHORD_PATTERN_AMERICAN, 'Cmaddb9'),
                           (ChordDetector.CHORD_PATTERN_AMERICAN, 'C♯add♭6'),
                           (ChordDetector.CHORD_PATTERN_EUROPEAN, 'Readdb6'),
                           (ChordDetector.CHORD_PATTERN_ROMAN, 'Iadd#11')):
        assert pattern.fullmatch(token), token


def test_transpose_keeps_the_added_tone():
    assert transpose_chord_token('Eaddb6', 2, 'american') == 'F#addb6'
    assert transpose_chord_token('Cmaddb9', 3, 'american') == 'Ebmaddb9'
    assert transpose_chord_token('Bbaddb6/D', 2, 'american') == 'Caddb6/E'
    assert transpose_chord_token('Miaddb6', 1, 'european') == 'Faaddb6'
    assert transpose_text("Eaddb6 Cadd#11 E(addb13)", 2, 'american') == "F#addb6 Dadd#11 F#(addb13)"


def test_european_conversion_round_trips(parser):
    text = "Eaddb6 Cadd#11 Cmaddb9 Faddb6 E(addb13) Bbaddb6/D"
    european = parser.convert_to_european(text)
    assert european == "Miaddb6 Doadd#11 Domaddb9 Faaddb6 Mi(addb13) Sibaddb6/Re"
    assert parser.convert_to_american(european) == text


# --- Every music21 reading has the selected notes ---------------------------

_SHARP_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
_FLAT_NAMES = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')
_SWEEP = {
    'major': (0, 4, 7), 'minor': (0, 3, 7), 'dim': (0, 3, 6), 'aug': (0, 4, 8),
    'sus2': (0, 2, 7), 'sus4': (0, 5, 7), '6': (0, 4, 7, 9), 'm6': (0, 3, 7, 9),
    '7': (0, 4, 7, 10), 'maj7': (0, 4, 7, 11), 'm7': (0, 3, 7, 10),
    'm7b5': (0, 3, 6, 10), 'dim7': (0, 3, 6, 9), 'add9': (0, 2, 4, 7),
}


def _voiced(names, lowest):
    """``names`` typed from ``names[lowest]`` up, each note above the last."""
    typed_notes, octave, previous = [], 3, -1
    for name in names[lowest:] + names[:lowest]:
        pc = parse_note_to_semitone(name)
        if pc <= previous:
            octave += 1
        typed_notes.append(f"{name}{octave}")
        previous = pc
    return ' '.join(typed_notes)


def _root_classes(name):
    """A chord name with its root and bass as pitch classes, so sharp and
    flat spellings of the same reading compare equal."""
    body, _, bass = name.partition('/')
    root = body[:2] if body[1:2] in ('#', 'b') else body[:1]
    return (parse_note_to_semitone(root), body[len(root):],
            parse_note_to_semitone(bass) if bass else None)


@pytest.mark.parametrize("quality", sorted(_SWEEP))
def test_no_candidate_names_other_notes(vm, helper, quality):
    for spelling in (_SHARP_NAMES, _FLAT_NAMES):
        for root in range(12):
            names = [spelling[(root + i) % 12] for i in _SWEEP[quality]]
            wanted = {(root + i) % 12 for i in _SWEEP[quality]}
            for lowest in range(len(names)):
                text = _voiced(names, lowest)
                found = typed(vm, text)
                assert found, text
                assert vm._get_bass_note_from_selection() == normalize_note_name(names[lowest])
                for name in found:
                    assert pitch_classes(helper, name) == wanted, (text, name)


def test_e_ab_b_c_reads_the_same_in_both_spellings(vm):
    sharps = typed(vm, "E4 G#4 B4 C5")
    flats = typed(vm, "E4 Ab4 B4 C5")
    assert {_root_classes(n) for n in flats} == {_root_classes(n) for n in sharps}
    assert flats[:3] == ['Eaddb6', 'Caugmaj7/E', 'Caugmaj7']


def test_music21_root_is_corrected(helper):
    # music21 says A- (Ab) augmented major 7, which is Ab C E G.
    assert helper.identify_chord(['E', 'A-', 'B', 'C'], 'E') == {'Caugmaj7', 'Caugmaj7/E'}


def test_augmented_eleventh_is_a_ninth_sharp_eleven(vm):
    # Not D13, which has a B where this has a G#.
    assert typed(vm, "D4 F#4 A4 C5 E5 G#5") == ['D9#11']


def test_quartal_notes_are_named_on_the_root_they_fit(vm):
    found = typed(vm, "C4 F4 Bb4")
    assert 'Fsus4/C' in found and 'Csus' not in found


def test_a_sharp_or_flat_root_on_the_bass_isnt_ranked_down():
    """F#dim7 (on the bass) leads; the root's accidental doesn't make it longer than Adim7."""
    vm = ChordIdentifierViewModel(SongParserService())
    vm.set_notes_from_string("F#3 A3 C4 Eb4")
    assert vm.identify_chords_from_notes()[0] == "F#dim7"


def test_typed_notes_without_octaves_stack_from_the_first(vm):
    """E G# B C typed as is: E is the bass (Tibi's case on the phone)."""
    assert typed(vm, "E G# B C")[0] == 'Eaddb6'
    assert typed(vm, "C E G# B")[0] == 'Caugmaj7'
