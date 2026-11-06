"""services.text_codec: how song files are decoded, and saved back in their
own encoding and line endings (shared by the desktop and Android stores)."""

import codecs

import pytest

from services.text_codec import TextFormat, decode_text, encode_text, format_of

LF = TextFormat()


@pytest.mark.parametrize("data, text, fmt", [
    (b"C G\nla la\n", "C G\nla la\n", TextFormat("utf-8", "\n")),
    ("Dó Ré\n".encode("utf-8"), "Dó Ré\n", TextFormat("utf-8", "\n")),
    (codecs.BOM_UTF8 + b"C\r\nla\r\n", "C\r\nla\r\n", TextFormat("utf-8-sig", "\r\n")),
    ("Am\r\nGrüße\r\n".encode("utf-16"), "Am\r\nGrüße\r\n", TextFormat("utf-16", "\r\n")),
    (codecs.BOM_UTF16_BE + "Am\nGrüße\n".encode("utf-16-be"),
     "Am\nGrüße\n", TextFormat("utf-16", "\n")),
    # Latin-1 / Windows-1252: not UTF-8, so the Windows code page.
    ("Am  F\ncafé “là”\n".encode("cp1252"), "Am  F\ncafé “là”\n", TextFormat("cp1252", "\n")),
    # A byte Windows-1252 leaves undefined: Latin-1, which takes any byte.
    (b"C\x81\n", "C\x81\n", TextFormat("latin-1", "\n")),
    (b"C\rla\r", "C\rla\r", TextFormat("utf-8", "\r")),
    (b"", "", TextFormat("utf-8", "\n")),
])
def test_decode(data, text, fmt):
    assert decode_text(data) == (text, fmt)


def test_line_endings_are_the_most_common_one():
    assert decode_text(b"a\r\nb\r\nc\n")[1].newline == "\r\n"
    assert decode_text(b"a\r\nb\nc\n")[1].newline == "\n"
    assert decode_text(b"a\r\nb\n")[1].newline == "\n"          # a tie: LF


@pytest.mark.parametrize("data", [
    b"C G\r\nla la\r\n",
    "Am  F\r\ncafé “là”\r\n".encode("cp1252"),
    codecs.BOM_UTF8 + "Dó\nRé\n".encode("utf-8"),
    "Am\r\nGrüße\r\n".encode("utf-16"),
    b"C\rla\r",
])
def test_an_unchanged_song_saves_back_byte_for_byte(data):
    text, _ = decode_text(data)
    editor_text = text.replace("\r\n", "\n").replace("\r", "\n")
    saved, note = encode_text(editor_text, format_of(data, LF))
    assert (saved, note) == (data, None)


def test_a_character_the_encoding_lacks_writes_utf8_and_says_so():
    fmt = format_of("Am\r\ncafé\r\n".encode("cp1252"), LF)
    saved, note = encode_text("Am\ncafé în șir\n", fmt)
    assert saved == "Am\r\ncafé în șir\r\n".encode("utf-8")       # line endings kept
    assert note == "Saved in UTF-8: Windows-1252, the file's encoding, has no ș"


def test_a_new_file_gets_the_default():
    assert format_of(None, TextFormat(newline="\r\n")) == TextFormat("utf-8", "\r\n")
    assert encode_text("C\nG\n", TextFormat(newline="\r\n")) == (b"C\r\nG\r\n", None)


def test_an_empty_or_one_line_file_takes_the_default_line_endings():
    assert format_of(b"", TextFormat(newline="\r\n")) == TextFormat("utf-8", "\r\n")
    assert format_of("café".encode("cp1252"), LF) == TextFormat("cp1252", "\n")
