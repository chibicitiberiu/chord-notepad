"""
Chord identification window with piano roll and note input
"""

import logging
import tkinter as tk
from tkinter import ttk
import re

logger = logging.getLogger(__name__)


class PianoRoll(tk.Canvas):
    """Interactive piano roll widget"""

    # Note names for one octave
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Black key positions (indices in the octave)
    BLACK_KEYS = [1, 3, 6, 8, 10]  # C#, D#, F#, G#, A#

    def __init__(self, parent, octaves=2, on_change=None, audio_player=None):
        """
        Initialize piano roll

        Args:
            parent: Parent widget
            octaves: Number of octaves to display (default 2)
            on_change: Callback function when selection changes
            audio_player: Optional NotePlayer for playing notes
        """
        self.octaves = octaves
        self.on_change = on_change
        self.audio_player = audio_player

        # Calculate dimensions
        self.white_key_width = 30
        self.white_key_height = 120
        self.black_key_width = 20
        self.black_key_height = 80

        # Calculate total white keys (7 per octave)
        white_keys_per_octave = 7
        total_white_keys = white_keys_per_octave * octaves
        width = total_white_keys * self.white_key_width

        super().__init__(parent, width=width, height=self.white_key_height,
                        bg='white', highlightthickness=1, highlightbackground='gray')

        # Selected notes with octave (e.g., ('C', 4), ('E', 4), ('G', 5))
        self.selected_notes = set()

        # Key rectangles for hit testing
        # List of (note_name, octave, x1, y1, x2, y2, canvas_id)
        self.key_rects = []

        # Base octave for the piano roll (first octave shown)
        self.base_octave = 4

        self.draw_piano()
        self.bind("<Button-1>", self.on_click)
        self.bind("<Button-3>", self.on_right_click)  # Right-click

    def draw_piano(self):
        """Draw the piano keys"""
        self.delete("all")
        self.key_rects.clear()

        x = 0
        for octave_offset in range(self.octaves):
            current_octave = self.base_octave + octave_offset

            # Draw white keys first
            white_x = x
            for i in range(12):
                if i not in self.BLACK_KEYS:
                    note_name = self.NOTE_NAMES[i]

                    # Determine if this note (with octave) is selected
                    is_selected = (note_name, current_octave) in self.selected_notes
                    fill_color = '#4a90e2' if is_selected else 'white'
                    outline_color = '#2a5a92' if is_selected else 'black'

                    rect_id = self.create_rectangle(
                        white_x, 0,
                        white_x + self.white_key_width, self.white_key_height,
                        fill=fill_color, outline=outline_color, width=2
                    )

                    # Add label at bottom
                    self.create_text(
                        white_x + self.white_key_width // 2,
                        self.white_key_height - 10,
                        text=note_name, font=('Arial', 8),
                        fill='white' if is_selected else 'black'
                    )

                    self.key_rects.append((
                        note_name, current_octave, white_x, 0,
                        white_x + self.white_key_width, self.white_key_height,
                        rect_id
                    ))

                    white_x += self.white_key_width

            # Draw black keys on top
            black_positions = [
                (0.7, 'C#'),   # Between C and D
                (1.7, 'D#'),   # Between D and E
                (3.7, 'F#'),   # Between F and G
                (4.7, 'G#'),   # Between G and A
                (5.7, 'A#'),   # Between A and B
            ]

            for pos, note_name in black_positions:
                black_x = x + int(pos * self.white_key_width)

                is_selected = (note_name, current_octave) in self.selected_notes
                fill_color = '#4a90e2' if is_selected else 'black'

                rect_id = self.create_rectangle(
                    black_x, 0,
                    black_x + self.black_key_width, self.black_key_height,
                    fill=fill_color, outline='black', width=2
                )

                # Add label
                self.create_text(
                    black_x + self.black_key_width // 2,
                    self.black_key_height - 10,
                    text=note_name, font=('Arial', 7), fill='white'
                )

                self.key_rects.append((
                    note_name, current_octave, black_x, 0,
                    black_x + self.black_key_width, self.black_key_height,
                    rect_id
                ))

            x = white_x

    def on_click(self, event):
        """Handle left mouse click on piano - toggle and play"""
        # Check black keys first (they're on top)
        for note_name, octave, x1, y1, x2, y2, _ in reversed(self.key_rects):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.toggle_note(note_name, octave, play=True)
                break

    def on_right_click(self, event):
        """Handle right mouse click on piano - play without selection"""
        # Check black keys first (they're on top)
        for note_name, octave, x1, y1, x2, y2, _ in reversed(self.key_rects):
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.play_note(note_name, octave)
                break

    def toggle_note(self, note_name, octave, play=False):
        """Toggle note selection and optionally play it"""
        note_tuple = (note_name, octave)

        if note_tuple in self.selected_notes:
            self.selected_notes.remove(note_tuple)
        else:
            self.selected_notes.add(note_tuple)
            # Play the note when selected
            if play:
                self.play_note(note_name, octave)

        self.draw_piano()

        if self.on_change:
            self.on_change()

    def play_note(self, note_name, octave):
        """Play a single note at the specified octave"""
        if not self.audio_player:
            return

        try:
            # Convert note name to MIDI note number
            midi_note = self.note_to_midi(note_name, octave)
            # Play the note
            self.audio_player.play_notes_immediate([midi_note])
        except Exception as e:
            logger.error(f"Error playing note: {e}", exc_info=True)

    def note_to_midi(self, note_name, octave):
        """
        Convert note name to MIDI note number

        Args:
            note_name: Note name like 'C', 'C#', etc.
            octave: Octave number

        Returns:
            MIDI note number
        """
        # MIDI note 60 = C4 (middle C)
        # Each octave is 12 semitones
        note_offset = self.NOTE_NAMES.index(note_name)
        midi_note = 12 + (octave * 12) + note_offset
        return midi_note

    def set_notes(self, note_names):
        """
        Set selected notes from list of note names (without octave info)
        Selects the note in the first octave where it appears
        """
        self.selected_notes.clear()
        for note_name in note_names:
            # Add to first octave (base octave)
            self.selected_notes.add((note_name, self.base_octave))
        self.draw_piano()

    def get_notes(self):
        """Get list of unique selected note names (without octave)"""
        # Extract unique note names from selected notes (ignore octave)
        unique_notes = set(note_name for note_name, octave in self.selected_notes)
        return sorted(unique_notes, key=lambda n: self.NOTE_NAMES.index(n))

    def get_bass_note(self):
        """Get the lowest selected note (actual bass note)"""
        if not self.selected_notes:
            return None

        # Find the note with the lowest MIDI number
        lowest = None
        lowest_midi = float('inf')

        for note_name, octave in self.selected_notes:
            midi = self.note_to_midi(note_name, octave)
            if midi < lowest_midi:
                lowest_midi = midi
                lowest = note_name

        return lowest


