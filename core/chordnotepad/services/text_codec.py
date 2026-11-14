"""How a song file's bytes become text and back.

Shared by the desktop's :class:`services.file_service.FileService` and the
Android document store, so a file reads and saves the same way on both.

Reading
-------
* A byte-order mark decides: UTF-8 with a BOM, UTF-16 (LE or BE).
* Otherwise UTF-8 if the bytes are valid UTF-8 (plain ASCII is too).
* Otherwise Windows-1252, the usual "ANSI" encoding of Western European
  Windows text, and a superset of Latin-1's printable characters; bytes it
  leaves undefined (0x81, 0x8D, 0x8F, 0x90, 0x9D) fall back to Latin-1,
  which decodes any byte. A file in another 8-bit code page (Central European
  cp1250, say) reads with the wrong accented letters: there's no telling
  them apart from the bytes alone.

Line endings are the most common of CRLF, LF and CR (LF on a tie or with
none); the text the editor gets always has ``\\n``.

Saving
------
Saving an existing file keeps what it has on disk: its encoding, its BOM and
its line endings, so a Windows file stays CRLF in Windows-1252 and other
programs read it as before. The format is read from the file at save time,
not remembered from the open, so it survives a restored draft, a rename and a
reopen. A new file is UTF-8 without a BOM, with the platform's line endings
on the desktop (CRLF on Windows) and LF on Android.

If the text has a character the file's encoding can't hold (``ș`` in a
Windows-1252 file), the file is written in UTF-8 instead and the save says so
(:func:`encode_text`'s note), rather than failing or losing the character.
"""

import codecs
from dataclasses import dataclass
from typing import Optional, Tuple

#: Encodings as the user reads them in a note.
_ENCODING_NAMES = {
    "utf-8": "UTF-8",
    "utf-8-sig": "UTF-8",
    "utf-16": "UTF-16",
    "cp1252": "Windows-1252",
    "latin-1": "Latin-1",
}


@dataclass(frozen=True)
class TextFormat:
    """How a text file is stored.

    Attributes:
        encoding: A Python codec name: ``utf-8``, ``utf-8-sig`` (with a BOM),
            ``utf-16`` (with a BOM, little-endian on write), ``cp1252`` or
            ``latin-1``.
        newline: ``"\\n"``, ``"\\r\\n"`` or ``"\\r"``.
    """

    encoding: str = "utf-8"
    newline: str = "\n"

    @property
    def encoding_name(self) -> str:
        """The encoding as the user reads it (``Windows-1252``)."""
        return _ENCODING_NAMES.get(self.encoding, self.encoding)


def decode_text(data: bytes) -> Tuple[str, TextFormat]:
    """The text of a file's bytes, line endings as they are, and its format.

    Never fails: the last fallback, Latin-1, decodes any byte.
    """
    if data.startswith(codecs.BOM_UTF8):
        encoding = "utf-8-sig"
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = "utf-16"
    else:
        encoding = "utf-8"
    for candidate in (encoding, "cp1252", "latin-1"):
        try:
            text = data.decode(candidate)
        except UnicodeDecodeError:
            continue
        return text, TextFormat(candidate, _newline_of(text))
    raise AssertionError("latin-1 decodes any byte")


def format_of(data: Optional[bytes], default: TextFormat) -> TextFormat:
    """The format a save keeps: that of the file's current bytes ``data``,
    or ``default`` when there's no file yet (``data`` None).

    An empty file has nothing to keep but its BOM-less encoding, so it gets
    the default's line endings.
    """
    if data is None:
        return default
    text, found = decode_text(data)
    if "\n" not in text and "\r" not in text:
        return TextFormat(found.encoding, default.newline)
    return found


def encode_text(text: str, fmt: TextFormat) -> Tuple[bytes, Optional[str]]:
    """``text`` (``\\n`` line endings) as bytes in ``fmt``, and a note for the
    user when that couldn't be done.

    Returns:
        ``(data, note)``: ``note`` is None, or says that the file was written
        in UTF-8 because ``fmt``'s encoding can't hold one of its characters.
    """
    if fmt.newline != "\n":
        text = text.replace("\n", fmt.newline)
    try:
        return text.encode(fmt.encoding), None
    except UnicodeEncodeError as e:
        bad = e.object[e.start:e.end]
        note = (f"Saved in UTF-8: {fmt.encoding_name}, the file's encoding, "
                f"has no {bad}")
        return text.encode("utf-8"), note


def _newline_of(text: str) -> str:
    """The most common line ending in ``text`` (LF on a tie or with none)."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf > lf and crlf >= cr:
        return "\r\n"
    if cr > lf and cr > crlf:
        return "\r"
    return "\n"
