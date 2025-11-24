"""
Tests for chord picker classes - verifies correct MIDI notes are produced
Uses parametrization to test both Piano and Guitar pickers with the same tests
Includes property-based testing with Hypothesis for fuzzing
"""

import pytest
from hypothesis import given, strategies as st, settings, seed
from typing import List, Set
from models.chord_notes import ChordNotes
from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from chord.helper import ChordHelper

# Use consistent seed for reproducible tests
seed(12346)


# Helper functions
def midi_to_note_class(midi: int) -> str:
    """Convert MIDI number to note class (without octave)"""
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return note_names[midi % 12]


def normalize_note(note: str) -> str:
    """Normalize note names (convert flats to sharps for comparison)"""
    note_map = {
        'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'
    }
    return note_map.get(note, note)


def notes_to_note_classes(notes: List[str]) -> Set[str]:
    """Convert note list to set of normalized note classes"""
    return {normalize_note(note) for note in notes}


def midi_list_to_note_classes(midi_notes: List[int]) -> Set[str]:
    """Convert MIDI note list to set of note classes"""
    return {midi_to_note_class(midi) for midi in midi_notes}


# Parametrized fixture for both pickers
@pytest.fixture(params=[
    ('piano', ChordNotePicker),
    ('guitar', GuitarChordPicker)
], ids=['piano', 'guitar'])
def picker(request):
    """Create picker instances for both Piano and Guitar"""
    picker_name, picker_class = request.param
    return picker_class()


# Hypothesis strategies for property-based testing
note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B',
              'Db', 'Eb', 'Gb', 'Ab', 'Bb']  # Include flats


@st.composite
def chord_notes_strategy(draw):
    """Generate random valid ChordNotes objects for fuzzing"""
    # Pick 2-6 unique notes
    num_notes = draw(st.integers(min_value=2, max_value=6))
    notes = draw(st.lists(
        st.sampled_from(note_names),
        min_size=num_notes,
        max_size=num_notes,
        unique=True
    ))

    # Root is typically the first note
    root = notes[0]

    # Bass note is root or one of the chord notes
    bass_note = draw(st.sampled_from(notes))

    return ChordNotes(notes=notes, bass_note=bass_note, root=root)


@st.composite
def realistic_chord_strategy(draw):
    """Generate realistic ChordNotes by parsing valid chord symbols"""
    helper = ChordHelper()

    # Common chord roots
    roots = ['C', 'D', 'E', 'F', 'G', 'A', 'B',
             'C#', 'D#', 'F#', 'G#', 'A#',
             'Db', 'Eb', 'Gb', 'Ab', 'Bb']

    # Common chord qualities (musically valid)
    qualities = [
        '',       # Major triad
        'm',      # Minor triad
        '7',      # Dominant 7th
        'maj7',   # Major 7th
        'm7',     # Minor 7th
        'dim',    # Diminished
        'aug',    # Augmented
        'sus2',   # Suspended 2nd
        'sus4',   # Suspended 4th
        '5',      # Power chord
        '6',      # Major 6th
        'm6',     # Minor 6th
        '9',      # Dominant 9th
        'maj9',   # Major 9th
        'm9',     # Minor 9th
        'add9',   # Add 9
        'madd9',  # Minor add 9
        'm7b5',   # Half-diminished
        'dim7',   # Diminished 7th
    ]

    root = draw(st.sampled_from(roots))
    quality = draw(st.sampled_from(qualities))
    chord_symbol = root + quality

    # 20% chance of adding a slash chord (any bass note - inversions, chromatic, polychords, etc.)
    if draw(st.booleans()) and draw(st.integers(min_value=0, max_value=4)) == 0:
        # Bass can be ANY note (C/Bb, C/D, Am/G, F/G, etc.)
        slash_bass = draw(st.sampled_from(roots))
        chord_symbol += '/' + slash_bass

    # Parse the chord symbol
    chord_notes = helper.compute_chord_notes(chord_symbol)

    # If parsing failed (shouldn't happen with our curated list), return fallback
    if chord_notes is None:
        return ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')

    return chord_notes


