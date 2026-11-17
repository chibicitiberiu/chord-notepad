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

from chordnotepad.audio.ensemble_voicer import EnsembleVoicer
from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES, DEFAULT_WEIGHTS, EnsembleSpec, VoiceSpec
from chordnotepad.models.chord_notes import ChordNotes
from chordnotepad.chord.midi_converter import parse_note_to_semitone


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
    """The cheapest drop-sets sacrifice the fifth/extension, never colour/seventh."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = cn(['C', 'F', 'G', 'Bb', 'D'], intervals=[0, 5, 7, 10, 14])
    meta = voicer._build_meta(chord)
    # Tones other than the (root) bass, ranked drop-sets of size 1.
    to_place = [(pc, role) for pc, role in meta.tones if pc != 0]
    ranked = voicer._ranked_drop_sets(to_place, 1)

    # Cheapest two singletons drop the fifth G (pc 7) and the extension D (pc 2).
    # Omit weights are signed (negative); the cheapest to drop is the one
    # closest to zero: the fifth, then the extension.
    assert ranked[0] == (7,)   # fifth
    assert ranked[1] == (2,)   # extension
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


def _metas(voicer, symbols, key=None):
    chords = [_HELPER.compute_chord_notes(sym, key=key) for sym in symbols.split()]
    metas = [voicer._build_meta(c) for c in chords]
    voicer._apply_keyless_leading_tones(chords, metas)
    return metas


def test_without_a_key_the_leading_tone_comes_from_the_inferred_key():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    metas = _metas(voicer, 'C F G7 C Am Dm G7 C')
    assert all(m.ctx.leading_tone_pc == 11 for m in metas)  # B, in C major
    assert all(m.ctx.leading_tone_weight == 1.0 for m in metas)
    minor = _metas(voicer, 'Am Dm E7 Am F Dm E7 Am')
    assert all(m.ctx.leading_tone_pc == 8 for m in minor)   # G#, in A minor


def test_a_chromatic_passage_gets_no_inferred_leading_tone():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    metas = _metas(voicer, 'C B Bb A Ab G F# F')
    assert all(m.ctx.leading_tone_pc is None for m in metas[2:-2])


def test_a_secondary_dominant_has_its_own_leading_tone_without_a_key():
    # A7 -> Dm in C: C# is a leading tone for that change, B (the key's) too.
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    metas = _metas(voicer, 'C F C A7 Dm G7 C')
    assert metas[3].ctx.dominant_leading_tone_pc == 1
    a7, dm = voicer.voice_sequence([_HELPER.compute_chord_notes(s) for s in 'C F C A7 Dm G7 C'.split()])[3:5]
    for b in range(4):
        if a7[b] % 12 == 1:
            assert dm[b] - a7[b] == 1, (a7, dm)


def test_an_explicit_key_always_wins():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    metas = _metas(voicer, 'C A7 Dm G7 C', key='C')
    assert all(m.ctx.leading_tone_pc == 11 and m.ctx.leading_tone_weight == 1.0
               and m.ctx.dominant_leading_tone_pc is None for m in metas)


# ---------------------------------------------------------------------------
# Relaxation ladder
# ---------------------------------------------------------------------------
def test_impossible_spec_still_voices_every_chord():
    """A spec whose voices cannot be ordered still voices via the closed-stack fallback."""
    # Top voice range sits BELOW the bottom voice range: no ascending assignment
    # exists even after widening, so only stage 3 (the forced closed stack) fires.
    # from_dict refuses voices out of order; the voicer still copes with a
    # spec built without it.
    impossible = EnsembleSpec(
        name='impossible', label='impossible',
        voices=(VoiceSpec('top', 40, 43), VoiceSpec('bottom', 60, 63)),
        max_spacing=(3,),
    )
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


# ---------------------------------------------------------------------------
# Ensemble omission order: the fifth goes first; root, third and 7th stay
# ---------------------------------------------------------------------------
TWO_VOICE_SPEC = EnsembleSpec.from_dict('duo', {
    'label': 'Duo',
    'voices': [
        {'name': 'Upper', 'range': ['C4', 'G5']},
        {'name': 'Lower', 'range': ['C3', 'C4']},
    ],
    'max_spacing': [19],
})


@pytest.mark.parametrize('spec,chord,kept,dropped', [
    # G7 in three voices: G, B and F, not the rootless B D F.
    (BUILTIN_ENSEMBLES['ssa'], cn(['G', 'B', 'D', 'F'], intervals=[0, 4, 7, 10]),
     {7, 11, 5}, {2}),
    (BUILTIN_ENSEMBLES['ssa'], cn(['C', 'E', 'G', 'Bb'], intervals=[0, 4, 7, 10]),
     {0, 4, 10}, {7}),
    (BUILTIN_ENSEMBLES['ssa'], cn(['A', 'C', 'E', 'G'], intervals=[0, 3, 7, 10]),
     {9, 0, 7}, {4}),
    (BUILTIN_ENSEMBLES['ssa'], cn(['C', 'E', 'G', 'B'], intervals=[0, 4, 7, 11]),
     {0, 4, 11}, {7}),
    # C9 in four voices: C, E, Bb and D, not the rootless E G Bb D.
    (BUILTIN_ENSEMBLES['satb'], cn(['C', 'E', 'G', 'Bb', 'D'], intervals=[0, 4, 7, 10, 14]),
     {0, 4, 10, 2}, {7}),
    (BUILTIN_ENSEMBLES['ttbb'], cn(['G', 'B', 'D', 'F', 'A'], intervals=[0, 4, 7, 10, 14]),
     {7, 11, 5, 9}, {2}),
    # C9 in three voices: root, third and 7th.
    (BUILTIN_ENSEMBLES['ssa'], cn(['C', 'E', 'G', 'Bb', 'D'], intervals=[0, 4, 7, 10, 14]),
     {0, 4, 10}, {7, 2}),
    # A triad in two voices keeps the root and the third.
    (TWO_VOICE_SPEC, cn(['C', 'E', 'G']), {0, 4}, {7}),
    (TWO_VOICE_SPEC, cn(['A', 'C', 'E'], intervals=[0, 3, 7]), {9, 0}, {4}),
])
def test_ensembles_omit_the_fifth_first(spec, chord, kept, dropped):
    voicing = EnsembleVoicer(spec).voice_sequence([chord])[0]
    pcs = {m % 12 for m in voicing}
    assert kept <= pcs, f"{voicing} lacks {kept - pcs}"
    assert not (dropped & pcs), f"{voicing} keeps {dropped & pcs}"


def test_ensemble_omission_defaults_differ_from_the_piano():
    from chordnotepad.models.ensemble_spec import DEFAULT_WEIGHTS
    omit = DEFAULT_WEIGHTS['omit']
    # Cheapest to drop first: fifth, then extension, then root.
    assert omit['fifth'] > omit['extension'] > omit['root']
    assert omit['root'] > omit['color'] >= omit['third']
    assert omit['root'] > omit['seventh']


def test_user_omission_weights_still_win():
    """A saved voicing that tuned its own omission weights keeps them."""
    spec = EnsembleSpec.from_dict('mine', {
        'label': 'Mine',
        'voices': [
            {'name': 'S1', 'range': ['C4', 'A5']},
            {'name': 'S2', 'range': ['A3', 'F5']},
            {'name': 'A', 'range': ['F3', 'D5']},
        ],
        'max_spacing': [12, 12],
        'weights': {'omit': {'root': -1.0, 'fifth': -30.0}},
    })
    g7 = cn(['G', 'B', 'D', 'F'], intervals=[0, 4, 7, 10])
    pcs = {m % 12 for m in EnsembleVoicer(spec).voice_sequence([g7])[0]}
    assert 7 not in pcs and {11, 2, 5} <= pcs


# ---------------------------------------------------------------------------
# The same chord over another written bass must sound another bass
# ---------------------------------------------------------------------------
# Tibi, 2026-11-15: "C then C/E or C/E then C ... shouldn't sound the same."
# A plain chord may take any chord tone in the bass, so holding all four voices
# of the neighbouring C/E (four common tones) used to beat root position. The
# transition term weights['same_bass_penalty'] nudges it back. The expected
# basses below come from the chord symbols alone: a plain chord's written bass
# is its root, a slash chord's is the note after the slash.
from chordnotepad.audio.ensemble_voicer import EnsembleVoicerState, same_chord_other_bass
from chordnotepad.chord.helper import ChordHelper

_HELPER = ChordHelper()
BUILTIN_NAMES = ['satb', 'ttbb', 'ssa', 'quartet']


def parsed(symbol):
    notes = _HELPER.compute_chord_notes(symbol)
    assert notes is not None, symbol
    return notes


def _ctx(symbol):
    return EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])._build_meta(parsed(symbol)).ctx


@pytest.mark.parametrize('a, b, expected', [
    ('C', 'C/E', True),     # root position vs first inversion written out
    ('C', 'C/G', True),
    ('C/E', 'C/G', True),   # two slash basses
    ('C', 'C/Bb', True),    # a bass that isn't a chord tone still counts
    ('Am', 'Am/C', True),
    ('G7', 'G7/F', True),
    ('C#', 'Db/F', True),   # spelling doesn't matter, pitch classes do
    ('C', 'C', False),      # same bass
    ('C/E', 'C/E', False),
    ('C', 'C/C', False),    # C/C is written over its root
    ('C/E', 'C/Fb', False),  # E and Fb are one pitch class
    ('C', 'Cm/Eb', False),  # another chord
    ('C', 'C7/E', False),   # another chord (adds the 7th)
    ('C/E', 'Em', False),   # another root
    ('C', 'Am/C', False),   # another root over C
    ('C', 'Cadd9/E', False),
])
def test_same_chord_other_bass_definition(a, b, expected):
    assert same_chord_other_bass(_ctx(a), _ctx(b)) is expected
    assert same_chord_other_bass(_ctx(b), _ctx(a)) is expected


def test_unknown_context_never_counts():
    from chordnotepad.audio.ensemble_voicer import _ChordContext
    empty = _ChordContext(frozenset(), None)
    assert not same_chord_other_bass(empty, _ctx('C/E'))
    assert not same_chord_other_bass(_ctx('C/E'), empty)


@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
@pytest.mark.parametrize('progression', [
    ['C', 'C/E', 'Dm', 'Am', 'G'],
    ['C/E', 'C', 'Dm', 'Am', 'G'],
])
def test_plain_chord_keeps_its_root_next_to_its_slash_chord(spec_name, progression):
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name])
    voicings = voicer.voice_sequence([parsed(s) for s in progression])
    basses = dict(zip(progression[:2], (v[0] % 12 for v in voicings[:2])))
    assert basses == {'C': 0, 'C/E': 4}, voicings[:2]


def _bass_pairs():
    """Each of 7 roots x (major, minor, 7th) beside its /3rd and /5th, both orders."""
    pairs = []
    for root in 'CDEFGAB':
        for quality in ('', 'm', '7'):
            plain = root + quality
            notes = parsed(plain).notes
            for slash_note in (notes[1], notes[2]):
                slash = f'{plain}/{slash_note}'
                pairs.append((plain, slash))
                pairs.append((slash, plain))
    return pairs


def test_bass_pair_corpus_has_84_pairs():
    assert len(_bass_pairs()) == 84


@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
def test_no_pair_sounds_the_same_bass(spec_name):
    """Before the nudge: satb 44, ttbb 55, ssa 70, quartet 25 of 84 collided."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name])
    same = []
    for a, b in _bass_pairs():
        first, second = voicer.voice_sequence([parsed(a), parsed(b)])
        if first[0] % 12 == second[0] % 12:
            same.append((a, b, first, second))
    assert same == []