class ChordIdentifierWindow(tk.Toplevel):
    """Window for identifying chords from notes"""

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Identify Chord")
        self.geometry("600x550")
        self.transient(parent)

        # Store reference to parent window for inserting chords
        self.parent_window = parent

        # Get audio player and chord picker from parent
        self.audio_player = getattr(parent, 'audio_player', None)
        self.chord_picker = getattr(parent, 'chord_picker', None)

        # Initialize ChordHelper
        from chord.helper import ChordHelper
        self.chord_helper = ChordHelper()

        self.create_widgets()

        # Center window
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def create_widgets(self):
        """Create window widgets"""
        # Instructions
        instructions = tk.Label(
            self,
            text="Select notes on the piano or type them below (e.g., C E G or C, E, G)",
            font=('Arial', 10),
            wraplength=550
        )
        instructions.pack(pady=10)

        # Piano roll
        piano_frame = ttk.Frame(self)
        piano_frame.pack(pady=10)

        self.piano_roll = PianoRoll(piano_frame, octaves=2, on_change=self.on_piano_change,
                                     audio_player=self.audio_player)
        self.piano_roll.pack()

        # Note input
        input_frame = ttk.Frame(self)
        input_frame.pack(pady=10, padx=20, fill=tk.X)

        ttk.Label(input_frame, text="Notes:").pack(side=tk.LEFT, padx=5)

        self.note_entry = ttk.Entry(input_frame, font=('Arial', 11))
        self.note_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.note_entry.bind("<KeyRelease>", self.on_text_change)

        clear_button = ttk.Button(input_frame, text="Clear", command=self.clear_all)
        clear_button.pack(side=tk.LEFT, padx=5)

        # Results area
        results_frame = ttk.LabelFrame(self, text="Possible Chords", padding=10)
        results_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        # Listbox for results
        scroll = ttk.Scrollbar(results_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox = tk.Listbox(
            results_frame,
            height=8,
            font=('Arial', 11),
            yscrollcommand=scroll.set,
            activestyle='dotbox'
        )
        self.results_listbox.pack(fill=tk.BOTH, expand=True)
        scroll.config(command=self.results_listbox.yview)

        # Bind single-click to play chord
        self.results_listbox.bind("<Button-1>", self.on_chord_click)
        # Bind double-click to insert
        self.results_listbox.bind("<Double-Button-1>", self.on_chord_double_click)

        # Insert button
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10, padx=20, fill=tk.X)

        insert_button = ttk.Button(button_frame, text="Insert into Editor", command=self.insert_selected_chord)
        insert_button.pack(side=tk.RIGHT)

        # Show info message initially
        self.results_listbox.insert(tk.END, "Select notes to identify chords...")
        self.results_listbox.config(state=tk.DISABLED)

    def on_piano_change(self):
        """Handle piano roll selection change"""
        notes = self.piano_roll.get_notes()
        self.note_entry.delete(0, tk.END)
        if notes:
            self.note_entry.insert(0, ' '.join(notes))
        self.identify_chord()

    def on_text_change(self, event=None):
        """Handle text entry change"""
        text = self.note_entry.get()
        notes = self.parse_notes(text)
        self.piano_roll.set_notes(notes)
        self.identify_chord()

    def parse_notes(self, text):
        """Parse note names from text input"""
        # Split by spaces, commas, or other punctuation
        parts = re.split(r'[,\s;/|]+', text.strip())

        notes = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Normalize note name (capitalize first letter)
            if len(part) >= 1:
                # Handle notes like "c#", "Db", "C", etc.
                normalized = part[0].upper() + part[1:]

                # Validate it's a real note
                if normalized in PianoRoll.NOTE_NAMES or normalized.replace('b', '#') in PianoRoll.NOTE_NAMES:
                    # Convert flats to sharps for consistency
                    if 'b' in normalized:
                        # Simple flat to sharp conversion
                        flat_to_sharp = {
                            'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'
                        }
                        normalized = flat_to_sharp.get(normalized, normalized)

                    notes.append(normalized)

        return notes

    def identify_chord(self):
        """Identify possible chords from selected notes"""
        notes = self.piano_roll.get_notes()
        bass_note = self.piano_roll.get_bass_note()  # Get actual lowest note

        if not notes:
            self.show_results(["Select notes to identify chords..."])
            return

        try:
            # Use ChordHelper to identify chords
            all_chords = set()

            # Try the notes in their original order
            chord_names = self.chord_helper.identify_chord(notes, bass_note)
            all_chords.update(chord_names)

            # Check if this is a symmetric chord (diminished 7th)
            # For these chords, manually add all possible root interpretations
            if self.is_diminished_seventh(notes):
                # All notes can be the root of a dim7 chord
                for note in notes:
                    if bass_note and bass_note != note:
                        all_chords.add(f"{note}dim7/{bass_note}")
                    all_chords.add(f"{note}dim7")

            # For better coverage, try all inversions/rotations for non-symmetric chords
            if not self.is_diminished_seventh(notes):
                for i in range(1, len(notes)):
                    rotated = notes[i:] + notes[:i]
                    chord_names = self.chord_helper.identify_chord(rotated, bass_note)
                    all_chords.update(chord_names)

            if all_chords:
                # Sort chords: prioritize simpler chords, then alphabetically
                chord_list = sorted(all_chords, key=lambda c: (len(c), c))
                self.show_results(chord_list)
            else:
                self.show_results([
                    f"Notes: {', '.join(notes)}",
                    "",
                    "No standard chord found.",
                    "Try adding or removing notes."
                ])

        except Exception as e:
            self.show_results([
                f"Notes: {', '.join(notes)}",
                "",
                f"Error: {str(e)}",
                "Make sure you've selected valid notes."
            ])

    def is_diminished_seventh(self, notes):
        """Check if the notes form a diminished seventh chord"""
        if len(notes) != 4:
            return False

        # Check if any interpretation is a diminished 7th chord
        for note in notes:
            chord_name = f"{note}dim7"
            chord_notes = self.chord_helper.get_notes(chord_name)
            if chord_notes and set(chord_notes) == set(notes):
                return True

        return False

    def identify_chord_music21(self, notes, actual_bass_note=None):
        """
        Identify chord using music21

        Args:
            notes: List of note names (e.g., ['C', 'E', 'G'])
            actual_bass_note: The actual lowest note selected (for slash chords)

        Returns:
            Set of chord names in shorthand notation
        """
        chord_names = set()

        try:
            # Create a music21 Chord object
            c = self.music21_chord.Chord(notes)

            # First, try manual pattern matching for common extended chords
            manual_chords = self.identify_extended_chords(notes, c)
            chord_names.update(manual_chords)

            # Use actual bass note if provided, otherwise use music21's bass
            bass_note = actual_bass_note if actual_bass_note else c.bass().name
            root_note = c.root().name

            # Get the common name
            try:
                common_name = c.commonName
                if common_name and 'enharmonic' not in common_name.lower():
                    # Convert to shorthand notation
                    shorthand = self.convert_to_shorthand(c.root().name, common_name)
                    if shorthand:
                        # Add slash chord if bass != root
                        if bass_note != root_note:
                            chord_names.add(f"{shorthand}/{bass_note}")
                        chord_names.add(shorthand)
                elif 'enharmonic equivalent to' in common_name.lower():
                    # Extract the actual chord type
                    # e.g., "enharmonic equivalent to minor triad"
                    actual_type = common_name.replace('enharmonic equivalent to ', '')
                    shorthand = self.convert_to_shorthand(c.root().name, actual_type)
                    if shorthand:
                        if bass_note != root_note:
                            chord_names.add(f"{shorthand}/{bass_note}")
                        chord_names.add(shorthand)
            except:
                pass

            # Get pitched common name (includes root)
            try:
                pitched_name = c.pitchedCommonName
                if pitched_name and pitched_name != 'Chord' and 'enharmonic' not in pitched_name.lower():
                    # Extract root and type from pitched name
                    # e.g., "C-major triad" -> "C", "major triad"
                    shorthand = self.convert_pitched_name_to_shorthand(pitched_name)
                    if shorthand:
                        if bass_note != root_note:
                            chord_names.add(f"{shorthand}/{bass_note}")
                        chord_names.add(shorthand)
                elif 'enharmonic equivalent to' in pitched_name.lower():
                    # Handle enharmonic cases
                    # e.g., "enharmonic equivalent to minor triad above C"
                    parts = pitched_name.split(' above ')
                    if len(parts) == 2:
                        root = parts[1]
                        chord_type = parts[0].replace('enharmonic equivalent to ', '')
                        shorthand = self.convert_to_shorthand(root, chord_type)
                        if shorthand:
                            if bass_note != root_note:
                                chord_names.add(f"{shorthand}/{bass_note}")
                            chord_names.add(shorthand)
            except:
                pass

        except Exception as e:
            pass

        return chord_names

    def identify_extended_chords(self, notes, chord_obj):
        """
        Manually identify common extended chords that music21 might miss

        Args:
            notes: List of note names
            chord_obj: music21 Chord object

        Returns:
            Set of chord names in shorthand notation
        """
        chord_names = set()

        if len(notes) < 3:
            return chord_names

        try:
            root = chord_obj.root().name
            pitch_classes = chord_obj.pitchClasses  # Semitone offsets from root

            # Normalize to semitones from root
            root_pc = chord_obj.root().pitchClass
            intervals = sorted([(pc - root_pc) % 12 for pc in pitch_classes])

            # Common chord patterns (intervals from root)
            patterns = {
                # Triads
                (0, 4, 7): '',              # Major triad
                (0, 3, 7): 'm',             # Minor triad
                (0, 3, 6): 'dim',           # Diminished triad
                (0, 4, 8): 'aug',           # Augmented triad
                (0, 2, 7): 'sus2',          # Sus2
                (0, 5, 7): 'sus4',          # Sus4
                (0, 2, 4): 'sus2',          # Whole-tone cluster (C D E)

                # Extended chords
                (0, 2, 4, 7): 'add9',       # Major triad + major 9th
                (0, 2, 3, 7): 'madd9',      # Minor triad + major 9th
                (0, 4, 5, 7): 'add11',      # Major triad + perfect 11th
                (0, 3, 5, 7): 'madd11',     # Minor triad + perfect 11th
                (0, 4, 7, 9): '6',          # Major sixth
                (0, 3, 7, 9): 'm6',         # Minor sixth
                (0, 3, 7, 11): 'mM7',       # Minor-major seventh

                # Seventh chords
                (0, 4, 7, 10): '7',         # Dominant 7th
                (0, 4, 7, 11): 'maj7',      # Major 7th
                (0, 3, 7, 10): 'm7',        # Minor 7th
                (0, 3, 6, 9): 'dim7',       # Diminished 7th
                (0, 3, 6, 10): 'm7b5',      # Half-diminished 7th

                # Incomplete seventh chords (no 5th)
                (0, 4, 10): '7',            # Dominant 7th no 5th
                (0, 4, 11): 'maj7',         # Major 7th no 5th
                (0, 3, 10): 'm7',           # Minor 7th no 5th
                (0, 7, 10): '7',            # Dominant 7th no 3rd (shell voicing)
                (0, 7, 11): 'maj7',         # Major 7th no 3rd

                # Ninth chords
                (0, 4, 7, 10, 2): '9',      # Dominant 9th
                (0, 4, 7, 11, 2): 'maj9',   # Major 9th
                (0, 3, 7, 10, 2): 'm9',     # Minor 9th

                # Higher extensions
                (0, 4, 7, 10, 2, 5): '11',  # Dominant 11th
                (0, 4, 7, 10, 2, 5, 9): '13', # Dominant 13th
            }

            intervals_tuple = tuple(intervals)
            if intervals_tuple in patterns:
                chord_names.add(f"{root}{patterns[intervals_tuple]}")

        except Exception as e:
            pass

        return chord_names

    def convert_to_shorthand(self, root, chord_type):
        """Convert music21 chord type to shorthand notation"""
        if not root or not chord_type:
            return None

        # Mapping of music21 chord types to shorthand
        type_map = {
            # Triads
            'major triad': '',
            'minor triad': 'm',
            'diminished triad': 'dim',
            'augmented triad': 'aug',
            'suspended-second triad': 'sus2',
            'suspended-fourth triad': 'sus4',
            'quartal trichord': 'sus',  # Could be sus2 or sus4
            'whole-tone trichord': 'sus2',  # C D E - treat as sus2-ish cluster

            # Seventh chords
            'dominant seventh chord': '7',
            'incomplete dominant-seventh chord': '7',  # D F# C (no 5th)
            'major seventh chord': 'maj7',
            'incomplete major-seventh chord': 'maj7',  # No 5th
            'minor seventh chord': 'm7',
            'incomplete minor-seventh chord': 'm7',  # No 5th
            'diminished seventh chord': 'dim7',
            'half-diminished seventh chord': 'm7b5',
            'augmented seventh chord': 'aug7',
            'major-minor seventh chord': '7',
            'minor-major seventh chord': 'mM7',
            'minor-augmented tetrachord': 'mM7',  # D F A C# = DmM7
            'augmented major tetrachord': 'augmaj7',  # C E G# B

            # Sixth chords
            'major sixth': '6',
            'minor sixth': 'm6',

            # Ninth chords
            'dominant ninth': '9',
            'dominant-ninth': '9',
            'major ninth': 'maj9',
            'major-ninth chord': 'maj9',
            'minor ninth': 'm9',
            'minor-ninth chord': 'm9',

            # Eleventh and thirteenth
            'dominant-eleventh': '11',
            'dominant-thirteenth': '13',
            'augmented-eleventh': '13',

            # Add chords (these get weird names from music21)
            'major-second major tetrachord': 'add9',
            'perfect-fourth major tetrachord': 'add11',

            # Altered chords
            'flat-ninth pentachord': '7b9',
            'neapolitan pentachord': '7#9',

            # Enharmonic equivalents (map to standard chords)
            'enharmonic equivalent to diminished triad': 'dim',
            'enharmonic equivalent to major triad': '',
            'enharmonic equivalent to minor triad': 'm',
            'enharmonic equivalent to half-diminished seventh chord': 'm7b5',
            'enharmonic equivalent to major seventh chord': 'maj7',
            'enharmonic equivalent to minor seventh chord': 'm7',
            'enharmonic to dominant seventh chord': '7',
            'enharmonic equivalent to dominant-ninth': '9',
            'enharmonic equivalent to major-ninth chord': 'maj9',
            'enharmonic equivalent to minor-ninth chord': 'm9',

            # Incomplete chords
            'incomplete half-diminished seventh chord': 'm7b5',

            # Augmented sixth chords
            'german augmented sixth chord in third inversion': 'Ger+6',

            # Extended/altered chords
            'augmented seventh chord': 'aug7',
            'augmented-diminished ninth chord': 'aug7b9',
            'diminished-augmented ninth chord': 'dim7#9',
            'diminished-major ninth chord': 'dim(maj9)',
            'diminished minor-ninth chord': 'dimm9',
            'major-augmented ninth chord': 'maj7#5(9)',
            'minor-major ninth chord': 'mM9',
            'minor-diminished ninth chord': 'm7b5(b9)',

            # Add chords with minor
            'major-second minor tetrachord': 'madd9',
        }

        suffix = type_map.get(chord_type.lower(), '')
        return f"{root}{suffix}" if suffix is not None else None

    def convert_pitched_name_to_shorthand(self, pitched_name):
        """Convert pitched common name to shorthand"""
        # e.g., "C-major triad" -> "C"
        # e.g., "A-minor seventh chord" -> "Am7"
        # e.g., "B-diminished seventh chord" -> "Bdim7"

        if not pitched_name or pitched_name == 'Chord':
            return None

        try:
            parts = pitched_name.split('-', 1)
            if len(parts) != 2:
                return None

            root = parts[0]
            chord_type = parts[1]

            return self.convert_to_shorthand(root, chord_type)
        except:
            return None

    def show_results(self, chord_list):
        """Display results in the listbox"""
        self.results_listbox.config(state=tk.NORMAL)
        self.results_listbox.delete(0, tk.END)

        for chord in chord_list:
            self.results_listbox.insert(tk.END, chord)

        # Enable/disable based on content
        if chord_list and chord_list[0] not in ["Select notes to identify chords...", "No standard chord found."]:
            self.results_listbox.config(state=tk.NORMAL)
        else:
            self.results_listbox.config(state=tk.DISABLED)

    def on_chord_click(self, event=None):
        """Handle single-click on a chord in the list - play it"""
        # Let the click select the item first
        self.after(10, self.play_selected_chord)

    def on_chord_double_click(self, event=None):
        """Handle double-click on a chord in the list"""
        self.insert_selected_chord()

    def play_selected_chord(self):
        """Play the currently selected chord"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        chord_name = self.results_listbox.get(selection[0])

        # Don't play info messages
        if chord_name.startswith("Selected notes:") or chord_name.startswith("Notes:") or \
           chord_name in ["", "Select notes to identify chords...", "No standard chord found.",
                         "Try adding or removing notes.", "Install 'music21' library to identify chords:",
                         "Make sure you've selected valid notes."]:
            return

        # Play the chord
        if self.audio_player:
            try:
                # Use ChordHelper to convert chord name to MIDI notes
                midi_notes = self.chord_helper.chord_to_midi(chord_name, base_octave=3)
                if not midi_notes:
                    logger.warning(f"Cannot play chord {chord_name}: chord not recognized")
                    return

                # Play the chord
                self.audio_player.play_notes_immediate(midi_notes)

            except Exception as e:
                logger.error(f"Error playing chord {chord_name}: {e}", exc_info=True)

    def chord_name_to_midi_fallback(self, chord_name):
        """
        Fallback method to convert chord name to MIDI notes using music21
        when pychord doesn't recognize the chord
        """
        try:
            # Remove slash chord notation if present
            base_chord = chord_name.split('/')[0]

            # Try to construct the chord using music21
            if self.music21_available:
                # Parse the chord - extract root and quality
                root = self.extract_root_from_chord_name(base_chord)
                if not root:
                    return None

                # Build notes based on quality
                notes = self.build_chord_notes(base_chord, root)
                if not notes:
                    return None

                # Convert note names to MIDI
                octave = 3  # Default octave for chord playback
                midi_notes = []
                for i, note in enumerate(notes):
                    # Use music21 to parse note name
                    from music21 import note as m21_note
                    n = m21_note.Note(note)
                    n.octave = octave
                    midi_notes.append(n.pitch.midi)
                    # Move to next octave if we go past C
                    if i > 0 and n.pitch.pitchClass < midi_notes[i-1] % 12:
                        octave += 1
                        n.octave = octave
                        midi_notes[-1] = n.pitch.midi

                return midi_notes
        except Exception as e:
            logger.error(f"Fallback chord conversion failed: {e}", exc_info=True)
            return None

    def extract_root_from_chord_name(self, chord_name):
        """Extract root note from chord name"""
        # Match note name at the start (e.g., C, C#, Db, F#)
        import re
        match = re.match(r'^([A-G][#b]?)', chord_name)
        if match:
            return match.group(1)
        return None

    def build_chord_notes(self, chord_name, root):
        """Build chord notes based on chord name"""
        # Map of chord qualities to interval patterns (semitones from root)
        quality_intervals = {
            'augmaj7': [0, 4, 8, 11],      # Augmented major 7th
            'aug7': [0, 4, 8, 10],          # Augmented 7th
            'aug7b9': [0, 4, 8, 10, 13],    # Augmented 7th flat 9
            'maj7#5(9)': [0, 4, 8, 11, 14], # Major 7 #5 add 9
            'maj7': [0, 4, 7, 11],          # Major 7th
            '7': [0, 4, 7, 10],             # Dominant 7th
            '7b9': [0, 4, 7, 10, 13],       # Dominant 7th flat 9
            'm7': [0, 3, 7, 10],            # Minor 7th
            'm7b5': [0, 3, 6, 10],          # Half-diminished
            'm7b5(b9)': [0, 3, 6, 10, 13],  # Half-diminished flat 9
            'dim7': [0, 3, 6, 9],           # Diminished 7th
            'dim7#9': [0, 3, 6, 9, 15],     # Diminished 7th sharp 9
            'dim(maj9)': [0, 3, 6, 11, 14], # Diminished with maj7 and 9
            'dimm9': [0, 3, 6, 10, 14],     # Diminished minor 9th
            'mM7': [0, 3, 7, 11],           # Minor-major 7th
            'mM9': [0, 3, 7, 11, 14],       # Minor-major 9th
            'maj9': [0, 4, 7, 11, 14],      # Major 9th
            '9': [0, 4, 7, 10, 14],         # Dominant 9th
            'm9': [0, 3, 7, 10, 14],        # Minor 9th
            '6': [0, 4, 7, 9],              # Major 6th
            'm6': [0, 3, 7, 9],             # Minor 6th
            'add9': [0, 4, 7, 14],          # Add 9
            'madd9': [0, 3, 7, 14],         # Minor add 9
            'add11': [0, 4, 7, 17],         # Add 11
            'sus2': [0, 2, 7],              # Sus2
            'sus4': [0, 5, 7],              # Sus4
            'aug': [0, 4, 8],               # Augmented
            'dim': [0, 3, 6],               # Diminished
            'm': [0, 3, 7],                 # Minor
            '': [0, 4, 7],                  # Major (default)
        }

        # Extract quality from chord name (everything after root)
        quality = chord_name[len(root):]

        # Find matching quality
        intervals = quality_intervals.get(quality)
        if not intervals:
            # Try partial matches for complex chords
            for qual, ints in quality_intervals.items():
                if qual and quality.startswith(qual):
                    intervals = ints
                    break

        if not intervals:
            return None

        # Build notes from intervals
        from music21 import pitch
        root_pitch = pitch.Pitch(root)
        notes = [root]

        for interval in intervals[1:]:
            new_pitch = root_pitch.transpose(interval)
            notes.append(new_pitch.name)

        return notes

    def insert_selected_chord(self):
        """Insert the selected chord into the parent text editor"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        chord_name = self.results_listbox.get(selection[0])

        # Don't insert info messages
        if chord_name.startswith("Selected notes:") or chord_name.startswith("Notes:") or \
           chord_name in ["", "Select notes to identify chords...", "No standard chord found.",
                         "Try adding or removing notes.", "Install 'mingus' library to identify chords:",
                         "Make sure you've selected valid notes."]:
            return

        # Insert into parent text editor at current cursor position with trailing space
        try:
            self.parent_window.text_editor.insert(tk.INSERT, chord_name + " ")
            # Trigger chord detection after inserting
            self.parent_window.text_editor._detect_chords()
            self.parent_window.text_editor.focus_set()
            self.parent_window.update_statusbar(f"Inserted chord: {chord_name}")
        except Exception as e:
            logger.error(f"Error inserting chord: {e}", exc_info=True)

    def clear_all(self):
        """Clear all selections"""
        self.piano_roll.set_notes([])
        self.note_entry.delete(0, tk.END)
        self.show_results(["Select notes to identify chords..."])
