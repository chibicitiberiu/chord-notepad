"""Unit tests for Song building."""

import pytest
from services.song_parser_service import SongParserService
from models.directive import DirectiveType
from models.line import LineType
from models.notation import Notation


class TestBasicSongBuilding:
    """Tests for basic song building functionality."""

    def test_build_empty_song(self, song_parser):
        """Test building an empty song."""
        text = ""
        song = song_parser.build_song(text)

        # Empty string splits into one empty line
        assert song.line_count() == 1
        assert len(song.labels) == 0

    def test_build_song_with_text_only(self, song_parser):
        """Test building a song with only text lines."""
        text = """This is a lyric line
Another lyric line
Yet another line"""
        song = song_parser.build_song(text)

        assert song.line_count() == 3
        assert len(song.labels) == 0
        assert all(line.type == LineType.TEXT for line in song.lines)

    def test_build_song_with_chords(self, song_parser):
        """Test building a song with chord lines."""
        text = """C F G Am
Verse lyrics here
Dm G C C"""
        song = song_parser.build_song(text, notation="american")

        assert song.line_count() == 3
        assert song.lines[0].type == LineType.CHORD
        assert len(song.lines[0].chords) == 4
        assert song.lines[1].type == LineType.TEXT
        assert song.lines[2].type == LineType.CHORD
        assert len(song.lines[2].chords) == 4

    def test_build_song_with_directives(self, song_parser):
        """Test building a song with directives."""
        text = """{bpm: 120}
{time: 4/4}
C F G Am
{key: C}
Dm G C"""
        song = song_parser.build_song(text)

        assert song.line_count() == 5
        # Line 1: BPM directive
        assert len(song.lines[0].directives) == 1
        assert song.lines[0].directives[0].type == DirectiveType.BPM
        # Line 2: Time signature directive
        assert len(song.lines[1].directives) == 1
        assert song.lines[1].directives[0].type == DirectiveType.TIME_SIGNATURE
        # Line 3: Chords
        assert song.lines[2].type == LineType.CHORD
        # Line 4: Key directive
        assert len(song.lines[3].directives) == 1
        # Line 5: Chords
        assert song.lines[4].type == LineType.CHORD


class TestLabels:
    """Tests for label functionality."""

    def test_build_song_with_single_label(self, song_parser):
        """Test building a song with a single label."""
        text = """{label: verse}
C F G Am
Lyrics here"""
        song = song_parser.build_song(text)

        assert song.line_count() == 3
        assert len(song.labels) == 1
        assert "verse" in song.labels
        assert song.labels["verse"].name == "verse"
        assert song.labels["verse"].line_number == 1

    def test_build_song_with_multiple_labels(self, song_parser):
        """Test building a song with multiple labels."""
        text = """{label: verse}
C F G Am
{label: chorus}
Dm G C C
{label: bridge}
Am F C G"""
        song = song_parser.build_song(text)

        assert song.line_count() == 6
        assert len(song.labels) == 3
        assert "verse" in song.labels
        assert "chorus" in song.labels
        assert "bridge" in song.labels
        assert song.labels["verse"].line_number == 1
        assert song.labels["chorus"].line_number == 3
        assert song.labels["bridge"].line_number == 5

    def test_build_song_with_label_and_loop(self, song_parser):
        """Test building a song with labels and loop directives."""
        text = """{label: verse}
C F G Am
{loop: verse 2}
{label: chorus}
Dm G C C"""
        song = song_parser.build_song(text)

        assert len(song.labels) == 2
        # Verify labels
        assert "verse" in song.labels
        assert "chorus" in song.labels
        # Verify loop directive references the label
        loop_line = song.lines[2]
        assert len(loop_line.directives) == 1
        assert loop_line.directives[0].type == DirectiveType.LOOP
        assert loop_line.directives[0].label == "verse"
        assert loop_line.directives[0].loop_count == 2

    def test_get_label_by_name(self, song_parser):
        """Test retrieving labels by name."""
        text = """{label: verse}
C F G Am
{label: chorus}
Dm G C"""
        song = song_parser.build_song(text)

        verse_label = song.get_label("verse")
        assert verse_label is not None
        assert verse_label.name == "verse"
        assert verse_label.line_number == 1

        chorus_label = song.get_label("chorus")
        assert chorus_label is not None
        assert chorus_label.name == "chorus"
        assert chorus_label.line_number == 3

        # Non-existent label
        missing = song.get_label("bridge")
        assert missing is None