@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
def test_click_to_play_keeps_the_basses_apart(spec_name):
    """The greedy path (one chord after the previous) applies the same weight."""
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name])
    for symbol, bass in (('C/E', 4), ('C', 0), ('C/G', 7), ('C', None), ('C/E', 4)):
        lowest = voicer.chord_to_midi(parsed(symbol))[0] % 12
        if bass is None:
            assert lowest != 7  # after C/G, a plain C mustn't sound G
        else:
            assert lowest == bass, (symbol, lowest)


def test_zero_weight_brings_back_the_held_voicing():
    """The term is what moves the bass: switched off, C copies C/E.

    On the SATB voices with the default weights; the preset's own root-position
    inversion weights would move it too.
    """
    data = BUILTIN_ENSEMBLES['satb'].to_dict()
    data['weights'] = {'same_bass_penalty': 0.0}
    voicer = EnsembleVoicer(EnsembleSpec.from_dict('satb', data))
    first, second = voicer.voice_sequence([parsed('C'), parsed('C/E')])
    assert first == second and first[0] % 12 == 4


def test_penalty_is_added_once_in_the_transition():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    prev = (52, 60, 67, 72)  # E3 C4 G4 C5, as C/E
    cur = (52, 60, 67, 72)   # the same notes, as a plain C
    without = voicer._score_transition(prev, cur, _ctx('C/E'))
    with_ctx = voicer._score_transition(prev, cur, _ctx('C/E'), _ctx('C'))
    assert with_ctx - without == pytest.approx(DEFAULT_WEIGHTS["same_bass_penalty"])
    # Another bass note sounding: no penalty.
    root_pos = (48, 64, 67, 72)
    assert (voicer._score_transition(prev, root_pos, _ctx('C/E'), _ctx('C'))
            == voicer._score_transition(prev, root_pos, _ctx('C/E')))


