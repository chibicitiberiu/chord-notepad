"""Quick Start's pages on every platform: the snippets are real songs, the
pictures ship.

Tk's Quick Start dialog showed ``quick_start.pages(DESKTOP)`` and these
checks ran over it; here they run over the core's pages for each platform,
so they stayed when the Tk front end went.
"""

from pathlib import Path

import pytest

from chordnotepad.models.line import LineType
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session import quick_start
from chordnotepad.session.platform import PLATFORMS

REPO = Path(__file__).resolve().parent.parent


def _blocks(kind):
    for platform in PLATFORMS:
        for page in quick_start.pages(platform):
            for block in page["blocks"]:
                if block[0] == kind:
                    yield platform, page["title"], block


SNIPPETS = [(p, title, block[1], block[2]) for p, title, block in _blocks("snippet")]


@pytest.mark.parametrize("platform,title,text,notation", SNIPPETS)
def test_snippet_chords_are_detected_and_valid(platform, title, text, notation):
    lines = SongParserService().detect_chords_in_text(text, notation)
    chord_lines = [line for line in lines if line.type == LineType.CHORD]
    assert chord_lines, f"{platform} {title}: no chord line detected"
    for line in chord_lines:
        assert all(chord.is_valid for chord in line.chords), f"{platform} {title}: invalid chord"


@pytest.mark.parametrize("platform,title,text,notation", SNIPPETS)
def test_snippet_lyric_lines_stay_text(platform, title, text, notation):
    # Lines that aren't directives or comments and have lowercase words are
    # lyrics in these examples: they must not be read as chords.
    lines = SongParserService().detect_chords_in_text(text, notation)
    raw = text.split("\n")
    for line in lines:
        source = raw[line.line_number - 1]
        if source.startswith(("{", "//")):
            continue
        if any(word.islower() and len(word) > 3 for word in source.split()):
            assert line.type == LineType.TEXT, f"{platform} {title}: lyric read as chords: {source!r}"


def test_every_platform_has_snippets():
    assert {p for p, *_ in SNIPPETS} == set(PLATFORMS)


@pytest.mark.parametrize("platform,title,block", list(_blocks("image")))
def test_every_picture_ships_in_resources(platform, title, block):
    assert (REPO / block[1]).is_file(), f"{platform} {title}: missing {block[1]}"
