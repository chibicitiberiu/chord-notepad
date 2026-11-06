"""ViewModel for the chord identifier window (desktop dialog and Android screen).

The note helpers at module level (:func:`note_to_midi`, :func:`bass_note`,
:func:`parse_notes`) are plain functions both UIs share; the desktop piano
widget calls them too.
"""

import itertools
import logging
import re
import unicodedata
from typing import Callable, Dict, Iterable, List, Tuple, Set, Optional

from music21 import chord as m21_chord
from chord.converter import NotationConverter
from utils.observable import Observable
from services.song_parser_service import SongParserService
from exceptions import ChordDetectionError

logger = logging.getLogger(__name__)

#: The note names the identifier works with (sharps only), in pitch order.
NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')

#: What the results list shows before any note is selected.
SELECT_NOTES_PROMPT = "Select notes to identify chords..."

_FLAT_TO_SHARP = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
_SHARP_TO_FLAT = {sharp: flat for flat, sharp in _FLAT_TO_SHARP.items()}

#: How a chord's root is usually spelled, for notes that read as a chord
#: either way (F# rather than Gb, Eb minor rather than D# minor).
_USUAL_ROOTS = frozenset(('C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'))

#: Spelling preferences: what the typed notes used.
FLATS = "flats"
SHARPS = "sharps"
#: A typed note: an American letter or a solfège syllable (either case),
#: accidentals (none, one or more: ``Bbb``, ``F##``), an octave.
_NOTE_TOKEN = re.compile(r'((?i:sol|do|re|mi|fa|la|si)|[A-Ga-g])([#b]*)(\d+)?')
#: The semitone of each natural note above C.
_NATURAL_SEMITONE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
_SOLFEGE = {'do': 'C', 're': 'D', 'mi': 'E', 'fa': 'F', 'sol': 'G', 'la': 'A', 'si': 'B'}
#: The root of an (American) chord name.
_ROOT = re.compile(r'[A-G][#b]?')

#: The identifier's piano, on the desktop and Android: C4 to B5.
PIANO_LOWEST_MIDI = 60
PIANO_HIGHEST_MIDI = 83

#: How long the keys of a played candidate stay highlighted, in seconds.
SOUNDING_SECONDS = 3.0

#: Seconds between the notes of a rolled chord (lowest first), like a quick
#: strum or a spread chord.
ROLL_GAP_SECONDS = 0.06


def note_to_midi(note_name: str, octave: int) -> int:
    """The MIDI number of a note (C4 = 60); an unknown name counts as C."""
    offset = NOTE_NAMES.index(note_name) if note_name in NOTE_NAMES else 0
    return (octave + 1) * 12 + offset


def spell(name: str, notation: str) -> str:
    """An American note or chord name as ``notation`` writes it: in European
    ``C#`` is ``Do#``, ``Bb4`` is ``Sib4`` and ``Cmaj7/E`` is ``Domaj7/Mi``.
    The identifier works in American; this is only for showing names."""
    return NotationConverter.format_for_display(name, notation)


def midi_name(midi: int, notation: str = "american") -> str:
    """A MIDI number as a note name with its octave (48 -> ``C3``, ``Do3``
    in European)."""
    return spell(f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}", notation)


def outside_piano(midi_notes: Iterable[int], lowest: int = PIANO_LOWEST_MIDI,
                  highest: int = PIANO_HIGHEST_MIDI,
                  notation: str = "american") -> Tuple[Optional[str], Optional[str]]:
    """Markers for the sounding notes the piano doesn't draw.

    Returns:
        ``(below, above)``: ``"◂ C3"`` for the notes under the lowest key and
        ``"D6 ▸"`` for those over the highest (several names, lowest
        first, when more than one), or None for an end with none. The
        names are spelled in ``notation``.
    """
    notes = sorted(set(midi_notes))
    below = [midi_name(m, notation) for m in notes if m < lowest]
    above = [midi_name(m, notation) for m in notes if m > highest]
    return ("◂ " + " ".join(below) if below else None,
            " ".join(above) + " ▸" if above else None)


def bass_note(notes: Iterable[Tuple[str, int]]) -> Optional[str]:
    """The name of the lowest of ``(name, octave)`` notes, or None for none."""
    lowest = None
    lowest_midi = float('inf')
    for note_name, octave in notes:
        midi = note_to_midi(note_name, octave)
        if midi < lowest_midi:
            lowest_midi = midi
            lowest = note_name
    return lowest