def test_state_round_trips_the_chord_identity():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    voicer.chord_to_midi(parsed('C/E'))
    state = voicer.state
    assert (state.previous_root_pc, state.previous_bass_pc) == (0, 4)
    assert state.previous_chord_pcs == (0, 4, 7)
    rebuilt = EnsembleVoicerState.from_dict(state.to_dict())
    assert rebuilt == state


def test_old_state_dict_loads_without_identity():
    old = {'previous_voicing': [52, 60, 67, 72], 'previous_seventh_pcs': [],
           'previous_leading_tone_pc': None}
    state = EnsembleVoicerState.from_dict(old)
    assert state.previous_root_pc is None and state.previous_chord_pcs is None
    assert state.context.root_pc is None


# ---------------------------------------------------------------------------
# Background-texture terms: spacing threshold, outer leaps, middle band
# ---------------------------------------------------------------------------
def _two_voice(weights=None, low=('C3', 'C4'), high=('C4', 'C6')):
    """A two-voice spec whose ranges are easy to reason about."""
    return EnsembleSpec.from_dict('two', {
        'voices': [{'name': 'Hi', 'range': list(high)}, {'name': 'Lo', 'range': list(low)}],
        'max_spacing': [36],
        **({'weights': weights} if weights else {}),
    })


def test_middle_band_is_the_middle_half_of_each_range():
    # Hi C4-C6 (60-84): band 66-78. Off by default.
    plain = EnsembleVoicer(_two_voice())
    banded = EnsembleVoicer(_two_voice({'middle_range_penalty': -1.0}))
    for midi in range(60, 85):
        assert banded._comfort(midi, 1) - plain._comfort(midi, 1) == pytest.approx(
            -1.0 * (max(0, 66 - midi) + max(0, midi - 78)))
    assert banded._comfort(72, 1) == 0.0
    assert banded._comfort(65, 1) == -1.0


