"""Tests for the Quick Start tour's example snippets and dialog."""

import os

import pytest

from constants import TAG_CHORD_VALID
from models.line import LineType
from services.song_parser_service import SongParserService
from ui.dialogs.quick_start import QuickStartDialog


def _snippets():
    for page in QuickStartDialog.PAGES:
        for block in page["blocks"]:
            if block[0] == "snippet":
                yield page["title"], block[1], block[2]


@pytest.mark.parametrize("title,text,notation", list(_snippets()))
def test_snippet_chords_are_detected_and_valid(title, text, notation):
    lines = SongParserService().detect_chords_in_text(text, notation)
    chord_lines = [line for line in lines if line.type == LineType.CHORD]
    assert chord_lines, f"{title}: no chord line detected"
    for line in chord_lines:
        assert all(chord.is_valid for chord in line.chords), f"{title}: invalid chord"


@pytest.mark.parametrize("title,text,notation", list(_snippets()))
def test_snippet_lyric_lines_stay_text(title, text, notation):
    # Lines that aren't directives or comments and contain lowercase words
    # are lyrics in these examples; they must not be classified as chords.
    lines = SongParserService().detect_chords_in_text(text, notation)
    raw = text.split("\n")
    for line in lines:
        source = raw[line.line_number - 1]
        if source.startswith(("{", "//")):
            continue
        if any(word.islower() and len(word) > 3 for word in source.split()):
            assert line.type == LineType.TEXT, f"{title}: lyric detected as chords: {source!r}"


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY")) or os.name == "nt"


@pytest.fixture
def root():
    tk = pytest.importorskip("tkinter")
    if not _has_display():
        pytest.skip("No display available for tkinter tests")
    try:
        instance = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    instance.withdraw()
    yield instance
    instance.destroy()


def test_every_page_renders_with_highlighted_read_only_snippets(root):
    dialog = QuickStartDialog(root)
    try:
        for index, page in enumerate(QuickStartDialog.PAGES):
            dialog._load_page(index)
            expected = sum(1 for block in page["blocks"] if block[0] == "snippet")
            assert len(dialog._snippets) == expected
            for snippet in dialog._snippets:
                assert snippet.cget("state") == "disabled"
                assert snippet.tag_ranges(TAG_CHORD_VALID), "snippet has no highlighted chords"
    finally:
        dialog.destroy()
