"""
Custom text editor widget with support for chord detection
"""

import re
import tkinter as tk
from typing import Optional, List, Any, Tuple
from models.line import Line
from models.chord import ChordInfo
from viewmodels.text_editor_viewmodel import TextEditorViewModel
from constants import (
    TAG_CHORD_VALID, TAG_CHORD_INVALID, TAG_CHORD_PLAYING,
    TAG_DIRECTIVE_VALID, TAG_DIRECTIVE_INVALID, TAG_COMMENT,
    COLOR_CHORD_VALID, COLOR_CHORD_INVALID, COLOR_CHORD_PLAYING_BG,
    COLOR_DIRECTIVE_VALID, COLOR_DIRECTIVE_INVALID, COLOR_COMMENT,
    CHORD_DETECTION_DEBOUNCE_MS
)


class ChordTextEditor(tk.Text):
    """Text editor widget with chord detection support.

    This is a thin view layer that delegates all business logic to TextEditorViewModel.
    """

    def __init__(self, parent: Any, viewmodel: TextEditorViewModel, **kwargs: Any) -> None:
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
        self.tag_config(TAG_CHORD_VALID, foreground=COLOR_CHORD_VALID, underline=True)
        self.tag_config(TAG_CHORD_INVALID, foreground=COLOR_CHORD_INVALID, underline=True)
        self.tag_config(TAG_CHORD_PLAYING, background=COLOR_CHORD_PLAYING_BG, foreground='black', underline=True)

        # Configure tags for directive highlighting
        self.tag_config(TAG_DIRECTIVE_VALID, foreground=COLOR_DIRECTIVE_VALID, underline=False)
        self.tag_config(TAG_DIRECTIVE_INVALID, foreground=COLOR_DIRECTIVE_INVALID, underline=True, underlinefg=COLOR_DIRECTIVE_INVALID)

        # Configure tag for comments
        self.tag_config(TAG_COMMENT, foreground=COLOR_COMMENT)

        # Bind numpad Enter to work like regular Enter
        self.bind('<KP_Enter>', lambda e: self.insert(tk.INSERT, '\n'))

        # Typing timer for delayed chord detection
        self._typing_timer = None
        self._typing_delay = CHORD_DETECTION_DEBOUNCE_MS

        # Bind key events to trigger chord detection
        self.bind('<KeyRelease>', self._on_typing)

        # Bind mouse motion to change cursor over chords
        self.bind('<Motion>', self._on_mouse_motion)

        # Fix paste to replace selection
        self.bind('<<Paste>>', self._on_paste)

        # Set up observers for ViewModel property changes
        self._setup_viewmodel_observers()

    def _setup_viewmodel_observers(self) -> None:
        """Set up observers for ViewModel property changes."""
        # Observe detected lines changes
        self.viewmodel.observe('detected_lines', self._on_detected_lines_changed)

        # Observe notation changes
        self.viewmodel.observe('current_notation', self._on_notation_changed)

    def _on_detected_lines_changed(self, lines: List[Line]) -> None:
        """Handle detected lines change from ViewModel.

        Args:
            lines: List of Line objects from ViewModel
        """
        self.lines = lines
        self._update_highlighting()

    def _on_notation_changed(self, notation: str) -> None:
        """Handle notation change from ViewModel.

        Args:
            notation: New notation value
        """
        # Re-detect chords with new notation
        self._detect_chords()

    def cleanup_observers(self) -> None:
        """Clean up all observers to prevent memory leaks."""
        self.viewmodel.clear_observers()

    def set_notation(self, notation: str) -> None:
        """Set the notation type and refresh highlighting.

        Args:
            notation: "american" or "european"
        """
        self.viewmodel.set_notation(notation)
        self._detect_chords()

    def _reset_typing_timer(self) -> None:
        """Reset the typing timer"""
        if self._typing_timer:
            self.after_cancel(self._typing_timer)
            self._typing_timer = None

    def _on_typing(self, event: Optional[Any] = None) -> None:
        """Handle typing event - trigger chord detection after delay"""
        self._reset_typing_timer()
        self._typing_timer = self.after(self._typing_delay, self._detect_chords)

    def _detect_chords(self) -> None:
        """Detect and highlight chords in the text, classify lines"""
        # Get all text content
        text = self.get('1.0', 'end-1c')

        # Delegate chord detection to ViewModel
        self.viewmodel.on_text_changed(text)

        # The ViewModel will notify us via _on_detected_lines_changed
        # which will then call _update_highlighting

    def _find_comments(self, text: str) -> List[Tuple[int, int]]:
        """Find all comment regions in the text.

        Args:
            text: The full text content

        Returns:
            List of (start, end) tuples for each comment region
        """
        comments = []
        for match in re.finditer(r'//[^\n]*', text):
            comments.append((match.start(), match.end()))
        return comments

    def _update_highlighting(self) -> None:
        """Update text highlighting based on detected lines."""
        # Clear existing chord tags
        self.tag_remove(TAG_CHORD_VALID, '1.0', tk.END)
        self.tag_remove(TAG_CHORD_INVALID, '1.0', tk.END)

        # Clear existing directive tags
        self.tag_remove(TAG_DIRECTIVE_VALID, '1.0', tk.END)
        self.tag_remove(TAG_DIRECTIVE_INVALID, '1.0', tk.END)

        # Clear existing comment tags
        self.tag_remove(TAG_COMMENT, '1.0', tk.END)

        # Get text for comment detection
        text = self.get('1.0', 'end-1c')

        # Find and highlight comments first (so they appear as gray)
        comments = self._find_comments(text)
        for start, end in comments:
            start_idx = f"1.0 + {start} chars"
            end_idx = f"1.0 + {end} chars"
            self.tag_add(TAG_COMMENT, start_idx, end_idx)

        # Collect all chords for highlighting
        self.detected_chords = []

        for line in self.lines:
            if line.is_chord_line():
                # Chords already have absolute positions from detector
                for chord_info in line.chords:
                    self.detected_chords.append(chord_info)

        # Highlight detected chords
        for chord_info in self.detected_chords:
            start_idx = f"1.0 + {chord_info.start} chars"
            end_idx = f"1.0 + {chord_info.end} chars"

            if chord_info.is_valid:
                self.tag_add(TAG_CHORD_VALID, start_idx, end_idx)
            else:
                self.tag_add(TAG_CHORD_INVALID, start_idx, end_idx)

        # Highlight directives
        for line in self.lines:
            for directive in line.directives:
                start_idx = f"1.0 + {directive.start} chars"
                end_idx = f"1.0 + {directive.end} chars"

                if directive.is_valid:
                    self.tag_add(TAG_DIRECTIVE_VALID, start_idx, end_idx)
                else:
                    self.tag_add(TAG_DIRECTIVE_INVALID, start_idx, end_idx)

    def get_detected_chords(self) -> List[ChordInfo]:
        """Get list of detected chords"""
        return self.detected_chords

    def get_lines(self) -> List[Line]:
        """Get list of Line objects with classification"""
        return self.lines

    def get_chord_at_coordinates(self, x: int, y: int) -> Optional[ChordInfo]:
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
            if chord_info.start <= char_pos < chord_info.end:
                return chord_info

        return None

    def _on_mouse_motion(self, event: Any) -> None:
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
            if chord_info.start <= char_pos < chord_info.end and chord_info.is_valid:
                over_chord = True
                break

        # Change cursor
        if over_chord:
            self.config(cursor='hand2')
        else:
            self.config(cursor='xterm')

    def _on_paste(self, event: Any) -> Optional[str]:
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
