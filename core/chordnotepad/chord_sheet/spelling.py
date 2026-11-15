"""How the chord sheet spells a sounding note: letter, accidental, octave.

The staff places notes by their spelling, and the views that print note
names (the piano roll) must name them the same way, so the rules live here
once. A note is spelled from the chord it belongs to and the key in force:

1. **The chord's own stack.** A note of the chord is spelled with the chord
   from its root: the key's letter when the root is diatonic to the key (a
   ``Db`` chord in F# is C# E# G#), the chord's own spelling when it is
   chromatic, and every other note at its letter distance from the root (a
   ``B`` chord in Db is B D# F#, never B Eb Gb). A double accidental is
   respelled from the root's other spelling, or falls through.
2. **Diatonic in the key.** A pitch class the chord doesn't spell takes the
   key signature's spelling when it is diatonic to the key.
3. **Fallback.** Anything else is a flat in flat keys and a sharp otherwise
   (sharp keys, C major, or no key).

The octave follows the spelling, so ``letter + accidental + octave`` is the
MIDI note exactly across the B/C seam: 60 spelled B# is ``B#3``, 71 spelled
Cb is ``Cb5`` (MIDI 60 is C4).

Public API: :func:`key_fifths`, :func:`spell_midi` and :func:`note_name`.
"""

from __future__ import annotations

import functools
import logging
from typing import Dict, List, NamedTuple, Optional, Tuple

from chordnotepad.chord.converter import NotationConverter
from chordnotepad.chord.keys import american_key
from chordnotepad.chord.midi_converter import parse_note_to_semitone

logger = logging.getLogger(__name__)

# --- Diatonic tables -------------------------------------------------------
#: Letter -> its ordinal within an octave (C=0 .. B=6), for diatonic indexing.
_LETTER_VALUE = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}
#: Letter -> its natural semitone within an octave.
_LETTER_SEMITONE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_LETTERS = 'CDEFGAB'
#: Default (letter, accidental) per pitch class, sharp convention.
_SHARP_SPELLING: Tuple[Tuple[str, int], ...] = (
    ('C', 0), ('C', 1), ('D', 0), ('D', 1), ('E', 0), ('F', 0),
    ('F', 1), ('G', 0), ('G', 1), ('A', 0), ('A', 1), ('B', 0),
)
#: Default (letter, accidental) per pitch class, flat convention (used as the
#: fallback in flat keys so unmatched chromatic pitch classes read as flats).
_FLAT_SPELLING: Tuple[Tuple[str, int], ...] = (
    ('C', 0), ('D', -1), ('D', 0), ('E', -1), ('E', 0), ('F', 0),
    ('G', -1), ('G', 0), ('A', -1), ('A', 0), ('B', -1), ('B', 0),
)

# --- Key-signature tables --------------------------------------------------
#: Major key -> position on the circle of fifths (+ sharps / - flats).
_MAJOR_FIFTHS: Dict[str, int] = {
    'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
    'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
}
#: Minor key -> circle-of-fifths position (via its relative major).
_MINOR_FIFTHS: Dict[str, int] = {
    'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
    'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5, 'Ebm': -6, 'Abm': -7,
}
#: The order sharps are added in (F C G D A E B); flats go the other way.
_SHARP_LETTERS = 'FCGDAEB'
_FLAT_LETTERS = 'BEADGCF'

#: Canonical circle-of-fifths position per tonic *pitch class*, used as the
#: enharmonic fallback when a key's literal spelling has no real signature
#: (Gbm, D#, a double-accidental tonic, ...). Each pc maps to the fifths of
#: its conventional key: the unique real signature where one exists (D#/Gb ->
#: Eb major's -3) and the fewer-accidentals twin at the F#/Gb-style seams.
_PC_MAJOR_FIFTHS: Dict[int, int] = {
    0: 0, 1: -5, 2: 2, 3: -3, 4: 4, 5: -1, 6: 6, 7: 1, 8: -4, 9: 3, 10: -2, 11: 5,
}
_PC_MINOR_FIFTHS: Dict[int, int] = {
    9: 0, 4: 1, 11: 2, 6: 3, 1: 4, 8: 5, 3: -6, 10: -5, 2: -1, 7: -2, 0: -3, 5: -4,
}


class SpelledNote(NamedTuple):
    """A MIDI note as written: ``letter`` (``'C'``..``'B'``), ``accidental``
    (+1 sharp, -1 flat, 0 natural) and ``octave`` (C4 is middle C, MIDI 60)."""

    letter: str
    accidental: int
    octave: int

    @property
    def diatonic_index(self) -> int:
        """Absolute diatonic step index (C4 -> 28), the staff's vertical position."""
        return diatonic_index(self.letter, self.octave)