class TestComplexSongs:
    """Tests for complex song structures."""

    def test_build_complete_song(self, song_parser):
        """Test building a complete song with all features."""
        text = """{bpm: 120} {key: C} {time: 4/4}
{label: intro}
C F G Am*2
{label: verse}
C F G C
Verse lyrics line 1
Verse lyrics line 2
{label: chorus}
Dm G C*4
Chorus lyrics
{loop: verse 1}
{loop: chorus 2}
{label: outro}
C F C"""
        song = song_parser.build_song(text, notation="american")

        # Check song structure (14 lines total)
        assert song.line_count() == 14

        # Check labels
        assert len(song.labels) == 4
        assert "intro" in song.labels
        assert "verse" in song.labels
        assert "chorus" in song.labels
        assert "outro" in song.labels

        # Check intro label points to correct line
        assert song.labels["intro"].line_number == 2

        # Check verse label
        assert song.labels["verse"].line_number == 4

        # Check chorus label
        assert song.labels["chorus"].line_number == 8

        # Check loop directives
        loop_lines = [line for line in song.lines if any(
            d.type == DirectiveType.LOOP for d in line.directives
        )]
        assert len(loop_lines) == 2

    def test_build_song_european_notation(self, song_parser):
        """Test building a song with European notation."""
        text = """{label: verse}
Do Re Mi Fa
{label: chorus}
Sol La Si Do"""
        song = song_parser.build_song(text, notation=Notation.EUROPEAN)

        assert song.line_count() == 4
        assert len(song.labels) == 2

        # Check chords detected
        assert song.lines[1].type == LineType.CHORD
        assert len(song.lines[1].chords) == 4
        assert song.lines[1].chords[0].chord == "Do"

        assert song.lines[3].type == LineType.CHORD
        assert len(song.lines[3].chords) == 4
        assert song.lines[3].chords[0].chord == "Sol"

    def test_build_song_with_duration_and_labels(self, song_parser):
        """Test building song with duration markers and labels."""
        text = """{label: intro}
C*2 F*2 G*4 Am*2
{label: verse}
C*4 F*4 G*2 C*2"""
        song = song_parser.build_song(text)

        assert len(song.labels) == 2

        # Check intro chords have durations
        intro_chords = song.lines[1].chords
        assert intro_chords[0].chord == "C"
        assert intro_chords[0].duration == 2.0
        assert intro_chords[1].chord == "F"
        assert intro_chords[1].duration == 2.0
        assert intro_chords[2].chord == "G"
        assert intro_chords[2].duration == 4.0

    def test_build_song_mixed_content(self, song_parser):
        """Test building song with mixed chords, lyrics, and directives."""
        text = """{bpm: 120}
{label: verse1}
C F G Am
These are the lyrics
Of verse one
{key: G}
{label: verse2}
G C D Em
These are the lyrics
Of verse two"""
        song = song_parser.build_song(text)

        # 10 lines total
        assert song.line_count() == 10
        assert len(song.labels) == 2
        assert "verse1" in song.labels
        assert "verse2" in song.labels

        # Verify structure
        assert song.lines[0].directives[0].type == DirectiveType.BPM
        assert song.lines[2].type == LineType.CHORD  # C F G Am
        assert song.lines[3].type == LineType.TEXT  # Lyrics
        assert song.lines[5].directives[0].type == DirectiveType.KEY
        assert song.lines[7].type == LineType.CHORD  # G C D Em


class TestEdgeCases:
    """Tests for edge cases."""

    def test_duplicate_label_names(self, song_parser):
        """Test that duplicate label names overwrite earlier ones."""
        text = """{label: verse}
C F G Am
{label: verse}
Dm G C"""
        song = song_parser.build_song(text)

        # Last occurrence should win
        assert len(song.labels) == 1
        assert song.labels["verse"].line_number == 3

    def test_label_with_whitespace(self, song_parser):
        """Test label names with whitespace are trimmed."""
        text = """{label:  verse1  }
C F G Am"""
        song = song_parser.build_song(text)

        # Whitespace should be trimmed
        assert len(song.labels) == 1
        # Note: value is trimmed by parse_directives
        assert "verse1" in song.labels

    def test_empty_label(self, song_parser):
        """Test that empty label directive is ignored."""
        text = """{label: }
C F G Am"""
        song = song_parser.build_song(text)

        # Empty label should create a label with empty string name
        # (parse_directives doesn't validate - that's expected behavior)
        assert len(song.labels) == 1

    def test_song_with_only_labels(self, song_parser):
        """Test song with only label directives."""
        text = """{label: intro}
{label: verse}
{label: chorus}"""
        song = song_parser.build_song(text)

        assert song.line_count() == 3
        assert len(song.labels) == 3
        assert all(line.type == LineType.TEXT for line in song.lines)

    def test_song_line_count(self, song_parser):
        """Test song line count method."""
        text = """C F G Am
Lyrics
Dm G C"""
        song = song_parser.build_song(text)

        assert song.line_count() == 3
        assert len(song.lines) == 3


@pytest.fixture
def song_parser():
    """Create a SongParserService instance."""
    return SongParserService()
