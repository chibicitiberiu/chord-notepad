"""Fuzz tests for transpose: random chords, songs and regions.

Whatever the input, a chord the editor reads as valid must come out of
transpose as a valid chord with its notes moved by the shift (as the editor
and playback read it), and nothing else in the text may change but spacing.
The exhaustive grid is in test_transpose_exhaustive.py; this explores
combinations the grid doesn't list (alterations, parentheses, durations,
mixed lines, directives and regions).
"""

import re

from hypothesis import assume, given, settings, strategies as st

from chord.detector import ChordDetector
from services.transpose_service import transpose_text
from tests.test_transpose_exhaustive import bad_spellings, notes_of

_LETTERS = 'CDEFGAB'
_EUROPEAN = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa', 'G': 'Sol', 'A': 'La', 'B': 'Si'}
_ACCIDENTALS = ['', '', '', '#', 'b', '♯', '♭']
_QUALITIES = [
    '', '', 'm', '7', 'maj7', 'm7', '6', 'm6', '9', 'm9', 'maj9', '11', '13', 'dim', 'dim7',
    'aug', 'sus2', 'sus4', '7sus4', 'add9', 'madd9', '5', '69', '7b9', '7#9', '7b5', '7#5',
    'm7b5', '9#11', '13b9', 'maj7#11', 'add#11', 'addb6', 'addb13', '°', '°7', 'ø', 'ø7',
    '+', 'Δ', '-', '-7', 'mM7', 'm(maj7)', '7(b9)', '(no3)', 'min', 'mi7', 'M7',
]


@st.composite
def roots(draw, notation):
    letter = draw(st.sampled_from(_LETTERS))
    name = _EUROPEAN[letter] if notation == 'european' else letter
    return name + draw(st.sampled_from(_ACCIDENTALS))


@st.composite
def chords(draw, notation):
    """A chord symbol: root (either case), quality, maybe a slash bass and a
    duration. Not every draw is a valid chord; the tests keep the valid ones."""
    root = draw(roots(notation))
    if draw(st.booleans()):
        root = root.lower()
    chord = root + draw(st.sampled_from(_QUALITIES))
    if draw(st.integers(0, 3)) == 0:
        chord += '/' + draw(roots(notation))
    if draw(st.integers(0, 5)) == 0:
        chord += draw(st.sampled_from(['*2', '*0.5', '*4']))
    return chord


notations = st.sampled_from(['american', 'european'])
shifts = st.integers(-11, 11).filter(bool)


def absolute_chords(text, notation):
    """The valid absolute chords in ``text``, in order, as the editor reads them."""
    return [c for c in ChordDetector(notation=notation).detect_chords_in_text(text)
            if c.is_valid and not c.is_relative and not c.is_rest]


def moved(chord, shift, notation):
    notes = notes_of(chord, notation)
    return None if notes is None else sorted((pc + shift) % 12 for pc in notes)


@settings(max_examples=1500)
@given(st.data(), notations, shifts)
def test_a_random_chord_transposes_to_a_valid_chord_with_its_notes_moved(data, notation, shift):
    chord = data.draw(chords(notation))
    found = absolute_chords(chord, notation)
    assume(len(found) == 1 and found[0].chord + chord[len(found[0].chord):] == chord)
    assume(notes_of(found[0].chord, notation) is not None)

    text = transpose_text(chord + '\n', shift, notation)
    result = absolute_chords(text, notation)
    assert len(result) == 1, f"{chord} {shift:+d} -> {text!r}"
    assert notes_of(result[0].chord, notation) == moved(found[0].chord, shift, notation), (
        f"{chord} {shift:+d} -> {result[0].chord}")
    assert result[0].chord[0].islower() == chord[0].islower()
    # The duration and anything else after the chord stay as written.
    assert text.strip().endswith(chord[len(found[0].chord):])


_LYRICS = ['Amazing grace how sweet the sound', 'la la la', 'I once was lost',
           'and here we go again', 'Do you hear the people sing', 'a b c', '']
_DIRECTIVES = ['{bpm: 90}', '{time: 3/4}', '{label: verse}', '{loop: verse 2}', '{title: x}']


