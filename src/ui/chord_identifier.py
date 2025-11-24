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

    def __init__(self, parent, octaves=2, on_change=None, on_play_note=None):
        """
        Initialize piano roll

        Args:
            parent: Parent widget
            octaves: Number of octaves to display (default 2)
            on_change: Callback function when selection changes
            on_play_note: Callback function(note_name, octave) for playing notes
        """
        self.octaves = octaves
        self.on_change = on_change
        self.on_play_note = on_play_note

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
        if not self.on_play_note:
            return

        try:
            # Delegate to callback
            self.on_play_note(note_name, octave)
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

    def __init__(self, parent, viewmodel, on_insert_chord=None):
        """Initialize chord identifier window.

        Args:
            parent: Parent window
            viewmodel: ChordIdentifierViewModel instance
            on_insert_chord: Callback function(chord_name: str) for inserting chords
        """
        super().__init__(parent)

        self.title("Identify Chord")
        self.geometry("600x550")
        self.transient(parent)

        # Store ViewModel
        self.viewmodel = viewmodel
        self.on_insert_chord = on_insert_chord

        # Wire up ViewModel observers
        self.viewmodel.observe("identified_chords", self._on_chords_identified)

        # Set up window close handler to clean up observers
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

        self.piano_roll = PianoRoll(
            piano_frame,
            octaves=2,
            on_change=self.on_piano_change,
            on_play_note=self._on_play_note
        )
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

        # Update ViewModel with actual selected notes (with their octaves from piano roll)
        note_tuples = list(self.piano_roll.selected_notes)
        self.viewmodel.set_notes(note_tuples)

    def on_text_change(self, event=None):
        """Handle text entry change"""
        text = self.note_entry.get()
        # Use ViewModel to parse notes
        self.viewmodel.set_notes_from_string(text)

        # Update piano roll display
        notes_only = self.viewmodel.get_selected_note_names()
        self.piano_roll.set_notes(notes_only)

    def _on_play_note(self, note_name: str, octave: int):
        """Handle note playback request from piano roll.

        Args:
            note_name: Note name to play
            octave: Octave number
        """
        # Delegate to ViewModel
        self.viewmodel.play_note(note_name, octave, duration=1.0)

    def _on_chords_identified(self, chord_list):
        """Observer callback when chords are identified in ViewModel.

        Args:
            chord_list: List of identified chord names
        """
        logger.debug(f"Observer callback received chord_list: {chord_list}")
        self.show_results(chord_list)

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
                         "Try adding or removing notes.", "Make sure you've selected valid notes."]:
            return

        # Delegate to ViewModel
        self.viewmodel.play_chord(chord_name, duration=2.0)

    def insert_selected_chord(self):
        """Insert the selected chord into the parent text editor"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        chord_name = self.results_listbox.get(selection[0])

        # Don't insert info messages
        if chord_name.startswith("Selected notes:") or chord_name.startswith("Notes:") or \
           chord_name in ["", "Select notes to identify chords...", "No standard chord found.",
                         "Try adding or removing notes.", "Make sure you've selected valid notes."]:
            return

        # Use callback to insert chord
        if self.on_insert_chord:
            try:
                self.on_insert_chord(chord_name)
            except Exception as e:
                logger.error(f"Error inserting chord: {e}", exc_info=True)

    def clear_all(self):
        """Clear all selections"""
        # Clear ViewModel state
        self.viewmodel.clear_selection()

        # Clear UI elements
        self.piano_roll.set_notes([])
        self.note_entry.delete(0, tk.END)

    def _on_close(self):
        """Handle window close and clean up observers"""
        # Clean up observers to prevent memory leaks
        self.viewmodel.clear_observers()
        # Destroy the window
        self.destroy()
