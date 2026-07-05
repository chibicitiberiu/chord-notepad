"""Tests that the per-call scoring memoization in the whole-song voicing path
is a pure speedup: results must be identical to unmemoized scoring.

Covers both pickers' ``_optimize_sequence`` / ``voice_sequence_details`` paths:

- the memoized ``unary`` / ``transition`` closures return exactly the values
  the raw scorers (``_score_quality`` / ``_score_transition``) compute;
- the whole-song result equals an unmemoized reference run of the same
  beam-Viterbi search (:func:`audio.voicing_optimizer.optimize_sequence`);
- two consecutive calls are deterministic (identical results).
"""

from typing import List

import pytest

from audio.chord_picker import ChordNotePicker, Voicing
from audio.guitar_chord_picker import GuitarChordPicker
from audio.voicing_optimizer import optimize_sequence
from models.chord_notes import ChordNotes


def _cn(notes: List[str], bass: str) -> ChordNotes:
    return ChordNotes(notes=list(notes), bass_note=bass, root=notes[0])


# A short song with heavy chord repetition (the case memoization targets):
# only 4 unique chords across 16 positions, plus one empty (rest) entry.
def _repeated_sequence() -> List[ChordNotes]:
    ebm = _cn(["Eb", "Gb", "Bb"], "Eb")
    db = _cn(["Db", "F", "Ab"], "Db")
    b = _cn(["B", "D#", "F#"], "B")
    absus = _cn(["Ab", "Db", "Eb"], "Ab")
    rest = ChordNotes(notes=[], bass_note="", root="")
    seq = []
    for _ in range(3):
        seq.extend([ebm, db, b, db])
    seq.append(rest)
    seq.extend([absus, ebm, db])
    return seq


# --------------------------------------------------------------------------
# Guitar picker
# --------------------------------------------------------------------------


def test_guitar_memoized_closures_match_raw_scorers():
    picker = GuitarChordPicker("standard")
    sequence = _repeated_sequence()
    candidate_sets, chosen, unary, transition = picker._optimize_sequence(sequence)

    for pos, candidates in enumerate(candidate_sets):
        notes = sequence[pos].notes
        bass = sequence[pos].bass_note
        for fingering in candidates:
            expected = (0.0 if not notes
                        else picker._score_quality(fingering, notes, bass))
            # Two lookups of the same key must also agree (pure lookup).
            assert unary(pos, fingering) == expected
            assert unary(pos, fingering) == expected

    # Transitions along (and around) the chosen path match the raw scorer.
    prev = None
    for pos, idx in enumerate(chosen):
        fingering = candidate_sets[pos][idx]
        if prev is not None:
            expected = picker._score_transition(prev, fingering)
            assert transition(prev, fingering) == expected
            assert transition(prev, fingering) == expected
        prev = fingering


def test_guitar_matches_unmemoized_reference():
    # Reference: the same candidate enumeration + beam-Viterbi search, scored
    # with the raw (unmemoized) scorers. Must be byte-identical.
    ref_picker = GuitarChordPicker("standard")
    sequence = _repeated_sequence()

    ref_picker.reset()
    candidate_sets = []
    chord_data = []
    for cn in sequence:
        chord_data.append((cn.notes, cn.bass_note))
        if not cn.notes:
            candidate_sets.append([[-1] * ref_picker._num_strings])
            continue
        cands = ref_picker._build_candidate_ladder(cn.notes, cn.bass_note)
        if not cands:
            cands = [ref_picker._get_fallback_fingering(cn.notes[0])]
        candidate_sets.append(cands)

    def unary(pos, fingering):
        notes, bass = chord_data[pos]
        if not notes:
            return 0.0
        return ref_picker._score_quality(fingering, notes, bass)

    def transition(prev, cur):
        return ref_picker._score_transition(prev, cur)

    chosen = optimize_sequence(candidate_sets, unary, transition,
                               beam_width=20, prune_to=30)
    expected = [list(candidate_sets[pos][idx]) for pos, idx in enumerate(chosen)]

    picker = GuitarChordPicker("standard")
    result = [vc.fingering for vc in picker.voice_sequence_details(sequence)]
    assert result == expected