# --------------------------------------------------------------------------
# Key signatures
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=256)
def key_fifths(key: Optional[str]) -> Optional[int]:
    """Circle-of-fifths position for ``key`` (+sharps/-flats), or ``None``.

    Minor keys resolve through their relative major. A spelling outside the
    tables (Gbm, D# -- names with no real signature of their own, typically
    from style-preserving transposition or typed directly) falls back to its
    tonic's *pitch class* and takes the conventional enharmonic key's
    signature: Gbm engraves as F#m (3 sharps), D# as Eb (3 flats). Only a
    wholly unparseable key (or ``None``) yields ``None`` -- no signature drawn.
    European names (``Sol``, ``Lab``, ``Fa#m``: the song's key and its
    ``{key}`` directives as written) read as their American spelling.
    """
    if not key:
        return None
    k = american_key(key) or key.strip()
    if k in _MINOR_FIFTHS:
        return _MINOR_FIFTHS[k]
    if k in _MAJOR_FIFTHS:
        return _MAJOR_FIFTHS[k]
    minor = k.endswith('m')
    root = k[:-1] if minor else k
    pc = parse_note_to_semitone(root)
    if pc is not None:
        fifths = (_PC_MINOR_FIFTHS if minor else _PC_MAJOR_FIFTHS)[pc % 12]
        logger.debug("Key %r has no real signature; engraving its enharmonic "
                     "twin (%+d fifths)", key, fifths)
        return fifths
    logger.debug("No key signature mapping for key %r", key)
    return None


def signature_letter_map(fifths: Optional[int]) -> Dict[str, int]:
    """Letter -> the accidental the key signature applies to it (+1/-1)."""
    if not fifths:
        return {}
    if fifths > 0:
        return {letter: 1 for letter in _SHARP_LETTERS[:fifths]}
    return {letter: -1 for letter in _FLAT_LETTERS[:-fifths]}


def diatonic_key_map(fifths: Optional[int]) -> Dict[int, Tuple[str, int]]:
    """Pitch class -> its diatonic ``(letter, accidental)`` in the key.

    Built straight from the key signature: each of the seven letters carries
    the accidental the signature applies to it, giving the major scale as the
    signature spells it (F#: F#/G#/A#/B/C#/D#/E#; Gb: Gb/Ab/Bb/Cb/Db/Eb/F, so
    pc 11 is Cb -- a non-natural letter, not skipped). Minor keys share their
    relative major's ``fifths`` and so the same map. ``None`` (no key) yields an
    empty map, disabling the diatonic-in-key rule.
    """
    if fifths is None:
        return {}
    sig_map = signature_letter_map(fifths)
    out: Dict[int, Tuple[str, int]] = {}
    for letter in _LETTER_VALUE:
        acc = sig_map.get(letter, 0)
        pc = (_LETTER_SEMITONE[letter] + acc) % 12
        out[pc] = (letter, acc)
    return out


# --------------------------------------------------------------------------
# Spelling
# --------------------------------------------------------------------------

def diatonic_index(letter: str, octave: int) -> int:
    """Absolute diatonic step index of ``letter`` in ``octave`` (C4 -> 28)."""
    return octave * 7 + _LETTER_VALUE[letter]


def _source_names(chord_notes) -> List[str]:
    """The chord's own note names: its notes, then the bass, then the root."""
    names: List[str] = list(chord_notes.notes or [])
    if chord_notes.bass_note:
        names.append(chord_notes.bass_note)
    if chord_notes.root:
        names.append(chord_notes.root)
    return [n for n in names if n and n[0].upper() in _LETTER_VALUE
            and parse_note_to_semitone(n) is not None]


def _respelled(names: List[str], root: str, letter: str) -> Dict[int, Tuple[str, int]]:
    """``names`` (a chord spelled from ``root``) spelled from the root letter
    ``letter``: each note keeps its letter distance from the root, so the
    chord still stacks the same way (C#7's C# E# G# B from D is Db F Ab Cb).
    A note that would need a double accidental is left out."""
    out: Dict[int, Tuple[str, int]] = {}
    root_index = _LETTER_VALUE[root[0].upper()]
    new_index = _LETTER_VALUE[letter]
    for name in names:
        pc = parse_note_to_semitone(name)
        steps = (_LETTER_VALUE[name[0].upper()] - root_index) % 7
        new_letter = _LETTERS[(new_index + steps) % 7]
        acc = (pc - _LETTER_SEMITONE[new_letter] + 6) % 12 - 6
        if abs(acc) <= 1:
            out.setdefault(pc, (new_letter, acc))
    return out