def test_middle_band_never_pulls_the_bottom_voice_up():
    # Lo C3-C4 (48-60): no floor, the ceiling of the middle half (57) stays.
    plain = EnsembleVoicer(_two_voice())
    banded = EnsembleVoicer(_two_voice({'middle_range_penalty': -1.0}))
    for midi in range(48, 61):
        assert banded._comfort(midi, 0) - plain._comfort(midi, 0) == pytest.approx(
            -1.0 * max(0, midi - 57))


def test_quartet_cello_keeps_the_verse_in_its_low_octave():
    # Test oracle: the middle band used to lift the whole line to C4 B3 A3.
    from chordnotepad.models.ensemble_spec import parse_note_name
    voicings = EnsembleVoicer(BUILTIN_ENSEMBLES['quartet']).voice_sequence(
        _song('C C/B Am Em/G F Fdim C/E Dm Dm/F C/E C/G F/A G/B C'))
    names = 'C3 B2 A2 G2 F2 F2 E2 D2 F2 E2 G2 A2 B2 C3'.split()
    assert [v[0] for v in voicings] == [parse_note_name(n) for n in names]


def test_outer_leap_penalty_scales_beyond_a_fifth_for_the_outer_voices_only():
    spec3 = lambda w: EnsembleSpec.from_dict('three', {
        'voices': [{'name': 'T', 'range': ['C4', 'C6']}, {'name': 'M', 'range': ['C3', 'C5']},
                   {'name': 'B', 'range': ['C2', 'C4']}],
        'max_spacing': [36, 36], **({'weights': w} if w else {})})
    off = EnsembleVoicer(spec3(None))
    on = EnsembleVoicer(spec3({'outer_leap_penalty': -1.0}))
    ctx = off._state.context
    prev = (36, 60, 72)
    for cur, extra in (((46, 60, 72), -3.0),   # bass leaps 10: 3 beyond a fifth
                       ((36, 60, 81), -2.0),   # top leaps 9
                       ((36, 70, 72), 0.0),    # inner voice leaps 10: not outer
                       ((43, 60, 72), 0.0)):   # a fifth is not beyond a fifth
        gain = on._score_transition(prev, cur, ctx) - off._score_transition(prev, cur, ctx)
        assert gain == pytest.approx(extra)