@st.composite
def songs(draw, notation):
    """A song: chord lines (chords, roman numerals, NC, inline directives),
    lyric lines, {key} and other directives, comments, '.' text lines."""
    lines = []
    for _ in range(draw(st.integers(1, 12))):
        kind = draw(st.integers(0, 6))
        if kind <= 2:
            items = []
            for _ in range(draw(st.integers(1, 6))):
                pick = draw(st.integers(0, 9))
                if pick == 0:
                    items.append(draw(st.sampled_from(['I', 'IV', 'V7', 'vi', 'ii7', 'bVII'])))
                elif pick == 1:
                    items.append('NC')
                else:
                    items.append(draw(chords(notation)))
            spaces = draw(st.lists(st.integers(1, 6), min_size=len(items), max_size=len(items)))
            line = ''.join(item + ' ' * n for item, n in zip(items, spaces)).rstrip()
            if draw(st.integers(0, 4)) == 0:
                line += ' // ' + draw(st.sampled_from(['C G', 'comment', 'Do Re']))
            lines.append(line)
        elif kind == 3:
            lines.append(draw(st.sampled_from(_LYRICS)))
        elif kind == 4:
            key = draw(roots(notation)) + draw(st.sampled_from(['', 'm']))
            lines.append('{key: %s}' % key)
        elif kind == 5:
            lines.append(draw(st.sampled_from(_DIRECTIVES)))
        else:
            lines.append(draw(st.sampled_from(['.C G Am', '// C G', '. la la'])))
    return '\n'.join(lines) + '\n'


def _without_spacing(text):
    return re.sub(r'[ \-]', '', text)


@settings(max_examples=400)
@given(st.data(), notations, shifts)
def test_a_random_song_transposes_every_chord_and_nothing_else(data, notation, shift):
    song = data.draw(songs(notation))
    before = absolute_chords(song, notation)
    assume(all(notes_of(c.chord, notation) is not None for c in before))

    text = transpose_text(song, shift, notation)
    after = absolute_chords(text, notation)
    assert len(after) == len(before), f"{song!r} {shift:+d} -> {text!r}"
    for old, new in zip(before, after):
        assert notes_of(new.chord, notation) == moved(old.chord, shift, notation), (
            f"{old.chord} {shift:+d} -> {new.chord} in {text!r}")

    # Spelled by a {key}, a detected key or the plain table, a moved chord is
    # never E#, B#, Cb, Fb or a double accidental.
    assert not bad_spellings(text, notation), f"{song!r} {shift:+d} -> {text!r}"

    # Roman numerals, NC, comments, lyrics and other directives are as they
    # were (spacing aside: a longer chord may push a lyric along with "-").
    for old_line, new_line in zip(song.split('\n'), text.split('\n')):
        old_chords = [c.chord for c in absolute_chords(old_line, notation)]
        if old_chords or '{key' in old_line:
            continue
        # A lyric line, "." lines included, may be stretched under a chord
        # line whose chords grew.
        assert _without_spacing(new_line) == _without_spacing(old_line)

    # Every {key} is still a valid key directive.
    from services.song_parser_service import SongParserService
    keys = [d for d in SongParserService().parse_directives(text) if d.type.name == 'KEY']
    assert all(d.is_valid for d in keys), text

    # And back again gives the same notes.
    back = absolute_chords(transpose_text(text, -shift, notation), notation)
    assert [notes_of(c.chord, notation) for c in back] == [
        notes_of(c.chord, notation) for c in before]


@settings(max_examples=300)
@given(st.data(), notations, shifts)
def test_a_region_transposes_only_the_chords_it_touches(data, notation, shift):
    song = data.draw(songs(notation))
    before = absolute_chords(song, notation)
    assume(before and all(notes_of(c.chord, notation) is not None for c in before))
    start = data.draw(st.integers(0, len(song)))
    end = data.draw(st.integers(start, len(song)))

    text = transpose_text(song, shift, notation, region=(start, end))
    after = absolute_chords(text, notation)
    assert len(after) == len(before)
    for old, new in zip(before, after):
        inside = old.start < end and old.end > start
        expected = moved(old.chord, shift if inside else 0, notation)
        assert notes_of(new.chord, notation) == expected, (
            f"{old.chord} ({'in' if inside else 'out of'} {start}-{end}) -> {new.chord}")
