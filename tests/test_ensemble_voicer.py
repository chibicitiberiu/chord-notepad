"""Tests for the ensemble (SATB-style) voicer.

Cover the hard constraints (voice count, ordering, ranges, spacing, the
top-first/bottom-up index mapping), determinism, and the musical behaviours the
scoring weights are meant to produce (bass/slash handling, omission, doubling,
parallel-perfect avoidance, common-tone retention, and key-driven resolution).
The frozen musical assertions were each verified empirically first, then pinned
to a defensible bound rather than the exact voicing.
"""

import pytest
from collections import Counter

from audio.ensemble_voicer import EnsembleVoicer
from models.ensemble_spec import BUILTIN_ENSEMBLES, EnsembleSpec
from models.chord_notes import ChordNotes


# ---------------------------------------------------------------------------
# Helpers and specs
# ---------------------------------------------------------------------------
def cn(notes, bass=None, root=None, intervals=None, key=None):
    """Build a ChordNotes with sensible defaults for the root/bass."""
    return ChordNotes(
        notes=notes,
        bass_note=bass or notes[0],
        root=root or notes[0],
        intervals=intervals,
        key=key,
    )


SIX_VOICE_SPEC = EnsembleSpec.from_dict('six', {
    'label': 'Six-voice',
    'voices': [
        {'name': 'V1', 'range': ['E4', 'C6']},
        {'name': 'V2', 'range': ['C4', 'A5']},
        {'name': 'V3', 'range': ['G3', 'E5']},
        {'name': 'V4', 'range': ['C3', 'A4']},
        {'name': 'V5', 'range': ['E2', 'C4']},
        {'name': 'V6', 'range': ['C2', 'G3']},
    ],
    'max_spacing': [12, 12, 12, 12, 19],
})


def _spec(name):
    if name == 'six':
        return SIX_VOICE_SPEC
    return BUILTIN_ENSEMBLES[name]


ALL_SPEC_NAMES = ['satb', 'ssa', 'six']


# A varied corpus: triads, sevenths, suspensions, slash chords, 9/11/13
# extensions, and key-stamped (roman-resolved) chords. ``triad`` flags the
# plain 3-note chords, for which every ensemble voices within the strict range.
CORPUS = [
    ('C', cn(['C', 'E', 'G']), True),
    ('Am', cn(['A', 'C', 'E']), True),
    ('F', cn(['F', 'A', 'C']), True),
    ('G', cn(['G', 'B', 'D']), True),
    ('D', cn(['D', 'F#', 'A']), True),
    ('Bb', cn(['Bb', 'D', 'F']), True),
    ('Cm', cn(['C', 'Eb', 'G']), True),
    ('Bdim', cn(['B', 'D', 'F'], intervals=[0, 3, 6]), True),
    ('Caug', cn(['C', 'E', 'G#'], intervals=[0, 4, 8]), True),
    ('Csus2', cn(['C', 'D', 'G'], intervals=[0, 2, 7]), True),
    ('Csus4', cn(['C', 'F', 'G'], intervals=[0, 5, 7]), True),
    ('Cmaj7', cn(['C', 'E', 'G', 'B'], intervals=[0, 4, 7, 11]), False),
    ('G7', cn(['G', 'B', 'D', 'F'], intervals=[0, 4, 7, 10]), False),
    ('Am7', cn(['A', 'C', 'E', 'G'], intervals=[0, 3, 7, 10]), False),
    ('Dm7b5', cn(['D', 'F', 'Ab', 'C'], intervals=[0, 3, 6, 10]), False),
    ('E7', cn(['E', 'G#', 'B', 'D'], intervals=[0, 4, 7, 10]), False),
    ('C/E', cn(['C', 'E', 'G'], bass='E'), False),
    ('G/B', cn(['G', 'B', 'D'], bass='B'), False),
    ('F/A', cn(['F', 'A', 'C'], bass='A'), False),
    ('Cadd9', cn(['C', 'E', 'G', 'D'], intervals=[0, 4, 7, 14]), False),
    ('C9', cn(['C', 'E', 'G', 'Bb', 'D'], intervals=[0, 4, 7, 10, 14]), False),
    ('C11', cn(['C', 'E', 'G', 'Bb', 'D', 'F'], intervals=[0, 4, 7, 10, 14, 17]), False),
    ('C13', cn(['C', 'E', 'G', 'Bb', 'D', 'A'], intervals=[0, 4, 7, 10, 14, 21]), False),
    ('G7(V7 in C)', cn(['G', 'B', 'D', 'F'], intervals=[0, 4, 7, 10], key='C'), False),
    ('Am(vi in C)', cn(['A', 'C', 'E'], key='C'), True),
]


