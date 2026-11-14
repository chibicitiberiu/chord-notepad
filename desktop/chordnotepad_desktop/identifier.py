"""The chord identifier sidebar (plan step F5): the Python side.

The panel is QML (``IdentifierPanel.qml``); what it shows and does comes
from the session's ``IdentifierState`` and its commands, through this model
(Android's ``IdentifierModel.kt`` for the desktop):

* **The piano** is :class:`PianoLayout`: two octaves from the core's
  ``PIANO_LOWEST_MIDI`` (C4, which ``IdentifierState.sounding_below`` /
  ``sounding_above`` count from), in white-key units. QML draws the keys from
  :attr:`IdentifierModel.keys` and asks :meth:`IdentifierModel.keyAt` what
  was pressed, so the drawing and the hit test share one geometry. Black keys
  are hit-tested first: they lie over the white keys (pitfall 6: one input
  area for the whole keyboard). The geometry is the mockup's: black keys
  0.62 of a white key wide, 0.6 of the height, centred on the gap.
* **A press** toggles the key (``identifier_toggle_note``; the session
  sounds a key that became selected). Right-click and Shift+click only play
  it (``play_note``).
* **The notes field** (:attr:`IdentifierModel.typed`) is re-parsed on every
  keystroke (``identifier_set_notes_text``, either notation, commas). After
  a key press it shows the session's ``notes_text``; while the user types it
  keeps their text. When the song's notation changes it is respelled only
  if it still showed the selection (Tk's and Android's rule).
* **Candidates**: a click inserts one at the caret (``insert_chord``, then
  the window gives the editor the focus back), ▶ auditions it
  (``play_identified_chord``) and Shift+▶ plays it rolled (resolution 1).
  None are listed while the typed notes have something that isn't a note
  (Android's B5): the session still names chords for the part it read,
  which would read as the answer for what was typed.
* **Sounding keys** (what a candidate or Play sounded) stay lit for the
  state's ``sounding_seconds`` (3 s), with the "◂ C3" / "D6 ▸" markers for
  notes off the keyboard; a new play restarts the time.
* **An insert that fails** (an offset the session refuses, a bug) shows
  Tk's "Could not insert the chord X." with the reason, instead of the
  generic error: :meth:`IdentifierModel.insert_failure`.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, List, Optional, Tuple

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from chordnotepad.viewmodels.chord_identifier_viewmodel import PIANO_LOWEST_MIDI, spell

logger = logging.getLogger(__name__)

#: The piano's octaves (Tk's and Android's two).
OCTAVES = 2
#: Note names by semitone above C, with sharps (as the session spells notes).
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_WHITE_STEPS = (0, 2, 4, 5, 7, 9, 11)
#: A black key's width in white-key widths, and its height as a fraction of
#: the keyboard's (the mockup's piano).
BLACK_WIDTH = 0.62
BLACK_HEIGHT = 0.6

#: Tk's message for an insert that failed (``chordnotepad_tk.main_window``,
#: ``_on_insert_chord_from_identifier``); its title is "Error".
INSERT_FAILED_TITLE = "Error"


def insert_failed_message(chord: str, reason: str) -> str:
    """Tk's "Could not insert the chord X." with the reason under it."""
    return f"Could not insert the chord {chord}.\n\n{reason}"


def instructions(notation: str) -> str:
    """The line over the piano, with an example in ``notation`` (Tk's)."""
    example = "Do Mi Sol or Do, Mi, Sol" if notation == "european" else "C E G or C, E, G"
    return f"Select notes on the piano or type them below (e.g., {example})"


def placeholder(notation: str) -> str:
    """The empty notes field's hint (the mockup's "C E G", in ``notation``)."""
    return "Do Mi Sol" if notation == "european" else "C E G"


@dataclass(frozen=True)
class PianoKey:
    """One key of the identifier's piano.

    Attributes:
        name: The note, with sharps (``C#``).
        octave: Its octave (C4 is middle C).
        midi: Its MIDI number.
        black: A black key.
        left: Its left edge, in white-key widths from the keyboard's left.
        width: Its width, in white-key widths.
    """

    name: str
    octave: int
    midi: int
    black: bool
    left: float
    width: float


