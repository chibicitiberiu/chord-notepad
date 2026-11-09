"""Every chord quality sounds the notes music theory says it has.

The other chord tests compare the app with itself (transposed against
source, converted against source), so a quality read wrong everywhere, such
as ``C-7`` once read as C flat, passes them. This table is written from
theory, independently of the code: semitones above the root for each way
of writing a quality the guide documents or the parser reads, and
(OMITTED) each with its fifth or third left out. Each is checked for every root
spelling, in American and European, upper and lower case where that means
minor, and with a slash bass, against what playback resolves
(``ChordHelper.compute_chord_notes``) and the editor's note lookup
(``ChordHelper.get_notes``).

Deliberate voicing choices (help/reference.rst, the curated qualities in
chord.helper): an 11th chord (maj11 too) leaves out the 3rd, and a 13th
chord leaves out the 11th.

The chord identifier's fuzz test (test_chord_identifier_fuzz) takes its
notes from these tables too.
"""

import pytest

from chord.helper import ChordHelper

_HELPER = ChordHelper()

MAJOR = (0, 4, 7)
MINOR = (0, 3, 7)

#: Spellings of each quality and its intervals above the root.
REFERENCE = {
    # triads
    ('', 'maj', 'M'): MAJOR,
    ('m', 'min', 'mi', '-'): MINOR,
    ('dim', '°', 'm(b5)'): (0, 3, 6),
    ('aug', '+', '(#5)'): (0, 4, 8),
    ('sus4', 'sus', '4'): (0, 5, 7),        # C4 as guitar books write it
    ('sus2', '2'): (0, 2, 7),
    ('5',): (0, 7),
    # sixths and sevenths
    ('6',): (0, 4, 7, 9),
    ('m6', '-6', 'min6'): (0, 3, 7, 9),
    ('69', '6/9'): (0, 4, 7, 9, 2),
    ('7', 'dom7'): (0, 4, 7, 10),
    ('maj7', 'M7', 'Δ', 'Δ7'): (0, 4, 7, 11),
    ('m7', '-7', 'min7', 'mi7'): (0, 3, 7, 10),
    ('mM7', 'm(maj7)', 'mmaj7'): (0, 3, 7, 11),
    ('dim7', '°7'): (0, 3, 6, 9),
    ('m7b5', 'ø', 'ø7', '-7b5', 'm7-5', 'm7(b5)'): (0, 3, 6, 10),
    ('aug7', '+7', '7#5'): (0, 4, 8, 10),
    ('maj7#5', 'augmaj7', 'maj7(#5)'): (0, 4, 8, 11),
    ('7sus4', '7sus'): (0, 5, 7, 10),
    ('7sus2', '9sus2'): (0, 2, 7, 10),      # in 9sus2 the 9th is the sus2
    ('7b5', '7-5'): (0, 4, 6, 10),
    # extensions
    ('9',): (0, 4, 7, 10, 2),
    ('m9', '-9', 'min9'): (0, 3, 7, 10, 2),
    ('maj9', 'M9', 'Δ9'): (0, 4, 7, 11, 2),
    ('11',): (0, 7, 10, 2, 5),
    ('m11', '-11'): (0, 3, 7, 10, 2, 5),
    ('13', '7(9,13)'): (0, 4, 7, 10, 2, 9),
    ('m13', '-13'): (0, 3, 7, 10, 2, 9),
    ('maj13', 'M13'): (0, 4, 7, 11, 2, 9),
    ('maj11', 'M11'): (0, 7, 11, 2, 5),
    ('maj13#11',): (0, 4, 7, 11, 2, 6, 9),
    # alterations
    ('7b9', '7-9', '7(b9)'): (0, 4, 7, 10, 1),
    ('7#9',): (0, 4, 7, 10, 3),
    ('7#11',): (0, 4, 7, 10, 6),
    ('9#11', '9(#11)', '7(9,#11)'): (0, 4, 7, 10, 2, 6),
    ('maj7#11', 'M7#11', 'maj7(#11)'): (0, 4, 7, 11, 6),
    ('13b9', '13-9', '7(b9,13)'): (0, 4, 7, 10, 1, 9),
    ('13#9',): (0, 4, 7, 10, 3, 9),
    ('13#11',): (0, 4, 7, 10, 2, 6, 9),
    ('13b5',): (0, 4, 6, 10, 2, 9),
    ('11b9',): (0, 7, 10, 1, 5),
    ('7b9b13',): (0, 4, 7, 10, 1, 8),
    ('7#9b13', '7(#9,b13)'): (0, 4, 7, 10, 3, 8),
    ('7b9#11', '7(b9,#11)'): (0, 4, 7, 10, 1, 6),
    ('7#9#11',): (0, 4, 7, 10, 3, 6),
    ('7#5#9', '7#9#5'): (0, 4, 8, 10, 3),
    ('7b5b9', '7b9b5'): (0, 4, 6, 10, 1),
    ('7b5#9', '7#9b5'): (0, 4, 6, 10, 3),
    ('7#5b9', '7b9#5', 'aug7b9'): (0, 4, 8, 10, 1),
    ('7b9#9', '7(b9,#9)'): (0, 4, 7, 10, 1, 3),
    ('m7b5b9', 'm7b9b5', 'm7b5(b9)'): (0, 3, 6, 10, 1),
    ('9b5', '9-5'): (0, 4, 6, 10, 2),
    ('9#5', 'aug9'): (0, 4, 8, 10, 2),
    ('7b13', '7-13'): (0, 4, 7, 10, 8),
    ('9sus4', '9sus'): (0, 5, 7, 10, 2),
    ('13sus4',): (0, 5, 7, 10, 2, 9),
    ('maj7b5', 'maj7(b5)'): (0, 4, 6, 11),
    ('m7#5',): (0, 3, 8, 10),
    ('mM9', 'm(maj9)', 'mmaj9'): (0, 3, 7, 11, 2),
    ('m69',): (0, 3, 7, 9, 2),
    ('m11b5',): (0, 3, 6, 10, 2, 5),
    ('maj9#11',): (0, 4, 7, 11, 2, 6),
    ('dim(maj7)',): (0, 3, 6, 11),
    ('dim(maj9)',): (0, 3, 6, 11, 2),
    ('dimm9',): (0, 3, 6, 10, 2),
    ('dim7#9',): (0, 3, 6, 9, 3),           # the #9 sounds as the minor 3rd
    ('maj7#5(9)',): (0, 4, 8, 11, 2),
    ('6b5',): (0, 4, 6, 9),
    ('(b5)', 'majb5'): (0, 4, 6),
    ('sus2sus4', 'sus24'): (0, 2, 5, 7),
    ('add13',): (0, 4, 7, 9),
    ('6add9',): (0, 4, 7, 9, 2),
    # added tones
    ('add9', 'add2', 'Madd9', 'majadd9'): (0, 4, 7, 2),
    ('madd9', 'm(add9)'): (0, 3, 7, 2),
    ('add11', 'add4', 'Madd4', 'majadd4'): (0, 4, 7, 5),
    ('add#11',): (0, 4, 7, 6),
    ('addb5', '(addb5)'): (0, 4, 7, 6),     # "add" keeps the 5th
    ('add#5',): (0, 4, 7, 8),
    ('addb6', 'addb13'): (0, 4, 7, 8),
    ('addb9',): (0, 4, 7, 1),
    ('add#9',): (0, 4, 7, 3),
    ('madd11', 'madd4'): (0, 3, 7, 5),
    ('madd#11',): (0, 3, 7, 6),
    ('maddb6',): (0, 3, 7, 8),
    ('maddb9',): (0, 3, 7, 1),
    ('sus4add9', 'sus4add2'): (0, 5, 7, 2),
    ('7add11',): (0, 4, 7, 10, 5),
    ('7add13',): (0, 4, 7, 10, 9),
    ('m7add11',): (0, 3, 7, 10, 5),
    ('maj7add11', 'M7add11'): (0, 4, 7, 11, 5),
    ('maj7add13', 'M7add13'): (0, 4, 7, 11, 9),
    ('mM7add11', 'mmaj7add11'): (0, 3, 7, 11, 5),
    ('(no3)',): (0, 7),
    ('7(no3)',): (0, 7, 10),
}

