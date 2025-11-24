"""Song parser service for parsing chords, directives, and labels."""

import logging
import re
from typing import List, Union, Optional

from chord.detector import ChordDetector
from chord.helper import ChordHelper
from chord.converter import NotationConverter
from models.line import Line
from models.chord import ChordInfo
from models.directive import Directive, DirectiveType, BPMModifierType
from models.song import Song
from models.label import Label
from models.notation import Notation


class SongParserService:
    """Manages song parsing operations.

    Provides a high-level interface for chord detection, directive parsing,
    duration parsing, and song structure building.
    """

    def __init__(self):
        self._helper = ChordHelper()
        self._converter = NotationConverter()
        self._logger = logging.getLogger(__name__)

    def parse_directives(self, text: str) -> List[Directive]:
        """Parse directives from text.

        Directives follow the format: {keyword: value}
        Supported directives:
        - {bpm: 120}
        - {time: 4/4}
        - {key: C}
        - {loop: label count}

        Args:
            text: Text to parse

        Returns:
            List of Directive objects found in the text
        """
        directives = []

        # Pattern to match {keyword: value}
        pattern = r'\{([^:}]+):\s*([^}]+)\}'

        for match in re.finditer(pattern, text):
            start = match.start()
            end = match.end()
            keyword = match.group(1).strip().lower()
            value = match.group(2).strip()

            directive_created = False

            try:
                if keyword in ('bpm', 'tempo'):
                    directive = self._parse_bpm_directive(value, start, end)
                    directives.append(directive)
                    directive_created = True

                elif keyword == 'time':
                    # Parse time signature like "4/4"
                    parts = value.split('/')
                    if len(parts) == 2:
                        beats = int(parts[0])
                        unit = int(parts[1])
                        directive = Directive(
                            type=DirectiveType.TIME_SIGNATURE,
                            start=start,
                            end=end,
                            beats=beats,
                            unit=unit
                        )
                        directives.append(directive)
                        directive_created = True
                    else:
                        # Invalid time signature format
                        raise ValueError(f"Invalid time signature format: {value}")

                elif keyword == 'key':
                    directive = Directive(
                        type=DirectiveType.KEY,
                        start=start,
                        end=end,
                        key=value
                    )
                    directives.append(directive)
                    directive_created = True

                elif keyword == 'loop':
                    # Parse loop directive: "label count"
                    parts = value.split()
                    if len(parts) >= 1:
                        label = parts[0]
                        count = int(parts[1]) if len(parts) >= 2 else 2
                        directive = Directive(
                            type=DirectiveType.LOOP,
                            start=start,
                            end=end,
                            label=label,
                            loop_count=count
                        )
                        directives.append(directive)
                        directive_created = True
                    else:
                        raise ValueError(f"Invalid loop format: {value}")

                elif keyword == 'label':
                    # Parse label directive: {label: name}
                    directive = Directive(
                        type=DirectiveType.LABEL,
                        start=start,
                        end=end,
                        label=value
                    )
                    directives.append(directive)
                    directive_created = True

                else:
                    # Unknown directive keyword
                    raise ValueError(f"Unknown directive keyword: {keyword}")

            except (ValueError, IndexError) as e:
                self._logger.warning(f"Failed to parse directive at position {start}: {e}")
                # Create an invalid directive
                if not directive_created:
                    directive = Directive(
                        type=DirectiveType.UNKNOWN,
                        start=start,
                        end=end,
                        is_valid=False
                    )
                    directives.append(directive)

        return directives

    def _parse_bpm_directive(self, value: str, start: int, end: int) -> Directive:
        """Parse a BPM directive value into a Directive object.

        Supports multiple formats:
        - Absolute: "120" -> set BPM to 120
        - Relative: "+20" or "-20" -> add/subtract from current BPM
        - Percentage: "50%" -> set to 50% of current BPM
        - Multiplier: "2x" or "0.5x" -> multiply current BPM
        - Reset: "reset" or "original" -> restore initial BPM

        Args:
            value: The BPM value string to parse
            start: Start position in text
            end: End position in text

        Returns:
            Directive object (valid or invalid)
        """
        value = value.strip()

        # Check for reset keywords
        if value.lower() in ('reset', 'original'):
            return Directive(
                type=DirectiveType.BPM,
                start=start,
                end=end,
                bpm_modifier_type=BPMModifierType.RESET
            )

        # Check for percentage (e.g., "50%")
        if value.endswith('%'):
            try:
                percentage = float(value[:-1])
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    bpm_modifier_type=BPMModifierType.PERCENTAGE,
                    bpm_modifier_value=percentage
                )
            except ValueError:
                self._logger.warning(f"Invalid percentage BPM value: {value}")
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    is_valid=False
                )

        # Check for multiplier (e.g., "2x", "0.5x")
        if value.endswith('x'):
            try:
                multiplier = float(value[:-1])
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    bpm_modifier_type=BPMModifierType.MULTIPLIER,
                    bpm_modifier_value=multiplier
                )
            except ValueError:
                self._logger.warning(f"Invalid multiplier BPM value: {value}")
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    is_valid=False
                )

        # Check for relative adjustment (e.g., "+20", "-10")
        if value.startswith(('+', '-')):
            try:
                relative_value = int(value)
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    bpm_modifier_type=BPMModifierType.RELATIVE,
                    bpm_modifier_value=float(relative_value)
                )
            except ValueError:
                self._logger.warning(f"Invalid relative BPM value: {value}")
                return Directive(
                    type=DirectiveType.BPM,
                    start=start,
                    end=end,
                    is_valid=False
                )

        # Default: absolute BPM value
        try:
            bpm_value = int(value)
            return Directive(
                type=DirectiveType.BPM,
                start=start,
                end=end,
                bpm=bpm_value,
                bpm_modifier_type=BPMModifierType.ABSOLUTE
            )
        except ValueError:
            self._logger.warning(f"Invalid BPM value: {value}")
            return Directive(
                type=DirectiveType.BPM,
                start=start,
                end=end,
                is_valid=False
            )

    def is_roman_numeral_chord(self, chord_str: str) -> bool:
        """Check if a chord string is a roman numeral chord.

        Args:
            chord_str: Chord string to check (e.g., "I", "vi", "♭III", "#ivo", "bVII")

        Returns:
            True if it's a roman numeral chord, False otherwise
        """
        # Remove quality markers and extensions to get the base
        base = chord_str.split('/')[0]  # Handle slash chords
        # Remove accidentals from the beginning
        base = re.sub(r'^[#b♭♯]', '', base)
        # Remove quality markers (including 'o' for diminished)
        base = re.sub(r'[o°+Δ∆]|[Mm]?[79]|sus[24]|add[0-9]|maj|min|dim|aug', '', base)

        # Check if base matches roman numeral pattern
        roman_pattern = r'^[IViv]+$'
        return bool(re.match(roman_pattern, base.strip()))

    def parse_chord_with_duration(self, chord_str: str) -> tuple[str, Optional[float]]:
        """Parse a chord string that may include duration.

        Duration format: chord*beats (e.g., "C*2", "Am*4")

        Args:
            chord_str: Chord string, potentially with duration

        Returns:
            Tuple of (chord_string, duration_or_None)
        """
        parts = chord_str.split('*')
        if len(parts) == 2:
            try:
                duration = float(parts[1])
                return (parts[0].strip(), duration)
            except ValueError:
                pass
        return (chord_str, None)

    def detect_chords_in_text(self, text: str, notation: Union[Notation, str] = "american") -> List[Line]:
        """Detect chords in a block of text.

        Args:
            text: Text content to analyze
            notation: Notation system (Notation enum or "american"/"european" string)

        Returns:
            List of Line objects with detected chords
        """
        # Convert Notation enum to string if needed
        notation_str = notation.value if isinstance(notation, Notation) else notation
        self._logger.debug(f"Detecting chords in text using {notation_str} notation")

        # Create detector with the specified notation
        detector = ChordDetector(notation=notation_str)

        # Get chord detections
        chord_infos = detector.detect_chords_in_text(text)
        self._logger.debug(f"Detected {len(chord_infos)} chords")

        # Convert to Line objects
        lines = self._convert_chord_infos_to_lines(text, chord_infos)
        self._logger.debug(f"Created {len(lines)} Line objects")

        return lines

    def detect_chords_in_line(self, line_text: str, line_number: int, notation: Union[Notation, str] = "american") -> Line:
        """Detect chords in a single line.

        Args:
            line_text: Line content to analyze
            line_number: Line number (1-indexed)
            notation: Notation system (Notation enum or string)

        Returns:
            Line object with detected chords
        """
        # Convert Notation enum to string if needed
        notation_str = notation.value if isinstance(notation, Notation) else notation

        # Create detector with the specified notation
        detector = ChordDetector(notation=notation_str)

        # Get chord detections for this line
        chord_infos = detector.detect_chords_in_text(line_text)

        # Filter to chords on line 1 (since we're only analyzing one line)
        line_chords = [c for c in chord_infos if c.line == 1]

        if line_chords:
            # Create chord line
            line = Line(content=line_text, line_number=line_number)
            line.set_as_chord_line(line_chords)
            return line
        else:
            # Return empty text line
            return Line(content=line_text, line_number=line_number)

    def _convert_chord_infos_to_lines(self, text: str, chord_infos: List[ChordInfo]) -> List[Line]:
        """Convert ChordInfo objects to Line objects with directive parsing.

        Args:
            text: Original text
            chord_infos: List of detected chords

        Returns:
            List of Line objects
        """
        lines = []
        text_lines = text.split('\n')

        # Group chords by line number
        chords_by_line = {}
        for chord_info in chord_infos:
            line_num = chord_info.line
            if line_num not in chords_by_line:
                chords_by_line[line_num] = []
            chords_by_line[line_num].append(chord_info)

        # Parse all directives from text
        all_directives = self.parse_directives(text)

        # Group directives by line number
        directives_by_line = {}
        char_offset = 0
        for line_num, content in enumerate(text_lines, start=1):
            # Find directives that fall within this line's character range
            line_start = char_offset
            line_end = char_offset + len(content)

            for directive in all_directives:
                if line_start <= directive.start < line_end:
                    if line_num not in directives_by_line:
                        directives_by_line[line_num] = []
                    directives_by_line[line_num].append(directive)

            char_offset += len(content) + 1  # +1 for newline

        # Create Line objects for each text line
        for line_num, content in enumerate(text_lines, start=1):
            line = Line(content=content, line_number=line_num)

            # Collect chords and directives for this line
            chords = chords_by_line.get(line_num, [])
            directives = directives_by_line.get(line_num, [])

            if chords:
                # This is a chord line - combine chords and directives
                items = chords + directives
                # Sort by position
                items.sort(key=lambda item: item.start)
                line.set_as_chord_line(chords)
                line.items = items  # Override to include directives
            elif directives:
                # Line has only directives - still a text line, but with directive items
                line.set_as_text_line()
                line.items = directives
            else:
                # Pure text line
                line.set_as_text_line()

            lines.append(line)

        return lines

    def validate_chord(self, chord_text: str, notation: str = "american") -> bool:
        """Validate if a string is a valid chord.

        Args:
            chord_text: Chord string to validate
            notation: Notation system to use

        Returns:
            True if valid chord, False otherwise
        """
        # Convert to american notation for validation if needed
        if notation == "european":
            chord_text = self._converter.european_to_american(chord_text)

        return self._helper.is_valid_chord(chord_text)

    def get_chord_notes(self, chord_text: str, notation: str = "american") -> List[str]:
        """Get the note names that make up a chord.

        Args:
            chord_text: Chord string (e.g., "C", "Dm7", "G7")
            notation: Notation system

        Returns:
            List of note names (e.g., ['C', 'E', 'G'])
        """
        # Convert to american notation for processing
        if notation == "european":
            chord_text = self._converter.european_to_american(chord_text)

        notes = self._helper.get_notes(chord_text)
        return notes if notes else []

    def convert_to_american(self, text: str) -> str:
        """Convert text from European to American notation.

        Args:
            text: Text in European notation

        Returns:
            Text in American notation
        """
        return self._converter.european_to_american(text)

    def convert_to_european(self, text: str) -> str:
        """Convert text from American to European notation.

        Args:
            text: Text in American notation

        Returns:
            Text in European notation
        """
        return self._converter.american_to_european(text)

    def identify_chord_from_notes(self, notes: List[str], bass_note: str = None) -> List[str]:
        """Identify possible chord names from a set of notes.

        Args:
            notes: List of note names (e.g., ['C', 'E', 'G'])
            bass_note: Optional bass note for slash chords

        Returns:
            List of possible chord names (e.g., ['C', 'Cmaj', 'C/G'])
        """
        chords = self._helper.identify_chord(notes, bass_note)
        return chords if chords else []

    def chord_to_midi(self, chord_name: str, base_octave: int = 4) -> List[int]:
        """Convert a chord name to MIDI note numbers.

        Args:
            chord_name: Chord name (e.g., "C", "Am7", "D/F#")
            base_octave: Base octave for the chord root

        Returns:
            List of MIDI note numbers
        """
        midi_notes = self._helper.chord_to_midi(chord_name, base_octave)
        return midi_notes if midi_notes else []

    def build_song(self, text: str, notation: Union[Notation, str] = "american") -> Song:
        """Build a complete Song object from text.

        Parses the text to detect chords, directives, and labels, then constructs
        a Song object with all lines and label references.

        Args:
            text: Song text content
            notation: Notation system (Notation enum or "american"/"european" string)

        Returns:
            Song object with parsed lines and labels
        """
        # Parse lines with chords and directives
        lines = self.detect_chords_in_text(text, notation)

        # Extract labels from LABEL directives
        labels = {}
        char_offset = 0
        text_lines = text.split('\n')

        for line_num, line_content in enumerate(text_lines, start=1):
            # Find label directives in this line
            line_start = char_offset
            line_end = char_offset + len(line_content)

            # Parse directives for this line
            line_directives = self.parse_directives(line_content)

            for directive in line_directives:
                if directive.type == DirectiveType.LABEL:
                    # Calculate offset within the line
                    offset = directive.start

                    # Create Label object
                    label = Label(
                        name=directive.label,
                        line_number=line_num,
                        offset=offset
                    )
                    labels[directive.label] = label
                    self._logger.debug(f"Found label '{directive.label}' at line {line_num}")

            char_offset += len(line_content) + 1  # +1 for newline

        # Build Song object
        song = Song(lines=lines, labels=labels)
        self._logger.info(f"Built song with {song.line_count()} lines and {len(labels)} labels")

        return song
