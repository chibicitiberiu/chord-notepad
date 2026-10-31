"""
Chord identification window with piano roll and note input
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import re

from exceptions import AudioInitializationError, ChordNotepadError
from ui.base.tooltip import ToolTip
from viewmodels.chord_identifier_viewmodel import (
    SOUNDING_SECONDS, bass_note, note_to_midi, outside_piano, spell,
)

logger = logging.getLogger(__name__)

# Selected keys are blue; the keys of the candidate played last are amber,
# or carry an amber dot when they are selected too.
SELECTED_FILL = '#4a90e2'
SOUNDING_FILL = '#f5a623'
SOUNDING_OUTLINE = '#9a6200'


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
        # MIDI notes of the candidate played last (highlighted for a while)
        self.sounding = set()
        # The notation the keys are labelled in (the song's)
        self.notation = "american"

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
                    is_sounding = note_to_midi(note_name, current_octave) in self.sounding
                    fill_color = (SELECTED_FILL if is_selected
                                  else SOUNDING_FILL if is_sounding else 'white')
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
                        text=spell(note_name, self.notation), font=('Arial', 8),
                        fill='white' if is_selected else 'black'
                    )
                    if is_selected and is_sounding:
                        self._sounding_dot(white_x + self.white_key_width // 2,
                                           self.white_key_height - 28)

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
                is_sounding = note_to_midi(note_name, current_octave) in self.sounding
                fill_color = (SELECTED_FILL if is_selected
                              else SOUNDING_FILL if is_sounding else 'black')

                rect_id = self.create_rectangle(
                    black_x, 0,
                    black_x + self.black_key_width, self.black_key_height,
                    fill=fill_color, outline='black', width=2
                )

                # Add label
                self.create_text(
                    black_x + self.black_key_width // 2,
                    self.black_key_height - 10,
                    text=spell(note_name, self.notation), font=('Arial', 7),
                    fill='black' if is_sounding and not is_selected else 'white'
                )
                if is_selected and is_sounding:
                    self._sounding_dot(black_x + self.black_key_width // 2,
                                       self.black_key_height - 26)

                self.key_rects.append((
                    note_name, current_octave, black_x, 0,
                    black_x + self.black_key_width, self.black_key_height,
                    rect_id
                ))

            x = white_x

    def _sounding_dot(self, x, y):
        """The amber dot on a selected key that also sounds."""
        r = 5
        self.create_oval(x - r, y - r, x + r, y + r,
                         fill=SOUNDING_FILL, outline=SOUNDING_OUTLINE, width=1)

    def set_notation(self, notation):
        """Label the keys in ``notation`` (``american`` or ``european``)."""
        self.notation = notation
        self.draw_piano()

    def set_sounding(self, midi_notes):
        """Highlight the keys of these MIDI notes (empty to stop)."""
        self.sounding = set(midi_notes)
        self.draw_piano()

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

        # Delegate to callback (it reports its own errors)
        self.on_play_note(note_name, octave)

    def note_to_midi(self, note_name, octave):
        """
        Convert note name to MIDI note number

        Args:
            note_name: Note name like 'C', 'C#', etc.
            octave: Octave number

        Returns:
            MIDI note number
        """
        return note_to_midi(note_name, octave)

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
        return bass_note(self.selected_notes)


class ChordIdentifierWindow(tk.Toplevel):
    """Window for identifying chords from notes"""

    def __init__(self, parent, viewmodel, on_insert_chord=None, on_audio_error=None):
        """Initialize chord identifier window.

        Args:
            parent: Parent window
            viewmodel: ChordIdentifierViewModel instance
            on_insert_chord: Callback function(chord_name: str) for inserting chords
            on_audio_error: Callback function(error) for audio that couldn't
                start; the main window reports it by the session's
                once-per-session policy for clicks
        """
        super().__init__(parent)

        self.title("Identify Chord")
        self.geometry("600x550")
        self.transient(parent)

        # Store ViewModel
        self.viewmodel = viewmodel
        self.on_insert_chord = on_insert_chord
        self.on_audio_error = on_audio_error

        # Wire up ViewModel observers
        self.viewmodel.observe("identified_chords", self._on_chords_identified)
        self.viewmodel.observe("sounding", self._on_sounding)
        self.viewmodel.observe("selected_notes", self._on_selection)
        self.viewmodel.observe("notation", self._on_notation)
        self._sounding_timer = None

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
        self.instructions = tk.Label(
            self,
            text=self._instructions(self.viewmodel.notation),
            font=('Arial', 10),
            wraplength=550
        )
        self.instructions.pack(pady=10)

        # Piano roll
        piano_frame = ttk.Frame(self)
        piano_frame.pack(pady=10)

        self.piano_roll = PianoRoll(
            piano_frame,
            octaves=2,
            on_change=self.on_piano_change,
            on_play_note=self._on_play_note
        )
        self.piano_roll.notation = self.viewmodel.notation
        self.piano_roll.draw_piano()
        self.piano_roll.pack()

        # Markers for sounding notes the piano doesn't show ("◂ C3", "D6 ▸")
        markers = ttk.Frame(piano_frame)
        markers.pack(fill=tk.X)
        self.below_marker = ttk.Label(markers, text="", font=('Arial', 9))
        self.below_marker.pack(side=tk.LEFT)
        self.above_marker = ttk.Label(markers, text="", font=('Arial', 9))
        self.above_marker.pack(side=tk.RIGHT)

        # Note input
        input_frame = ttk.Frame(self)
        input_frame.pack(pady=10, padx=20, fill=tk.X)

        ttk.Label(input_frame, text="Notes:").pack(side=tk.LEFT, padx=5)

        self.note_entry = ttk.Entry(input_frame, font=('Arial', 11))
        self.note_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.note_entry.bind("<KeyRelease>", self.on_text_change)

        clear_button = ttk.Button(input_frame, text="Clear", command=self.clear_all)
        clear_button.pack(side=tk.LEFT, padx=5)

        # Play: the selected keys; Shift+click or right-click plays them rolled
        self.play_button = ttk.Button(input_frame, text="Play", state=tk.DISABLED,
                                      command=self.play_selection)
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.play_button.bind("<Shift-Button-1>", self._play_selection_rolled)
        self.play_button.bind("<Button-3>", self._play_selection_rolled)
        ToolTip(self.play_button, "Plays the selected keys. Shift+click or right-click "
                                  "plays them rolled, one at a time from the lowest.")

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

        # Bind single-click to play chord, Shift+click to play it rolled
        self.results_listbox.bind("<Button-1>", self.on_chord_click)
        self.results_listbox.bind("<Shift-Button-1>", self.on_chord_shift_click)
        ToolTip(self.results_listbox, "Click a chord to hear it, Shift+click to hear it "
                                      "rolled, double-click to insert it.")
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

    @staticmethod
    def _instructions(notation):
        example = "Do Mi Sol or Do, Mi, Sol" if notation == "european" else "C E G or C, E, G"
        return f"Select notes on the piano or type them below (e.g., {example})"

    def _notes_text(self, notation):
        """The selected keys as the entry shows them, spelled in ``notation``."""
        return ' '.join(spell(n, notation) for n in self.piano_roll.get_notes())

    def _on_notation(self, notation):
        """The song's notation changed: relabel everything (the list comes
        respelled through identified_chords)."""
        old = self.piano_roll.notation
        # The entry follows when it shows the keys (not other typed text)
        if self.note_entry.get().strip() == self._notes_text(old):
            self.note_entry.delete(0, tk.END)
            self.note_entry.insert(0, self._notes_text(notation))
        self.instructions.config(text=self._instructions(notation))
        self.piano_roll.set_notation(notation)
        self._show_sounding(self.piano_roll.sounding)

    def on_piano_change(self):
        """Handle piano roll selection change"""
        self.note_entry.delete(0, tk.END)
        self.note_entry.insert(0, self._notes_text(self.viewmodel.notation))

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
        # Delegate to ViewModel. Clicking a key mainly selects it, so a broken
        # audio setup is reported once rather than on every click.
        try:
            self.viewmodel.play_note(note_name, octave, duration=1.0)
        except AudioInitializationError as e:
            self._report_audio_error(e)

    def _on_sounding(self, midi_notes):
        """Highlight a played candidate's keys for a few seconds."""
        if self._sounding_timer is not None:
            self.after_cancel(self._sounding_timer)
            self._sounding_timer = None
        self._show_sounding(midi_notes)
        if midi_notes:
            self._sounding_timer = self.after(int(SOUNDING_SECONDS * 1000), self._end_sounding)

    def _end_sounding(self):
        self._sounding_timer = None
        self._show_sounding(())

    def _show_sounding(self, midi_notes):
        self.piano_roll.set_sounding(midi_notes)
        below, above = outside_piano(midi_notes, notation=self.viewmodel.notation)
        self.below_marker.config(text=below or "")
        self.above_marker.config(text=above or "")

    def _report_audio_error(self, error):
        """Hand an audio failure to the owner (it applies the reporting policy)."""
        if self.on_audio_error is not None:
            self.on_audio_error(error)
        else:
            logger.warning(f"Audio unavailable: {error}")

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

    def on_chord_shift_click(self, event):
        """Shift+click on a chord: pick it and play it rolled."""
        if str(self.results_listbox.cget("state")) == tk.DISABLED:
            return "break"
        index = self.results_listbox.nearest(event.y)
        if index >= 0:
            self.results_listbox.selection_clear(0, tk.END)
            self.results_listbox.selection_set(index)
            self.results_listbox.activate(index)
            self.play_selected_chord(rolled=True)
        return "break"

    def _on_selection(self, selected_notes):
        """Play is only for a selection."""
        self.play_button.config(state=tk.NORMAL if selected_notes else tk.DISABLED)

    def play_selection(self, rolled=False):
        """Play the selected keys as they are (the Play button)."""
        try:
            self.viewmodel.play_selected_notes(duration=2.0, rolled=rolled)
        except AudioInitializationError as e:
            self._report_audio_error(e)

    def _play_selection_rolled(self, event=None):
        if str(self.play_button.cget("state")) != tk.DISABLED:
            self.play_selection(rolled=True)
        return "break"

    def on_chord_double_click(self, event=None):
        """Handle double-click on a chord in the list"""
        self.insert_selected_chord()

    def play_selected_chord(self, rolled=False):
        """Play the currently selected chord (one note at a time when ``rolled``)"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        chord_name = self.results_listbox.get(selection[0])

        # Don't play info messages
        if chord_name.startswith(("Selected notes:", "Notes:", "Error:")) or \
           chord_name in ["", "Select notes to identify chords...", "No standard chord found.",
                         "Try adding or removing notes.", "Make sure you've selected valid notes."]:
            return

        # Delegate to ViewModel
        try:
            self.viewmodel.play_chord(chord_name, duration=2.0, rolled=rolled)
        except AudioInitializationError as e:
            self._report_audio_error(e)
        except ChordNotepadError as e:
            messagebox.showerror("Identify Chord", str(e), parent=self)

    def insert_selected_chord(self):
        """Insert the selected chord into the parent text editor"""
        selection = self.results_listbox.curselection()
        if not selection:
            return

        chord_name = self.results_listbox.get(selection[0])

        # Don't insert info messages
        if chord_name.startswith(("Selected notes:", "Notes:", "Error:")) or \
           chord_name in ["", "Select notes to identify chords...", "No standard chord found.",
                         "Try adding or removing notes.", "Make sure you've selected valid notes."]:
            return

        # Use callback to insert chord (it reports its own errors)
        if self.on_insert_chord:
            self.on_insert_chord(chord_name)

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
        if self._sounding_timer is not None:
            self.after_cancel(self._sounding_timer)
        # Destroy the window
        self.destroy()