def _chord_spelling(chord_notes, fifths: Optional[int]) -> Dict[int, Tuple[str, int]]:
    """Pitch class -> ``(letter, accidental)`` for every note of the chord.

    The root decides: a root diatonic to the key takes the key's letter (a
    ``Db`` chord in F# is C#), a chromatic one keeps the chord's own (a ``B``
    chord in Db stays B). Every other note keeps its letter distance from
    the root in the chord's own spelling, so the chord is spelled as one
    stack of thirds: B in Db is B D# F#, never B Eb Gb. When that would
    need a double accidental (the chord ``Gbm``'s Bbb), the root's other
    single-accidental spelling is tried (F# A C#); a note neither spelling
    can write is left out, for :func:`match_letter`'s fallback.
    """
    if chord_notes is None:
        return {}
    names = _source_names(chord_notes)
    root = chord_notes.root if chord_notes.root and chord_notes.root in names else (
        names[0] if names else None)
    if root is None:
        return {}
    root_pc = parse_note_to_semitone(root)
    key_map = diatonic_key_map(fifths)
    first = key_map[root_pc][0] if root_pc in key_map else root[0].upper()
    # The root's spellings with at most one accidental, the chosen one first.
    letters = [first] + [
        letter for letter in _LETTERS if letter != first
        and abs((root_pc - _LETTER_SEMITONE[letter] + 6) % 12 - 6) <= 1]
    wanted = {parse_note_to_semitone(n) for n in names}
    best: Dict[int, Tuple[str, int]] = {}
    for letter in letters:
        spelled = _respelled(names, root, letter)
        if set(spelled) == wanted:
            return spelled
        if not best:
            best = spelled
    return best


def match_letter(pc: int, chord_notes, fifths: Optional[int] = None) -> Tuple[str, int]:
    """Return the ``(letter, accidental_offset)`` spelling a pitch class ``pc``.

    Precedence (the module docstring's rules):

    1. **The chord's own stack** (:func:`_chord_spelling`).
    2. **Diatonic-in-key.** A pitch class the chord doesn't spell, when
       ``fifths`` is known and it is diatonic, is spelled as the key
       signature spells it.
    3. **Fallback follows the signature.** Anything else falls back to flats
       in flat keys and sharps otherwise (sharp keys, C major, or no key).

    Args:
        pc: The pitch class (0 = C).
        chord_notes: The chord's ``ChordNotes`` (``notes``, ``bass_note``,
            ``root`` as the parser spells them), or None.
        fifths: The key in force as :func:`key_fifths` gives it, or None.
    """
    spelled = _chord_spelling(chord_notes, fifths)
    if pc in spelled:
        return spelled[pc]
    key_map = diatonic_key_map(fifths)
    if pc in key_map:
        return key_map[pc]
    table = _FLAT_SPELLING if (fifths is not None and fifths < 0) else _SHARP_SPELLING
    return table[pc % 12]


def spell_midi(midi: int, chord_notes=None, fifths: Optional[int] = None) -> SpelledNote:
    """Spell a MIDI note sounding in a chord, in the key in force.

    The letter and accidental come from :func:`match_letter`; the octave is
    derived so that they reproduce ``midi`` exactly, which handles the
    enharmonic seam (``B#3`` = 60 sits on the B position below middle C;
    ``Cb5`` = 71 on the C5 position with a flat), also when the key-aware
    spelling itself crosses it (Gb major's pc 11 is Cb).

    Args:
        midi: The MIDI note number (C4 = 60).
        chord_notes: The chord's ``ChordNotes`` (``RenderedChord.chord_notes``),
            or None for a note outside any chord.
        fifths: The key in force (:func:`key_fifths` of ``RenderedChord.key``),
            or None for no key.
    """
    letter, acc = match_letter(midi % 12, chord_notes, fifths)
    natural = _LETTER_SEMITONE[letter] + acc
    octave = (midi - natural) // 12 - 1
    return SpelledNote(letter, acc, octave)


def spelled_name(note: SpelledNote, notation: str = "american") -> str:
    """A spelled note as a name with its octave: ``C#3``, ``Bb2``, ``Cb5``
    in American; ``Do#3``, ``Sib2``, ``Dob5`` in European."""
    accidental = '#' * note.accidental if note.accidental > 0 else 'b' * -note.accidental
    name = f"{note.letter}{accidental}{note.octave}"
    return NotationConverter.format_for_display(name, notation)


def note_name(midi: int, chord_notes=None, key: Optional[str] = None,
              notation: str = "american") -> str:
    """The name a MIDI note of a chord takes in the key in force.

    Args:
        midi: The MIDI note number (C4 = 60).
        chord_notes: The chord's ``ChordNotes`` (``RenderedChord.chord_notes``),
            or None.
        key: The key in force (``RenderedChord.key``, either notation), or None.
        notation: ``"american"`` (``C#3``) or ``"european"`` (``Do#3``).
    """
    return spelled_name(spell_midi(midi, chord_notes, key_fifths(key)), notation)