def _bottom_up_range(spec, b, n):
    """Strict (low, high) range for bottom-up voice index ``b``."""
    voice = spec.voices[n - 1 - b]
    return voice.low, voice.high


def _spacing_cap(spec, b, n):
    """Max spacing between bottom-up voices ``b`` and ``b + 1``."""
    return spec.max_spacing[n - 2 - b]


# ---------------------------------------------------------------------------
# Hard-constraint properties over the corpus
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('spec_name', ALL_SPEC_NAMES)
def test_hard_constraints_over_corpus(spec_name):
    """Every voicing has N notes, is non-descending, in range, and spaced."""
    spec = _spec(spec_name)
    n = len(spec.voices)
    voicer = EnsembleVoicer(spec)
    sequence = [chord for _label, chord, _triad in CORPUS]
    voicings = voicer.voice_sequence(sequence)

    assert len(voicings) == len(sequence)
    for (label, _chord, is_triad), voicing in zip(CORPUS, voicings):
        assert len(voicing) == n, f"{spec_name}/{label}: expected {n} notes"

        # Non-descending low-to-high (equal only where unisons are allowed).
        for lower, upper in zip(voicing, voicing[1:]):
            assert upper >= lower, f"{spec_name}/{label}: not ascending {voicing}"

        # In range: bottom-up voice b must be in spec.voices[N-1-b]'s range.
        # None of the corpus chords trip the relaxation ladder, so the strict
        # range holds for every chord under these normal specs.
        for b, midi in enumerate(voicing):
            low, high = _bottom_up_range(spec, b, n)
            assert low <= midi <= high, (
                f"{spec_name}/{label}: voice {b} = {midi} outside [{low}, {high}]"
            )

        # Spacing respected (no chord hit the ladder, so caps hold everywhere).
        for b in range(n - 1):
            gap = voicing[b + 1] - voicing[b]
            assert gap <= _spacing_cap(spec, b, n), (
                f"{spec_name}/{label}: gap {gap} above voice {b} exceeds cap"
            )


def test_index_mapping_top_first_vs_bottom_up():
    """The bottom voice sits lowest and the top voice highest, per the mapping."""
    spec = BUILTIN_ENSEMBLES['satb']
    n = len(spec.voices)
    voicer = EnsembleVoicer(spec)
    voicing = voicer.voice_sequence([cn(['C', 'E', 'G'])])[0]

    # voicing[0] is the Bass (spec.voices[-1]); voicing[-1] is the Soprano.
    bass_low, bass_high = spec.voices[-1].low, spec.voices[-1].high
    sop_low, sop_high = spec.voices[0].low, spec.voices[0].high
    assert bass_low <= voicing[0] <= bass_high
    assert sop_low <= voicing[-1] <= sop_high
    assert voicing[0] < voicing[-1]


# ---------------------------------------------------------------------------
# Determinism and greedy/sequence consistency
# ---------------------------------------------------------------------------
def test_voice_sequence_is_deterministic():
    """Voicing the same sequence twice yields identical output."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    sequence = [chord for _label, chord, _triad in CORPUS]
    assert voicer.voice_sequence(sequence) == voicer.voice_sequence(sequence)


def test_chord_to_midi_matches_single_chord_sequence():
    """chord_to_midi after reset equals voice_sequence's (deduped) first voicing.

    For a single-chord sequence there is no transition, so the greedy argmax and
    the DP make the same choice; the greedy path returns it de-duplicated.
    """
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['C', 'E', 'G'])
    seq_first = voicer.voice_sequence([chord])[0]

    voicer.reset()
    greedy = voicer.chord_to_midi(chord)
    assert greedy == sorted(set(seq_first))


# ---------------------------------------------------------------------------
# Bass / slash
# ---------------------------------------------------------------------------
def test_slash_chord_pins_bottom_voice():
    """Every candidate for a slash chord sings the slash pitch class in the bass."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['C', 'E', 'G'], bass='E')  # C/E -> bottom voice is E (pc 4)
    meta = voicer._build_meta(chord)
    candidates = voicer._candidates(chord, meta)
    assert candidates
    assert all(stack[0] % 12 == 4 for stack in candidates)


