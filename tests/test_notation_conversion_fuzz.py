"""Converting between American and European notation keeps every chord,
and converting back gives the text as it was written.

Each valid chord in the source must come out as a valid chord in the other
notation with exactly the same notes (as the editor and playback read
them), so no chord and no quality is lost, and converting back gives the
same notes again. Checked on a grid of roots, cases, qualities and slash
basses, then on random chords and random songs.
"""

import pytest
from hypothesis import assume, given, settings, strategies as st

from chord.detector import ChordDetector
from services.aligned_rewrite import FILL
from services.song_parser_service import SongParserService
from tests.test_transpose_exhaustive import BASSES, ROOTS, notes_of, spell
from tests.test_transpose_fuzz import _QUALITIES, absolute_chords, chords, songs

_PARSER = SongParserService()
_OTHER = {'american': 'european', 'european': 'american'}


def convert(text, source):
    if source == 'american':
        return _PARSER.convert_to_european(text)
    return _PARSER.convert_to_american(text)


def marked(old, new):
    """Whether ``new`` is the lyric ``old`` with the "." text-line marker."""
    indent = len(old) - len(old.lstrip(' '))
    return new in ('.' + old, old[:indent - 1] + '.' + old[indent:] if indent else None)


def words(line):
    """A line's words, without the stretch fill and the "." marker."""
    return line.replace(FILL, '').lstrip(' .').split()


def check_song(text, source):
    """The problems converting ``text`` from ``source`` and back."""
    target = _OTHER[source]
    converted = convert(text, source)
    if converted == text:
        # Nothing to convert: the app says so and changes nothing, not even
        # the notation (test_session_editing), so there's no way back to check.
        return []
    # Line by line, on the lines that had chords: a lyric line can read as
    # chords in the other notation ("la la la" is La La La), which isn't a
    # chord the conversion lost or changed.
    chord_lines = [i for i, line in enumerate(text.split('\n')) if absolute_chords(line, source)]
    before = [c for i in chord_lines for c in absolute_chords(text.split('\n')[i], source)]
    after = [c for i in chord_lines for c in absolute_chords(converted.split('\n')[i], target)]
    problems = []
    if len(after) != len(before):
        problems.append(f"{text!r} -> {converted!r}: {len(before)} chords became {len(after)}")
        return problems
    for old, new in zip(before, after):
        if notes_of(new.chord, target) != notes_of(old.chord, source):
            problems.append(f"{old.chord} -> {new.chord}: notes changed")
        if (old.duration or None) != (new.duration or None):
            problems.append(f"{old.chord} -> {new.chord}: duration changed")
    back_lines = convert(converted, target).split('\n')
    back = [c for i in chord_lines for c in absolute_chords(back_lines[i], source)]
    # Converting back gives the text as written, but for a lyric that would
    # read as chords in the other notation ("la la la"), which keeps the "."
    # marker the conversion gave it.
    text_lines = text.split('\n')
    for i, (old, new) in enumerate(zip(text_lines, back_lines)):
        if new == old or marked(old, new):
            continue
        # A chord line moves right with a lyric marked without an indent.
        if (new == ' ' + old and i + 1 < len(text_lines)
                and back_lines[i + 1] == '.' + text_lines[i + 1]):
            continue
        # The listed exception (services.aligned_rewrite): with no lyric under
        # it, a gap a longer chord narrowed to one space stays one space.
        if absolute_chords(old, source) and old.split() == new.split() and (
                i + 1 >= len(text_lines) or not words(text_lines[i + 1])
                or absolute_chords(text_lines[i + 1], source)):
            continue
        problems.append(f"{old!r} -> {new!r}")
    if [notes_of(c.chord, source) for c in back] != [notes_of(c.chord, source) for c in before]:
        problems.append(f"{text!r} -> {converted!r} doesn't convert back to the same notes")
    return problems


