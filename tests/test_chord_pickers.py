"""
Tests for chord picker classes - verifies correct MIDI notes are produced
Uses parametrization to test both Piano and Guitar pickers with the same tests
Includes property-based testing with Hypothesis for fuzzing
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import List, Set
from models.chord_notes import ChordNotes
from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from chord.helper import ChordHelper
from services.song_renderer import SongRenderer
from services.song_parser_service import SongParserService

# Reproducible-seed behavior is provided by the "default" Hypothesis profile in
# tests/conftest.py (derandomize=True). Per-test @seed decorators are not needed.


# Helper functions
_SHARP_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def midi_to_note_class(midi: int) -> str:
    """Convert MIDI number to note class (without octave)"""
    return _SHARP_NOTE_NAMES[midi % 12]


def normalize_note(note: str) -> str:
    """Normalize any note name to its canonical sharp-only form.

    Handles all enharmonic spellings including E#/B# (-> F/C), Cb/Fb (-> B/E),
    and double accidentals (C## -> D, Cbb -> A#). Unparseable input is returned
    unchanged so error messages stay readable.
    """
    from chord.midi_converter import parse_note_to_semitone
    semitone = parse_note_to_semitone(note)
    if semitone is None:
        return note
    return _SHARP_NOTE_NAMES[semitone]


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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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
    @settings(max_examples=100)
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


class TestExtensionRegister:
    """Extensions (9th/11th/13th) must keep their upper register instead of
    collapsing into a 2nd/4th/6th that clashes with the root.

    The picker voices from the chord's intervals (register-preserving), so an
    11th lands at +17 and a 13th at +21 above the root. The whole block is then
    kept in a central register - extensions belong an octave up, but not
    stranded so high the quality gets thin.
    """

    @staticmethod
    def _chord_tone_intervals(picker, chord_notes):
        """Intervals of the chord voicing above its lowest chord tone.

        The picker prepends a bass note; drop it so we measure the chord
        voicing itself.
        """
        midi = picker.chord_to_midi(chord_notes)
        assert len(midi) > 1
        voicing = sorted(midi)[1:]  # strip the low bass
        return [m - voicing[0] for m in voicing]

    def test_dominant_11th_keeps_high_11th_first_chord(self):
        """C11 as the very first chord: 9th and 11th stay an octave up."""
        picker = ChordNotePicker()
        chord = ChordNotes(notes=['C', 'G', 'Bb', 'D', 'F'], bass_note='C', root='C')
        intervals = self._chord_tone_intervals(picker, chord)
        # D (9th) at +14, F (11th) at +17 - not +2 / +5
        assert intervals == [0, 7, 10, 14, 17]

    def test_major_11th_keeps_high_11th_first_chord(self):
        """Cmaj11 first chord: 11th stays a real 11th, not a 4th on the root."""
        picker = ChordNotePicker()
        chord = ChordNotes(notes=['C', 'G', 'B', 'D', 'F'], bass_note='C', root='C')
        intervals = self._chord_tone_intervals(picker, chord)
        assert intervals == [0, 7, 11, 14, 17]

    def test_major_13th_keeps_high_13th_first_chord(self):
        """Cmaj13 first chord: 9th at +14 and 13th at +21."""
        picker = ChordNotePicker()
        chord = ChordNotes(notes=['C', 'E', 'G', 'B', 'D', 'A'], bass_note='C', root='C')
        intervals = self._chord_tone_intervals(picker, chord)
        assert intervals == [0, 4, 7, 11, 14, 21]

    def test_register_consistent_first_vs_midprogression(self):
        """The 11th sits high whether C11 is first or follows another chord."""
        c11 = ChordNotes(notes=['C', 'G', 'Bb', 'D', 'F'], bass_note='C', root='C')

        first = ChordNotePicker()
        first_intervals = self._chord_tone_intervals(first, c11)

        after = ChordNotePicker()
        after.chord_to_midi(ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'))
        after_intervals = self._chord_tone_intervals(after, c11)

        # Both spread the 9th/11th up an octave (span > one octave).
        assert first_intervals[-1] >= 12
        assert after_intervals[-1] >= 12

    def test_extended_chord_stays_central(self):
        """A spread extended chord stays central - top at/below C5 initially."""
        picker = ChordNotePicker()
        chord = ChordNotes(
            notes=['C', 'E', 'G', 'B', 'D', 'A'],
            bass_note='C', root='C',
            intervals=[0, 4, 7, 11, 14, 21],
        )
        midi = picker.chord_to_midi(chord)
        assert max(midi) <= 72  # top note at/below C5 (prefer the closer register)

    def test_picker_uses_provided_intervals(self):
        """Explicit intervals drive register, not the pitch-class order.

        Same pitch classes, two different interval spellings: a close voicing
        vs. one with the 9th up an octave. The picker must honor each.
        """
        close = ChordNotes(
            notes=['C', 'D', 'E', 'G'], bass_note='C', root='C',
            intervals=[0, 2, 4, 7],           # D as a 2nd
        )
        spread = ChordNotes(
            notes=['C', 'D', 'E', 'G'], bass_note='C', root='C',
            intervals=[0, 4, 7, 14],          # D as a 9th, an octave up
        )
        close_tones = self._chord_tone_intervals(ChordNotePicker(), close)
        spread_tones = self._chord_tone_intervals(ChordNotePicker(), spread)

        assert close_tones == [0, 2, 4, 7]
        assert spread_tones == [0, 4, 7, 14]
        assert close_tones != spread_tones

    def test_no_duplicate_midi_notes(self):
        """A wide chord whose root lands on the bass must not double a key."""
        picker = ChordNotePicker()
        # G13 rooted low enough that the chord root can collide with the bass.
        chord = ChordNotes(
            notes=['G', 'B', 'D', 'F', 'A', 'E'],
            bass_note='G', root='G',
            intervals=[0, 4, 7, 10, 14, 21],
        )
        midi = picker.chord_to_midi(chord)
        assert len(midi) == len(set(midi)), f"duplicate MIDI notes: {midi}"

    def test_triad_first_chord_unchanged(self):
        """The register fix must not alter plain triad voicings."""
        picker = ChordNotePicker()
        chord = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')
        midi = picker.chord_to_midi(chord)
        # C2 bass + C4 E4 G4 - the long-standing initial voicing.
        assert midi == [36, 60, 64, 67]


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

    # --- Optimization-based voicing regressions ---
    # These lock in the open-position voicings the picker should settle on now
    # that shapes are chosen by scoring rather than by matching templates.

    def test_am_first_chord_is_open_shape(self):
        """Am as the first chord voices the open x02210 shape."""
        picker = GuitarChordPicker()
        picker.chord_to_midi(ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A'))
        assert picker.state.previous_fingering == [-1, 0, 2, 2, 1, 0]

    def test_am_after_g_stays_open_shape(self):
        """Am after G still voices x02210 (regression: used to become 5322xx)."""
        picker = GuitarChordPicker()
        picker.chord_to_midi(ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G'))
        picker.chord_to_midi(ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A'))
        fingering = picker.state.previous_fingering
        assert fingering == [-1, 0, 2, 2, 1, 0]
        assert fingering != [5, 3, 2, 2, -1, -1]

    def test_e_major_open_shape(self):
        """E major voices the open 022100 shape."""
        picker = GuitarChordPicker()
        picker.chord_to_midi(ChordNotes(notes=['E', 'G#', 'B'], bass_note='E', root='E'))
        assert picker.state.previous_fingering == [0, 2, 2, 1, 0, 0]

    def test_c_g_am_f_progression_full_open_voicings(self):
        """C-G-Am-F yields full open-position voicings with correct basses."""
        picker = GuitarChordPicker()
        prog = [
            ('C', ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')),
            ('G', ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G')),
            ('Am', ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A')),
            ('F', ChordNotes(notes=['F', 'A', 'C'], bass_note='F', root='F')),
        ]
        fingerings = {}
        for name, chord in prog:
            picker.chord_to_midi(chord)
            fingerings[name] = picker.state.previous_fingering

        assert fingerings['C'] == [-1, 3, 2, 0, 1, 0]   # x32010
        assert fingerings['G'] == [3, 2, 0, 0, 0, 3]    # 320003
        assert fingerings['Am'] == [-1, 0, 2, 2, 1, 0]  # x02210

        # F need not be a textbook shape, but must be a full voicing with F in bass.
        f = fingerings['F']
        sounding = [s for s in range(6) if f[s] >= 0]
        assert len(sounding) >= 4, f"F should sound >=4 strings, got {f}"
        lowest = min(sounding, key=lambda s: picker.tuning_midi[s] + f[s])
        lowest_pc = (picker.tuning_midi[lowest] + f[lowest]) % 12
        assert lowest_pc == 5, f"F should have F in the bass, got {f}"  # F == pitch class 5

    def test_playability_full_barre(self):
        """A full barre chord (six strings, one flat finger at the low fret) is playable."""
        picker = GuitarChordPicker()
        assert picker._is_playable([1, 3, 3, 2, 1, 1]) is True

    def test_playability_open_string_under_barre(self):
        """An open string trapped inside the barre range is unplayable."""
        picker = GuitarChordPicker()
        # Five fretted strings; the barre at fret 1 spans strings 0-5, but the
        # open A string (index 1) sits inside that range and cannot ring.
        assert picker._is_playable([1, 0, 3, 3, 1, 1]) is False

    def test_playability_partial_barre(self):
        """A partial barre across the higher strings is playable."""
        picker = GuitarChordPicker()
        assert picker._is_playable([-1, 2, 4, 4, 3, 2]) is True

    def test_playability_min_fret_on_single_string(self):
        """More than four fretted strings whose lowest fret is on a single
        string needs five fingers and is unplayable."""
        picker = GuitarChordPicker()
        # fret 1 only on the low E; four more strings fretted above it => 5 fingers.
        assert picker._is_playable([1, -1, 3, 3, 3, 3]) is False

    # --- Relaxation ladder ---
    # A degenerate tuning (all six strings tuned to the same note) makes each
    # pitch class reachable at exactly one fret in 0..12, so we can force the
    # ladder down a specific rung by choosing a chord whose tones sit too far
    # apart for the normal pass.

    def test_ladder_step2_wide_stretch_rescue(self):
        """Span-5 rescue: a dyad reachable only at a 5-fret stretch.

        With every string tuned to C, pitch class D lives only at fret 2 and G
        only at fret 7 (their fret-14/19 copies exceed MAX_FRET). The dyad D-G
        therefore needs a 5-fret span - impossible at the normal span of 4, so
        ladder step 2 (wide stretch) must find it.
        """
        picker = GuitarChordPicker(tuning=[48] * 6)  # all strings = C
        chord = ChordNotes(notes=['D', 'G'], bass_note='D', root='D')
        midi = picker.chord_to_midi(chord)

        note_classes = midi_list_to_note_classes(midi)
        assert 'D' in note_classes, f"expected D in {note_classes} ({midi})"
        assert 'G' in note_classes, f"expected G in {note_classes} ({midi})"

    def test_ladder_step3_coverage_rescue(self):
        """Coverage rescue: a triad too spread for any full voicing.

        With every string tuned to C, C#/E/G# sit at frets 1/4/8 - a 7-fret
        span, impossible even at the relaxed span of 5. Ladder step 3 must
        drop the coverage floor and return a 2-of-3-tone voicing (e.g. frets
        1+4), strictly better than the old lone-root fallback.
        """
        picker = GuitarChordPicker(tuning=[48] * 6)  # all strings = C
        chord = ChordNotes(notes=['C#', 'E', 'G#'], bass_note='C#', root='C#')
        midi = picker.chord_to_midi(chord)

        chord_pcs = notes_to_note_classes(['C#', 'E', 'G#'])
        present = midi_list_to_note_classes(midi) & chord_pcs
        assert len(present) >= 2, \
            f"coverage-relaxed voicing should keep >=2 chord tones, got {present} ({midi})"

    def test_ladder_does_not_disturb_fast_path(self):
        """Standard tuning is untouched: the cheap normal pass still wins.

        Am must still voice the open x02210 shape, and a plain C major triad
        must still enumerate a complete (all-three-tone) voicing - proof the
        ladder only engages when the normal pass comes up empty.
        """
        picker = GuitarChordPicker()
        picker.chord_to_midi(ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A'))
        assert picker.state.previous_fingering == [-1, 0, 2, 2, 1, 0]

        # C major's normal pass yields at least one complete voicing (C, E, G).
        candidates = picker._enumerate_candidates(['C', 'E', 'G'], 'C')
        assert candidates, "C major should enumerate candidates on the fast path"

        def pcs_of(fingering):
            return {(picker.tuning_midi[s] + f) % 12
                    for s, f in enumerate(fingering) if f >= 0}

        assert any({0, 4, 7} <= pcs_of(f) for f in candidates), \
            "C major fast path should include a complete voicing (all three tones)"


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


# ---------------------------------------------------------------------------
# Whole-song voicing (voice_sequence): batch optimization with lookahead.
# ---------------------------------------------------------------------------

def _major(root: str) -> ChordNotes:
    return ChordHelper().compute_chord_notes(root)


def _slash(root: str, bass: str) -> ChordNotes:
    cn = ChordHelper().compute_chord_notes(root)
    return ChordNotes(notes=cn.notes, bass_note=bass, root=cn.root)


class TestVoiceSequenceDeterminism:
    """voice_sequence must be deterministic and independent of prior state."""

    PROGRESSION = [
        ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'),
        ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G'),
        ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A'),
        ChordNotes(notes=['F', 'A', 'C'], bass_note='F', root='F'),
        ChordNotes(notes=['D', 'F#', 'A'], bass_note='D', root='D'),
        ChordNotes(notes=['E', 'G#', 'B'], bass_note='E', root='E'),
        ChordNotes(notes=['B', 'D', 'F#'], bass_note='B', root='B'),
        ChordNotes(notes=['Bb', 'D', 'F'], bass_note='Bb', root='Bb'),
        ChordNotes(notes=['G', 'B', 'D', 'F'], bass_note='G', root='G'),
        ChordNotes(notes=['C', 'E', 'G'], bass_note='G', root='C'),  # slash
        ChordNotes(notes=['A', 'C', 'E', 'G'], bass_note='A', root='A'),
        ChordNotes(notes=['F', 'A', 'C'], bass_note='F', root='F'),
    ]

    @pytest.mark.parametrize('picker_class', [ChordNotePicker, GuitarChordPicker],
                             ids=['piano', 'guitar'])
    def test_repeatable(self, picker_class):
        """Same sequence -> identical voicings, twice in a row."""
        picker = picker_class()
        first = picker.voice_sequence(self.PROGRESSION)
        second = picker.voice_sequence(self.PROGRESSION)
        assert first == second

    @pytest.mark.parametrize('picker_class', [ChordNotePicker, GuitarChordPicker],
                             ids=['piano', 'guitar'])
    def test_unaffected_by_prior_state(self, picker_class):
        """Prior chord_to_midi calls must not change the batch result."""
        clean = picker_class().voice_sequence(self.PROGRESSION)

        dirty = picker_class()
        # Pollute the picker's transition state with unrelated chords first.
        for junk in [ChordNotes(notes=['C#', 'F', 'G#'], bass_note='C#', root='C#'),
                     ChordNotes(notes=['Eb', 'G', 'Bb'], bass_note='Bb', root='Eb')]:
            dirty.chord_to_midi(junk)
        polluted = dirty.voice_sequence(self.PROGRESSION)

        assert polluted == clean


class TestGuitarVoiceSequence:
    """Guitar-specific whole-song optimization behavior."""

    @staticmethod
    def _fingering_for_midi(picker, chord_notes, midi):
        """Recover the fingering a voice_sequence MIDI list came from."""
        cands = picker._build_candidate_ladder(chord_notes.notes, chord_notes.bass_note)
        if not cands:
            cands = [picker._get_fallback_fingering(chord_notes.notes[0])]
        for f in cands:
            if picker._fingering_to_midi(f) == midi:
                return f
        raise AssertionError(f"no candidate fingering matches {midi}")

    @classmethod
    def _total_path_score(cls, picker, sequence, fingerings):
        """Sum of intrinsic quality plus consecutive transition scores."""
        total = 0.0
        prev = None
        for cn, f in zip(sequence, fingerings):
            total += picker._score_quality(f, cn.notes, cn.bass_note)
            total += picker._score_transition(prev, f)
            prev = f
        return total

    def _greedy_fingerings(self, sequence):
        picker = GuitarChordPicker()
        picker.reset()
        out = []
        for cn in sequence:
            picker.chord_to_midi(cn)
            out.append(picker.state.previous_fingering)
        return out

    def _dp_fingerings(self, picker, sequence):
        midis = picker.voice_sequence(sequence)
        return [self._fingering_for_midi(picker, cn, m)
                for cn, m in zip(sequence, midis)]

    def test_canonical_open_voicings_every_occurrence(self):
        """C-G-Am-F x2 gives the canonical open voicings for BOTH passes."""
        C = ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C')
        G = ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G')
        Am = ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A')
        F = ChordNotes(notes=['F', 'A', 'C'], bass_note='F', root='F')
        sequence = [C, G, Am, F, C, G, Am, F]

        voicings = GuitarChordPicker().voice_sequence(sequence)

        # Both occurrences must be identical (whole-song, not drifting).
        assert voicings[0:4] == voicings[4:8]

        # C, G, Am land on their canonical open shapes.
        assert voicings[0] == [48, 52, 55, 60, 64]   # x32010
        assert voicings[1] == [43, 47, 50, 55, 59, 67]  # 320003
        assert voicings[2] == [45, 52, 57, 60, 64]   # x02210

        # F: a full voicing (>=4 strings) with F (pitch class 5) in the bass.
        f_midi = voicings[3]
        assert len(f_midi) >= 4
        assert min(f_midi) % 12 == 5

    def test_dp_beats_greedy_on_lookahead_case(self):
        """A progression where greedy's locally-best first chord forces later
        jumps; whole-song DP takes a slightly weaker first shape for a better
        total. DP total path score must be strictly greater here.

        Eb, G/E, Cm: greedy voices Eb high (5 sounding strings incl. an open G
        rank its quality above the low shape), which then jumps down to the two
        low following chords. The optimizer keeps Eb low, tightening the whole
        run.
        """
        sequence = [_major('Eb'), _slash('G', 'E'), _major('Cm')]

        greedy_fs = self._greedy_fingerings(sequence)
        picker = GuitarChordPicker()
        dp_fs = self._dp_fingerings(picker, sequence)

        greedy_total = self._total_path_score(picker, sequence, greedy_fs)
        dp_total = self._total_path_score(picker, sequence, dp_fs)

        # DP maximizes the exact objective, so it can never be worse.
        assert dp_total >= greedy_total - 1e-9
        # For this constructed case it is strictly better.
        assert dp_total > greedy_total + 1e-6

    def test_dp_never_worse_than_greedy(self):
        """Across several progressions, DP's total path score is >= greedy's."""
        progressions = [
            [_major('C'), _major('G'), _major('A'), _major('F')],
            [_major('Eb'), _slash('G', 'E'), _major('Cm')],
            [_major('F'), _major('Ab'), _slash('G', 'F#')],
            [_major('C'), _major('Bb'), _major('Eb'), _major('C')],
            [_slash('C', 'F'), _slash('D', 'Eb'), _major('Ab')],
        ]
        for sequence in progressions:
            greedy_fs = self._greedy_fingerings(sequence)
            picker = GuitarChordPicker()
            dp_fs = self._dp_fingerings(picker, sequence)
            greedy_total = self._total_path_score(picker, sequence, greedy_fs)
            dp_total = self._total_path_score(picker, sequence, dp_fs)
            assert dp_total >= greedy_total - 1e-9, \
                f"DP worse than greedy for {[cn.root for cn in sequence]}"

    @given(st.lists(realistic_chord_strategy(), min_size=20, max_size=60))
    @settings(max_examples=50)
    def test_voice_sequence_no_wrong_notes(self, chord_sequence):
        """FUZZ: whole-song guitar voicing never sounds a wrong note (same HARD
        invariant as the chord_to_midi fuzz test)."""
        picker = GuitarChordPicker()
        voicings = picker.voice_sequence(chord_sequence)

        assert len(voicings) == len(chord_sequence)

        for i, (chord_notes, midi) in enumerate(zip(chord_sequence, voicings)):
            if len(midi) == 0:
                continue
            expected = notes_to_note_classes(chord_notes.notes)
            expected_bass = normalize_note(chord_notes.bass_note)
            actual = midi_list_to_note_classes(midi)
            for note in actual:
                is_in_chord = note in expected or normalize_note(note) in expected
                is_bass_note = normalize_note(note) == expected_bass or note == expected_bass
                assert is_in_chord or is_bass_note, \
                    f"FUZZ FAIL at chord {i}: Note {note} not in chord {expected} " \
                    f"or bass {expected_bass}. MIDI: {midi}"


class TestSongRendererVoicing:
    """SongRenderer voices played chords via voice_sequence; rests stay silent."""

    def _render(self, text, picker):
        lines = SongParserService().detect_chords_in_text(text)
        return SongRenderer().render(
            lines=lines,
            initial_key=None,
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=picker,
        )

    @pytest.mark.parametrize('picker_class', [ChordNotePicker, GuitarChordPicker],
                             ids=['piano', 'guitar'])
    def test_loop_song_all_played_chords_voiced(self, picker_class):
        """A looped song: every played chord has midi_notes; rests have none."""
        text = (
            "{label: verse}\n"
            "C G\n"
            "NC Am\n"
            "F\n"
            "{loop: verse 2}\n"
        )
        rendered = self._render(text, picker_class())
        assert rendered is not None

        played = [rc for rc in rendered.chords if not rc.is_rest and not rc.skipped]
        rests = [rc for rc in rendered.chords if rc.is_rest]

        assert played, "expected some played chords"
        for rc in played:
            assert rc.midi_notes, f"played chord {rc.chord_info.chord} not voiced"

        assert rests, "expected the NC rest to appear"
        for rc in rests:
            assert rc.midi_notes is None

        # The loop really repeated (verse body played more than once).
        c_chords = [rc for rc in played if rc.chord_info.chord == 'C']
        assert len(c_chords) >= 2