#: Spellings the app doesn't read as chords (shown in red, never played).
#: Supporting one means moving it to REFERENCE with its intervals.
UNSUPPORTED = ['7+5', '7no5', 'no3', '-5']

def _third(intervals):
    """The third of a chord: the major one when there are both (the minor
    one is then a #9, as in 7#9), else the minor one, else None."""
    return 4 if 4 in intervals else 3 if 3 in intervals else None


def omitted_forms():
    """``{spellings: intervals}`` for a fifth or a third left out:
    ``(no5)`` / ``(omit5)`` take out the perfect fifth, ``(no3)`` /
    ``(omit3)`` the third, of each REFERENCE quality that has both (a
    power chord, a sus or an altered fifth has nothing of the kind to
    leave out). Only the first spelling of a quality takes the suffix;
    REFERENCE checks the others."""
    table = {}
    for spellings, intervals in REFERENCE.items():
        quality = spellings[0]
        third = _third(intervals)
        if 7 not in intervals or third is None:
            continue
        for number, tone in (('5', 7), ('3', third)):
            forms = (f'{quality}(no{number})', f'{quality}(omit{number})')
            table[forms] = tuple(i for i in intervals if i != tone)
    return table


#: The omitted-tone forms: C69(no5) keeps its 3rd, C13(no5) leaves out the
#: 11th as C13 does.
OMITTED = omitted_forms()