def test_upper_spacing_threshold_moves_where_wide_spacing_starts():
    four = lambda t: EnsembleVoicer(EnsembleSpec.from_dict('four', {
        'voices': [{'name': n, 'range': ['C2', 'C6']} for n in 'ABCD'],
        'max_spacing': [24, 24, 24], 'weights': {'upper_spacing_threshold': t}}))
    chord = cn(['C', 'E', 'G'])
    fifth, octave = four(7), four(12)
    meta = fifth._build_meta(chord)
    stack = (36, 52, 55, 64)    # gaps above the bass: 3 and 9
    # 9 is 2 beyond a fifth, within an octave.
    assert fifth._score_quality(stack, meta) - octave._score_quality(stack, meta) == \
        pytest.approx(-0.15 * 2)
    assert DEFAULT_WEIGHTS['upper_spacing_threshold'] == 7


def test_hidden_perfects_cost_only_with_a_leaping_top_voice():
    spec = lambda w: EnsembleSpec.from_dict('three', {
        'voices': [{'name': 'T', 'range': ['C4', 'C6']}, {'name': 'M', 'range': ['C3', 'C5']},
                   {'name': 'B', 'range': ['C2', 'C4']}],
        'max_spacing': [36, 36], **({'weights': w} if w else {})})
    off = EnsembleVoicer(spec({'hidden_perfect_penalty': 0.0}))
    on = EnsembleVoicer(spec(None))
    assert DEFAULT_WEIGHTS['hidden_perfect_penalty'] == -2.0
    ctx = off._state.context
    prev = (48, 64, 76)                 # C3 E4 E5
    gain = lambda cur: on._score_transition(prev, cur, ctx) - off._score_transition(prev, cur, ctx)
    assert gain((55, 64, 79)) == pytest.approx(-2.0)   # G3 G5: up into an octave, top leaps
    assert gain((50, 64, 81)) == pytest.approx(-2.0)   # D3 A5: up into a fifth, top leaps
    assert gain((53, 64, 77)) == pytest.approx(0.0)    # F3 F5: the top steps
    assert gain((43, 64, 79)) == pytest.approx(0.0)    # G2 G5: contrary motion


