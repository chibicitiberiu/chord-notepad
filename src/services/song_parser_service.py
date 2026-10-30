"""Song parser service for parsing chords, directives, and labels."""

import logging
import math
import re
from typing import List, Union, Optional

from chord.detector import ChordDetector
from chord.helper import ChordHelper
from chord.converter import NotationConverter
from chord.keys import is_valid_key
from constants import MAX_BEATS, MAX_BPM, MIN_BEATS, MIN_BPM, TIME_SIGNATURE_UNITS
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

    # Comment pattern - matches // and everything after it
    COMMENT_PATTERN = re.compile(r'//.*$', re.MULTILINE)

    def __init__(self):
        self._helper = ChordHelper()
        self._converter = NotationConverter()
        self._logger = logging.getLogger(__name__)

    # Anything in braces is a directive: {keyword: value}, or {keyword} with
    # the value missing. Unknown keywords and bad values are invalid ones.
    # Empty braces ({}) aren't a directive at all.
    DIRECTIVE_PATTERN = re.compile(r'\{([^}]*[^}\s][^}]*)\}')

    _KEYWORD_TYPES = {
        'bpm': DirectiveType.BPM, 'tempo': DirectiveType.BPM,
        'time': DirectiveType.TIME_SIGNATURE, 'key': DirectiveType.KEY,
        'capo': DirectiveType.CAPO, 'label': DirectiveType.LABEL, 'loop': DirectiveType.LOOP,
    }

    def parse_directives(self, text: str) -> List[Directive]:
        """Parse directives from text.

        Directives follow the format ``{keyword: value}``: ``bpm`` (or
        ``tempo``), ``time``, ``key``, ``capo``, ``label`` and ``loop``. Each
        one comes back valid, or invalid with ``message`` saying why (a value
        out of range, the wrong format, a missing value, an unknown keyword,
        a loop to a label that isn't above it...). Every directive carries its
        ``keyword``, so a view can show the correct syntax
        (:attr:`Directive.syntax`).

        Directives in comments (// to end of line) and on plain-text lines
        (first non-space character '.') are skipped.

        Args:
            text: Text to parse

        Returns:
            List of Directive objects found in the text
        """
        directives = []

        # Find all comment regions to skip directives inside them; a line
        # starting with '.' is plain text, so it counts as one whole region.
        comment_regions = [(m.start(), m.end()) for m in self.COMMENT_PATTERN.finditer(text)]
        comment_regions += [(m.start(), m.end())
                            for m in ChordDetector.TEXT_LINE_PATTERN.finditer(text)]

        def is_in_comment(pos: int) -> bool:
            """Check if a position is inside a comment."""
            for start, end in comment_regions:
                if start <= pos < end:
                    return True
            return False

        for match in self.DIRECTIVE_PATTERN.finditer(text):
            if is_in_comment(match.start()):
                continue
            directives.append(self._parse_one(match.group(1), match.start(), match.end()))

        self._check_labels_and_loops(directives, text)
        return directives

    def _parse_one(self, body: str, start: int, end: int) -> Directive:
        """One directive from the text between its braces."""
        keyword, colon, value = body.partition(':')
        keyword = keyword.strip().lower()
        value = value.strip()
        kind = self._KEYWORD_TYPES.get(keyword, DirectiveType.UNKNOWN)
        try:
            if kind == DirectiveType.UNKNOWN:
                if not keyword:
                    raise ValueError("Empty directive")
                raise ValueError(f"Unknown directive '{keyword}'")
            if not colon or not value:
                raise ValueError(self._MISSING_VALUE[kind])
            directive = self._parse_value(kind, value, start, end)
        except (ValueError, IndexError) as e:
            self._logger.debug(f"Invalid directive at position {start}: {e}")
            # An invalid tempo keeps its type; other invalid directives are
            # UNKNOWN (``keyword`` still says what they were meant to be).
            invalid_type = kind if kind == DirectiveType.BPM else DirectiveType.UNKNOWN
            return Directive(type=invalid_type, start=start, end=end, is_valid=False,
                             keyword=keyword, message=str(e))
        directive.keyword = keyword
        return directive

    _MISSING_VALUE = {
        DirectiveType.BPM: "Tempo needs a value",
        DirectiveType.TIME_SIGNATURE: "Time signature needs a value such as 4/4",
        DirectiveType.KEY: "Key needs a note name",
        DirectiveType.CAPO: "Capo needs a fret from 0 to 12",
        DirectiveType.LABEL: "Label needs a name",
        DirectiveType.LOOP: "Loop needs a label to repeat",
    }

    def _parse_value(self, kind: DirectiveType, value: str, start: int, end: int) -> Directive:
        """A valid directive of ``kind``; ValueError (the reason) if the value is bad."""
        if kind == DirectiveType.BPM:
            return self._parse_bpm_directive(value, start, end)
        if kind == DirectiveType.TIME_SIGNATURE:
            beats_text, slash, unit_text = value.partition('/')
            try:
                beats, unit = int(beats_text), int(unit_text)
            except ValueError:
                raise ValueError("Time signature must be beats/unit, such as 4/4")
            if not slash:
                raise ValueError("Time signature must be beats/unit, such as 4/4")
            if not MIN_BEATS <= beats <= MAX_BEATS:
                raise ValueError(f"Beats must be {MIN_BEATS}-{MAX_BEATS}")
            if unit not in TIME_SIGNATURE_UNITS:
                units = ', '.join(str(u) for u in TIME_SIGNATURE_UNITS[:-1])
                raise ValueError(f"Beat unit must be {units} or {TIME_SIGNATURE_UNITS[-1]}")
            return Directive(type=kind, start=start, end=end, beats=beats, unit=unit)
        if kind == DirectiveType.KEY:
            if not is_valid_key(value):
                raise ValueError("Key must be a note name such as G, Am, F#m or Sol")
            return Directive(type=kind, start=start, end=end, key=value)
        if kind == DirectiveType.CAPO:
            # {capo: N}: a fret 0..12 (0 means no capo).
            try:
                fret = int(value)
            except ValueError:
                fret = -1
            if not 0 <= fret <= 12:
                raise ValueError("Capo must be a fret from 0 to 12")
            return Directive(type=kind, start=start, end=end, capo=fret)
        if kind == DirectiveType.LOOP:
            # "label [count]": the count is the last word when it is a whole
            # number; the label is everything before it, so a label may
            # contain spaces ({loop: my verse 2}).
            label, count = self._split_loop_value(value)
            if not label:
                raise ValueError("Loop needs a label to repeat")
            return Directive(type=kind, start=start, end=end, label=label, loop_count=count)
        # DirectiveType.LABEL
        return Directive(type=kind, start=start, end=end, label=value)

    def _check_labels_and_loops(self, directives: List[Directive], text: str) -> None:
        """Mark repeated labels and loops that can't be played invalid.

        A label name may be used once; a repeat is invalid (loops go to the
        first). A loop must name a label above it (or ``@start``): a loop
        repeats a section that has just played. A loop to a missing label, or
        one that would jump forward, is invalid; this also rules out loops
        that send each other back and forth forever.
        """
        def line_of(pos: int) -> int:
            return text.count('\n', 0, pos) + 1

        labels = {}
        for directive in directives:
            if directive.type == DirectiveType.LABEL and directive.is_valid:
                if directive.label in labels:
                    directive.is_valid = False
                    directive.message = (f"Label '{directive.label}' is already used on "
                                         f"line {line_of(labels[directive.label])}")
                else:
                    labels[directive.label] = directive.start
        for directive in directives:
            if directive.type != DirectiveType.LOOP or not directive.is_valid:
                continue
            if directive.label == '@start':
                continue
            label_start = labels.get(directive.label)
            if label_start is None:
                directive.is_valid = False
                directive.message = f"No label '{directive.label}' in the song"
            elif label_start > directive.start:
                directive.is_valid = False
                directive.message = (f"Label '{directive.label}' comes after the loop; "
                                     f"a loop repeats a section above it")

    def _parse_bpm_directive(self, value: str, start: int, end: int) -> Directive:
        """Parse a BPM directive value into a Directive object.

        Supports multiple formats:
        - Absolute: "120" -> set BPM to 120 (MIN_BPM-MAX_BPM)
        - Relative: "+20" or "-20" -> add/subtract from current BPM
        - Percentage: "50%" -> set to 50% of current BPM (above 0)
        - Multiplier: "2x" or "0.5x" -> multiply current BPM (above 0)
        - Reset: "reset" or "original" -> restore the song's starting tempo

        Relative results are clamped to MIN_BPM-MAX_BPM when played.

        Args:
            value: The BPM value string to parse
            start: Start position in text
            end: End position in text

        Returns:
            A valid BPM Directive.

        Raises:
            ValueError: With the reason, for a value that isn't one of these.
        """
        value = value.strip()

        if value.lower() in ('reset', 'original'):
            return Directive(type=DirectiveType.BPM, start=start, end=end,
                             bpm_modifier_type=BPMModifierType.RESET)

        if value.endswith('%'):
            percentage = self._positive_float(value[:-1], "A percentage")
            return Directive(type=DirectiveType.BPM, start=start, end=end,
                             bpm_modifier_type=BPMModifierType.PERCENTAGE,
                             bpm_modifier_value=percentage)

        if value.endswith('x'):
            multiplier = self._positive_float(value[:-1], "A multiplier")
            return Directive(type=DirectiveType.BPM, start=start, end=end,
                             bpm_modifier_type=BPMModifierType.MULTIPLIER,
                             bpm_modifier_value=multiplier)

        if value.startswith(('+', '-')):
            try:
                relative_value = int(value)
            except ValueError:
                raise ValueError("A tempo change must be a whole number, such as +10")
            return Directive(type=DirectiveType.BPM, start=start, end=end,
                             bpm_modifier_type=BPMModifierType.RELATIVE,
                             bpm_modifier_value=float(relative_value))

        try:
            bpm_value = int(value)
        except ValueError:
            raise ValueError(f"Tempo must be a whole number from {MIN_BPM} to {MAX_BPM}, "
                             f"a change (+10, 50%, 2x) or reset")
        if not MIN_BPM <= bpm_value <= MAX_BPM:
            raise ValueError(f"Tempo must be {MIN_BPM}-{MAX_BPM}")
        return Directive(type=DirectiveType.BPM, start=start, end=end, bpm=bpm_value,
                         bpm_modifier_type=BPMModifierType.ABSOLUTE)

    _LOOP_COUNT = re.compile(r'^(.*?)\s+([+-]?\d+)$')

    @classmethod
    def _split_loop_value(cls, value: str) -> tuple:
        """Split a ``{loop}`` value into ``(label, count)``.

        The count is the last whitespace-separated token when it is an integer
        (default 2); the label is the rest. Raises ValueError for a count
        below 1.
        """
        match = cls._LOOP_COUNT.match(value.strip())
        if not match:
            return value.strip(), 2
        count = int(match.group(2))
        if count < 1:
            raise ValueError("Loop count must be at least 1")
        return match.group(1).strip(), count

    @staticmethod
    def _positive_float(text: str, what: str = "A number") -> float:
        """``text`` as a finite number above zero; ValueError otherwise."""
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{what} must be a number, such as 50% or 0.5x")
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f"{what} must be above 0")
        return number

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
        base = re.sub(r'[o°+Δ∆]|[Mm]?[79]|sus[24]|add[0-9]|maj|min|dim|aug|m', '', base)

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
            chord_text = self._converter.chord_european_to_american(chord_text)

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
            chord_text = self._converter.chord_european_to_american(chord_text)

        notes = self._helper.get_notes(chord_text)
        return notes if notes else []

    def convert_to_american(self, text: str, lines: Optional[List[Line]] = None) -> str:
        """Convert text from European to American notation.

        Uses the document's pre-detected chord positions to substitute only
        valid chords on chord lines — lyrics like "A week ago" are not touched.
        If `lines` is not supplied, the text is parsed with the European
        detector before substituting.
        """
        if lines is None:
            lines = self.detect_chords_in_text(text, notation="european")
        return self._apply_chord_conversion(
            text, lines, self._converter.chord_european_to_american
        )

    def convert_to_european(self, text: str, lines: Optional[List[Line]] = None) -> str:
        """Convert text from American to European notation.

        Uses the document's pre-detected chord positions to substitute only
        valid chords on chord lines — lyrics are not touched. If `lines` is
        not supplied, the text is parsed with the American detector first.
        """
        if lines is None:
            lines = self.detect_chords_in_text(text, notation="american")
        return self._apply_chord_conversion(
            text, lines, self._converter.chord_american_to_european
        )

    @staticmethod
    def rewrite_chord_spans(text: str, spans, transform) -> str:
        """Splice a per-chord ``transform`` into ``text`` for the given spans.

        This is the shared token-walk/replacement core used by notation
        conversion (and reused by the transpose service). Each span is a
        ``(start, end, chord_part)`` tuple where ``[start, end)`` is the full
        match in ``text`` and ``chord_part`` is the chord string proper.
        ``transform(chord_part)`` returns the replacement chord text.

        Spans are rewritten from the end of the text so earlier offsets stay
        valid. Any trailing characters in ``[start, end)`` beyond
        ``chord_part`` (e.g. a "*2" duration suffix) are preserved verbatim.

        Note: this performs a flat substitution with no chord-line/lyric
        alignment adjustment. The transpose service layers alignment on top of
        the same detection + transform primitives.

        Args:
            text: Full document text.
            spans: Iterable of (start, end, chord_part) tuples.
            transform: Callable mapping a chord string to its replacement.

        Returns:
            The rewritten text.
        """
        result = text
        for start, end, chord_part in sorted(spans, key=lambda s: s[0], reverse=True):
            original = result[start:end]
            trailing = original[len(chord_part):]
            result = result[:start] + transform(chord_part) + trailing + result[end:]
        return result

    @staticmethod
    def _apply_chord_conversion(text: str, lines: List[Line], convert_chord) -> str:
        """Substitute each detected chord with its converted form.

        Builds the chord spans from the pre-detected chord lines (valid,
        non-relative chords only) and delegates the splice to
        :py:meth:`rewrite_chord_spans`.
        """
        spans = [
            (chord.start, chord.end, chord.chord)
            for line in lines if line.is_chord_line()
            for chord in line.get_valid_chords()
            if not chord.is_relative
        ]
        return SongParserService.rewrite_chord_spans(text, spans, convert_chord)

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
                if directive.type == DirectiveType.LABEL and directive.is_valid:
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
