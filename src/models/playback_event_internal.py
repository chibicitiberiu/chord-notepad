"""Internal playback event model for producer-consumer architecture."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class MidiEventType(Enum):
    """Types of MIDI events in the playback buffer."""
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    END_OF_SONG = "end_of_song"


@dataclass
class MidiEvent:
    """Represents a MIDI event with absolute timing.

    This event is used internally by the producer-consumer playback architecture
    to decouple chord computation from playback timing.

    Attributes:
        timestamp: Absolute time in seconds from the start of the song
        event_type: Type of MIDI event (NOTE_ON, NOTE_OFF, END_OF_SONG)
        midi_notes: List of MIDI note numbers to play/stop
        velocity: MIDI velocity (0-127), typically used for NOTE_ON
        metadata: Optional metadata for UI callbacks (chord info, line/item indices)
    """
    timestamp: float
    event_type: MidiEventType
    midi_notes: List[int] = field(default_factory=list)
    velocity: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        """String representation for debugging."""
        notes_str = f"[{','.join(map(str, self.midi_notes))}]" if self.midi_notes else "[]"
        return (f"MidiEvent(t={self.timestamp:.3f}s, type={self.event_type.name}, "
                f"notes={notes_str}, vel={self.velocity})")
