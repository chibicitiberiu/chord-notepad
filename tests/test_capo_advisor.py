"""Tests for the capo advisor and the picker's whole-song score.

The advisor scores every capo position with
``GuitarChordPicker.voice_sequence_score`` and suggests the best one only when
it beats capo 0 by ``CAPO_MIN_GAIN``. These tests pin the behaviour the
chord-sheet header relies on: a barre-heavy key suggests a nonzero capo, an
open-friendly key suggests none, and the score sums the same path the details
API voices.
"""

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from constants import CAPO_MIN_GAIN
from models.chord_notes import ChordNotes
from models.fretboard_spec import BUILTIN_FRETBOARDS
from services.capo_advisor import _capo_spec, suggest_capo

STANDARD = BUILTIN_FRETBOARDS["standard"]


def _cn(notes, root, bass=None):
    return ChordNotes(notes=notes, bass_note=bass or root, root=root)


# F#-major-flavoured progression: every shape is a barre in open position.
FSHARP_PROGRESSION = [
    _cn(["F#", "A#", "C#"], "F#"),
    _cn(["B", "D#", "F#"], "B"),
    _cn(["C#", "F", "G#"], "C#"),
    _cn(["D#", "F#", "A#"], "D#"),
]

# Cowboy C-major progression: already comfortable open chords.
CMAJOR_PROGRESSION = [
    _cn(["C", "E", "G"], "C"),
    _cn(["G", "B", "D"], "G"),
    _cn(["A", "C", "E"], "A"),
    _cn(["F", "A", "C"], "F"),
]


# --------------------------------------------------------------------------
# suggest_capo
# --------------------------------------------------------------------------


def test_barre_heavy_key_suggests_a_nonzero_capo():
    suggested = suggest_capo(STANDARD, FSHARP_PROGRESSION)
    assert suggested is not None
    assert suggested > 0

    # The suggestion must genuinely be easier: its whole-song score beats capo
    # 0 by at least the minimum gain the advisor requires.
    base = GuitarChordPicker(STANDARD).voice_sequence_score(FSHARP_PROGRESSION)
    at_suggested = GuitarChordPicker(
        _capo_spec(STANDARD, suggested)
    ).voice_sequence_score(FSHARP_PROGRESSION)
    assert at_suggested - base >= CAPO_MIN_GAIN


def test_open_friendly_key_suggests_no_capo():
    assert suggest_capo(STANDARD, CMAJOR_PROGRESSION) is None


def test_suggestion_is_deterministic():
    first = suggest_capo(STANDARD, FSHARP_PROGRESSION)
    second = suggest_capo(STANDARD, FSHARP_PROGRESSION)
    assert first == second


def test_ties_go_to_the_lower_capo():
    # Craft a scenario where two capos score identically: with a large min_gain
    # of 0 and a symmetric spec, we rely on the strictly-greater rule. A single
    # open-string-free chord voiced identically at two capos must resolve to the
    # lower one. We simulate a tie by asserting that when capo N and a higher
    # capo M have equal scores, the lower is chosen. Use a low min_gain so a
    # nonzero capo is returned, then confirm no *higher* capo with the same
    # score displaced it.
    seq = FSHARP_PROGRESSION
    suggested = suggest_capo(STANDARD, seq, min_gain=0.0)
    assert suggested is not None
    best_score = GuitarChordPicker(
        _capo_spec(STANDARD, suggested)
    ).voice_sequence_score(seq)
    # No lower capo ties the winner's score (else it would have been chosen).
    for lower in range(0, suggested):
        lower_score = GuitarChordPicker(
            _capo_spec(STANDARD, lower)
        ).voice_sequence_score(seq)
        assert lower_score < best_score


def test_empty_sequence_returns_none():
    assert suggest_capo(STANDARD, []) is None


def test_all_empty_chord_notes_returns_none():
    empties = [_cn([], "C"), _cn([], "G")]
    assert suggest_capo(STANDARD, empties) is None


def test_below_min_gain_returns_none():
    # A huge min_gain no real capo can reach yields no suggestion.
    assert suggest_capo(STANDARD, FSHARP_PROGRESSION, min_gain=10_000.0) is None


# --------------------------------------------------------------------------
# GuitarChordPicker.voice_sequence_score consistency with the details path
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sequence",
    [
        FSHARP_PROGRESSION,
        CMAJOR_PROGRESSION,
        [_cn(["A", "C#", "E"], "A"), _cn(["E", "G#", "B"], "E"), _cn(["D", "F#", "A"], "D")],
    ],
)
def test_score_equals_recomputed_details_path(sequence):
    picker = GuitarChordPicker(STANDARD)

    voicings = picker.voice_sequence_details(sequence)
    # Recompute the score of exactly the fingerings the details path chose,
    # using the same intrinsic-quality and transition scorers.
    total = 0.0
    prev = None
    for voiced, cn in zip(voicings, sequence):
        total += picker._score_quality(voiced.fingering, cn.notes, cn.bass_note)
        if prev is not None:
            total += picker._score_transition(prev, voiced.fingering)
        prev = voiced.fingering

    assert picker.voice_sequence_score(sequence) == pytest.approx(total)


def test_empty_sequence_scores_zero():
    assert GuitarChordPicker(STANDARD).voice_sequence_score([]) == 0.0