# Basic functionality tests (parametrized for both pickers)
class TestChordPickerBasics:
    """Test suite for both chord pickers"""

    def test_simple_c_major(self, picker):
        """Test C major chord produces correct notes"""
        chord_notes = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')
        midi = picker.chord_to_midi(chord_notes)

        assert len(midi) > 0, "Should produce at least one note"
        note_classes = midi_list_to_note_classes(midi)
        assert 'C' in note_classes
        assert 'E' in note_classes
        assert 'G' in note_classes

    def test_a_minor(self, picker):
        """Test A minor chord produces correct notes"""
        chord_notes = ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A')
        midi = picker.chord_to_midi(chord_notes)

        note_classes = midi_list_to_note_classes(midi)
        assert 'A' in note_classes
        assert 'C' in note_classes
        assert 'E' in note_classes

    def test_seventh_chord(self, picker):
        """Test G7 chord produces all four notes"""
        chord_notes = ChordNotes(notes=['G', 'B', 'D', 'F'], bass_note='G', root='G')
        midi = picker.chord_to_midi(chord_notes)

        note_classes = midi_list_to_note_classes(midi)
        assert 'G' in note_classes
        assert 'B' in note_classes
        assert 'D' in note_classes
        assert 'F' in note_classes

    def test_slash_chord_bass(self, picker):
        """Test slash chord has correct bass note"""
        chord_notes = ChordNotes(notes=['C', 'E', 'G'], bass_note='G', root='C')
        midi = picker.chord_to_midi(chord_notes)

        # Bass note should be the lowest
        assert len(midi) > 0
        lowest_note = midi_to_note_class(midi[0])
        assert lowest_note == 'G', "Lowest note should be bass note"

    def test_empty_chord(self, picker):
        """Test empty chord returns empty list"""
        chord_notes = ChordNotes(notes=[], bass_note='C', root='C')
        midi = picker.chord_to_midi(chord_notes)
        assert midi == []

    def test_state_reset(self, picker):
        """Test reset clears state"""
        chord_notes = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')
        picker.chord_to_midi(chord_notes)

        # State should have previous chord info
        state = picker.state
        # Piano has previous_chord_midi, Guitar has previous_fingering
        has_state = (
            getattr(state, 'previous_chord_midi', None) is not None or
            getattr(state, 'previous_fingering', None) is not None or
            state.previous_chord_notes is not None
        )
        assert has_state, "State should have previous chord information"

        picker.reset()

        # State should be cleared
        state = picker.state
        assert getattr(state, 'previous_chord_midi', None) is None
        assert getattr(state, 'previous_fingering', None) is None
        assert state.previous_chord_notes is None


