"""Acoustic open-chord fixtures for the standard-tuning guitar picker.

Each fixture voices a chord, alone or inside the progression that gives it its
context, through ``GuitarChordPicker('standard').voice_sequence_details`` (the
whole-song path the chord sheet and Play use) and checks the pick against the
shapes a typical acoustic player uses: a set of acceptable fingerings, or one
that must not come back. Fingerings are written low E to high e, ``x`` muted.

These are test oracles only. The engine never sees a shape list: its picks come
from the search and the weights. A fixture marked ``xfail(strict=True)`` fails
on purpose until a tuning step makes it pass; that step removes the mark.
"""

from functools import lru_cache

import pytest

from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.chord.helper import ChordHelper

_HELPER = ChordHelper()


def _parse(shape):
    """'x32010' -> [-1, 3, 2, 0, 1, 0]; frets above 9 are written '(10)'."""
    frets, i = [], 0
    while i < len(shape):
        c = shape[i]
        if c == 'x':
            frets.append(-1)
            i += 1
        elif c == '(':
            j = shape.index(')', i)
            frets.append(int(shape[i + 1:j]))
            i = j + 1
        else:
            frets.append(int(c))
            i += 1
    return frets


def _show(frets):
    return ''.join('x' if f < 0 else str(f) if f < 10 else f'({f})' for f in frets)


@lru_cache(maxsize=None)
def _voice(symbols):
    chords = []
    for symbol in symbols:
        chord_notes = _HELPER.compute_chord_notes(symbol)
        assert chord_notes is not None, f"could not resolve {symbol}"
        chords.append(chord_notes)
    picker = GuitarChordPicker('standard')
    details = picker.voice_sequence_details(chords)
    return tuple(tuple(d.fingering) for d in details), tuple(chords)


def _fixture(name, sequence, index=None, ok=None, forbid=None, xfail=None):
    """One pick check: ``sequence`` voiced whole, the chord at ``index``
    (default: the last) must be one of ``ok`` and none of ``forbid``.
    ``ok`` may also be a callable judging the fingering."""
    symbols = tuple(sequence.split())
    if index is None:
        index = len(symbols) - 1
    marks = [pytest.mark.xfail(strict=True, reason=xfail)] if xfail else []
    return pytest.param(symbols, index, ok, forbid, id=name, marks=marks)


# Must keep passing.
KEEP = [
    _fixture('C', 'C', ok={'x32010'}),
    _fixture('G', 'G', ok={'320003', '320033'}),
    _fixture('Am', 'Am', ok={'x02210'}),
    _fixture('Em', 'Em', ok={'022000'}),
    _fixture('D', 'D', ok={'xx0232'}),
    _fixture('A', 'A', ok={'x02220'}),
    _fixture('E', 'E', ok={'022100'}),
    _fixture('Dm', 'Dm', ok={'xx0231'}),
    _fixture('F', 'F', ok={'133211'}),
    _fixture('B7', 'B7', ok={'x21202'}),
    _fixture('A7', 'A7', ok={'x02020'}),
    _fixture('E7', 'E7', ok={'020100'}),
    _fixture('G7', 'G7', ok={'320001'}),
    _fixture('Cmaj7', 'Cmaj7', ok={'x32000'}),
    _fixture('Bm', 'Bm', ok={'x24432'}),
    _fixture('F#m', 'F#m', ok={'244222'}),
    _fixture('Bb', 'Bb', ok={'x13331'}),
    _fixture('G/B', 'G/B', ok={'x20003', 'x20033', 'x2000x'}),
    _fixture('F/A', 'F/A', ok={'x03211'}),
    _fixture('Bm/D after Bm', 'Bm Bm/D', ok={'xx0432'}),
    _fixture('Fsus2', 'Fsus2', ok={'xx3011', '133011'}),
    _fixture('Fsus2 in colour, key F', 'Fadd9 Fsus2 Fsus4 F6 Dm9 Bbmaj9', index=1,
             ok={'xx3011', '133011'}),
    _fixture('C#m/E', 'C#m/E', ok={'xx2120'}),
    _fixture('C#m/E in the verse, key A',
             'A A/G# F#m C#m/E D Ddim A/C# Bm Bm/D A/C# A/E D/F# E/G# A', index=3,
             ok={'xx2120'}),
    _fixture('Fmaj7', 'Fmaj7', ok={'xx3210', '132210'}),
]