def grid():
    for source in ('american', 'european'):
        for root in ROOTS:
            for lower in (False, True):
                for quality in _QUALITIES:
                    for bass in BASSES:
                        bass_token = spell(bass[1:], source, False) if bass else ''
                        chord = (spell(root, source, lower) + quality
                                 + ('/' + bass_token if bass else ''))
                        yield source, chord


def _grid_chords(source):
    """The grid's chords the editor reads as one valid chord with notes."""
    valid = []
    for notation, chord in grid():
        if notation != source:
            continue
        found = absolute_chords(chord, source)
        if len(found) == 1 and found[0].chord == chord and notes_of(chord, source):
            valid.append(chord)
    return valid


@pytest.mark.fuzz
@pytest.mark.parametrize("source", ['american', 'european'])
def test_every_grid_chord_converts_with_the_same_notes(source):
    chords_ = _grid_chords(source)
    assert len(chords_) > 3000
    problems = [p for chord in chords_ for p in check_song(chord + '\n', source)]
    assert not problems, f"{len(problems)} problems:\n" + "\n".join(problems[:40])


@pytest.mark.fuzz
@pytest.mark.parametrize("source", ['american', 'european'])
def test_a_line_of_grid_chords_converts_with_the_same_notes(source):
    """The same chords side by side on chord lines, as in a song."""
    chords_ = _grid_chords(source)
    lines = [' '.join(chords_[i:i + 8]) for i in range(0, len(chords_), 8)]
    problems = check_song('\n'.join(lines) + '\n', source)
    assert not problems, "\n".join(problems[:40])


@pytest.mark.fuzz
@settings(max_examples=1500)
@given(st.data(), st.sampled_from(['american', 'european']))
def test_a_random_chord_converts_with_the_same_notes(data, source):
    chord = data.draw(chords(source))
    found = absolute_chords(chord, source)
    assume(len(found) == 1 and notes_of(found[0].chord, source) is not None)
    assert not check_song(chord + '\n', source)


@pytest.mark.fuzz
@settings(max_examples=400)
@given(st.data(), st.sampled_from(['american', 'european']))
def test_a_random_song_converts_every_chord_and_nothing_else(data, source):
    song = data.draw(songs(source))
    before = absolute_chords(song, source)
    assume(all(notes_of(c.chord, source) is not None for c in before))
    # No invalid chord (shown in red): it isn't converted, and as text in the
    # other notation it can tip its line below the chord-line threshold.
    assume(all(c.is_valid for c in ChordDetector(notation=source).detect_chords_in_text(song)))
    assert not check_song(song, source)

    # Lines without chords or a {key} are left as they are: lyrics, comments,
    # "." lines, roman numerals, NC, other directives.
    converted = convert(song, source)
    target = _OTHER[source]
    assume(converted != song)       # else nothing changes (see check_song)
    for old, new in zip(song.split('\n'), converted.split('\n')):
        if not absolute_chords(old, source) and '{key' not in old:
            # A lyric keeps its words: only the spacing and the fill that
            # keep the chords over it may change (services.aligned_rewrite).
            assert words(new) == words(old) or marked(old, new)
            # A lyric stays a lyric in the other notation.
            assert not absolute_chords(new, target), new


@pytest.mark.parametrize("source, text, expected, back", [
    # Without a leading space for the "." the chord line moves right with
    # the lyric, so the chords stay over their syllables both ways.
    ('american', "C G\nla la la\n", " Do Sol\n.la  la la\n", " C G\n.la la la\n"),
    ('american', "C   G\n  la la la\n", "Do  Sol\n .la la la\n", "C   G\n .la la la\n"),
    ('european', "Do Sol\na b c\n", " C  G\n.a b c\n", " Do Sol\n.a b c\n"),
    ('american', "C G\nWords here\n.la la\n", "Do Sol\nWo\u00b7rds here\n.la la\n",
     "C G\nWords here\n.la la\n"),
])
def test_a_lyric_that_would_read_as_chords_gets_the_text_marker(source, text, expected, back):
    assert convert(text, source) == expected
    assert convert(expected, _OTHER[source]) == back
