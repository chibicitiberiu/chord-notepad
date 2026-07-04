"""
Chord note picker - converts chords to MIDI notes with voice leading
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict
from copy import deepcopy
from audio.note_picker_interface import INotePicker
from chord.midi_converter import parse_note_to_semitone, intervals_from_note_names

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes


@dataclass
class ChordPickerState:
    """Immutable state object for chord picker"""
    previous_chord_midi: Optional[List[int]] = None
    previous_chord_notes: Optional[List[str]] = None
    voicing_octave: int = 3
    position_context: Optional[int] = None  # Track general position on keyboard

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChordPickerState':
        """Create from dict"""
        return cls(**data)


class ChordNotePicker(INotePicker):
    """Picks MIDI notes for chords with intelligent voice leading"""

    def __init__(self, chord_octave: int = 3, bass_octave: int = 2, add_bass: bool = True) -> None:
        """
        Initialize chord note picker

        Args:
            chord_octave: Default octave for chord notes (default 3)
            bass_octave: Default octave for bass note (default 2)
            add_bass: Whether to add a bass note (root doubled) (default True)
        """
        self.chord_octave = chord_octave
        self.bass_octave = bass_octave
        self.add_bass = add_bass
        self._state = ChordPickerState(voicing_octave=chord_octave)

    @property
    def state(self) -> ChordPickerState:
        """Get current state (returns a copy to prevent external modification)"""
        return deepcopy(self._state)

    @state.setter
    def state(self, new_state: ChordPickerState) -> None:
        """Set state (accepts a copy to prevent external references)"""
        self._state = deepcopy(new_state)

    def reset(self) -> None:
        """Reset to initial state"""
        self._state = ChordPickerState(voicing_octave=self.chord_octave)


    @staticmethod
    def _note_to_midi(note_str: str, default_octave: int = 4) -> Optional[int]:
        """
        Convert note string to MIDI number

        Args:
            note_str: Note like "C4", "D#5", "Bb3", "C##5", or just "C", "D#"
            default_octave: Octave to use if not specified (default 4 = middle C)

        Returns:
            MIDI note number (0-127)
        """
        import re
        # Allow any number of accidentals so double-sharps/double-flats parse.
        match = re.match(r'^([A-Ga-g][#b]*)(\d+)?$', note_str)
        if not match:
            return None

        note_name = match.group(1)
        octave_str = match.group(2)
        octave = int(octave_str) if octave_str else default_octave

        semitone = parse_note_to_semitone(note_name)
        if semitone is None:
            return None

        # C4 = 60, so octave 4 starts at MIDI 48
        midi_number = (octave + 1) * 12 + semitone
        return midi_number if 0 <= midi_number <= 127 else None

    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """
        Convert chord to MIDI with voice leading

        Args:
            chord_notes: ChordNotes object with notes, bass_note, and root

        Returns:
            List of MIDI note numbers
        """
        # Extract notes from ChordNotes object
        notes = chord_notes.notes
        bass_note = chord_notes.bass_note

        if not notes:
            return []

        # The chord's register lives in its intervals (semitones above the
        # root): a 9th at +14, an 11th at +17, a 13th at +21. Voice from those
        # so extensions land where they belong instead of collapsing against
        # the root. Reconstruct from note order only when intervals are absent
        # (e.g. a ChordNotes built directly, without going through the helper).
        root_note = chord_notes.root or notes[0]
        intervals = chord_notes.intervals
        if not intervals or len(intervals) != len(notes):
            intervals = intervals_from_note_names(notes)

        # Find optimal voicing based on state
        if self._state.previous_chord_midi:
            chord_midi = self._find_best_voicing(
                root_note,
                intervals,
                self._state.previous_chord_midi,
                self._state.voicing_octave
            )
        else:
            # First chord - use smart initial positioning
            chord_midi = self._get_initial_voicing(root_note, intervals)

        # Add bass note
        result = []
        if self.add_bass and notes:
            bass_to_use = bass_note if bass_note else notes[0]
            bass_midi = self._note_to_midi(bass_to_use, self.bass_octave)
            if bass_midi is not None:
                result.append(bass_midi)

        result.extend(chord_midi)

        # A keyboard voicing can't sound the same key twice - drop exact
        # duplicates (e.g. a wide chord whose root lands on the bass note)
        # while keeping the order.
        seen = set()
        result = [m for m in result if not (m in seen or seen.add(m))]

        # Update state for next chord
        self._update_state(chord_midi, notes)

        return result

    def _find_best_voicing(self, root_note: str, intervals: List[int],
                        previous_midi: List[int],
                        preferred_octave: int) -> List[int]:
        """Find smoothest voice leading from previous chord.

        The chord shape (root + intervals) is rigid, so extensions keep their
        register. Voice leading only chooses which octave the whole block sits
        in - it never folds an individual extension back down against the root.
        """

        candidates = []

        # Define ideal center range (around middle C)
        IDEAL_CENTER = 60  # Middle C
        IDEAL_RANGE = (48, 72)  # C3 to C5

        # Try different octave positions for the whole chord block
        for octave_shift in [-1, 0, 1]:
            octave = preferred_octave + octave_shift

            root_midi = self._note_to_midi(root_note, octave)
            if root_midi is None:
                continue

            # Rigid shape: root plus each register-preserving interval.
            voicing = [root_midi + interval for interval in intervals]
            if not voicing:
                continue

            # Skip if range too wide
            if max(voicing) - min(voicing) > 24:  # More than 2 octaves
                continue

            # Calculate average position
            avg_position = sum(voicing) / len(voicing)

            # Skip if getting too low or too high
            if avg_position < 45:  # Too low (below A2)
                continue
            if avg_position > 75:  # Too high (above Eb5)
                continue

            # Calculate voice leading distance
            voice_distance = self._calculate_voice_distance(voicing, previous_midi)

            # Add penalty for being far from ideal center
            center_penalty = abs(avg_position - IDEAL_CENTER) * 0.5

            # Add stronger penalty for being too low
            if avg_position < IDEAL_RANGE[0]:
                center_penalty += (IDEAL_RANGE[0] - avg_position) * 2

            # Total score combines voice leading and position preference
            total_score = voice_distance + center_penalty

            candidates.append((total_score, voicing))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        # Fallback - aim for the middle register but keep the rigid shape.
        target_octave = 4 if preferred_octave < 3 else preferred_octave
        root_midi = self._note_to_midi(root_note, target_octave)
        if root_midi is None:
            return []
        return [root_midi + interval for interval in intervals]

    def _update_state(self, chord_midi: List[int], chord_notes: List[str]) -> None:
        """Update internal state after playing a chord"""
        self._state.previous_chord_midi = chord_midi
        self._state.previous_chord_notes = chord_notes
        
        # Don't update voicing_octave as aggressively
        # Keep a bias towards the original octave
        if chord_midi:
            avg_midi = sum(chord_midi) / len(chord_midi)
            current_octave = int(avg_midi / 12) - 1
            
            # Only update if we've moved significantly
            if abs(current_octave - self.chord_octave) <= 1:
                # Stay close to original octave with slow drift
                self._state.voicing_octave = self.chord_octave
            else:
                # We've moved far, allow some adjustment
                self._state.voicing_octave = current_octave
            
            self._state.position_context = int(avg_midi)

    def _calculate_voice_distance(self, voicing1: List[int], voicing2: List[int]) -> float:
        """Calculate smooth voice leading distance"""

        # Reward common tones and small movements
        total = 0.0

        for note1 in voicing1:
            # Find closest note in previous chord
            distances = [abs(note1 - note2) for note2 in voicing2]
            min_dist = min(distances)

            # Score based on movement
            if min_dist == 0:
                total -= 3  # Reward keeping same note
            elif min_dist <= 2:
                total += min_dist  # Small movement is good
            elif min_dist <= 7:
                total += min_dist * 1.5  # Medium movement
            else:
                total += min_dist * 2  # Penalize large jumps

        return total

    def _get_initial_voicing(self, root_note: str, intervals: List[int]) -> List[int]:
        """Get initial voicing for first chord or after reset.

        Builds the rigid root + intervals shape (extensions stay an octave above
        the root), then keeps it in a central, hearable register: if the top
        climbs past C5 the whole block drops an octave. Extensions belong in an
        upper octave, but stranded high the chord quality gets thin, so prefer
        the closest register that still keeps them above the root.
        """

        # Start in a good middle position; gives room to move up and down.
        root = root_note.rstrip('#b')
        
        # More consistent initial positioning
        octave_map = {
            'C': 4, 'D': 4, 'E': 3,
            'F': 3, 'G': 3, 'A': 3, 'B': 3
        }
        
        octave = octave_map.get(root, 3)

        root_midi = self._note_to_midi(root_note, octave)
        if root_midi is None:
            return []

        voicing = [root_midi + interval for interval in intervals]

        # Prefer the closest register: drop the whole block (preserving the
        # spread) whenever the top note climbs into a thin, hard-to-hear range.
        while max(voicing) > 72:  # keep the top at/below C5
            voicing = [m - 12 for m in voicing]

        return voicing