def test_a_close_interval_costs_per_semitone_below_its_low_interval_limit():
    spec = lambda w: EnsembleSpec.from_dict('three', {
        'voices': [{'name': 'T', 'range': ['C4', 'C6']}, {'name': 'M', 'range': ['C2', 'C5']},
                   {'name': 'B', 'range': ['B1', 'E3']}],
        'max_spacing': [36, 36], **({'weights': w} if w else {})})
    off = EnsembleVoicer(spec({'low_interval_limit_penalty': 0.0}))
    on = EnsembleVoicer(spec(None))
    assert DEFAULT_WEIGHTS['low_interval_limit_penalty'] == -2.0
    meta = off._build_meta(parsed('Am'))
    cost = lambda stack: on._score_quality(stack, meta) - off._score_quality(stack, meta)
    assert cost((45, 48, 76)) == pytest.approx(-6.0)   # A2 C3: a minor third, 3 below C3
    assert cost((47, 50, 76)) == pytest.approx(-2.0)   # B2 D3: 1 below C3, it fades in
    assert cost((48, 51, 76)) == pytest.approx(0.0)    # C3 Eb3: at the limit
    assert cost((45, 52, 72)) == pytest.approx(0.0)    # A2 E3: a fifth, above Bb1
    assert cost((57, 60, 76)) == pytest.approx(0.0)    # A3 C4: the third up where it is clear
    assert cost((45, 57, 60)) == pytest.approx(0.0)    # A2 A3: an octave is never charged
    assert cost((40, 45, 76)) == pytest.approx(-10.0)  # E2 A2: a fourth, 5 below A2


def test_a_quintet_puts_the_third_of_am_above_the_low_strings():
    # Tibi's String Quartet copy with a double bass added: Am after C and Dm
    # had the cello's C3 a minor third over the bass's A2.
    quintet = EnsembleSpec.from_dict('quintet', {
        'voices': [{'name': 'Violin I', 'range': [55, 88]}, {'name': 'Violin II', 'range': [55, 84]},
                   {'name': 'Viola', 'range': [48, 76]}, {'name': 'Cello', 'range': [36, 64]},
                   {'name': 'Double Bass', 'range': [35, 52]}],
        'max_spacing': [14, 14, 24, 12], 'allow_unisons': False,
        'weights': {'movement': [-0.4, -0.6, -0.4, -0.4, -0.15]}})
    voiced = EnsembleVoicer(quintet).voice_sequence([parsed(s) for s in ('C', 'Dm', 'Am', 'G')])
    from chordnotepad.audio.ensemble_voicer import _LOW_INTERVAL_LIMITS
    am = voiced[2]
    assert am[0] == 45 and am[1] - am[0] >= 7          # A2, then a fifth or wider
    assert all(lo >= _LOW_INTERVAL_LIMITS.get(hi - lo, 0) for lo, hi in zip(am, am[1:]))
    assert any(n % 12 == 0 and n >= 60 for n in am)    # the third (C) sounds from C4 up


# ---------------------------------------------------------------------------
# The bass plan
# ---------------------------------------------------------------------------
#: Tibi's six-voice strings (the setup the bass plan was written for).
STRINGS_SIX = EnsembleSpec.from_dict('strings6', {
    'voices': [
        {'name': 'Solo', 'range': ['G3', 'E6']}, {'name': 'Violin I', 'range': ['G3', 'E6']},
        {'name': 'Violin II', 'range': ['G3', 'C6']}, {'name': 'Viola', 'range': ['C3', 'E5']},
        {'name': 'Cello', 'range': ['C2', 'E4']}, {'name': 'Contrabass', 'range': ['B0', 'A2']},
    ],
    'max_spacing': [12, 14, 14, 24, 12],
})


def _song(symbols, key='C'):
    return [_HELPER.compute_chord_notes(s, key=key) for s in symbols.split()]


def test_bass_line_that_fits_the_range_stays_unbroken():
    # Test oracle: the written line fits the contrabass in one octave, and
    # voicing every voice at once used to jump A1 to G2.
    voicings = EnsembleVoicer(STRINGS_SIX).voice_sequence(_song('C C/B Am Em/G F Fdim C/E'))
    names = ['C2', 'B1', 'A1', 'G1', 'F1', 'F1', 'E1']
    from chordnotepad.models.ensemble_spec import parse_note_name
    assert [v[0] for v in voicings] == [parse_note_name(n) for n in names]


