"""Tests for the spec-driven fretboard voicing model (``GuitarChordPicker``).

These exercise the generalization of the engine from hard-coded six-string
guitar constants to an arbitrary :class:`FretboardSpec`: alternate string
counts (3-string, 7-string), re-entrant tunings (ukulele high-G), live tunable
weights, and per-spec hand parameters (``fingers``, ``allow_barres``).

The frozen-behavior of default six-string guitar is covered by
``tests/test_chord_pickers.py`` and the golden gate in
``tests/test_playback_characterization.py``; this file covers the new,
generalized surface.
"""

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from models.fretboard_spec import FretboardSpec, BUILTIN_FRETBOARDS
from models.chord_notes import ChordNotes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _triad(root, notes):
    return ChordNotes(notes=notes, bass_note=notes[0], root=root)


# A fixed 10-chord progression reused across several tests.
PROGRESSION = [
    _triad('C', ['C', 'E', 'G']),
    _triad('G', ['G', 'B', 'D']),
    _triad('A', ['A', 'C', 'E']),
    _triad('F', ['F', 'A', 'C']),
    _triad('D', ['D', 'F#', 'A']),
    _triad('E', ['E', 'G#', 'B']),
    _triad('B', ['B', 'D', 'F#']),
    _triad('Bb', ['Bb', 'D', 'F']),
    ChordNotes(notes=['G', 'B', 'D', 'F'], bass_note='G', root='G'),
    ChordNotes(notes=['C', 'E', 'G'], bass_note='G', root='C'),  # slash
]

# Common-chord corpus for playability sweeps.
CORPUS = [
    _triad('C', ['C', 'E', 'G']),
    _triad('G', ['G', 'B', 'D']),
    _triad('A', ['A', 'C', 'E']),
    _triad('F', ['F', 'A', 'C']),
    _triad('E', ['E', 'G#', 'B']),
    _triad('B', ['B', 'D', 'F#']),
    _triad('Bb', ['Bb', 'D', 'F']),
    ChordNotes(notes=['G', 'B', 'D', 'F'], bass_note='G', root='G'),
    ChordNotes(notes=['D', 'F#', 'A', 'C'], bass_note='D', root='D'),
    ChordNotes(notes=['A', 'C', 'E', 'G'], bass_note='A', root='A'),
]


def _fretted_count(fingering):
    return len([f for f in fingering if f > 0])


def _requires_barre(fingering, fingers):
    """A fingering needs a barre when more strings are fretted than fingers.

    This mirrors the model's own rule (``n_fret > spec.fingers`` in
    ``_enumerate_candidates`` / ``_is_playable``).
    """
    return _fretted_count(fingering) > fingers


def _fingers_used(fingering, fingers):
    """Physical finger count for a fingering, counting a barre as one finger."""
    fretted = [f for f in fingering if f > 0]
    if not fretted:
        return 0
    if len(fretted) <= fingers:
        return len(fretted)
    f_min = min(fretted)
    above = sum(1 for f in fretted if f > f_min)
    return 1 + above


def _span(fingering):
    fretted = [f for f in fingering if f > 0]
    return (max(fretted) - min(fretted)) if fretted else 0


def _sequence_fingerings(picker, sequence):
    """Recover the fingering behind each voice_sequence MIDI list."""
    midis = picker.voice_sequence(sequence)
    out = []
    for cn, midi in zip(sequence, midis):
        cands = picker._build_candidate_ladder(cn.notes, cn.bass_note)
        if not cands:
            cands = [picker._get_fallback_fingering(cn.notes[0])]
        match = next((f for f in cands if picker._fingering_to_midi(f) == midi), None)
        assert match is not None, f"no candidate fingering matches {midi}"
        out.append(match)
    return out


# ---------------------------------------------------------------------------
# Default-spec equivalence and live weights
# ---------------------------------------------------------------------------