# Should flip to passing; each is xfail until the step that fixes it.
FLIP = [
    _fixture('C/G', 'C/G', ok={'332010', '3x2010'}),
    _fixture('D/F#', 'D/F#', ok={'2x0232', '200232'},
             xfail="2002xx still 1.65 ahead of 2x0232; more low mud breaks DADGAD's 400200, "
                   "a cheaper damped mute breaks Fsus2/Esus2"),
    _fixture('E/G#', 'E/G#', ok={'4x2100'},
             xfail="422400 (full, right bass) leads by 4.2: 4x2100's 1-to-4 span costs 5"),
    _fixture('Am/G', 'Am/G', ok={'3x2210', '3x2010'},
             xfail="302010 leads by 3.2 on its extra open string and finger"),
    _fixture('F#dim7', 'F#dim7', ok={'2x121x'},
             xfail="201212 leads by 2.8 on two more strings"),
    _fixture('Dm/F after Dm', 'Dm Dm/F', ok={'xx3231', '1x0231'}),
    _fixture('C6 in colour, key C', 'Cadd9 Csus2 Csus4 C6 Am9 Fmaj9', index=3,
             ok={'x32210'}),
    _fixture('Gadd9', 'Gadd9', ok={'320203', '3x0203'},
             xfail="300003 leads 3x0203 by 4.2 on open strings and fingers"),
    _fixture('Csus4 after Cadd9, colour', 'Cadd9 Csus2 Csus4 C6 Am9 Fmaj9', index=2,
             ok={'x33011', 'x33013'}),
    _fixture('F/C in walk slash, key C', 'C/E F G/B C F/C G/D', index=4,
             ok={'x33211'}),
    _fixture('Aaug in dim/aug, key A', 'Adim7 A#dim7 Aaug Dm6', index=2,
             ok={'x03221'}),
    _fixture('Gm/Bb', 'Gm/Bb', ok={'x10033'}),
]

# Any pick but the forbidden one.
FORBID = [
    _fixture('Ab after Eb/G, walk slash, key Eb', 'Eb/G Ab Bb/D Eb Ab/Eb Bb/F', index=1,
             forbid={'43151x'}),
    _fixture('Eb in pop, key Bb', 'Bb F Gm Eb', forbid={'xx13x3'}),
    _fixture('Eb in andalusian, key Bb', 'Gm F Eb D', index=2, forbid={'xx13x3'}),
    _fixture('Bb/F', 'Bb/F', forbid={'110xxx'}),
    _fixture('Bb/F in walk slash, key F', 'F/A Bb C/E F Bb/F C/G', index=4,
             forbid={'110xxx'}),
    _fixture('B/D# in walk slash, key E', 'E/G# A B/D# E A/E B/F#', index=2,
             forbid={'xx1x02'},
             xfail="xx1x02 is 0.4 behind x6440x alone; staying in open position between A "
                   "and E wins on movement"),
    _fixture('Esus2 in colour, key E', 'Eadd9 Esus2 Esus4 E6 C#m9 Amaj9', index=1,
             forbid={'xx2x02'}),
]