# ---------------------------------------------------------------------------
# Omission favours character tones
# ---------------------------------------------------------------------------
def test_omission_keeps_color_tone():
    """A 5-tone C9sus4 in 4 voices never drops the suspended 4th (colour)."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['C', 'F', 'G', 'Bb', 'D'], intervals=[0, 5, 7, 10, 14])
    voicing = voicer.voice_sequence([chord])[0]
    voiced_pcs = {m % 12 for m in voicing}
    assert 5 in voiced_pcs, f"colour tone F dropped: {voicing}"


def test_drop_set_ranking_prefers_expendable_tones():
    """The cheapest drop-sets sacrifice the extension/fifth, never colour/seventh."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['C', 'F', 'G', 'Bb', 'D'], intervals=[0, 5, 7, 10, 14])
    meta = voicer._build_meta(chord)
    # Tones other than the (root) bass, ranked drop-sets of size 1.
    to_place = [(pc, role) for pc, role in meta.tones if pc != 0]
    ranked = voicer._ranked_drop_sets(to_place, 1)

    # Cheapest two singletons drop the extension D (pc 2) and the fifth G (pc 7).
    # Omit weights are now signed (negative); the cheapest to drop is the one
    # closest to zero: extension -7.0, then fifth -8.0.
    assert ranked[0] == (2,)   # extension, omit weight -7.0
    assert ranked[1] == (7,)   # fifth, omit weight -8.0
    # Colour F (-30.0) and seventh Bb (-40.0) are the most expensive to drop.
    assert ranked.index((5,)) > ranked.index((7,))
    assert ranked.index((10,)) > ranked.index((5,))


# ---------------------------------------------------------------------------
# Doubling
# ---------------------------------------------------------------------------
def test_triad_doubles_the_root():
    """A plain C major triad in SATB doubles the root under default weights."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    voicing = voicer.voice_sequence([cn(['C', 'E', 'G'])])[0]
    counts = Counter(m % 12 for m in voicing)
    doubled = [pc for pc, count in counts.items() if count > 1]
    assert doubled == [0], f"expected only the root doubled, got {counts}"


# ---------------------------------------------------------------------------
# Parallel avoidance and common-tone voice leading
# ---------------------------------------------------------------------------
def _parallel_perfect_pairs(prev, cur):
    """Voice pairs that move in parallel perfect fifths/octaves."""
    n = len(prev)
    deltas = [cur[b] - prev[b] for b in range(n)]
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if deltas[i] != 0 and deltas[j] != 0:
                prev_ic = (prev[j] - prev[i]) % 12
                cur_ic = (cur[j] - cur[i]) % 12
                if prev_ic == cur_ic and prev_ic in (0, 7):
                    pairs.append((i, j, prev_ic))
    return pairs


def test_no_parallel_perfects_in_progression():
    """C - G - Am - F voiced in SATB contains no parallel perfect fifths/octaves."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    seq = [cn(['C', 'E', 'G']), cn(['G', 'B', 'D']),
           cn(['A', 'C', 'E']), cn(['F', 'A', 'C'])]
    voicings = voicer.voice_sequence(seq)
    for prev, cur in zip(voicings, voicings[1:]):
        assert _parallel_perfect_pairs(prev, cur) == [], (
            f"parallel perfect between {prev} and {cur}"
        )