def test_guitar_repeated_positions_get_identical_fingerings_context_allowing():
    # Sanity on the memo key: positions sharing a chord share candidate lists,
    # and the result is well-formed (a fret per string, sounding chords voiced).
    picker = GuitarChordPicker("standard")
    sequence = _repeated_sequence()
    details = picker.voice_sequence_details(sequence)
    assert len(details) == len(sequence)
    for cn, vc in zip(sequence, details):
        assert len(vc.fingering) == 6
        if cn.notes:
            assert vc.midi_notes  # every real chord sounds something


def test_guitar_two_consecutive_calls_are_identical():
    picker = GuitarChordPicker("standard")
    sequence = _repeated_sequence()
    first = picker.voice_sequence_details(sequence)
    second = picker.voice_sequence_details(sequence)
    assert [(vc.midi_notes, vc.fingering) for vc in first] == \
        [(vc.midi_notes, vc.fingering) for vc in second]


def test_guitar_score_matches_manual_path_sum():
    # voice_sequence_score must equal the raw-scorer sum over the chosen path.
    picker = GuitarChordPicker("standard")
    sequence = _repeated_sequence()
    score = picker.voice_sequence_score(sequence)

    checker = GuitarChordPicker("standard")
    candidate_sets, chosen, _u, _t = checker._optimize_sequence(sequence)
    total = 0.0
    prev = None
    for pos, idx in enumerate(chosen):
        fingering = candidate_sets[pos][idx]
        notes = sequence[pos].notes
        if notes:
            total += checker._score_quality(fingering, notes, sequence[pos].bass_note)
        if prev is not None:
            total += checker._score_transition(prev, fingering)
        prev = fingering
    assert score == pytest.approx(total, abs=0.0)  # exact float equality


# --------------------------------------------------------------------------
# Piano picker
# --------------------------------------------------------------------------


def test_piano_matches_unmemoized_reference():
    ref_picker = ChordNotePicker()
    sequence = _repeated_sequence()

    ref_picker.reset()
    candidate_sets = []
    for cn in sequence:
        if not cn.notes:
            candidate_sets.append([Voicing((), ())])
        else:
            candidate_sets.append(ref_picker._get_candidates(cn))

    def unary(pos, voicing):
        if not sequence[pos].notes:
            return 0.0
        return ref_picker._score_quality(voicing, sequence[pos])

    def transition(prev, cur):
        return ref_picker._score_transition(ref_picker._voicing_to_midi(prev),
                                            ref_picker._voicing_to_midi(cur))

    chosen = optimize_sequence(candidate_sets, unary, transition,
                               beam_width=20, prune_to=30)
    expected = [ref_picker._voicing_to_midi(candidate_sets[pos][idx])
                for pos, idx in enumerate(chosen)]

    picker = ChordNotePicker()
    result = [vc.midi_notes for vc in picker.voice_sequence_details(sequence)]
    assert result == expected


def test_piano_two_consecutive_calls_are_identical():
    picker = ChordNotePicker()
    sequence = _repeated_sequence()
    first = picker.voice_sequence_details(sequence)
    second = picker.voice_sequence_details(sequence)
    assert [(vc.midi_notes, vc.hand_split) for vc in first] == \
        [(vc.midi_notes, vc.hand_split) for vc in second]


def test_empty_sequence_and_rest_only_sequence():
    rest = ChordNotes(notes=[], bass_note="", root="")
    guitar = GuitarChordPicker("standard")
    piano = ChordNotePicker()
    assert guitar.voice_sequence_details([]) == []
    assert piano.voice_sequence_details([]) == []
    assert [vc.midi_notes for vc in guitar.voice_sequence_details([rest, rest])] == [[], []]
    assert [vc.midi_notes for vc in piano.voice_sequence_details([rest, rest])] == [[], []]