class TestDefaultSpecEquivalence:
    def test_name_and_spec_produce_identical_output(self):
        """GuitarChordPicker('standard') == GuitarChordPicker(BUILTIN_FRETBOARDS['standard'])."""
        by_name = GuitarChordPicker('standard').voice_sequence(PROGRESSION)
        by_spec = GuitarChordPicker(BUILTIN_FRETBOARDS['standard']).voice_sequence(PROGRESSION)
        assert by_name == by_spec

    def test_unknown_name_falls_back_to_standard(self):
        """An unknown fretboard name falls back to the standard six-string spec."""
        bogus = GuitarChordPicker('does-not-exist')
        assert bogus.tuning_midi == list(BUILTIN_FRETBOARDS['standard'].tuning)
        assert bogus.voice_sequence(PROGRESSION) == \
            GuitarChordPicker('standard').voice_sequence(PROGRESSION)

    def test_list_tuning_builds_adhoc_spec(self):
        """A bare MIDI list is wrapped in an ad-hoc spec with default limits."""
        picker = GuitarChordPicker([40, 45, 50, 55, 59, 64])
        assert picker.tuning_midi == [40, 45, 50, 55, 59, 64]
        assert picker.spec.max_fret == 12
        assert picker.spec.fingers == 4

    def test_weight_override_changes_output(self):
        """A single overridden weight yields a different result: weights are live.

        A large ``span_penalty`` makes wide stretches far more costly, forcing
        the optimizer onto tighter shapes for at least one chord of the
        progression. If weights were resolved once and ignored, the two
        sequences would be identical.
        """
        base = GuitarChordPicker(BUILTIN_FRETBOARDS['standard']).voice_sequence(PROGRESSION)

        data = BUILTIN_FRETBOARDS['standard'].to_dict()
        data['weights'] = dict(data['weights'])
        data['weights']['span_penalty'] = 50.0
        tweaked_spec = FretboardSpec.from_dict('tweaked', data)
        tweaked = GuitarChordPicker(tweaked_spec).voice_sequence(PROGRESSION)

        assert tweaked != base, "overriding span_penalty must change the voicing"


# ---------------------------------------------------------------------------
# Ukulele: re-entrant tuning correctness (the high-G pin)
# ---------------------------------------------------------------------------

class TestUkulele:
    CHORDS = {
        'C': _triad('C', ['C', 'E', 'G']),
        'Am': _triad('A', ['A', 'C', 'E']),
        'F': _triad('F', ['F', 'A', 'C']),
        'G7': ChordNotes(notes=['G', 'B', 'D', 'F'], bass_note='G', root='G'),
    }

    def test_four_strings_and_fret_bounds(self):
        """Every ukulele fingering has <=4 entries, all within 0..12."""
        for name, chord in self.CHORDS.items():
            picker = GuitarChordPicker('ukulele')
            picker.chord_to_midi(chord)
            fingering = picker.state.previous_fingering
            assert len(fingering) == 4, f"{name}: {fingering}"
            for fret in fingering:
                assert fret == -1 or 0 <= fret <= 12, f"{name}: {fingering}"

    def test_c_chord_bass_is_lowest_pitch_not_lowest_string(self):
        """RE-ENTRANT PIN: the bass of C is the lowest sounding *pitch* (C4),
        not the lowest string index (which on a high-G ukulele is G4).

        Standard ukulele tuning is G4-C4-E4-A4: string 0 (G4=67) sounds *above*
        string 1 (C4=60). A naive "lowest string index is the bass" rule would
        call G the bass; the correct rule picks C4 as the lowest pitch.
        """
        picker = GuitarChordPicker('ukulele')
        assert picker.tuning_midi == [67, 60, 64, 69]  # high-G, re-entrant

        midi = picker.chord_to_midi(self.CHORDS['C'])
        assert min(midi) % 12 == 0, f"bass should be C (pc 0): {midi}"
        # The lowest note is C4, sourced from string index 1, not the lower-index
        # string 0 which sounds the higher G4.
        assert min(midi) == 60, f"bass should be C4=60, got {min(midi)} in {midi}"

    def test_chords_voice_without_final_fallback(self):
        """The common ukulele chords all enumerate real candidates (the lone-root
        fallback is never reached)."""
        picker = GuitarChordPicker('ukulele')
        for name, chord in self.CHORDS.items():
            cands = picker._build_candidate_ladder(chord.notes, chord.bass_note)
            assert cands, f"{name} hit the empty-ladder fallback"


# ---------------------------------------------------------------------------
# Alternate string counts: 7-string and synthetic 3-string
# ---------------------------------------------------------------------------

SEVEN_STRING = FretboardSpec.from_dict(
    'seven', {'tuning': [35, 40, 45, 50, 55, 59, 64]})  # B1 E2 A2 D3 G3 B3 E4
THREE_STRING = FretboardSpec.from_dict(
    'three', {'tuning': [43, 50, 55]})  # G2 D3 G3


class TestAlternateStringCounts:
    @pytest.mark.parametrize('spec', [SEVEN_STRING, THREE_STRING],
                             ids=['7string', '3string'])
    def test_common_chords_voice_without_final_fallback(self, spec):
        """Common triads/sevenths enumerate real candidates on both instruments."""
        picker = GuitarChordPicker(spec)
        for chord in CORPUS:
            cands = picker._build_candidate_ladder(chord.notes, chord.bass_note)
            assert cands, f"{chord.root} on {spec.name} hit the empty-ladder fallback"

    @pytest.mark.parametrize('spec', [SEVEN_STRING, THREE_STRING],
                             ids=['7string', '3string'])
    def test_playability_invariants(self, spec):
        """Chosen fingerings honor span and finger limits (barre counts as one)."""
        picker = GuitarChordPicker(spec)
        for chord in CORPUS:
            picker.chord_to_midi(chord)
            fingering = picker.state.previous_fingering
            assert len(fingering) == len(spec.tuning)
            assert _span(fingering) <= spec.relaxed_span, \
                f"{chord.root} on {spec.name}: span {_span(fingering)} > {spec.relaxed_span}"
            assert _fingers_used(fingering, spec.fingers) <= spec.fingers, \
                f"{chord.root} on {spec.name}: too many fingers ({fingering})"


