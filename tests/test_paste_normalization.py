"""Tests for song-text normalization on paste and file open.

Regression: pasting text with Windows CRLF line endings left literal ``\\r``
characters in the widget, rendering as junk glyphs at line ends (e.g. right
after a pasted ``[Chorus]``).
"""

import os
import time

import pytest

tk = pytest.importorskip("tkinter")

from ui.text_editor import ChordTextEditor
from utils.text_normalization import normalize_song_text
from viewmodels.text_editor_viewmodel import TextEditorViewModel
from services.song_parser_service import SongParserService


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

    def test_plain_text_unchanged(self):
        text = "C  G  Am\nEvery night\n"
        assert normalize_song_text(text) == text


# ---------------------------------------------------------------------------
# Widget paste path (needs a display)
# ---------------------------------------------------------------------------

def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY")) or os.name == "nt"


@pytest.fixture
def editor():
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    root = tk.Tk()
    vm = TextEditorViewModel(SongParserService())
    widget = ChordTextEditor(root, vm)
    widget.pack()
    # The window must be mapped: Tk does not deliver synthesized <<Paste>>
    # events to widgets of a withdrawn window in a fresh interpreter.
    root.deiconify()
    widget.wait_visibility()
    root.update()
    yield widget
    root.destroy()




def _set_clipboard(widget, text):
    """Set the clipboard and wait until it is actually retrievable.

    The first clipboard round-trip in a fresh X11 process can lag behind
    ``clipboard_append``; generating <<Paste>> before it settles reads an
    empty clipboard.
    """
    widget.clipboard_clear()
    widget.clipboard_append(text)
    for _ in range(50):
        widget.update()
        try:
            if widget.clipboard_get() == text:
                return
        except tk.TclError:
            pass
        time.sleep(0.01)
    pytest.skip("clipboard not available in this environment")

class TestPasteNormalizesClipboard:
    def test_crlf_paste_leaves_no_cr_in_widget(self, editor):
        _set_clipboard(editor, "[Chorus]\r\nC  G  Am\r\nlyrics\r\n")
        editor.update()
        editor.focus_force()
        editor.event_generate("<<Paste>>")
        editor.update()
        content = editor.get("1.0", "end-1c")
        assert "\r" not in content
        assert content.startswith("[Chorus]\nC  G  Am\n")

    def test_paste_replaces_selection(self, editor):
        editor.insert("1.0", "old text")
        editor.tag_add(tk.SEL, "1.0", "1.3")
        editor.mark_set(tk.INSERT, "1.3")
        _set_clipboard(editor, "new\r\n")
        editor.update()
        editor.focus_force()
        editor.event_generate("<<Paste>>")
        editor.update()
        assert editor.get("1.0", "end-1c") == "new\n text"


# ---------------------------------------------------------------------------
# File open path
# ---------------------------------------------------------------------------

class TestFileOpenNormalizes:
    def _open(self, tmp_path, raw: bytes) -> str:
        from unittest.mock import MagicMock
        from services.file_service import FileService
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