# Property-based fuzzing tests
class TestChordPickerFuzzing:
    """Property-based fuzzing tests using Hypothesis - tests full song sequences"""

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_piano_song_sequence_no_wrong_notes(self, chord_sequence):
        """FUZZ: Piano should never produce wrong notes throughout a full song (HARD requirement)"""
        picker = ChordNotePicker()

        for i, chord_notes in enumerate(chord_sequence):
            midi = picker.chord_to_midi(chord_notes)

            if len(midi) == 0:
                continue

            # HARD REQUIREMENT: No extra notes allowed
            # For slash chords, bass note is allowed even if not in chord
            expected = notes_to_note_classes(chord_notes.notes)
            expected_bass = normalize_note(chord_notes.bass_note)
            actual = midi_list_to_note_classes(midi)

            for note in actual:
                # Note is valid if it's in the chord OR it's the bass note
                is_in_chord = note in expected or normalize_note(note) in expected
                is_bass_note = normalize_note(note) == expected_bass or note == expected_bass

                assert is_in_chord or is_bass_note, \
                    f"FUZZ FAIL at chord {i}: Note {note} not in chord {expected} or bass {expected_bass}. " \
                    f"Chord: {chord_notes.notes}, Bass: {chord_notes.bass_note}, MIDI: {midi}"

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_guitar_song_sequence_no_wrong_notes(self, chord_sequence):
        """FUZZ: Guitar should never produce wrong notes throughout a full song (HARD requirement)"""
        picker = GuitarChordPicker()

        for i, chord_notes in enumerate(chord_sequence):
            midi = picker.chord_to_midi(chord_notes)

            if len(midi) == 0:
                continue

            # HARD REQUIREMENT: No extra notes allowed
            # For slash chords, bass note is allowed even if not in chord
            expected = notes_to_note_classes(chord_notes.notes)
            expected_bass = normalize_note(chord_notes.bass_note)
            actual = midi_list_to_note_classes(midi)

            for note in actual:
                # Note is valid if it's in the chord OR it's the bass note
                is_in_chord = note in expected or normalize_note(note) in expected
                is_bass_note = normalize_note(note) == expected_bass or note == expected_bass

                assert is_in_chord or is_bass_note, \
                    f"FUZZ FAIL at chord {i}: Note {note} not in chord {expected} or bass {expected_bass}. " \
                    f"Chord: {chord_notes.notes}, Bass: {chord_notes.bass_note}, MIDI: {midi}"

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_piano_bass_note_preference(self, chord_sequence):
        """FUZZ: Piano should prefer correct bass note (SOFT - 90% threshold for realistic chords)"""
        picker = ChordNotePicker()

        correct_bass_count = 0
        total_valid_chords = 0

        for chord_notes in chord_sequence:
            midi = picker.chord_to_midi(chord_notes)

            if len(midi) < 2:
                continue

            total_valid_chords += 1
            lowest_midi = min(midi)
            lowest_note = midi_to_note_class(lowest_midi)
            expected_bass = normalize_note(chord_notes.bass_note)

            if normalize_note(lowest_note) == expected_bass or lowest_note == expected_bass:
                correct_bass_count += 1

        if total_valid_chords > 0:
            success_rate = correct_bass_count / total_valid_chords
            assert success_rate >= 0.90, \
                f"FUZZ FAIL: Only {success_rate:.1%} of chords had correct bass note (need ≥90%)"

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_guitar_bass_note_preference(self, chord_sequence):
        """FUZZ: Guitar should prefer correct bass note (SOFT - 75% threshold for realistic chords)"""
        picker = GuitarChordPicker()

        correct_bass_count = 0
        total_valid_chords = 0

        for chord_notes in chord_sequence:
            midi = picker.chord_to_midi(chord_notes)

            if len(midi) < 2:
                continue

            total_valid_chords += 1
            lowest_midi = min(midi)
            lowest_note = midi_to_note_class(lowest_midi)
            expected_bass = normalize_note(chord_notes.bass_note)

            if normalize_note(lowest_note) == expected_bass or lowest_note == expected_bass:
                correct_bass_count += 1

        if total_valid_chords > 0:
            success_rate = correct_bass_count / total_valid_chords
            assert success_rate >= 0.75, \
                f"FUZZ FAIL: Only {success_rate:.1%} of chords had correct bass note (need ≥75%)"

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_piano_note_completeness(self, chord_sequence):
        """FUZZ: Piano should include all notes for small chords (SOFT - 95% threshold for realistic chords)"""
        picker = ChordNotePicker()

        complete_count = 0
        total_small_chords = 0

        for chord_notes in chord_sequence:
            # Only test small chords (≤3 notes)
            if len(chord_notes.notes) > 3:
                continue

            midi = picker.chord_to_midi(chord_notes)
            if len(midi) == 0:
                continue

            total_small_chords += 1
            expected = notes_to_note_classes(chord_notes.notes)
            actual = midi_list_to_note_classes(midi)

            # Check if all notes present
            all_present = all(
                note in actual or any(normalize_note(n) == note for n in actual)
                for note in expected
            )

            if all_present:
                complete_count += 1

        if total_small_chords > 0:
            success_rate = complete_count / total_small_chords
            assert success_rate >= 0.95, \
                f"FUZZ FAIL: Only {success_rate:.1%} of small chords had all notes (need ≥95%)"

    @given(st.lists(realistic_chord_strategy(), min_size=50, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_guitar_note_completeness(self, chord_sequence):
        """FUZZ: Guitar note completeness with nuanced requirements based on chord size"""
        picker = GuitarChordPicker()

        pass_count = 0
        total_chords = 0
        failures = []

        for i, chord_notes in enumerate(chord_sequence):
            midi = picker.chord_to_midi(chord_notes)
            if len(midi) == 0:
                continue

            # Count unique notes in the chord
            unique_notes = set(normalize_note(n) for n in chord_notes.notes)
            num_unique = len(unique_notes)

            total_chords += 1
            expected = notes_to_note_classes(chord_notes.notes)
            actual = midi_list_to_note_classes(midi)

            # How many notes are present?
            notes_present = sum(1 for note in expected if note in actual or normalize_note(note) in actual)
            notes_missing = len(expected) - notes_present

            # Determine if this chord passes based on size
            passes = False
            if num_unique <= 3:
                # Small chords (≤3 unique notes): must have all notes
                passes = (notes_missing == 0)
            elif num_unique <= 5:
                # Medium chords (4-5 unique notes): can have at most 1 missing
                passes = (notes_missing <= 1)
            else:
                # Large chords (≥6 unique notes): must have at least 4 notes
                passes = (notes_present >= 4)

            if passes:
                pass_count += 1
            else:
                # Track first few failures for debugging
                if len(failures) < 3:
                    state = picker.state
                    failures.append({
                        'index': i,
                        'chord': chord_notes.notes,
                        'bass': chord_notes.bass_note,
                        'unique_count': num_unique,
                        'expected': expected,
                        'got': actual,
                        'missing': notes_missing,
                        'midi': midi,
                        'state_prev_fingering': state.previous_fingering,
                    })

        if total_chords > 0:
            success_rate = pass_count / total_chords
            # Expect 90% of chords to meet their size-based requirements
            failure_msg = f"FUZZ FAIL: Only {success_rate:.1%} of chords met completeness requirements (need ≥90%)"
            if failures:
                failure_msg += f"\n\nFirst {len(failures)} incomplete chords:"
                for f in failures:
                    failure_msg += f"\n  [{f['index']}] {f['chord']} ({f['unique_count']} unique notes, bass={f['bass']})"
                    failure_msg += f"\n      Expected {f['expected']}, got {f['got']}, missing {f['missing']}"
                    failure_msg += f"\n      State: prev_fingering={f['state_prev_fingering']}"
            assert success_rate >= 0.90, failure_msg

    @given(chord_notes_strategy(), chord_notes_strategy())
    @settings(max_examples=500, deadline=None)
    def test_piano_voice_leading_reasonable(self, chord1, chord2):
        """FUZZ: Piano voice leading should not jump excessively"""
        picker = ChordNotePicker()

        midi1 = picker.chord_to_midi(chord1)
        midi2 = picker.chord_to_midi(chord2)

        if len(midi1) == 0 or len(midi2) == 0:
            return

        # Calculate average position
        avg_midi1 = sum(midi1) / len(midi1)
        avg_midi2 = sum(midi2) / len(midi2)

        # Voice leading shouldn't jump more than 2.5 octaves
        jump = abs(avg_midi2 - avg_midi1)
        assert jump < 30, \
            f"FUZZ FAIL: Voice leading jump too large ({jump} semitones). " \
            f"Chord1: {chord1.notes}, Chord2: {chord2.notes}"


# Picker-specific tests
class TestPianoPickerSpecific:
    """Tests specific to piano picker"""

    def test_voice_leading_consistency(self):
        """Test voice leading maintains consistency"""
        picker = ChordNotePicker()
        chord_notes = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')

        midi1 = picker.chord_to_midi(chord_notes)
        midi2 = picker.chord_to_midi(chord_notes)

        # Should produce same voicing for same chord
        assert set(midi1) == set(midi2), "Same chord should produce same notes"


class TestGuitarPickerSpecific:
    """Tests specific to guitar picker"""

    def test_guitar_range(self):
        """Test guitar produces notes in reasonable range"""
        picker = GuitarChordPicker()
        chord_notes = ChordNotes(notes=['E', 'G#', 'B'], bass_note='E', root='E')
        midi = picker.chord_to_midi(chord_notes)

        # Guitar range is typically E2 (40) to E5 (76), be generous
        assert all(36 <= note <= 84 for note in midi), "Notes should be in guitar range"

    def test_different_tuning(self):
        """Test guitar with drop D tuning"""
        picker = GuitarChordPicker(tuning='drop_d')
        chord_notes = ChordNotes(notes=['D', 'A', 'D'], bass_note='D', root='D')
        midi = picker.chord_to_midi(chord_notes)

        note_classes = midi_list_to_note_classes(midi)
        assert 'D' in note_classes
        assert 'A' in note_classes

    def test_cache_works(self):
        """Test that fingering cache improves performance"""
        picker = GuitarChordPicker()
        chord_notes = ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G')

        # First call generates fingerings
        midi1 = picker.chord_to_midi(chord_notes)
        cache_size_1 = len(picker._fingering_cache)

        # Second call should use cache
        midi2 = picker.chord_to_midi(chord_notes)
        cache_size_2 = len(picker._fingering_cache)

        # Cache should not grow on second call
        assert cache_size_1 == cache_size_2
        # Should produce same result
        assert set(midi1) == set(midi2)


# Edge cases tests (parametrized)
class TestEdgeCases:
    """Test edge cases and potential bugs"""

    def test_single_note_chord(self, picker):
        """Test chord with single note"""
        chord_notes = ChordNotes(notes=['C'], bass_note='C', root='C')
        midi = picker.chord_to_midi(chord_notes)

        assert len(midi) > 0
        note_classes = midi_list_to_note_classes(midi)
        assert 'C' in note_classes

    def test_many_notes_chord(self, picker):
        """Test chord with many notes (13th chord)"""
        chord_notes = ChordNotes(
            notes=['C', 'E', 'G', 'B', 'D', 'F', 'A'],
            bass_note='C',
            root='C'
        )
        midi = picker.chord_to_midi(chord_notes)

        if len(midi) == 0:
            # Guitar might not handle this
            return

        note_classes = midi_list_to_note_classes(midi)
        # At least the root should be there
        assert 'C' in note_classes

    def test_flats_and_sharps(self, picker):
        """Test that flats and sharps are handled correctly"""
        # Db = C#, should produce same note classes
        chord_notes1 = ChordNotes(notes=['Db', 'F', 'Ab'], bass_note='Db', root='Db')
        chord_notes2 = ChordNotes(notes=['C#', 'F', 'G#'], bass_note='C#', root='C#')

        picker.reset()
        midi1 = picker.chord_to_midi(chord_notes1)
        picker.reset()
        midi2 = picker.chord_to_midi(chord_notes2)

        if len(midi1) == 0 or len(midi2) == 0:
            return

        # Should produce equivalent note classes
        notes1 = midi_list_to_note_classes(midi1)
        notes2 = midi_list_to_note_classes(midi2)

        normalized1 = {normalize_note(n) for n in notes1}
        normalized2 = {normalize_note(n) for n in notes2}

        assert normalized1 == normalized2, \
            f"Enharmonic chords should produce same notes: {normalized1} vs {normalized2}"

    def test_multiple_chords_sequence(self, picker):
        """Test playing a sequence of common chords"""
        chords = [
            ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'),
            ChordNotes(notes=['F', 'A', 'C'], bass_note='F', root='F'),
            ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G'),
            ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'),
        ]

        for chord_notes in chords:
            midi = picker.chord_to_midi(chord_notes)
            assert len(midi) > 0

            # Verify correct notes
            expected = notes_to_note_classes(chord_notes.notes)
            actual = midi_list_to_note_classes(midi)

            for note in expected:
                assert note in actual or normalize_note(note) in actual
