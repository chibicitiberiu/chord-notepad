"""
Custom text editor widget with support for chord detection
"""

import tkinter as tk
from chord.detector import ChordDetector
from chord.converter import NotationConverter
from chord.line_model import Line
from chord.chord_model import ChordInfo


class ChordTextEditor(tk.Text):
    """Text editor widget with chord detection support"""

    def __init__(self, parent, **kwargs):
        # Enable undo by default
        kwargs.setdefault('undo', True)
        kwargs.setdefault('maxundo', -1)
        kwargs.setdefault('wrap', tk.WORD)
        kwargs.setdefault('insertbackground', 'black')

        super().__init__(parent, **kwargs)

        # Chord detection
        self.notation = 'american'  # Will be set by main window
        self.chord_detector = ChordDetector(threshold=0.6, notation=self.notation)
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

    def set_notation(self, notation):
        """Set the notation type and refresh highlighting"""
        self.notation = notation
        self.chord_detector.notation = notation
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

        # Clear existing chord tags
        self.tag_remove('chord', '1.0', tk.END)
        self.tag_remove('chord_invalid', '1.0', tk.END)

        # Parse text into Line objects
        self.lines = []
        text_lines = text.split('\n')

        for line_num, content in enumerate(text_lines, start=1):
            line = Line(content, line_num)

            # Classify the line
            if self.chord_detector._is_chord_line(content):
                # This is a chord line - detect chords in it
                chords = self._detect_chords_in_line(content, line_num)
                line.set_as_chord_line(chords)
            else:
                # This is a text/lyric line
                line.set_as_text_line()

            self.lines.append(line)

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

    def _detect_chords_in_line(self, line_content, line_num):
        """Detect chords within a single line"""
        # Use the detector's pattern
        american_pattern = ChordDetector.CHORD_PATTERN_AMERICAN
        european_pattern = ChordDetector.CHORD_PATTERN_EUROPEAN

        pattern = european_pattern if self.notation == 'european' else american_pattern

        chords = []
        for match in pattern.finditer(line_content):
            chord_str = match.group(1)
            is_valid, notes = self.chord_detector._validate_chord(chord_str)

            chord_info = ChordInfo(
                chord=chord_str,
                line_offset=match.start(),  # Position within the line
                is_valid=is_valid,
                notes=notes
            )
            # Add line number as extra attribute
            chord_info.line = line_num

            chords.append(chord_info)

        return chords

    def get_detected_chords(self):
        """Get list of detected chords"""
        return self.detected_chords

    def get_lines(self):
        """Get list of Line objects with classification"""
        return self.lines

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