def _clean_f_bass(frets, chord_notes):
    """Fdim: any shape with F in the bass, every tone, and no buried mute."""
    tuning = GuitarChordPicker('standard').tuning_midi
    sounding = [s for s, f in enumerate(frets) if f >= 0]
    pitches = sorted(tuning[s] + frets[s] for s in sounding)
    pcs = {p % 12 for p in pitches}
    want = {GuitarChordPicker._normalize_note(n) for n in chord_notes.notes}
    buried = any(frets[s] < 0 for s in range(sounding[0] + 1, sounding[-1]))
    return pitches[0] % 12 == 5 and want <= pcs and not buried


_LINE1 = 'C C/B Am Em/G F Fdim C/E'
_LINE2 = 'Dm Dm/F C/E C/G F/A G/B C'

# The Quick Start example's Duration verse (examples/01_quick_start.txt), each
# line voiced as one sequence.
SONG = [
    _fixture('verse 1: C', _LINE1, 0, ok={'x32010'}),
    _fixture('verse 1: C/B', _LINE1, 1, ok={'x22010'}),
    _fixture('verse 1: Am', _LINE1, 2, ok={'x02210'}),
    _fixture('verse 1: Em/G', _LINE1, 3, ok={'322000', '3x2000'}),
    _fixture('verse 1: F', _LINE1, 4, ok={'133211'}),
    _fixture('verse 1: Fdim', _LINE1, 5, ok=_clean_f_bass),
    _fixture('verse 1: C/E', _LINE1, 6, ok={'032010'}),
    _fixture('verse 2: Dm', _LINE2, 0, ok={'xx0231'}),
    _fixture('verse 2: Dm/F', _LINE2, 1, ok={'xx3231', '1x0231'}),
    _fixture('verse 2: C/E', _LINE2, 2, ok={'032010'}),
    _fixture('verse 2: C/G', _LINE2, 3, ok={'332010', '3x2010'}),
    _fixture('verse 2: F/A', _LINE2, 4, ok={'x03211'}),
    _fixture('verse 2: G/B', _LINE2, 5, ok={'x20003', 'x20033', 'x2000x'}),
    _fixture('verse 2: C', _LINE2, 6, ok={'x32010'}),
]


@pytest.mark.parametrize('symbols,index,ok,forbid', KEEP + FLIP + FORBID + SONG)
def test_pick(symbols, index, ok, forbid):
    fingerings, chords = _voice(symbols)
    frets = list(fingerings[index])
    shape = _show(frets)
    context = ' '.join(symbols)
    if callable(ok):
        assert ok(frets, chords[index]), f"{symbols[index]} = {shape} in {context}"
    elif ok is not None:
        assert shape in ok, f"{symbols[index]} = {shape}, want one of {sorted(ok)} in {context}"
    if forbid is not None:
        assert shape not in forbid, f"{symbols[index]} = {shape} (forbidden) in {context}"


_ALL_SEQUENCES = sorted({p.values[0] for p in KEEP + FLIP + FORBID + SONG})


@pytest.mark.parametrize('symbols', _ALL_SEQUENCES, ids=' '.join)
def test_bass_and_tones(symbols):
    """Music theory first: every pick sounds the written bass (the slash note,
    else the root) lowest, and drops no tone but a plain perfect 5th of a
    chord of four or more tones."""
    fingerings, chords = _voice(symbols)
    tuning = GuitarChordPicker('standard').tuning_midi
    norm = GuitarChordPicker._normalize_note
    for symbol, frets, chord in zip(symbols, fingerings, chords):
        pitches = sorted(tuning[s] + f for s, f in enumerate(frets) if f >= 0)
        bass = norm(chord.bass_note) if chord.bass_note else norm(chord.root)
        assert pitches[0] % 12 == bass, f"{symbol} = {_show(frets)}: wrong bass"
        want = {norm(n) for n in chord.notes}
        missing = want - {p % 12 for p in pitches}
        if len(want) <= 4:
            fifth = (norm(chord.root) + 7) % 12
            assert missing <= ({fifth} if len(want) == 4 else set()), (
                f"{symbol} = {_show(frets)} drops {sorted(missing)}")
