"""Every root, case, notation and shift: a transposed chord is a valid chord
with the source's notes moved by the shift, as the editor and playback
read it.

Reported on Android: ``A b c c c`` down a tone gave ``G a bb bb bb``, and
lowercase flat minors (``bb``, ``eb``, ``sib``) weren't valid chords. Each
test below runs one source token through ``transpose_text`` for all 23
shifts and checks the result the way the editor and playback read it.
"""

import pytest

from chord.detector import ChordDetector
from chord.helper import ChordHelper
from models.notation import AMERICAN_KEYS, EUROPEAN_KEYS
from services.transpose_service import transpose_key, transpose_text

_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_EUROPEAN = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa', 'G': 'Sol', 'A': 'La', 'B': 'Si'}
_HELPER = ChordHelper()
SHIFTS = [s for s in range(-11, 12) if s]

ROOTS = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab',
         'A', 'A#', 'Bb', 'B', 'C♯', 'D♭', 'B♭', 'F♯']
#: Qualities after an uppercase root, and after a lowercase (minor) one.
UPPER_SUFFIXES = ['', 'm', '7', 'maj7', 'm7', 'sus4', 'dim', 'aug', 'add9', '7b9', 'm7b5', '6']
LOWER_SUFFIXES = ['', '7', 'maj7', '6']
BASSES = ['', '/E', '/Bb', '/F#', '/G♭']


def spell(token, notation, lower):
    """An American root (+ accidental) in ``notation`` and case."""
    if notation == 'european':
        token = _EUROPEAN[token[0]] + token[1:]
    return token.lower() if lower else token


def pitch(root):
    """The pitch class of an American root (``Bb``, ``C♯``)."""
    pc = _PC[root[0].upper()]
    for acc in root[1:]:
        pc += 1 if acc in '#♯' else -1
    return pc % 12


def notes_of(chord, notation):
    """The pitch classes of ``chord``, or None when it has none.

    Read twice, as the editor reads it (``ChordDetector.get_chord_notes``)
    and as playback does (``ChordHelper.compute_chord_notes``, root, notes
    and slash bass), and both must agree.
    """
    names = ChordDetector(notation=notation).get_chord_notes(chord)
    played = _HELPER.compute_chord_notes(chord)
    if names is None or played is None:
        return None
    editor = sorted({pitch(n.replace('-', 'b')) for n in names})
    playback = sorted({pitch(n.replace('-', 'b')) for n in [*played.notes, played.bass_note]})
    return editor if editor == playback else None


def cases():
    for notation in ('american', 'european'):
        for root in ROOTS:
            for lower, suffixes in ((False, UPPER_SUFFIXES), (True, LOWER_SUFFIXES)):
                for suffix in suffixes:
                    for bass in BASSES:
                        if bass and suffix in ('m7b5', 'dim', 'aug'):
                            continue
                        bass_token = spell(bass[1:], notation, False) if bass else ''
                        chord = spell(root, notation, lower) + suffix + ('/' + bass_token if bass else '')
                        yield pytest.param(chord, notation, id=f"{notation}-{chord}")


@pytest.mark.parametrize("chord, notation", list(cases()))
def test_every_shift_gives_a_valid_chord_with_the_notes_moved(chord, notation):
    detector = ChordDetector(notation=notation)
    [source] = detector.detect_chords_in_text(chord)
    assert source.is_valid, f"{chord} isn't read as a chord"
    before = notes_of(chord, notation)
    assert before

    problems = []
    for shift in SHIFTS:
        text = transpose_text(f"{chord} {chord}\n", shift, notation)
        found = detector.detect_chords_in_text(text)
        if len(found) != 2 or not all(c.is_valid for c in found):
            problems.append(f"{shift:+d}: {text.strip()!r} isn't two valid chords")
            continue
        result = found[0].chord
        if found[1].chord != result:
            problems.append(f"{shift:+d}: {text.strip()!r} transposed differently")
        expected = sorted((pc + shift) % 12 for pc in before)
        if notes_of(result, notation) != expected:
            problems.append(f"{shift:+d}: {result} doesn't have the notes of {chord} moved")
        if result[0].islower() != chord[0].islower():
            problems.append(f"{shift:+d}: {result} changed the case of {chord}")
        back = transpose_text(text, -shift, notation)
        if notes_of(detector.detect_chords_in_text(back)[0].chord, notation) != before:
            problems.append(f"{shift:+d}: {back.strip()!r} doesn't go back to {chord}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("notation, keys", [("american", AMERICAN_KEYS), ("european", EUROPEAN_KEYS)])
def test_every_key_transposes_to_a_key_with_the_tonic_moved(notation, keys):
    american = dict(zip(keys, AMERICAN_KEYS))
    problems = []
    for key in keys:
        for shift in SHIFTS:
            result = transpose_key(key, shift, notation)
            if result not in keys:
                problems.append(f"{key} {shift:+d} -> {result!r}: not a key")
                continue
            source, moved = american[key], american[result]
            if source.endswith('m') != moved.endswith('m'):
                problems.append(f"{key} {shift:+d} -> {result}: mode changed")
            if pitch(moved.rstrip('m')) != (pitch(source.rstrip('m')) + shift) % 12:
                problems.append(f"{key} {shift:+d} -> {result}: wrong tonic")
            directive = transpose_text(f"{{key: {key}}}\n{spell('C', notation, False)}\n", shift, notation)
            if f"{{key: {result}}}" not in directive:
                problems.append(f"{key} {shift:+d}: the directive became {directive.splitlines()[0]!r}")
    assert not problems, "\n".join(problems)


def test_the_reported_song():
    assert transpose_text("A b c c c\n", -2, "american") == "G a bb bb bb\n"
    # Back up, each shorter chord keeps its column (padded with a space).
    assert transpose_text("G a bb bb bb\n", 2, "american").split() == "A b c c c".split()
    assert transpose_text("La si do do do\n", -2, "european") == "Sol la sib sib sib\n"
