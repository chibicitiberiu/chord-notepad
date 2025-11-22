"""
Custom text editor widget with support for chord detection
"""

import tkinter as tk
from typing import Optional
from chord.line_model import Line
from chord.chord_model import ChordInfo
from viewmodels.text_editor_viewmodel import TextEditorViewModel


class ChordTextEditor(tk.Text):
    """Text editor widget with chord detection support.

    This is a thin view layer that delegates all business logic to TextEditorViewModel.
    """

    def __init__(self, parent, viewmodel: TextEditorViewModel, **kwargs):
        """Initialize the text editor with a ViewModel.

        Args:
            parent: Parent widget
            viewmodel: TextEditorViewModel for presentation logic
            **kwargs: Additional keyword arguments passed to tk.Text
        """
        # Enable undo by default
        kwargs.setdefault('undo', True)
        kwargs.setdefault('maxundo', -1)
        kwargs.setdefault('wrap', tk.WORD)
        kwargs.setdefault('insertbackground', 'black')

        super().__init__(parent, **kwargs)

        # Store ViewModel
        self.viewmodel = viewmodel

        # Chord detection state (maintained for highlighting)
        self.detected_chords = []
        self.lines = []  # List of Line objects with cached classification

        # Configure tags for chord highlighting
        self.tag_config('chord', foreground='blue', underline=True)
        self.tag_config('chord_invalid', foreground='gray', underline=True)
        self.tag_config('chord_comment', foreground='red', overstrike=True)
        self.tag_config('chord_playing', background='yellow', foreground='black', underline=True)

        # Bind numpad Enter to work like regular Enter
        self.bind('<KP_Enter>', lambda e: self.insert(tk.INSERT, '\n'))

        # Typing timer for delayed chord detection
        self._typing_timer = None
        self._typing_delay = 500  # 0.5 second delay

        # Bind key events to trigger chord detection
        self.bind('<KeyRelease>', self._on_typing)

        # Bind mouse motion to change cursor over chords
        self.bind('<Motion>', self._on_mouse_motion)

        # Fix paste to replace selection
        self.bind('<<Paste>>', self._on_paste)

        # Set up observers for ViewModel property changes
        self._setup_viewmodel_observers()

    def _setup_viewmodel_observers(self):
        """Set up observers for ViewModel property changes."""
        # Observe detected lines changes
        self.viewmodel.observe('detected_lines', self._on_detected_lines_changed)

        # Observe notation changes
        self.viewmodel.observe('current_notation', self._on_notation_changed)

    def _on_detected_lines_changed(self, lines):
        """Handle detected lines change from ViewModel.

        Args:
            lines: List of Line objects from ViewModel
        """
        self.lines = lines
        self._update_highlighting()

    def _on_notation_changed(self, notation: str):
        """Handle notation change from ViewModel.

        Args:
            notation: New notation value
        """
        # Re-detect chords with new notation
        self._detect_chords()

    def set_notation(self, notation: str):
        """Set the notation type and refresh highlighting.

        Args:
            notation: "american" or "european"
        """
        self.viewmodel.set_notation(notation)
        self._detect_chords()

    def _reset_typing_timer(self):
        """Reset the typing timer"""
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None

    def _on_typing(self, event=None):
        """Handle typing event - trigger chord detection after delay"""
        self._reset_typing_timer()
        self._typing_timer = self.after(self._typing_delay, self._detect_chords)

    def _detect_chords(self):
        """Detect and highlight chords in the text, classify lines"""
        # Get all text content
        text = self.get('1.0', 'end-1c')

        # Delegate chord detection to ViewModel
        self.viewmodel.on_text_changed(text)

        # The ViewModel will notify us via _on_detected_lines_changed
        # which will then call _update_highlighting

    def _update_highlighting(self):
        """Update text highlighting based on detected lines."""
        # Clear existing chord tags
        self.tag_remove('chord', '1.0', tk.END)
        self.tag_remove('chord_invalid', '1.0', tk.END)

        # Collect all chords for highlighting
        self.detected_chords = []
        char_offset = 0

        for line in self.lines:
            if line.is_chord_line():
                # Add chords with adjusted positions for highlighting
                for chord_info in line.chords:
                    # Create a new ChordInfo with adjusted position
                    chord_with_offset = ChordInfo(
                        chord=chord_info.chord,
                        line_offset=chord_info.line_offset,
                        is_valid=chord_info.is_valid,
                        notes=chord_info.notes
                    )
                    # Add positioning attributes for highlighting
                    chord_with_offset.start = char_offset + chord_info.line_offset
                    chord_with_offset.end = char_offset + chord_info.line_offset + len(chord_info.chord)
                    self.detected_chords.append(chord_with_offset)

            # Update offset (include newline)
            char_offset += len(line.content) + 1

        # Highlight detected chords
        for chord_info in self.detected_chords:
            start_idx = f"1.0 + {chord_info.start} chars"
            end_idx = f"1.0 + {chord_info.end} chars"

            if chord_info.is_valid:
                self.tag_add('chord', start_idx, end_idx)
            else:
                self.tag_add('chord_invalid', start_idx, end_idx)

    def get_detected_chords(self):
        """Get list of detected chords"""
        return self.detected_chords

    def get_lines(self):
        """Get list of Line objects with classification"""
        return self.lines

    def get_chord_at_coordinates(self, x, y) -> Optional[ChordInfo]:
        """Get the chord at the given pixel coordinates.

        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels

        Returns:
            ChordInfo object if a chord is at those coordinates, None otherwise
        """
        # Get the text index at coordinates
        index = self.index(f"@{x},{y}")
        line, col = map(int, index.split('.'))

        # Calculate character position
        char_pos = 0
        text = self.get('1.0', 'end-1c')
        lines = text.split('\n')
        for i in range(line - 1):
            char_pos += len(lines[i]) + 1  # +1 for newline
        char_pos += col

        # Find chord at this position
        for chord_info in self.detected_chords:
            if hasattr(chord_info, 'start') and hasattr(chord_info, 'end'):
                if chord_info.start <= char_pos < chord_info.end:
                    return chord_info

        return None

    def _on_mouse_motion(self, event):
        """Handle mouse motion - change cursor when over chords"""
        # Get the index at mouse position
        index = self.index(f"@{event.x},{event.y}")
        line, col = map(int, index.split('.'))

        # Calculate character position
        char_pos = 0
        text = self.get('1.0', 'end-1c')
        lines = text.split('\n')
        for i in range(line - 1):
            char_pos += len(lines[i]) + 1
        char_pos += col

        # Check if we're over a chord
        over_chord = False
        for chord_info in self.detected_chords:
            if hasattr(chord_info, 'start') and hasattr(chord_info, 'end'):
                if chord_info.start <= char_pos < chord_info.end and chord_info.is_valid:
                    over_chord = True
                    break

        # Change cursor
        if over_chord:
            self.config(cursor='hand2')
        else:
            self.config(cursor='xterm')

    def _on_paste(self, event):
        """Handle paste - replace selection if any"""
        try:
            # Check if there's a selection
            if self.tag_ranges(tk.SEL):
                # Delete the selection first
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)

            # Get clipboard content
            clipboard_text = self.clipboard_get()

            # Insert at current cursor position
            self.insert(tk.INSERT, clipboard_text)

            # Trigger chord detection after paste
            self._reset_typing_timer()
            self._typing_timer = self.after(self._typing_delay, self._detect_chords)

            # Prevent default paste behavior
            return 'break'
        except tk.TclError:
            # No clipboard content or other error - allow default behavior
            pass