def test_common_tones_are_retained():
    """C -> Am keeps at least two voices static (shared C and E)."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    voicings = voicer.voice_sequence([cn(['C', 'E', 'G']), cn(['A', 'C', 'E'])])
    held = sum(1 for b in range(4) if voicings[0][b] == voicings[1][b])
    assert held >= 2, f"expected >= 2 common tones, got {held}: {voicings}"


# ---------------------------------------------------------------------------
# Key-driven rules
# ---------------------------------------------------------------------------
def test_leading_tone_not_doubled():
    """With key G stamped on D7, the leading tone F# is never doubled."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['D', 'F#', 'A', 'C'], root='D', intervals=[0, 4, 7, 10], key='G')
    voicing = voicer.voice_sequence([chord])[0]
    counts = Counter(m % 12 for m in voicing)
    assert counts.get(6, 0) <= 1, f"F# doubled: {voicing}"


def test_leading_tone_resolves_up():
    """D7 -> G in key G resolves the F#-singing voice up a semitone to G."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    d7 = cn(['D', 'F#', 'A', 'C'], root='D', intervals=[0, 4, 7, 10], key='G')
    g = cn(['G', 'B', 'D'], key='G')
    prev, cur = voicer.voice_sequence([d7, g])

    lt_voices = [b for b in range(4) if prev[b] % 12 == 6]
    assert lt_voices, f"no voice sang F#: {prev}"
    for b in lt_voices:
        assert cur[b] - prev[b] == 1, (
            f"leading tone in voice {b} did not resolve up: {prev} -> {cur}"
        )


# ---------------------------------------------------------------------------
# Relaxation ladder
# ---------------------------------------------------------------------------
def test_impossible_spec_still_voices_every_chord():
    """A spec whose voices cannot be ordered still voices via the closed-stack fallback."""
    # Top voice range sits BELOW the bottom voice range: no ascending assignment
    # exists even after widening, so only stage 3 (the forced closed stack) fires.
    impossible = EnsembleSpec.from_dict('impossible', {
        'voices': [
            {'name': 'top', 'range': [40, 43]},
            {'name': 'bottom', 'range': [60, 63]},
        ],
        'max_spacing': [3],
    })
    voicer = EnsembleVoicer(impossible)
    seq = [cn(['C', 'E', 'G']), cn(['G', 'B', 'D']), cn(['F', 'A', 'C'])]
    voicings = voicer.voice_sequence(seq)

    assert len(voicings) == len(seq)
    assert all(len(v) == 2 for v in voicings)
    for v in voicings:
        assert v[1] >= v[0]  # weakly ascending, guaranteed by the fallback
    assert voicings == voicer.voice_sequence(seq)  # deterministic


# ---------------------------------------------------------------------------
# Unisons
# ---------------------------------------------------------------------------
def test_allow_unisons_false_never_emits_equal_adjacent_notes():
    """A spec with allow_unisons=False never produces equal adjacent voices."""
    spec = EnsembleSpec.from_dict('no_unison', {
        'voices': [
            {'name': 'A', 'range': ['C4', 'C6']},
            {'name': 'B', 'range': ['C3', 'C5']},
            {'name': 'C', 'range': ['C2', 'C4']},
        ],
        'max_spacing': [12, 12],
        'allow_unisons': False,
    })
    voicer = EnsembleVoicer(spec)
    # The second chord would love to collapse to a unison if it were allowed.
    voicings = voicer.voice_sequence([cn(['C', 'E', 'G']), cn(['C', 'C', 'C'])])
    for voicing in voicings:
        for lower, upper in zip(voicing, voicing[1:]):
            assert lower != upper, f"adjacent unison in {voicing}"


# ---------------------------------------------------------------------------
# Interface contract
# ---------------------------------------------------------------------------
def test_voice_labels_top_first_and_voicings_low_to_high():
    """voice_labels are top-first; emitted voicings are low-to-high."""
    spec = BUILTIN_ENSEMBLES['satb']
    voicer = EnsembleVoicer(spec)
    assert voicer.voice_labels == ['Soprano', 'Alto', 'Tenor', 'Bass']

    voicing = voicer.voice_sequence([cn(['C', 'E', 'G'])])[0]
    assert voicing == sorted(voicing)  # low to high
