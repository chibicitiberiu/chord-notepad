"""
Line model for storing text lines with metadata
"""

class Line:
    """Represents a line of text with metadata"""

    def __init__(self, content, line_number):
        """
        Initialize a line

        Args:
            content: The text content of the line
            line_number: Line number (1-indexed)
        """
        self.content = content
        self.line_number = line_number
        self.type = None  # 'chord' or 'text'
        self.chords = []  # List of chord info dicts for chord lines

    def is_chord_line(self):
        """Check if this is a chord line"""
        return self.type == 'chord'

    def is_text_line(self):
        """Check if this is a text/lyric line"""
        return self.type == 'text'

    def set_as_chord_line(self, chords):
        """Mark this line as a chord line with detected chords"""
        self.type = 'chord'
        self.chords = chords

    def set_as_text_line(self):
        """Mark this line as a text/lyric line"""
        self.type = 'text'
        self.chords = []

    def __repr__(self):
        return f"Line({self.line_number}, type={self.type}, content='{self.content[:30]}...')"