# ---------------------------------------------------------------------------
# Hand-parameter generalization
# ---------------------------------------------------------------------------

class TestHandParameters:
    def test_allow_barres_false_never_picks_a_barre(self):
        """With barres forbidden, no chosen fingering frets more strings than
        there are fingers (i.e. none would need a barre)."""
        data = BUILTIN_FRETBOARDS['standard'].to_dict()
        data['allow_barres'] = False
        spec = FretboardSpec.from_dict('no_barre', data)
        picker = GuitarChordPicker(spec)

        for chord in CORPUS:
            picker.chord_to_midi(chord)
            fingering = picker.state.previous_fingering
            assert not _requires_barre(fingering, spec.fingers), \
                f"{chord.root}: barre chosen despite allow_barres=False ({fingering})"

    def test_allow_barres_false_rejects_barre_in_is_playable(self):
        """The barre-free spec also rejects an explicit barre via _is_playable."""
        data = BUILTIN_FRETBOARDS['standard'].to_dict()
        data['allow_barres'] = False
        picker = GuitarChordPicker(FretboardSpec.from_dict('no_barre', data))
        # A full six-string barre, playable on the default spec, is now rejected.
        assert picker._is_playable([1, 3, 3, 2, 1, 1]) is False

    def test_fingers_three_never_uses_more_than_three(self):
        """With three fingers, no chosen fingering uses more than three (a barre
        counts as a single finger)."""
        data = BUILTIN_FRETBOARDS['standard'].to_dict()
        data['fingers'] = 3
        spec = FretboardSpec.from_dict('three_finger', data)
        picker = GuitarChordPicker(spec)

        for chord in CORPUS:
            picker.chord_to_midi(chord)
            fingering = picker.state.previous_fingering
            assert _fingers_used(fingering, spec.fingers) <= 3, \
                f"{chord.root}: used >3 fingers ({fingering})"


# ---------------------------------------------------------------------------
# Coverage clamp
# ---------------------------------------------------------------------------

class TestCoverageClamp:
    THIRTEENTH = ChordNotes(
        notes=['C', 'E', 'G', 'B', 'D', 'F', 'A'], bass_note='C', root='C')

    def test_thirteenth_voices_on_ukulele(self):
        """A 7-tone (13th) chord still voices on a 4-string ukulele: the coverage
        floor is clamped to the string count instead of forcing the ladder."""
        picker = GuitarChordPicker('ukulele')
        midi = picker.chord_to_midi(self.THIRTEENTH)
        assert midi, "13th chord produced no notes on ukulele"
        assert len(midi) <= 4
        # Every sounded note is a chord tone.
        chord_pcs = {(picker.tuning_midi[s] + f) % 12
                     for s, f in enumerate(picker.state.previous_fingering) if f >= 0}
        allowed = {0, 4, 7, 11, 2, 5, 9}
        assert chord_pcs <= allowed, f"non-chord tone in {chord_pcs}"

    def test_thirteenth_on_standard_matches_old_rule(self):
        """On >=6 strings the clamp is a no-op: a 6+-unique-tone chord keeps the
        old floor of 4 tones. The standard-guitar voicing sounds >=4 chord
        tones (matching the historic large-chord rule)."""
        picker = GuitarChordPicker('standard')
        midi = picker.chord_to_midi(self.THIRTEENTH)
        pcs = {m % 12 for m in midi}
        chord_pcs = {0, 4, 7, 11, 2, 5, 9}
        present = pcs & chord_pcs
        assert len(present) >= 4, f"large chord should keep >=4 tones, got {present}"


# ---------------------------------------------------------------------------
# Determinism on alternate instruments
# ---------------------------------------------------------------------------

class TestDeterminism:
    @pytest.mark.parametrize('spec', ['ukulele', SEVEN_STRING],
                             ids=['ukulele', '7string'])
    def test_voice_sequence_repeatable(self, spec):
        """voice_sequence twice in a row is identical on ukulele and 7-string."""
        picker = GuitarChordPicker(spec)
        first = picker.voice_sequence(PROGRESSION)
        second = picker.voice_sequence(PROGRESSION)
        assert first == second
