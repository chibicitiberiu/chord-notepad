"""
Guitar chord picker - optimized version with correct note generation
"""

from typing import Dict, List, Optional, Tuple, Set, Union, TYPE_CHECKING
from dataclasses import dataclass, asdict
from copy import deepcopy
import logging
from audio.note_picker_interface import INotePicker

if TYPE_CHECKING:
    from models.chord_notes import ChordNotes

logger = logging.getLogger(__name__)


@dataclass
class GuitarPickerState:
    """Immutable state object for guitar chord picker"""
    previous_fingering: Optional[List[int]] = None
    previous_chord_notes: Optional[List[str]] = None
    current_position: int = 0  # Average fret position
    position_context: Optional[int] = None  # Track general position on neck

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GuitarPickerState':
        """Create from dict"""
        return cls(**data)


class GuitarChordPicker(INotePicker):
    """Optimized guitar chord picker with correct voicing generation"""
    
    # Common tunings - defined by MIDI values (low string to high string)
    # Format: [String 0 (lowest/thickest), String 1, ..., String 5 (highest/thinnest)]
    TUNINGS = {
        'standard': [40, 45, 50, 55, 59, 64],  # E2, A2, D3, G3, B3, E4
        'drop_d': [38, 45, 50, 55, 59, 64],    # D2, A2, D3, G3, B3, E4
        'dadgad': [38, 45, 50, 55, 57, 62],    # D2, A2, D3, G3, A3, D4
        'open_g': [38, 43, 50, 55, 59, 62],    # D2, G2, D3, G3, B3, D4
    }
    
    NOTE_TO_MIDI_BASE = {
        'C': 0, 'C#': 1, 'Db': 1,
        'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4,
        'F': 5, 'F#': 6, 'Gb': 6,
        'G': 7, 'G#': 8, 'Ab': 8,
        'A': 9, 'A#': 10, 'Bb': 10,
        'B': 11
    }
    
    # Common chord shapes (relative to root) - these are "templates"
    CHORD_SHAPES = {
        'major': [
            # Open C shape
            {'pattern': [-1, 3, 2, 0, 1, 0], 'root_string': 1, 'root_fret': 3},
            # Open G shape  
            {'pattern': [3, 2, 0, 0, 0, 3], 'root_string': 0, 'root_fret': 3},
            # Open D shape
            {'pattern': [-1, -1, 0, 2, 3, 2], 'root_string': 3, 'root_fret': 0},
            # Open A shape
            {'pattern': [-1, 0, 2, 2, 2, 0], 'root_string': 1, 'root_fret': 0},
            # Open E shape
            {'pattern': [0, 2, 2, 1, 0, 0], 'root_string': 0, 'root_fret': 0},
            # Barre F shape (E shape barred)
            {'pattern': [1, 3, 3, 2, 1, 1], 'root_string': 0, 'root_fret': 1},
        ],
        'minor': [
            # Am shape
            {'pattern': [-1, 0, 2, 2, 1, 0], 'root_string': 1, 'root_fret': 0},
            # Em shape  
            {'pattern': [0, 2, 2, 0, 0, 0], 'root_string': 0, 'root_fret': 0},
            # Dm shape
            {'pattern': [-1, -1, 0, 2, 3, 1], 'root_string': 3, 'root_fret': 0},
        ]
    }

    def __init__(self, tuning: Union[str, List[int]] = 'standard') -> None:
        """Initialize guitar chord picker

        Args:
            tuning: Either a tuning name (str) or list of 6 MIDI values for strings 0-5
        """

        # Set tuning MIDI values
        if isinstance(tuning, str):
            self.tuning_midi = self.TUNINGS.get(tuning, self.TUNINGS['standard'])
        else:
            # Custom tuning provided as MIDI values
            if len(tuning) != 6:
                raise ValueError("Tuning must have exactly 6 MIDI values (one per string)")
            self.tuning_midi = tuning

        # Derive note names from MIDI values
        self.tuning_notes = [self._midi_to_note(midi) for midi in self.tuning_midi]

        # Initialize state
        self._state = GuitarPickerState()

        # Cache for fingerings
        self._fingering_cache = {}

        # Pre-compute fret-to-note mapping for each string (optimization)
        self._string_note_map = self._build_string_note_map()

    def _build_string_note_map(self) -> List[Dict[int, str]]:
        """Pre-compute which note each fret produces on each string"""
        string_maps = []

        for string_idx in range(6):
            fret_map = {}
            for fret in range(13):  # 0-12 frets
                midi = self.tuning_midi[string_idx] + fret
                note = self._midi_to_note(midi)
                fret_map[fret] = note  # Keep sharps/flats!
            string_maps.append(fret_map)

        return string_maps

    @staticmethod
    def _normalize_note(note: str) -> int:
        """Convert note to MIDI pitch class (0-11) handling enharmonics"""
        note_map = {
            'C': 0, 'C#': 1, 'Db': 1,
            'D': 2, 'D#': 3, 'Eb': 3,
            'E': 4, 'Fb': 4,
            'F': 5, 'E#': 5, 'F#': 6, 'Gb': 6,
            'G': 7, 'G#': 8, 'Ab': 8,
            'A': 9, 'A#': 10, 'Bb': 10,
            'B': 11, 'Cb': 11
        }
        return note_map.get(note, 0)

    @staticmethod
    def _notes_match(note1: str, note2: str) -> bool:
        """Check if two notes are enharmonically equivalent"""
        return GuitarChordPicker._normalize_note(note1) == GuitarChordPicker._normalize_note(note2)

    @property
    def state(self) -> GuitarPickerState:
        """Get current state (returns a copy)"""
        return deepcopy(self._state)

    @state.setter  
    def state(self, new_state: GuitarPickerState) -> None:
        """Set state (accepts a copy)"""
        self._state = deepcopy(new_state)

    def reset(self) -> None:
        """Reset to initial state"""
        self._state = GuitarPickerState()
        self._fingering_cache.clear()

    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        """Convert chord to MIDI notes via guitar fingering"""

        # Extract notes from ChordNotes object
        notes = chord_notes.notes
        bass_note = chord_notes.bass_note

        if not notes:
            return []

        # Find best fingering
        fingering = self._find_best_fingering(notes, bass_note)
        
        # Convert fingering to MIDI notes
        midi_notes = self._fingering_to_midi(fingering)
        
        # Update state
        self._update_state(fingering, notes)
        
        return midi_notes

    def _find_best_fingering(self, chord_notes: List[str], bass_note: Optional[str] = None) -> List[int]:
        """Find the best playable fingering for the chord"""

        # Keep chord notes with their sharps/flats
        chord_note_list = chord_notes

        # Create normalized pitch class set for comparison
        chord_pitch_classes = {self._normalize_note(n) for n in chord_notes}

        # Check cache
        cache_key = (tuple(sorted(chord_pitch_classes)), bass_note)

        if cache_key not in self._fingering_cache:
            # Generate fingerings efficiently
            all_fingerings = self._generate_fingerings_optimized(chord_note_list, bass_note)
            self._fingering_cache[cache_key] = all_fingerings
        else:
            all_fingerings = self._fingering_cache[cache_key]

        if not all_fingerings:
            logger.warning(f"No fingerings found for {chord_notes}, using fallback")
            return self._get_fallback_fingering(chord_notes[0])

        # Score based on current state - PASS chord_notes for bass checking
        if self._state.previous_fingering:
            # Minimize movement from previous position
            best_score = float('inf')
            best_fingering = all_fingerings[0]

            for fingering in all_fingerings:
                score = self._score_fingering_transition(
                    fingering, self._state.previous_fingering, chord_notes
                )
                if score < best_score:
                    best_score = score
                    best_fingering = fingering

            return best_fingering
        else:
            # First chord - prefer open/low position with correct bass
            best_score = float('inf')
            best_fingering = all_fingerings[0]

            for fingering in all_fingerings:
                score = self._score_fingering_initial(fingering, chord_notes)
                if score < best_score:
                    best_score = score
                    best_fingering = fingering

            return best_fingering

    def _generate_fingerings_optimized(self, chord_notes: List[str], bass_note: Optional[str] = None) -> List[List[int]]:
        """Generate fingerings using multiple strategies for speed"""

        fingerings = []

        # Strategy 1: Try common chord shapes first (FAST)
        shape_fingerings = self._try_chord_shapes(chord_notes, bass_note)
        fingerings.extend(shape_fingerings)

        # If we have enough good fingerings, return early
        if len(fingerings) >= 5:
            return fingerings[:10]

        # Strategy 2: Build from chord tones only (MEDIUM)
        position_fingerings = self._build_from_chord_tones(chord_notes, bass_note, max_positions=3)
        fingerings.extend(position_fingerings)

        # Deduplicate
        unique_fingerings = []
        seen = set()
        for f in fingerings:
            key = tuple(f)
            if key not in seen:
                seen.add(key)
                unique_fingerings.append(f)

        return unique_fingerings[:15]  # Return max 15 fingerings

    def _try_chord_shapes(self, chord_notes: List[str], bass_note: Optional[str] = None) -> List[List[int]]:
        """Try to adapt common chord shapes to the target chord"""

        fingerings = []
        root = chord_notes[0] if chord_notes else 'C'

        # Determine chord type (simplified)
        is_minor = len(chord_notes) >= 3  # This is simplified - you'd check actual intervals

        shapes = self.CHORD_SHAPES.get('minor' if is_minor else 'major', [])

        for shape in shapes:
            # Try to transpose this shape to our root
            for position in range(8):  # Try different positions
                fingering = self._transpose_shape(shape, root, position)
                if fingering:
                    # Verify it produces correct notes
                    if self._verify_fingering(fingering, chord_notes, bass_note):
                        fingerings.append(fingering)
                        if len(fingerings) >= 3:
                            return fingerings

        return fingerings

    def _transpose_shape(self, shape: Dict, target_root: str, position: int) -> Optional[List[int]]:
        """Transpose a chord shape to a new position"""
        
        pattern = shape['pattern']
        transposed = []
        
        for fret in pattern:
            if fret == -1:
                transposed.append(-1)
            elif fret == 0 and position == 0:
                transposed.append(0)
            else:
                new_fret = fret + position
                if new_fret > 12:  # Too high
                    return None
                transposed.append(new_fret)
        
        return transposed

    def _build_from_chord_tones(self, chord_notes: List[str], bass_note: Optional[str],
                                max_positions: int = 3) -> List[List[int]]:
        """Build fingerings by only considering chord tones"""

        fingerings = []

        # Create pitch class set for comparison
        chord_pitch_classes = {self._normalize_note(n) for n in chord_notes}

        # Also include bass note for slash chords
        if bass_note:
            bass_pitch_class = self._normalize_note(bass_note)
        else:
            bass_pitch_class = None

        # Try a few positions
        for position in range(max_positions):
            # For each string, find frets that produce chord tones OR bass note
            string_options = []

            for string_idx in range(6):
                options = []

                # Always can mute
                options.append(-1)

                # Check frets in this position range
                for fret in range(max(0, position), min(position + 5, 13)):
                    # Use pre-computed map for speed
                    note = self._string_note_map[string_idx][fret]
                    note_pc = self._normalize_note(note)

                    # Add if it's a chord tone OR the bass note (for slash chords)
                    if note_pc in chord_pitch_classes or note_pc == bass_pitch_class:
                        options.append(fret)

                string_options.append(options)

            # Generate combinations efficiently
            position_fingerings = self._generate_combinations_smart(
                string_options, chord_notes, bass_note
            )

            fingerings.extend(position_fingerings[:5])  # Max 5 per position

            if len(fingerings) >= 10:
                break

        return fingerings

    def _generate_combinations_smart(self, string_options: List[List[int]],
                                    chord_notes: List[str],
                                    bass_note: Optional[str]) -> List[List[int]]:
        """Generate combinations intelligently without exhaustive search"""

        fingerings = []

        # Start with promising combinations
        # Prefer patterns with 3-4 played strings
        for num_played in [4, 3, 5, 6]:
            if len(fingerings) >= 5:
                break

            # Try different string combinations
            combos = self._get_string_combinations(num_played, string_options, chord_notes)

            for combo in combos:
                if self._is_playable(combo):
                    if self._verify_fingering(combo, chord_notes, bass_note):
                        fingerings.append(combo)
                        if len(fingerings) >= 5:
                            break

        return fingerings

    def _get_string_combinations(self, num_played: int, string_options: List[List[int]],
                                chord_notes: List[str]) -> List[List[int]]:
        """Get promising string combinations"""
        from itertools import product

        combos = []

        # Try combinations with consecutive strings
        for start in range(7 - num_played):
            # Get the strings we're playing
            strings_to_play = list(range(start, min(start + num_played, 6)))

            # Build options for each string in this range
            options_for_combo = []
            for i in range(6):
                if i in strings_to_play:
                    # For strings we're playing, use their valid frets (excluding -1)
                    valid_frets = [f for f in string_options[i] if f != -1]
                    if not valid_frets:
                        # If no valid frets, must mute
                        options_for_combo.append([-1])
                    else:
                        # Limit options to avoid explosion
                        options_for_combo.append(valid_frets[:3])
                else:
                    # Muted strings
                    options_for_combo.append([-1])

            # Generate combinations (limit to 20 per range to avoid explosion)
            for combo_tuple in list(product(*options_for_combo))[:20]:
                combo = list(combo_tuple)
                # Skip if all muted
                if all(f == -1 for f in combo):
                    continue
                combos.append(combo)
                if len(combos) >= 50:  # Reasonable limit
                    return combos

        return combos

    def _verify_fingering(self, fingering: List[int], chord_notes: List[str],
                         bass_note: Optional[str]) -> bool:
        """Verify a fingering produces exactly the chord notes"""

        # Get pitch classes of chord notes
        chord_pitch_classes = {self._normalize_note(n) for n in chord_notes}

        notes_played_pitch_classes = set()
        lowest_note = None
        lowest_midi = 999

        for string_idx, fret in enumerate(fingering):
            if fret >= 0:
                note = self._string_note_map[string_idx][fret]
                notes_played_pitch_classes.add(self._normalize_note(note))

                midi = self.tuning_midi[string_idx] + fret
                if midi < lowest_midi:
                    lowest_midi = midi
                    lowest_note = note

        # Must have all chord notes (pitch class matching)
        if not chord_pitch_classes.issubset(notes_played_pitch_classes):
            return False

        # Must NOT have extra notes, EXCEPT the bass note for slash chords
        extra_notes = notes_played_pitch_classes - chord_pitch_classes
        if extra_notes:
            # Allow bass note as an exception (e.g., C/D has D as extra note)
            if bass_note:
                bass_pitch_class = self._normalize_note(bass_note)
                # Remove bass note from extra notes
                extra_notes_without_bass = extra_notes - {bass_pitch_class}
                if extra_notes_without_bass:
                    return False
            else:
                return False

        # Check bass note if specified (enharmonic match)
        if bass_note and lowest_note:
            if not self._notes_match(lowest_note, bass_note):
                return False

        return True

    def _is_playable(self, fingering: Union[List[int], Tuple[int, ...]]) -> bool:
        """Check if a fingering is physically playable"""
        
        fretted = [f for f in fingering if f > 0]
        
        if not fretted:
            return True
        
        # Check stretch
        if max(fretted) - min(fretted) > 4:
            return False
        
        # Check finger count
        unique_frets = set(fretted)
        if len(unique_frets) > 4:
            # Check for barre possibility
            for fret in unique_frets:
                if fretted.count(fret) >= 2:
                    if len(unique_frets) - 1 <= 4:
                        return True
            return False
        
        return True

    def _score_fingering_initial(self, fingering: List[int], chord_notes: List[str] = None) -> float:
        """Score for first chord - prefer correct bass note"""

        score = 0.0
        fretted = [f for f in fingering if f > 0]

        if fretted:
            # Prefer lower positions
            avg_fret = sum(fretted) / len(fretted)
            score += avg_fret * 2

            # Penalize stretches
            stretch = max(fretted) - min(fretted)
            score += stretch * 3

        # Reward open strings
        score -= fingering.count(0) * 2

        # Penalize muted strings
        score += fingering.count(-1) * 1.5

        # NEW: Strongly prefer root note in bass
        if chord_notes:
            root_note = chord_notes[0]  # First note is root
            lowest_string_idx = next((i for i in range(6) if fingering[i] >= 0), None)

            if lowest_string_idx is not None:
                lowest_note = self._string_note_map[lowest_string_idx][fingering[lowest_string_idx]]

                if self._notes_match(lowest_note, root_note):
                    score -= 5  # Big bonus for correct bass
                else:
                    score += 3  # Penalty for wrong bass

        return score

    def _score_fingering_transition(self, fingering: List[int], previous: List[int],
                                chord_notes: List[str] = None) -> float:
        """Score based on transition from previous - also consider bass note"""

        score = 0.0

        # Position change
        curr_pos = self._get_position(fingering)
        prev_pos = self._get_position(previous)
        position_jump = abs(curr_pos - prev_pos)

        if position_jump > 5:
            score += position_jump * 10
        elif position_jump > 3:
            score += position_jump * 5
        else:
            score += position_jump * 2

        # Reward keeping similar pattern
        pattern_similarity = sum(1 for i in range(6) if fingering[i] == previous[i])
        score -= pattern_similarity * 1.5

        # NEW: Still prefer correct bass note even during transitions
        if chord_notes:
            root_note = chord_notes[0]
            lowest_string_idx = next((i for i in range(6) if fingering[i] >= 0), None)

            if lowest_string_idx is not None:
                lowest_note = self._string_note_map[lowest_string_idx][fingering[lowest_string_idx]]

                if self._notes_match(lowest_note, root_note):
                    score -= 3  # Bonus for correct bass (less than initial to prioritize smooth transition)
                else:
                    score += 2  # Smaller penalty during transitions

        return score

    def _get_position(self, fingering: List[int]) -> float:
        """Get average position"""
        
        fretted = [f for f in fingering if f > 0]
        return sum(fretted) / len(fretted) if fretted else 0

    def _fingering_to_midi(self, fingering: List[int]) -> List[int]:
        """Convert fingering to MIDI notes"""
        
        midi_notes = []
        
        for string_idx, fret in enumerate(fingering):
            if fret >= 0:
                midi = self.tuning_midi[string_idx] + fret
                midi_notes.append(midi)
        
        return sorted(midi_notes)

    def _midi_to_note(self, midi: int) -> str:
        """Convert MIDI to note name"""
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        return note_names[midi % 12]

    def _get_fallback_fingering(self, root_note: str) -> List[int]:
        """Simple fallback - just play the root note"""

        # Try to find root on low strings using enharmonic matching
        for string_idx in range(3):  # Try first 3 strings
            for fret in range(13):  # Check all frets
                note = self._string_note_map[string_idx][fret]
                if self._notes_match(note, root_note):
                    fingering = [-1] * 6
                    fingering[string_idx] = fret
                    # Just play the root, don't add anything else
                    return fingering

        # Last resort: mute everything
        return [-1] * 6

    def _update_state(self, fingering: List[int], chord_notes: List[str]) -> None:
        """Update state after playing"""
        
        self._state.previous_fingering = fingering
        self._state.previous_chord_notes = chord_notes
        self._state.current_position = int(self._get_position(fingering))
        
        if fingering:
            fretted = [f for f in fingering if f > 0]
            if fretted:
                self._state.position_context = max(fretted)