def normalize_note_name(note_name: str) -> str:
    """Capitalize a note name and spell flats as sharps (``db`` -> ``C#``)."""
    if not note_name:
        return note_name
    normalized = note_name[0].upper() + note_name[1:]
    if 'b' in normalized:
        normalized = _FLAT_TO_SHARP.get(normalized, normalized)
    return normalized


def spelling_preference(note_string: str) -> Optional[str]:
    """Whether typed notes lean on flats or sharps (:data:`FLATS`,
    :data:`SHARPS`), or None when they use neither or as many of each."""
    flats = sharps = 0
    for part in re.split(r'[,\s;/|]+', note_string.strip()):
        match = _NOTE_TOKEN.match(_without_accents(part))
        if match and match.group(2):
            if 'b' in match.group(2):
                flats += 1
            else:
                sharps += 1
    if flats == sharps:
        return None
    return FLATS if flats > sharps else SHARPS


def _music21_name(name: str) -> str:
    return name.replace('b', '-') if len(name) == 2 else name


def _app_name(name: str) -> str:
    """A music21 note or chord name in the app's spelling (``B-`` -> ``Bb``)."""
    return name.replace('-', 'b')


def _root_of(chord_name: str) -> str:
    """The root note of a chord name (``Bbm7`` -> ``Bb``)."""
    match = _ROOT.match(chord_name)
    return match.group(0) if match else ''


def spell_for_identification(names: Iterable[str], bass: Optional[str] = None,
                             preference: Optional[str] = None) -> Dict[str, str]:
    """Spell sharp-named keys so the chord they make stacks in thirds.

    music21 finds a chord's root from how its notes are spelled: A# D F is
    not stacked in thirds, so it reads as some kind of D, while Bb D F reads
    as Bb major. Each black key is tried as a sharp and as a flat, and the
    spellings music21 calls a plain chord (not an "enharmonic equivalent")
    win. Among those, the typed ``preference`` comes first, then a usual
    root spelling (Eb minor over D# minor), a root in the bass, fewer
    accidentals, and sharps.

    Args:
        names: Note names spelled with sharps (:data:`NOTE_NAMES`).
        bass: The lowest note's name, also with a sharp.
        preference: :data:`FLATS`, :data:`SHARPS` or None.

    Returns:
        Each name mapped to its spelling. When no spelling reads as a plain
        chord, the preferred accidental is used throughout (sharps by default).
    """
    names = sorted(set(names), key=NOTE_NAMES.index)
    black = [n for n in names if n in _SHARP_TO_FLAT]
    best_key = None
    best: Optional[Dict[str, str]] = None
    if 2 <= len(names) <= 7:
        for flats in itertools.product((False, True), repeat=len(black)):
            flat = {n for n, f in zip(black, flats) if f}
            spelled = {n: _SHARP_TO_FLAT[n] if n in flat else n for n in names}
            try:
                c = m21_chord.Chord([_music21_name(spelled[n]) for n in names])
                if c.commonName.startswith('enharmonic'):
                    continue
                root = _app_name(c.root().name)
            except Exception:  # music21 can't read it: not a chord
                continue
            sharps = len(black) - len(flat)
            key = (
                sharps if preference == FLATS else len(flat) if preference == SHARPS else 0,
                root not in _USUAL_ROOTS,
                bass is not None and root != spelled.get(bass),
                len(flat),
            )
            if best_key is None or key < best_key:
                best_key, best = key, spelled
    if best is not None:
        return best
    if preference == FLATS:
        return {n: _SHARP_TO_FLAT.get(n, n) for n in names}
    return {n: n for n in names}


#: The piano's top octave (two octaves from C4): typed notes stack up to it.
_HIGHEST_TYPED_OCTAVE = 5


