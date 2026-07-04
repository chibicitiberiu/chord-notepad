"""
Interface for note pickers (Piano, Guitar, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes


@dataclass(frozen=True)
class VoicedChord:
    """One voiced chord plus optional model-specific display detail.

    Returned by :meth:`INotePicker.voice_sequence_details`. ``midi_notes`` is
    always the same list :meth:`INotePicker.voice_sequence` yields for that
    position (same order, same content); the extra fields are populated only by
    the models that have them and stay ``None`` everywhere else, so the
    detail-carrying API is a strict superset of the plain one.
    """

    midi_notes: List[int]
    """The voiced MIDI notes for this chord, identical to the corresponding
    entry of :meth:`INotePicker.voice_sequence`."""

    fingering: Optional[List[int]] = None
    """Fretboard fingering for fretted-instrument (guitar) models, else ``None``.

    One entry per string in the spec's string order (lowest string first, the
    same order as ``GuitarChordPicker.tuning_midi``): ``-1`` = muted string,
    ``0`` = open string, a positive integer = that fret. The sounding MIDI note
    of a non-muted string ``s`` is ``tuning_midi[s] + fingering[s]``, so
    ``midi_notes == sorted(tuning_midi[s] + f for s, f in enumerate(fingering)
    if f >= 0)``."""

    hand_split: Optional[int] = None
    """Left-/right-hand split point for the piano model, else ``None``.

    With ``midi_notes`` read low-to-high, ``midi_notes[:hand_split]`` is the
    left hand and ``midi_notes[hand_split:]`` is the right hand. ``0`` when the
    model emits no left-hand (bass) notes (e.g. ``add_bass`` disabled)."""


class INotePicker(ABC):
    """Interface for chord-to-MIDI converters with voice leading"""

    @abstractmethod
    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """
        Convert chord to MIDI notes

        Args:
            chord_notes: ChordNotes object with notes, bass_note, and root

        Returns:
            List of MIDI note numbers
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state for new playback session"""
        pass

    @property
    @abstractmethod
    def state(self):
        """Get current state (implementation-specific)"""
        pass

    @state.setter
    @abstractmethod
    def state(self, value) -> None:
        """Set current state (implementation-specific)"""
        pass

    def voice_sequence(self, sequence: List['ChordNotes']) -> List[List[int]]:
        """Voice an entire song in order.

        Deterministic: the same sequence always yields the same voicings,
        regardless of prior picker state. The default implementation resets and
        voices greedily chord-by-chord; pickers that can do better (e.g. by
        optimizing the whole sequence with lookahead) should override this.

        Args:
            sequence: The chords to voice, in playback order.

        Returns:
            One MIDI-note list per chord, positionally aligned with ``sequence``.
        """
        self.reset()
        return [self.chord_to_midi(cn) for cn in sequence]

    def voice_sequence_details(self, sequence: List['ChordNotes']) -> List['VoicedChord']:
        """Voice an entire song, returning per-chord display detail.

        Same selection and ordering as :meth:`voice_sequence` -- each result's
        ``midi_notes`` equals the corresponding ``voice_sequence`` entry -- but
        wrapped in :class:`VoicedChord` so model-specific detail (a guitar
        fingering, a piano hand split) can ride along. The default
        implementation wraps :meth:`voice_sequence` with detail-less entries
        (``fingering``/``hand_split`` left ``None``); models that have such
        detail override this method and let ``voice_sequence`` delegate to it,
        so the underlying whole-song search runs once and the two APIs can never
        disagree.

        Args:
            sequence: The chords to voice, in playback order.

        Returns:
            One :class:`VoicedChord` per chord, positionally aligned with
            ``sequence``.
        """
        return [VoicedChord(midi_notes=notes) for notes in self.voice_sequence(sequence)]

    @property
    def voice_labels(self) -> Optional[List[str]]:
        """Ordered voice names (top voice first), or ``None``.

        Populated by pickers that voice a fixed ensemble of monophonic voices
        (e.g. an SATB voicer): such pickers guarantee that ``voice_sequence``
        emits exactly one note per voice per chord, ordered LOW to HIGH
        (bottom voice first), with duplicates allowed for unisons. ``None``
        for free-voiced pickers (piano, guitar), which is the default.
        """
        return None

    @property
    def voice_staves(self) -> Optional[List[str]]:
        """Ordered per-voice grand-staff assignments (top voice first), or ``None``.

        Populated by the same fixed-ensemble pickers that report
        :attr:`voice_labels`, in the exact same order (top voice first) and
        with one entry per voice: each entry is ``'treble'`` or ``'bass'``,
        naming which staff of a grand staff that voice is drawn on by a
        chord-sheet staff renderer. ``None`` for free-voiced pickers (piano,
        guitar), which is the default.
        """
        return None