_LETTER_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_EUROPEAN = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa', 'G': 'Sol', 'A': 'La', 'B': 'Si'}
ROOTS = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab',
         'A', 'A#', 'Bb', 'B', 'C♯', 'B♭']
BASSES = ['', 'E', 'Bb', 'F#']


def pitch(name):
    """The pitch class of a note name (``Bb``, ``C♯``, ``D##``, ``B-``)."""
    pc = _LETTER_PC[name[0].upper()]
    for acc in name[1:]:
        pc += 1 if acc in '#♯' else -1 if acc in 'b♭-' else 0
    return pc % 12


def spell(root, notation):
    return _EUROPEAN[root[0]] + root[1:] if notation == 'european' else root


def cases(spellings):
    """``(notation, chord, root, bass)`` for each way of writing the quality."""
    intervals = REFERENCE[spellings]
    for notation in ('american', 'european'):
        for quality in spellings:
            for root in ROOTS:
                for bass in BASSES:
                    slash = '/' + spell(bass, notation) if bass else ''
                    yield notation, spell(root, notation) + quality + slash, root, bass
                    if quality in ('m', 'm6', 'm7', 'm9', 'm11', 'm13', 'm7b5'):
                        # A lowercase root is minor too: c7 is Cm7.
                        yield notation, spell(root, notation).lower() + quality[1:] + slash, root, bass


def _expected(root, intervals, bass):
    pcs = {(pitch(root) + i) % 12 for i in intervals}
    if bass:
        pcs.add(pitch(bass))
    return sorted(pcs)


def _check(notation, chord, root, bass, intervals):
    expected = _expected(root, intervals, bass)
    played = _HELPER.compute_chord_notes(chord)
    if played is None:
        return f"{chord}: no notes"
    problems = []
    got = sorted({pitch(n) for n in played.notes} | {pitch(played.bass_note)})
    if got != expected:
        problems.append(f"plays {got}, should be {expected}")
    if pitch(played.root) != pitch(root):
        problems.append(f"root {played.root}")
    if pitch(played.bass_note) != pitch(bass or root):
        problems.append(f"bass {played.bass_note}")
    editor = _HELPER.get_notes(chord)
    if editor is None or sorted({pitch(n) for n in editor}) != expected:
        problems.append(f"the editor's notes are {editor}")
    return f"{chord}: " + "; ".join(problems) if problems else None


@pytest.mark.parametrize("spellings", list(REFERENCE), ids=lambda s: s[0] or 'major')
def test_every_spelling_of_a_quality_has_its_notes(spellings):
    problems = [p for case in cases(spellings)
                for p in [_check(*case, REFERENCE[spellings])] if p]
    assert not problems, f"{len(problems)} problems:\n" + "\n".join(problems[:30])


def _omitted_cases(spellings, roots, basses):
    for notation in ('american', 'european'):
        for quality in spellings:
            for root in roots:
                for bass in basses:
                    slash = '/' + spell(bass, notation) if bass else ''
                    yield notation, spell(root, notation) + quality + slash, root, bass