class PianoLayout:
    """The identifier's keyboard: ``octaves`` octaves from MIDI ``lowest`` (a C)."""

    def __init__(self, lowest: int = PIANO_LOWEST_MIDI, octaves: int = OCTAVES) -> None:
        self.lowest = lowest
        self.white_count = 7 * octaves
        keys: List[PianoKey] = []
        for i in range(self.white_count):
            keys.append(self._key(lowest + 12 * (i // 7) + _WHITE_STEPS[i % 7], i, 1.0, False))
        for i in range(self.white_count):
            step = _WHITE_STEPS[i % 7]
            if step in (4, 11):         # no black key after E and B
                continue
            keys.append(self._key(lowest + 12 * (i // 7) + step + 1,
                                  i + 1 - BLACK_WIDTH / 2, BLACK_WIDTH, True))
        #: White keys left to right, then black keys left to right.
        self.keys: Tuple[PianoKey, ...] = tuple(keys)

    @staticmethod
    def _key(midi: int, left: float, width: float, black: bool) -> PianoKey:
        return PianoKey(NOTE_NAMES[midi % 12], midi // 12 - 1, midi, black, left, width)

    @property
    def highest(self) -> int:
        """The MIDI number of the top key."""
        return self.lowest + 12 * (self.white_count // 7) - 1

    def key_at(self, u: float, v: float) -> Optional[PianoKey]:
        """The key at ``u`` white-key widths from the left and ``v`` (0-1)
        down from the top; black keys first. None outside the keyboard."""
        if not (0 <= u < self.white_count and 0 <= v < 1):
            return None
        if v < BLACK_HEIGHT:
            for key in self.keys:
                if key.black and key.left <= u < key.left + key.width:
                    return key
        for key in self.keys:
            if not key.black and key.left <= u < key.left + key.width:
                return key
        return None

    def index_of(self, key: PianoKey) -> int:
        return self.keys.index(key)


def _label(key: PianoKey, notation: str) -> str:
    """A key's name in ``notation``; a C carries its octave (``C4``, ``Do4``)."""
    name = spell(key.name, notation)
    return f"{name}{key.octave}" if key.midi % 12 == 0 else name


class IdentifierModel(QObject):
    """The identifier panel's state over the session's ``IdentifierState``.

    Args:
        store: The window's :class:`~chordnotepad_desktop.session_store.SessionStore`.
        editor: The editor's :class:`~chordnotepad_desktop.editor_bridge.EditorBridge`
            (where the caret is, for inserts).
    """

    #: Anything that comes from the state changed (keys, candidates, ...).
    changed = Signal()
    typedChanged = Signal()
    soundingChanged = Signal()

    def __init__(self, store: Any, editor: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._editor = editor
        self._piano = PianoLayout()
        self._state: dict = {}
        self._typed = ""
        self._follow_keys = False
        self._sounding: Tuple[int, ...] = ()
        self._sounding_token: Optional[int] = None
        self._sounding_timer = QTimer(self)
        self._sounding_timer.setSingleShot(True)
        self._sounding_timer.timeout.connect(self._end_sounding)
        #: The chords sent with insert_chord that haven't run yet, oldest first.
        self._inserting: Deque[str] = deque()
        store.stateChanged.connect(self._on_state_changed)
        self._read_state()

    # -- the state ------------------------------------------------------------------

    @Slot(str)
    def _on_state_changed(self, type_name: str) -> None:
        if type_name == "IdentifierState":
            self._read_state()

    def _read_state(self) -> None:
        mapping = self._store.state("IdentifierState")
        state = {key: mapping.value(key) for key in mapping.keys()}
        if state.get("notes") is None:
            return              # not published yet
        before, self._state = self._state, state
        if before and before.get("notation") != state.get("notation"):
            # The field follows if it showed the selection (Android's respell).
            if self._typed.strip() == (before.get("notes_text") or ""):
                self._set_typed(state.get("notes_text") or "")
        if self._follow_keys:
            self._follow_keys = False
            self._set_typed(state.get("notes_text") or "")
        self._read_sounding(state)
        self.changed.emit()

    def _read_sounding(self, state: dict) -> None:
        sounding = tuple(int(n) for n in state.get("sounding") or ())
        token = state.get("sounding_token")
        if not sounding:
            self._set_sounding(())
        elif token != self._sounding_token:
            self._set_sounding(sounding)
            seconds = float(state.get("sounding_seconds") or 0)
            self._sounding_timer.start(max(0, round(seconds * 1000)))
        self._sounding_token = token

    def _set_sounding(self, notes: Tuple[int, ...]) -> None:
        if not notes:
            self._sounding_timer.stop()
        if notes != self._sounding:
            self._sounding = notes
            self.soundingChanged.emit()

    @Slot()
    def _end_sounding(self) -> None:
        self._set_sounding(())

    def _set_typed(self, text: str) -> None:
        if text != self._typed:
            self._typed = text
            self.typedChanged.emit()

    def _notation(self) -> str:
        return self._state.get("notation") or "american"

    # -- for QML: what it shows -------------------------------------------------------

    def _get_notation(self) -> str:
        return self._notation()

    #: The song's notation, ``american`` or ``european``.
    notation = Property(str, _get_notation, notify=changed)

    def _get_keys(self) -> list:
        notation = self._notation()
        return [{"midi": k.midi, "black": k.black, "left": k.left, "width": k.width,
                 "label": _label(k, notation), "isC": k.midi % 12 == 0}
                for k in self._piano.keys]

    #: Every key: ``midi``, ``black``, ``left`` and ``width`` (white-key
    #: widths), ``label`` (in the song's notation, a C with its octave), ``isC``.
    keys = Property("QVariantList", _get_keys, notify=changed)

    def _get_white_count(self) -> int:
        return self._piano.white_count

    #: The white keys across (14).
    whiteCount = Property(int, _get_white_count, constant=True)

    def _get_black_height(self) -> float:
        return BLACK_HEIGHT

    #: A black key's height as a fraction of the keyboard's.
    blackHeight = Property(float, _get_black_height, constant=True)

    def _selected_midis(self) -> List[int]:
        return sorted(int(n["midi"]) for n in self._state.get("notes") or ())

    def _get_selected(self) -> list:
        return self._selected_midis()

    #: The selected notes' MIDI numbers, lowest first (some may be off the keyboard).
    selected = Property("QVariantList", _get_selected, notify=changed)

    def _get_bass(self) -> int:
        notes = self._selected_midis()
        return notes[0] if notes else -1

    #: The lowest selected note (the bass dot), -1 for none.
    bass = Property(int, _get_bass, notify=changed)

    def _get_sounding(self) -> list:
        return list(self._sounding)

    #: The notes still sounding (lit amber), empty once their time is up.
    sounding = Property("QVariantList", _get_sounding, notify=soundingChanged)

    def _get_below(self) -> str:
        return (self._state.get("sounding_below") or "") if self._sounding else ""

    #: "◂ C3" while notes under the keyboard sound, else "".
    soundingBelow = Property(str, _get_below, notify=soundingChanged)

    def _get_above(self) -> str:
        return (self._state.get("sounding_above") or "") if self._sounding else ""

    #: "D6 ▸" while notes over the keyboard sound, else "".
    soundingAbove = Property(str, _get_above, notify=soundingChanged)

    def _get_typed(self) -> str:
        return self._typed

    #: What the notes field shows.
    typed = Property(str, _get_typed, notify=typedChanged)

    def _get_error(self) -> str:
        return self._state.get("typed_text_error") or ""

    #: What wasn't a note in the typed text ("Not a note: H"), or "".
    typedError = Property(str, _get_error, notify=changed)

    def _get_candidates(self) -> list:
        if self._state.get("typed_text_error"):
            return []
        return list(self._state.get("candidates") or ())

    #: The chords to list, likeliest first, in the song's notation.
    candidates = Property("QVariantList", _get_candidates, notify=changed)

    def _get_message(self) -> str:
        if self._state.get("typed_text_error"):
            return ""
        return self._state.get("message") or ""

    #: What to show for lack of candidates (the session's prompt, "No
    #: standard chord found." ...), or "".
    message = Property(str, _get_message, notify=changed)

    def _get_instructions(self) -> str:
        return instructions(self._notation())

    #: The line over the piano (Tk's), with an example in the song's notation.
    instructions = Property(str, _get_instructions, notify=changed)

    def _get_placeholder(self) -> str:
        return placeholder(self._notation())

    #: The empty notes field's hint.
    placeholder = Property(str, _get_placeholder, notify=changed)

    def _get_can_play(self) -> bool:
        return bool(self._state.get("notes"))

    #: Whether Play has notes to play.
    canPlay = Property(bool, _get_can_play, notify=changed)

    # -- for QML: what it does --------------------------------------------------------

    @Slot(float, float, result=int)
    def keyAt(self, u: float, v: float) -> int:  # noqa: N802 (Qt)
        """The MIDI number of the key at ``u`` white-key widths from the left
        and ``v`` (0-1) from the top, black keys first; -1 outside."""
        key = self._piano.key_at(u, v)
        return key.midi if key is not None else -1

    def _key(self, midi: int) -> Optional[PianoKey]:
        return next((k for k in self._piano.keys if k.midi == midi), None)

    @Slot(int)
    def toggleKey(self, midi: int) -> None:  # noqa: N802 (Qt)
        """A left click on a key: select or deselect it; the field follows."""
        key = self._key(midi)
        if key is not None:
            self._follow_keys = True
            self._store.submit("identifier_toggle_note", {"note": key.name, "octave": key.octave})

    @Slot(int)
    def playKey(self, midi: int) -> None:  # noqa: N802 (Qt)
        """A right click or Shift+click on a key: sound it, don't select it."""
        key = self._key(midi)
        if key is not None:
            self._store.submit("play_note", {"note": key.name, "octave": key.octave})

    @Slot(str)
    def type(self, text: str) -> None:
        """The user edited the notes field: select what it names."""
        if text == self._typed:
            return
        self._typed = text
        self._follow_keys = False
        self.typedChanged.emit()
        self._store.submit("identifier_set_notes_text", {"text": text})

    @Slot()
    def clear(self) -> None:
        """Clear: no notes, an empty field."""
        self._follow_keys = False
        self._set_typed("")
        self._store.submit("identifier_clear")

    @Slot(bool)
    def play(self, rolled: bool) -> None:
        """Play: the selected keys as they are (2 s); ``rolled`` one at a time."""
        self._store.submit("identifier_play_selection", {"rolled": bool(rolled)})

    @Slot(str, bool)
    def audition(self, chord: str, rolled: bool) -> None:
        """▶ on a candidate: hear it; ``rolled`` (Shift+▶) one note at a time."""
        self._store.submit("play_identified_chord", {"chord": chord, "rolled": bool(rolled)})

    @Slot(str, result=bool)
    def insert(self, chord: str) -> bool:
        """A click on a candidate: insert it and a space at the caret (the
        session says "Inserted chord: X"; refused while playing). False when
        there is no editor to insert into."""
        position = self._editor.cursor_position()
        if position is None or not chord:
            return False
        offset = self._editor.to_code_point(position)
        self._inserting.append(chord)
        self._store.submit("insert_chord", {"at": offset, "chord": chord})
        self._store.after_commands(self._inserted)
        return True

    def _inserted(self) -> None:
        if self._inserting:
            self._inserting.popleft()

    # -- for the application ----------------------------------------------------------

    def insert_failure(self, message: str, context: Optional[str]) -> Optional[str]:
        """The message for an ``UnexpectedError`` of an ``insert_chord`` this
        model sent (Tk's text, its reason without the exception's type), or
        None when it isn't one of those."""
        if context != "insert_chord" or not self._inserting:
            return None
        reason = str(message)
        head, sep, rest = reason.partition(": ")
        if sep and head.isidentifier() and (head.endswith("Error") or head.endswith("Exception")):
            reason = rest
        return insert_failed_message(self._inserting[0], reason)
