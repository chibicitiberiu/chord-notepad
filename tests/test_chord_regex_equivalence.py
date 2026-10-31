"""The linear-time chord patterns match exactly what the old ones did.

The old patterns (kept inline below) let a run of digits split between the
``\\d+`` alternatives in exponentially many ways, and ``sus[24]?`` overlapped
``sus`` + a number, so a long failing token froze the parser. The new ones in
``ChordDetector`` take each digit run whole. These tests check that nothing a
user could type changes: every chord-like token in the tests, the examples and
the user guide, and random short tokens, give the same ``fullmatch`` and
``finditer`` results under both.
"""

import re
from pathlib import Path

from hypothesis import given, settings, strategies as st

from chord.detector import ChordDetector

ROOT = Path(__file__).resolve().parent.parent

OLD_AMERICAN = re.compile(
    r'\b([A-Ga-g][#b♯♭]?(?:°|ø|\+|Δ|-|m|M|maj|min|mi|dim|aug|dom|alt|sus[24]?|add\d+|no\d+|omit\d+|\d+|[#b♯♭]\d+|\([^)]+\))*(?:/[A-Ga-g][#b♯♭]?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
)
OLD_EUROPEAN = re.compile(
    r'\b((?:D[oóò]|R[eéèê]|Mi|F[aáà]|Sol|L[aáà]|Si|d[oóò]|r[eéèê]|mi|f[aáà]|sol|l[aáà]|si)[#b♯♭]?(?:°|ø|\+|Δ|M|m|maj|min|mi|dim|aug|dom|alt|sus[24]?|add\d+|no\d+|omit\d+|\d+|[#b♯♭]\d+|\([^)]+\))*(?:/(?:D[oóò]|R[eéèê]|Mi|F[aáà]|Sol|L[aáà]|Si|d[oóò]|r[eéèê]|mi|f[aáà]|sol|l[aáà]|si)[#b♯♭]?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
)
OLD_ROMAN = re.compile(
    r'(?<![A-Za-z0-9#b♭♯])([#b♭♯]?[IViv]+(?:o|°|ø|\+|maj|min|dim|aug|sus[24]?|add\d+|m|\d+|[#b]\d+)*(?:/[#b♭♯]?[IViv]+(?:o|°)?)?(?:\*[\d.]+)?)(?![A-Za-z0-9])'
)

PAIRS = {
    'american': (OLD_AMERICAN, ChordDetector.CHORD_PATTERN_AMERICAN),
    'european': (OLD_EUROPEAN, ChordDetector.CHORD_PATTERN_EUROPEAN),
    'roman': (OLD_ROMAN, ChordDetector.CHORD_PATTERN_ROMAN),
}

# Tokens where old and new may disagree, as (pattern name, token). None so
# far: the new patterns accept the same strings (sus2/sus4 are "sus" plus the
# bare-number alternative), and digit runs only ever matched whole anyway,
# because the patterns end in (?![A-Za-z0-9]).
ALLOWED_DIFFERENCES: set = set()

# The old patterns are exponential in the length of a digit run, so the
# corpus skips text with long ones (none of it is a chord).
_MAX_DIGIT_RUN = 10
_LONG_DIGITS = re.compile(r'\d{%d,}' % (_MAX_DIGIT_RUN + 1))

# First characters a chord (any notation) can start with.
_CHORD_START = set('ABCDEFGabcdefgIViv#b♯♭') | set('RMSLrmsl')
_PUNCT = '`\'".,;:!?()[]{}<>|'


def _results(pattern, text):
    full = pattern.fullmatch(text)
    found = [(m.span(), m.group(1)) for m in pattern.finditer(text)]
    return (full.group(1) if full else None), found


def _differences(texts):
    diffs = set()
    for text in texts:
        for name, (old, new) in PAIRS.items():
            if _results(old, text) != _results(new, text):
                diffs.add((name, text))
    return diffs


def _corpus_files():
    files = [p for p in (ROOT / 'tests').rglob('*')
             if p.is_file() and p.suffix in ('.py', '.txt', '.json', '.rst', '.md')]
    files += sorted((ROOT / 'examples').glob('*.txt'))
    files += sorted((ROOT / 'help').glob('*.rst'))
    return files


def _corpus():
    tokens, lines = set(), set()
    for path in _corpus_files():
        text = path.read_text(encoding='utf-8', errors='replace')
        for line in text.splitlines():
            if len(line) <= 400 and not _LONG_DIGITS.search(line):
                lines.add(line)
            for word in line.split():
                for candidate in (word, word.strip(_PUNCT), word.split('*')[0],
                                  word.strip(_PUNCT).split('*')[0]):
                    if (candidate and candidate[0] in _CHORD_START and len(candidate) <= 40
                            and not _LONG_DIGITS.search(candidate)):
                        tokens.add(candidate)
    return tokens, lines


def test_corpus_is_big_enough_to_mean_something():
    tokens, lines = _corpus()
    assert len(tokens) > 2000
    for chord in ('Cmaj7', 'Am7b5', 'Csus4', 'G7#9', 'Dosus4', 'ii7', '♭VII', 'C/G', 'Am*2'):
        assert chord in tokens


def test_corpus_tokens_match_the_same_under_old_and_new_patterns():
    tokens, _ = _corpus()
    assert _differences(sorted(tokens)) == ALLOWED_DIFFERENCES


def test_corpus_lines_find_the_same_chords_under_old_and_new_patterns():
    _, lines = _corpus()
    assert _differences(sorted(lines)) == ALLOWED_DIFFERENCES


_CHARS = 'ABCDEFGabcdefgIViv#b♯♭°ø+Δ-mMajinduglotsrSLRóé0123456789()/*. x'
_PIECES = ['C', 'a', 'Do', 're', 'Sol', 'la', 'I', 'iv', 'V', 'b', '#', '♭', '♯',
           'm', 'M', 'maj', 'min', 'mi', 'dim', 'aug', 'dom', 'alt', 'sus', 'add', 'no',
           'omit', 'o', '°', 'ø', '+', 'Δ', '-', '2', '4', '5', '7', '9', '11', '13',
           '(', ')', '/', '*', '.', ' ', 'x']


@settings(max_examples=3000)
@given(st.text(alphabet=_CHARS, max_size=8))
def test_random_short_tokens_match_the_same(token):
    assert _differences([token]) == set()


@settings(max_examples=3000)
@given(st.lists(st.sampled_from(_PIECES), max_size=6).map(''.join))
def test_random_chord_pieces_match_the_same(token):
    assert _differences([token]) == set()