@pytest.mark.parametrize("spellings", list(OMITTED), ids=lambda s: s[0])
def test_a_left_out_fifth_or_third_takes_out_that_note(spellings):
    """A few roots and basses here; make fuzz checks them all."""
    intervals = OMITTED[spellings]
    problems = [p for case in _omitted_cases(spellings, ['C', 'F#', 'Bb', 'Db'], ['', 'E'])
                for p in [_check(*case, intervals)] if p]
    assert not problems, f"{len(problems)} problems:\n" + "\n".join(problems[:30])


@pytest.mark.fuzz
@pytest.mark.parametrize("spellings", list(OMITTED), ids=lambda s: s[0])
def test_a_left_out_fifth_or_third_on_every_root_and_bass(spellings):
    intervals = OMITTED[spellings]
    problems = [p for case in _omitted_cases(spellings, ROOTS, BASSES)
                for p in [_check(*case, intervals)] if p]
    assert not problems, f"{len(problems)} problems:\n" + "\n".join(problems[:30])


@pytest.mark.parametrize("quality", UNSUPPORTED)
def test_an_unsupported_spelling_is_not_a_chord(quality):
    from chord.detector import ChordDetector

    for notation in ('american', 'european'):
        chord = spell('C', notation) + quality
        found = ChordDetector(notation=notation).detect_chords_in_text(chord)
        assert not any(c.is_valid and c.chord == chord for c in found), chord


@pytest.mark.parametrize("notation", ['american', 'european'])
@pytest.mark.parametrize("quality, intervals", [
    ('maj7', (0, 3, 7, 11)), ('M7', (0, 3, 7, 11)), ('Δ', (0, 3, 7, 11)), ('Δ7', (0, 3, 7, 11)),
    ('maj9', (0, 3, 7, 11, 2)), ('7', (0, 3, 7, 10)), ('', MINOR), ('6', (0, 3, 7, 9)),
])
def test_a_lowercase_root_is_always_minor(notation, quality, intervals):
    """c7 is Cm7, and cmaj7 / cM7 / cΔ are C minor-major 7, as in roman
    numerals (ii7 is Dm7, iimaj7 D minor-major 7)."""
    problems = [p for root in ROOTS
                for p in [_check(notation, spell(root, notation).lower() + quality, root, '', intervals)]
                if p]
    assert not problems, "\n".join(problems[:20])


@pytest.mark.parametrize("roman, expected", [
    ('ii7', ['D', 'F', 'A', 'C']), ('iimaj7', ['D', 'F', 'A', 'C#']),
    ('IImaj7', ['D', 'F#', 'A', 'C#']), ('imaj7', ['C', 'Eb', 'G', 'B']),
    ('iisus4', ['D', 'G', 'A']), ('vii°7', ['B', 'D', 'F', 'Ab']),
])
def test_roman_numerals_in_c(roman, expected):
    played = _HELPER.compute_chord_notes(roman, key='C', is_relative=True)
    assert sorted(pitch(n) for n in played.notes) == sorted(pitch(n) for n in expected)


_LETTERS = 'CDEFGAB'
#: Letters above the root each interval (mod 12) may take: a minor 3rd or
#: a #9 (3), a b5 or #11 (6), a #5 or b13 (8), a 6th or diminished 7th (9).
_LETTER_STEPS = {0: {0}, 1: {1}, 2: {1}, 3: {1, 2}, 4: {2}, 5: {3}, 6: {3, 4},
                 7: {4}, 8: {4, 5}, 9: {5, 6}, 10: {6}, 11: {6}}


@pytest.mark.parametrize("spellings", list(REFERENCE), ids=lambda s: s[0] or 'major')
def test_note_names_follow_the_intervals(spellings):
    """The staff draws a chromatic note with the chord's own note name, so
    a C#13's third must be E#, not F, and a C7b9b13's ninth Db, not C#."""
    problems = []
    for root in ROOTS:
        root = root.replace('♯', '#').replace('♭', 'b')
        played = _HELPER.compute_chord_notes(root + spellings[0])
        for name in played.notes:
            interval = (pitch(name) - pitch(root)) % 12
            steps = (_LETTERS.index(name[0].upper()) - _LETTERS.index(root[0])) % 7
            if steps not in _LETTER_STEPS[interval]:
                problems.append(f"{root}{spellings[0]}: {name}")
    assert not problems, ", ".join(problems)