@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
def test_presets_voice_plain_chords_on_their_root_in_every_key(spec_name):
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name])
    keys = {'C': 'C G Am F Dm G7 C', 'G': 'G D Em C Am D7 G', 'Eb': 'Eb Bb Cm Ab Fm Bb7 Eb',
            'E': 'E B C#m A F#m B7 E'}
    for key, symbols in keys.items():
        chords = _song(symbols, key)
        for chord, voicing in zip(chords, voicer.voice_sequence(chords)):
            assert voicing[0] % 12 == parse_note_to_semitone(chord.root), (key, chord.root)


def test_a_planned_bass_never_leaves_out_more_than_the_chord_must():
    # SSA's alto reaches D5, but C5 under a C7 leaves no room for the Bb above
    # it (Soprano 1 stops at A5): the plan doesn't take a bass that drops the 7th.
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['ssa'])
    for symbols, key in (('Gm7 C7 Fmaj7 D7 Gm7 C7 F6', 'F'), ('Dm7 G7 Cmaj7 A7 Dm7 G7 C6', 'C')):
        chords = _song(symbols, key)
        for chord, voicing in zip(chords, voicer.voice_sequence(chords)):
            sounding = {m % 12 for m in voicing}
            for note, interval in zip(chord.notes, chord.intervals):
                if interval % 12 != 7:      # only a perfect fifth may go
                    assert parse_note_to_semitone(note) in sounding, (chord.root, voicing)


def test_planned_candidates_all_sit_on_the_planned_bass():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    chord = parsed('Am')
    meta = voicer._build_meta(chord)
    for midi in voicer._bass_options(meta):
        stacks = voicer._candidates(chord, meta, midi)
        assert all(stack[0] == midi for stack in stacks)
    # The plan's options are every chord tone's octaves in the bass's range.
    assert voicer._bass_options(meta) == [40, 45, 48, 52, 57, 60]   # E2 A2 C3 E3 A3 C4


def test_unfit_chord_falls_back_to_the_ladder():
    # Nothing fits a two-voice spec whose voices can't be a third apart.
    spec = EnsembleSpec.from_dict('tight', {
        'voices': [{'name': 'Hi', 'range': ['C4', 'D4']}, {'name': 'Lo', 'range': ['C4', 'D4']}],
        'max_spacing': [1]})
    voicer = EnsembleVoicer(spec)
    chords = [parsed('E'), parsed('F#')]
    assert voicer._plan_bass(chords, [voicer._build_meta(c) for c in chords]) == [None, None]
    assert all(len(v) == 2 for v in voicer.voice_sequence(chords))


@pytest.mark.parametrize('spec_name', ['satb', 'quartet'])
def test_root_position_dominant_seventh_resolves_its_seventh(spec_name):
    # Both chords on their roots: the incomplete form (no fifth) lets F fall to E.
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name])
    g7, c = voicer.voice_sequence(_song('G7 C'))
    assert g7[0] % 12 == 7 and c[0] % 12 == 0
    for before, after in zip(g7, c):
        if before % 12 == 5:
            assert before - after in (1, 2)


def test_a_diminished_fifth_is_never_left_out():
    # Bm7b5's F defines it: the incomplete form drops only a perfect fifth.
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    meta = voicer._build_meta(parsed('Bm7b5'))
    plans = voicer._pc_plans(meta)
    assert plans
    for bass, upper in plans:
        assert 5 in upper or bass == 5
    # A G7's perfect fifth may go (G G B F), so its plans include one without D.
    g7_plans = voicer._pc_plans(voicer._build_meta(parsed('G7')))
    assert any(bass == 7 and 2 not in upper for bass, upper in g7_plans)


@pytest.mark.parametrize('progression', [
    'Bm7b5 E7 Am', 'Dm7b5 G7 Cm', 'C7#5 F', 'C7b5 F', 'Caug F', 'G7#5b9 Cm9'])
