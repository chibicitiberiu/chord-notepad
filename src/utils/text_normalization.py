"""Normalization for song text entering the editor from outside sources.

Text arrives from two unguarded doors -- the clipboard and files on disk --
and both routinely carry characters that either render as junk or silently
break chord detection:

- Windows/CRLF (and old-Mac lone CR) line endings: Tk inserts a pasted
  ``\\r`` as a literal character that shows as a junk glyph at the end of
  the line. (Python's universal newlines already normalize these on file
  READ, so the file path only relies on this for the other cases below.)
- Non-breaking spaces (``\\u00a0``), common in text copied from web pages:
  they look like spaces but are not, which breaks chord detection and
  chord/lyric column alignment.
- Zero-width characters (``\\u200b`` zero-width space, ``\\ufeff`` BOM):
  invisible, but they shift character offsets and split chord tokens.

The file on disk is never rewritten by normalization alone; the normalized
form only reaches disk when the user saves.
"""


def normalize_song_text(text: str) -> str:
    """Normalize song text from an external source (clipboard or file).

    Args:
        text: Raw incoming text.

    Returns:
        The text with line endings normalized to ``\\n``, non-breaking
        spaces replaced by plain spaces, and zero-width characters removed.
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\u00a0', ' ')
    return text.replace('\u200b', '').replace('\ufeff', '')
