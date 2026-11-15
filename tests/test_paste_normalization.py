"""Tests for song-text normalization on paste and file open.

Regression: pasting text with Windows CRLF line endings left literal ``\\r``
characters in the widget, rendering as junk glyphs at line ends (e.g. right
after a pasted ``[Chorus]``). The Qt editor's paste is in
tests/qt/test_qt_editor.py.
"""

from chordnotepad.utils.text_normalization import normalize_song_text


# ---------------------------------------------------------------------------
# Pure helper
# ---------------------------------------------------------------------------

class TestNormalizeSongText:
    def test_crlf_becomes_lf(self):
        assert normalize_song_text("[Chorus]\r\nC  G\r\n") == "[Chorus]\nC  G\n"

    def test_lone_cr_becomes_lf(self):
        assert normalize_song_text("line one\rline two") == "line one\nline two"

    def test_mixed_endings(self):
        assert normalize_song_text("a\r\nb\nc\r") == "a\nb\nc\n"

    def test_non_breaking_space_becomes_space(self):
        assert normalize_song_text("C  G") == "C  G"

    def test_zero_width_characters_removed(self):
        assert normalize_song_text("﻿C​m") == "Cm"

    def test_word_joiner_removed(self):
        # Android draws U+2060 inside chords so D/F# never wraps; a copy of
        # the drawn text must not carry it into a song.
        assert normalize_song_text("D/\u2060F# C\u2060-\u20605\n") == "D/F# C-5\n"

    def test_plain_text_unchanged(self):
        text = "C  G  Am\nEvery night\n"
        assert normalize_song_text(text) == text


# ---------------------------------------------------------------------------
# File open path
# ---------------------------------------------------------------------------

class TestFileOpenNormalizes:
    def _open(self, tmp_path, raw: bytes) -> str:
        from unittest.mock import MagicMock
        from chordnotepad.services.file_service import FileService
        p = tmp_path / "song.txt"
        p.write_bytes(raw)
        return FileService(MagicMock()).open_file(p)

    def test_crlf_file_opens_with_lf_only(self, tmp_path):
        content = self._open(tmp_path, b"[Chorus]\r\nC  G\r\nlyrics\n")
        assert "\r" not in content
        assert content == "[Chorus]\nC  G\nlyrics\n"

    def test_nbsp_and_zero_width_cleaned(self, tmp_path):
        raw = "C\u00a0G\u200b\n".encode("utf-8")
        assert self._open(tmp_path, raw) == "C G\n"
