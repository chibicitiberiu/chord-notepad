"""
Chord note picker - converts chords to MIDI notes with voice leading
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict
from copy import deepcopy
from audio.note_picker_interface import INotePicker

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

    # MIDI note mapping (C4 = Middle C = MIDI 60)
    NOTE_TO_MIDI_BASE: Dict[str, int] = {
        'C': 0, 'C#': 1, 'Db': 1,
        'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4,
        'F': 5, 'F#': 6, 'Gb': 6,
        'G': 7, 'G#': 8, 'Ab': 8,
        'A': 9, 'A#': 10, 'Bb': 10,
        'B': 11
    }

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
            note_str: Note like "C4", "D#5", "Bb3", or just "C", "D#"
            default_octave: Octave to use if not specified (default 4 = middle C)

        Returns:
            MIDI note number (0-127)
        """
        # Extract note name and octave
        import re
        match = re.match(r'([A-Ga-g][#b]?)(\d+)?', note_str)
        if not match:
            return None

        note_name = match.group(1)
        octave_str = match.group(2)

        # Use specified octave or default
        octave = int(octave_str) if octave_str else default_octave

        # Get base note value
        if note_name not in ChordNotePicker.NOTE_TO_MIDI_BASE:
            return None

        # Calculate MIDI number: (octave + 1) * 12 + note_offset
        # C4 = 60, so octave 4 starts at MIDI 48
        midi_number = (octave + 1) * 12 + ChordNotePicker.NOTE_TO_MIDI_BASE[note_name]

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

        # Find optimal voicing based on state
        if self._state.previous_chord_midi:
            chord_midi = self._find_best_voicing(
                notes,
                self._state.previous_chord_midi,
                self._state.voicing_octave
            )
        else:
            # First chord - use smart initial positioning
            chord_midi = self._get_initial_voicing(notes)

        # Add bass note
        result = []
        if self.add_bass and notes:
            bass_to_use = bass_note if bass_note else notes[0]
            bass_midi = self._note_to_midi(bass_to_use, self.bass_octave)
            if bass_midi is not None:
                result.append(bass_midi)

        result.extend(chord_midi)

        # Update state for next chord
        self._update_state(chord_midi, notes)

        return result

    def _find_best_voicing(self, notes: List[str],
                        previous_midi: List[int],
                        preferred_octave: int) -> List[int]:
        """Find smoothest voice leading from previous chord"""
        
        candidates = []
        
        # Define ideal center range (around middle C)
        IDEAL_CENTER = 60  # Middle C
        IDEAL_RANGE = (48, 72)  # C3 to C5
        
        # Try different octave positions
        for octave_shift in [-1, 0, 1]:
            octave = preferred_octave + octave_shift
            
            # Build chord at this octave
            voicing = []
            for note in notes:
                midi = self._note_to_midi(note, octave)
                
                if midi is None:
                    continue
                
                # Keep notes ascending within the chord
                if voicing and midi < voicing[-1]:
                    midi += 12
                
                voicing.append(midi)
            
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
        
        # Fallback - but aim for middle register
        target_octave = 4 if preferred_octave < 3 else preferred_octave
        return [self._note_to_midi(note, target_octave) for note in notes
                if self._note_to_midi(note, target_octave) is not None]

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

    def _get_initial_voicing(self, notes: List[str]) -> List[int]:
        """Get initial voicing for first chord or after reset"""
        
        # Always start in a good middle position
        # This gives us room to move both up and down
        root = notes[0].rstrip('#b')
        
        # More consistent initial positioning
        octave_map = {
            'C': 4, 'D': 4, 'E': 3,
            'F': 3, 'G': 3, 'A': 3, 'B': 3
        }
        
        octave = octave_map.get(root, 3)
        
        voicing = []
        for note in notes:
            midi = self._note_to_midi(note, octave)
            if midi is None:
                continue
            
            # Keep ascending but check bounds
            if voicing and midi < voicing[-1]:
                midi += 12
            
            # Don't let it go too high within the chord
            if midi > 72:  # C5
                midi -= 12
            
            voicing.append(midi)
        
        return voicing