@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
def test_an_altered_fifth_is_never_left_out(spec_name, progression):
    # Without its b5 Bm7b5 is Bm7, and without its #5 C7#5 is C7: with fewer
    # voices than tones (SSA) another tone goes, never the altered fifth.
    chords = _song(progression)
    voicings = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name]).voice_sequence(chords)
    for chord, voicing in zip(chords, voicings):
        root = parse_note_to_semitone(chord.root)
        altered = {(root + iv) % 12 for iv in chord.intervals if iv in (6, 8)}
        assert altered <= {m % 12 for m in voicing}, (chord.root, chord.intervals, voicing)


@pytest.mark.parametrize('symbol, named, stacked', [
    ('G13', 4, 9), ('Am11', 2, 11), ('D13', 11, 4)])
def test_a_stacked_extension_goes_before_the_named_one(symbol, named, stacked):
    # G13 for four voices: drop the fifth and the 9th the name only stacks
    # in, keep the 13th it spells (G B F E).
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    meta = voicer._build_meta(parsed(symbol))
    root = meta.root_pc
    to_place = [(pc, role) for pc, role in meta.tones if pc != root]
    best = voicer._ranked_drop_sets(to_place, len(to_place) - 3, meta.omit_cost)[0]
    assert stacked in best and named not in best
    assert meta.omit_cost[stacked] == pytest.approx(0.5 * meta.omit_cost[named])


@pytest.mark.parametrize('spec_name', BUILTIN_NAMES)
def test_an_added_ninth_is_kept_over_the_fifth(spec_name):
    # Without its 9 a Cadd9 is a plain triad: three voices leave out the fifth.
    for symbol in ('Cadd9', 'Gadd9', 'Dadd9', 'Fadd9'):
        chord = parsed(symbol)
        voicing = EnsembleVoicer(BUILTIN_ENSEMBLES[spec_name]).voice_sequence([chord])[0]
        root = parse_note_to_semitone(chord.root)
        assert (root + 2) % 12 in {m % 12 for m in voicing}, (symbol, voicing)


def test_a_diminished_seventh_may_still_leave_out_its_fifth():
    # Any three tones of a dim7 sound the same chord: SSA keeps F#dim7's root
    # (the line F F# G) and leaves out the C.
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES['ssa'])
    f, dim7, g = voicer.voice_sequence(_song('F F#dim7 C/G'))
    assert dim7[0] % 12 == 6
    assert 0 not in {m % 12 for m in dim7}


def test_a_doubled_bass_line_may_move_in_octaves_with_five_voices_or_more():
    six = EnsembleVoicer(STRINGS_SIX)
    four = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
    ctx = six._state.context
    # Contrabass and cello both on the bass, C to F in octaves; the rest hold.
    prev6, cur6 = (36, 48, 55, 64, 67, 72), (41, 53, 55, 64, 67, 72)
    assert six._score_transition(prev6, cur6, ctx) == pytest.approx(
        six._motion_score(0, 6, 5) + six._motion_score(1, 6, 5)
        + 4 * six._motion_score(2, 6, 0))
    # Octaves between two voices off the bass are still parallels.
    prev_off, cur_off = (36, 52, 55, 64, 67, 72), (36, 53, 55, 65, 67, 72)
    assert (six._score_transition(prev_off, cur_off, ctx)
            <= DEFAULT_WEIGHTS['parallel_perfect_penalty'] + 10)
    # Four voices: bass and tenor doubling the root in octaves is a fault.
    prev4, cur4 = (48, 60, 64, 67), (53, 65, 64, 67)
    assert (four._score_transition(prev4, cur4, ctx)
            <= DEFAULT_WEIGHTS['parallel_perfect_penalty'] + 10)


def test_a_held_bass_doesnt_turn_a_plain_chord_into_an_inversion():
    # Default weights (a custom ensemble): first inversion -1.5 used to lose to
    # a held bass (+1.5), so Am F sounded Am F/A on six strings.
    voicings = EnsembleVoicer(STRINGS_SIX).voice_sequence(_song('C G Am F C G Am F'))
    assert [v[0] % 12 for v in voicings] == [0, 7, 9, 5, 0, 7, 9, 5]