def parse_notes(note_string: str) -> Tuple[List[Tuple[str, int]], List[str]]:
    """Parse typed notes ("C4, E4, G4", "C E G", "Do Mi Sol", "Sib4 Re5").

    Either notation is read, whatever the song's: American letters and
    solfège syllables (accents are ignored, ``Ré`` is ``Re``).

    A note without an octave goes just above the note typed before it, so
    "E G# B C" is E4 G#4 B4 C5 (E in the bass, as typed); the first one is
    in octave 4. One that would go past the piano (octave 5) stays in 5.

    Any number of accidentals is read (``Bbb`` is A, ``G##`` is A), and the
    octave is the written note's: ``B#3`` sounds C4, ``Cb4`` sounds B3. The
    notes come back spelled with sharps (:data:`NOTE_NAMES`).

    Forgiving like the desktop field: a token that starts with a note name
    counts as that note (``Cm`` reads as ``C``), anything else is skipped.

    Returns:
        ``(notes, not_understood)``: the ``(name, octave)`` notes in typed
        order, and the tokens that weren't exactly a note (skipped or only
        partly read).
    """
    notes: List[Tuple[str, int]] = []
    not_understood: List[str] = []
    previous: Optional[int] = None
    for part in re.split(r'[,\s;/|]+', note_string.strip()):
        part = part.strip()
        if not part:
            continue
        part = _without_accents(part)
        match = _NOTE_TOKEN.match(part)
        midi = None
        if match:
            letter = _SOLFEGE.get(match.group(1).lower(), match.group(1)).upper()
            accidentals = match.group(2)
            shift = _NATURAL_SEMITONE[letter] + accidentals.count('#') - accidentals.count('b')

            def midi_in(octave: int) -> int:
                return (octave + 1) * 12 + shift

            if match.group(3):
                octave = int(match.group(3))
            elif previous is None:
                octave = 4
            else:
                octave = 4
                while octave < _HIGHEST_TYPED_OCTAVE and midi_in(octave) <= previous:
                    octave += 1
            midi = midi_in(octave)
        if midi is not None and 0 <= midi <= 127:
            previous = midi
            notes.append((NOTE_NAMES[midi % 12], midi // 12 - 1))
            if match.end() != len(part):
                not_understood.append(part)
        else:
            not_understood.append(part)
    return notes, not_understood


def _without_accents(text: str) -> str:
    """``text`` with its accents dropped (``Ré`` -> ``Re``)."""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')


#: How unusual a chord quality is (lower is more common), for the order of
#: the candidates. A quality not listed counts as 3.
_QUALITY_RARITY = {
    '': 0, 'm': 0, '7': 1, 'm7': 1, 'maj7': 1,
    '6': 1.5, 'm6': 1.5, 'sus4': 1.5, 'sus2': 1.5, 'add9': 1.5, 'madd9': 1.5,
    '9': 2, 'm9': 2, 'maj9': 2, '7sus4': 2, 'dim': 2, 'dim7': 2, 'm7b5': 2,
    'aug': 2.5, '7b9': 2.5, 'mmaj7': 2.5,
}

#: Cost of an added tone: a plain one (add9, add11, add13) or an altered
#: one (addb6, addb9, add#11), which is rarer.
_ADDED_COST = 1.5
_ALTERED_ADDED_COST = 3

#: Extra cost of a root that isn't the bass, when the bass is a note of the
#: chord before its added tones, by its interval above the root: the 3rd
#: (first inversion), the 5th, else (a 7th, 6th or altered 5th). A bass
#: that is an added tone, or no note of the chord, costs the most.
_INVERSION_COST = {3: 1.5, 4: 1.5, 7: 2}
_OTHER_INVERSION_COST = 2.5
_ADDED_BASS_COST = 4


def _likelihood(name: str, bass: Optional[str],
                base_pitches: Callable[[str], Set[int]]) -> Tuple[float, str]:
    """Sort key for a candidate: most likely first.

    A chord rooted on the bass beats an inversion, which beats a reading
    whose bass is an added tone (E G# B C: Eaddb6, then Caugmaj7/E, then
    G#augadd#9/E). Common qualities beat rare ones and each added tone
    costs a little, an altered one more. On another root than the bass,
    the slash form (which says where the bass is) comes just before the
    plain name.

    Args:
        name: The candidate.
        bass: The lowest selected note, or None.
        base_pitches: The pitch classes of a chord name (``"Em"``).
    """
    body, _, slash = name.partition('/')
    root = _root_of(body)
    quality = body[len(root):]
    base, *added = quality.split('add')
    cost = _QUALITY_RARITY.get(base, 3)
    cost += sum(_ALTERED_ADDED_COST if tone[:1] in ('b', '#') else _ADDED_COST for tone in added)
    if bass and root and _pitch(root) != _pitch(bass):
        interval = (_pitch(bass) - _pitch(root)) % 12
        if _pitch(bass) in base_pitches(root + base):
            cost += _INVERSION_COST.get(interval, _OTHER_INVERSION_COST)
        else:
            cost += _ADDED_BASS_COST
        if not slash:
            cost += 0.1
    return (cost, name)


def _pitch(name: str) -> int:
    """The pitch class of a note name (flats too)."""
    return NOTE_NAMES.index(normalize_note_name(name))


class ChordIdentifierViewModel(Observable):
    """ViewModel for the chord identifier window.

    Manages note selection, chord identification, and playback for the
    chord identifier UI.

    Identification and the likelihood order work in American names; what
    the views get (:attr:`candidates`, :attr:`info_lines`,
    :attr:`identified_chords`) is spelled in :attr:`notation`, the open
    song's, and :meth:`play_chord` takes a candidate in either spelling.
    """

    def __init__(self, song_parser_service: SongParserService, audio_service=None):
        """Initialize the ViewModel.

        Args:
            song_parser_service: Service for chord detection and identification
            audio_service: Optional audio service for playing notes and chords
        """
        super().__init__()

        self._chord_service = song_parser_service
        self._audio_service = audio_service

        # Observable state
        self._selected_notes: Set[Tuple[str, int]] = set()  # (note_name, octave) = []
        # The result: the chord names (American), or the explanation shown
        # for lack of them: the notes it names (American, spelled for
        # identification) and the lines after them.
        self._candidates: List[str] = []
        self._message_notes: List[str] = []
        self._message: List[str] = [SELECT_NOTES_PROMPT]
        self._notation: str = "american"
        # How the last typed notes were spelled (FLATS/SHARPS), so the answer
        # is spelled the same way; None after a key tap.
        self._spelling: Optional[str] = None
        # The MIDI notes of the candidate played last, for the piano to
        # highlight; a new token for each play restarts the views' timers.
        self._sounding: Tuple[int, ...] = ()
        self._sounding_token: int = 0

    @property
    def selected_notes(self) -> Set[Tuple[str, int]]:
        """Get the currently selected notes."""
        return self._selected_notes

    @property
    def identified_chords(self) -> List[str]:
        """What the results list shows: :attr:`candidates`, or
        :attr:`info_lines` when there are none."""
        return self.candidates if self._candidates else self.info_lines

    @property
    def candidates(self) -> List[str]:
        """The identified chord names only (no explanation lines), likeliest
        first, spelled in :attr:`notation`."""
        return [spell(name, self._notation) for name in self._candidates]

    @property
    def info_lines(self) -> List[str]:
        """What to say instead of chords (a prompt, "no chord found", an error);
        empty when there are candidates. Note names are in :attr:`notation`."""
        if self._candidates:
            return []
        lines = list(self._message)
        if self._message_notes:
            names = ', '.join(spell(n, self._notation) for n in self._message_notes)
            lines[:0] = [f"Notes: {names}", ""]
        return lines

    @property
    def notation(self) -> str:
        """The notation names are shown in (the open song's): ``american``
        or ``european``."""
        return self._notation

    def american_chord(self, chord_name: str) -> str:
        """The American name of a candidate shown in either spelling
        (``Lam7`` -> ``Am7`` while European). A name that isn't a candidate
        is read as written in :attr:`notation`."""
        if chord_name in self._candidates:
            return chord_name
        for name in self._candidates:
            if spell(name, self._notation) == chord_name:
                return name
        if self._notation == "european":
            return NotationConverter.chord_european_to_american(chord_name)
        return chord_name

    @property
    def sounding(self) -> Tuple[int, ...]:
        """The MIDI notes :meth:`play_chord` sent to the synth last, lowest
        first; empty once the selection changes. The views highlight them
        for :data:`SOUNDING_SECONDS` (``observe("sounding", ...)``)."""
        return self._sounding

    @property
    def sounding_token(self) -> int:
        """Changes with every :meth:`play_chord`, so a view can restart its
        timer when the same notes play again."""
        return self._sounding_token

    def _clear_sounding(self) -> None:
        if self._sounding:
            self._sounding = ()
            self.notify("sounding", self._sounding)

    def toggle_note(self, note_name: str, octave: int) -> None:
        """Toggle a note selection on/off.

        Args:
            note_name: Note name (e.g., "C", "D#", "Bb")
            octave: Octave number
        """
        note_tuple = (note_name, octave)
        self._spelling = None

        if note_tuple in self._selected_notes:
            self._selected_notes.remove(note_tuple)
            logger.debug(f"Deselected note: {note_name}{octave}")
        else:
            self._selected_notes.add(note_tuple)
            logger.debug(f"Selected note: {note_name}{octave}")

        self._clear_sounding()
        self.notify("selected_notes", self._selected_notes.copy())

        # Re-identify chords with new selection
        self._identify_chords()

    def set_notes(self, notes: List[Tuple[str, int]], spelling: Optional[str] = None) -> None:
        """Set the selected notes.

        Args:
            notes: List of (note_name, octave) tuples
            spelling: How the notes were typed (:func:`spelling_preference`),
                so the chords are named with the same accidentals; None
                for piano keys.
        """
        self._spelling = spelling
        self._selected_notes = set(notes)
        self._clear_sounding()
        self.notify("selected_notes", self._selected_notes.copy())
        self._identify_chords()

    def clear_selection(self) -> None:
        """Clear all selected notes."""
        logger.debug("Clearing note selection")
        self._selected_notes.clear()
        self._spelling = None
        self._candidates = []
        self._message_notes = []
        self._message = [SELECT_NOTES_PROMPT]
        if self._sounding and self._audio_service is not None:
            self._audio_service.stop_click_notes()  # a roll still going stops
        self._clear_sounding()
        self.notify("selected_notes", self._selected_notes.copy())
        self.notify("identified_chords", self.identified_chords)

    def _identify_chords(self) -> None:
        """Identify possible chords from selected notes with advanced logic.

        This includes:
        - Trying all inversions/rotations
        - Special handling for symmetric chords (diminished 7th)
        - Bass note detection for slash chords
        - Every note as the root, with added tones (Eaddb6, Cadd#11)
        """
        self._candidates = []
        self._message_notes = []
        if not self._selected_notes:
            self._message = [SELECT_NOTES_PROMPT]
            self.notify("identified_chords", self.identified_chords)
            return

        # The selection is piano keys, spelled with sharps. Respell them so
        # the chord they make stacks in thirds (A# D F is Bb D F): music21
        # finds the root from the spelling. Octaves don't matter here.
        keys = sorted(set(note for note, _ in self._selected_notes), key=NOTE_NAMES.index)
        lowest = self._get_bass_note_from_selection()
        spelled = spell_for_identification(keys, lowest, self._spelling)
        note_names = [spelled[n] for n in keys]
        bass_note = spelled.get(lowest) if lowest else None

        try:
            all_chords = set()

            # music21 spells flats with '-': hand it its own spelling, so a
            # root and a bass compare equal (B- vs B-, not B- vs Bb).
            m21_notes = [_music21_name(n) for n in note_names]
            m21_bass = _music21_name(bass_note) if bass_note else None

            # Try the notes in their original order
            chord_names = self._chord_service.identify_chord_from_notes(m21_notes, m21_bass)
            all_chords.update(chord_names)

            # Check if this is a symmetric chord (diminished 7th)
            # For these chords, manually add all possible root interpretations
            if self._is_diminished_seventh(keys):
                # All notes can be the root of a dim7 chord
                for note in note_names:
                    if bass_note and bass_note != note:
                        all_chords.add(f"{note}dim7/{bass_note}")
                    all_chords.add(f"{note}dim7")

            # For better coverage, try all inversions/rotations for non-symmetric chords
            if not self._is_diminished_seventh(keys):
                for i in range(1, len(m21_notes)):
                    rotated = m21_notes[i:] + m21_notes[:i]
                    chord_names = self._chord_service.identify_chord_from_notes(rotated, m21_bass)
                    all_chords.update(chord_names)

            all_chords = {_app_name(name) for name in all_chords}

            # Every note as the root, with added tones where needed: E G# B C
            # is also Eaddb6, and C E G A is also C6 (music21 only says Am7).
            # Over a bass that is a chord tone of the reading it's a slash
            # chord; one that isn't is named without the bass over it, so the
            # bass is never counted twice (G B D F: G7 and Bdim/G).
            all_chords.update(self._chord_service.name_by_root(note_names, bass_note))

            if all_chords:
                chord_list = sorted(all_chords, key=lambda name: _likelihood(name, bass_note, self._pitch_classes))
                logger.info(f"Identified {len(chord_list)} possible chords from notes: {note_names}")
                self._candidates = chord_list
            else:
                logger.info(f"No chords identified from notes: {note_names}")
                self._message_notes = list(note_names)
                self._message = ["No standard chord found.", "Try adding or removing notes."]

        except Exception as e:
            logger.error(f"Error identifying chords: {e}", exc_info=True)
            self._candidates = []
            self._message_notes = list(note_names)
            self._message = [f"Error: {str(e)}", "Make sure you've selected valid notes."]

        self.notify("identified_chords", self.identified_chords)

    def _get_bass_note_from_selection(self) -> Optional[str]:
        """Get the lowest selected note (actual bass note).

        Returns:
            The note name of the lowest selected note, or None if no selection
        """
        return bass_note(self._selected_notes)

    def _is_diminished_seventh(self, note_names: List[str]) -> bool:
        """Check if the notes form a diminished seventh chord.

        Diminished 7th chords are symmetric - any note can be the root.

        Args:
            note_names: List of note names

        Returns:
            True if the notes form a diminished 7th chord
        """
        if len(set(note_names)) != 4:
            return False
        steps = sorted(NOTE_NAMES.index(_FLAT_TO_SHARP.get(n, n)) for n in set(note_names))
        return all(b - a == 3 for a, b in zip(steps, steps[1:]))

    def _pitch_classes(self, chord_name: str) -> Set[int]:
        """The pitch classes of ``chord_name`` (empty if it doesn't resolve)."""
        return {midi % 12 for midi in self._chord_service.chord_to_midi(chord_name)}

    def identify_chords_from_notes(self) -> List[str]:
        """Manually trigger chord identification.

        Returns:
            List of identified chord names
        """
        self._identify_chords()
        return self.identified_chords

    def set_notation(self, notation: str) -> None:
        """Show names in ``notation`` from now on (the open song's).

        Observers get ``notation``, then ``identified_chords`` respelled;
        nothing is identified again.

        Args:
            notation: "american" or "european"

        Raises:
            ValueError: For any other notation.
        """
        if notation not in ("american", "european"):
            raise ValueError(f"unknown notation: {notation!r}")
        if notation == self._notation:
            return
        self.set_and_notify("notation", notation)
        self.notify("identified_chords", self.identified_chords)

    def get_note_list(self) -> List[str]:
        """Get selected notes as a formatted list.

        Returns:
            List of note strings (e.g., ["C4", "E4", "G4"])
        """
        return [f"{note}{octave}" for note, octave in sorted(self._selected_notes)]

    def parse_note_string(self, note_string: str) -> List[Tuple[str, int]]:
        """Parse a space or comma-separated list of notes.

        Args:
            note_string: String like "C4, E4, G4" or "C E G" or "C, E, G"

        Returns:
            List of (note_name, octave) tuples
        """
        return parse_notes(note_string)[0]

    def set_notes_from_string(self, note_string: str) -> None:
        """Set selected notes from a comma-separated string.

        Args:
            note_string: String like "C4, E4, G4"
        """
        try:
            notes = self.parse_note_string(note_string)
            self.set_notes(notes, spelling_preference(note_string))
            logger.debug(f"Set notes from string: {note_string} -> {notes}")
        except Exception as e:
            logger.error(f"Error parsing note string '{note_string}': {e}", exc_info=True)

    def get_selected_note_names(self) -> List[str]:
        """Get just the note names (without octaves) from selection.

        Returns:
            Sorted list of unique note names
        """
        return sorted(set(note for note, _ in self._selected_notes))

    def is_note_selected(self, note_name: str, octave: int) -> bool:
        """Check if a specific note is selected.

        Args:
            note_name: Note name
            octave: Octave number

        Returns:
            True if selected, False otherwise
        """
        return (note_name, octave) in self._selected_notes

    def get_chord_midi_notes(self, chord_name: str, base_octave: int = 3) -> List[int]:
        """Get MIDI notes for a chord name.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            base_octave: Base octave for the chord

        Returns:
            List of MIDI note numbers, or empty list if chord not recognized
        """
        try:
            midi_notes = self._chord_service.chord_to_midi(chord_name, base_octave)
            return midi_notes if midi_notes else []
        except Exception as e:
            logger.error(f"Error converting chord to MIDI: {e}", exc_info=True)
            return []

    def chord_midi_for_piano(self, chord_name: str) -> List[int]:
        """The MIDI notes a candidate plays, placed on the identifier's piano.

        A chord whose lowest note is the selected bass starts on that key
        (E4 G#4 B4 C5 plays Eaddb6 from E4); any other starts in octave 4.
        Notes can still fall outside the piano (:func:`outside_piano`).

        Returns:
            MIDI note numbers, lowest first, or an empty list if the chord
            isn't recognized.
        """
        midi_notes = self.get_chord_midi_notes(chord_name, base_octave=4)
        if not midi_notes or not self._selected_notes:
            return sorted(midi_notes)
        lowest = min(note_to_midi(name, octave) for name, octave in self._selected_notes)
        if min(midi_notes) % 12 == lowest % 12:
            shift = 12 * (lowest // 12 - 5)  # from octave 4 to the bass's octave
            midi_notes = [m + shift for m in midi_notes if 0 <= m + shift <= 127]
        return sorted(midi_notes)

    def normalize_note_name(self, note_name: str) -> str:
        """Normalize a note name (convert flats to sharps, capitalize).

        Args:
            note_name: Note name like "c#", "Db", "C"

        Returns:
            Normalized note name (e.g., "C#")
        """
        return normalize_note_name(note_name)

    def play_note(self, note_name: str, octave: int, duration: float = 1.0) -> None:
        """Play a single note.

        Args:
            note_name: Note name (e.g., "C", "D#")
            octave: Octave number
            duration: Duration in seconds

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play note: AudioService not available")
            return

        self._audio_service.play_note(note_name, octave, duration)
        logger.debug(f"Playing note: {note_name}{octave}")

    def play_chord(self, chord_name: str, duration: float = 2.0, rolled: bool = False) -> None:
        """Play a chord by name, on the piano's keys (:meth:`chord_midi_for_piano`).

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#"), or a candidate
                as shown in European (:meth:`american_chord`)
            duration: Duration in seconds
            rolled: Play the notes one at a time from the lowest up,
                :data:`ROLL_GAP_SECONDS` apart, each held

        Raises:
            ChordDetectionError: If the chord's notes can't be worked out.
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play chord: AudioService not available")
            return

        # Get MIDI notes for the chord, on the piano's keys
        midi_notes = self.chord_midi_for_piano(self.american_chord(chord_name))
        if not midi_notes:
            logger.warning(f"Cannot play chord: No MIDI notes for '{chord_name}'")
            raise ChordDetectionError(f"Could not work out the notes of {chord_name}.")

        self._sound(midi_notes, duration, rolled)
        logger.debug(f"Playing chord: {chord_name}")

    def play_selected_notes(self, duration: float = 2.0, rolled: bool = False) -> None:
        """Play the selected keys, in their octaves (the Play button).

        Nothing happens with no notes selected.

        Args:
            duration: Duration in seconds
            rolled: Play them one at a time from the lowest up (see
                :meth:`play_chord`)

        Raises:
            AudioInitializationError: If the audio output can't be started.
        """
        if self._audio_service is None:
            logger.warning("Cannot play selected notes: AudioService not available")
            return

        if not self._selected_notes:
            logger.warning("No notes selected to play")
            return

        midi_notes = sorted(note_to_midi(name, octave) for name, octave in self._selected_notes)
        self._sound(midi_notes, duration, rolled)
        logger.debug(f"Playing selected notes: {self._selected_notes}")

    def _sound(self, midi_notes: List[int], duration: float, rolled: bool) -> None:
        """Send ``midi_notes`` (lowest first) to the synth, then publish them
        as :attr:`sounding`, so the piano highlights exactly what was sent."""
        if rolled:
            self._audio_service.play_notes_rolled(midi_notes, ROLL_GAP_SECONDS)
        else:
            self._audio_service.play_chord_from_midi(midi_notes, duration)
        self._sounding = tuple(midi_notes)
        self._sounding_token += 1
        self.notify("sounding", self._sounding)
