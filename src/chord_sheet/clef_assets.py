"""Embedded grand-staff clef assets for the chord-sheet staff renderer.

The two clefs (treble G-clef, bass F-clef) are Bravura glyphs rendered at high
resolution upstream, then downscaled here (LANCZOS, <= 256px tall) and
base64-embedded so the staff card never touches an external file (the strict
Artifact/PyInstaller sandbox forbids remote assets). Each blob keeps its
*scaled* SMuFL registration metadata: ``px_per_staff_space`` (how many image
pixels one staff space spans at the embedded size) and ``baseline_y`` (the y,
in image pixels from the top, where the clef's reference staff line crosses --
the G line, 2nd from the bottom, for treble; the F line, 2nd from the top, for
bass).

A painter that draws a staff at some ``staff_space_px`` asks
:func:`clef_placement` for the image key + geometry to place: it emits an
``ops.image`` op with that key at ``(x, reference_line_y - placement.baseline_y)``
so the clef's reference line lands exactly on the right staff line.

**Image key format** -- the string an ``ImageOp`` carries and the panel later
resolves: ``'clef_<kind>:<int-height>'`` where ``<kind>`` is ``treble`` or
``bass`` and ``<int-height>`` is the target image height in whole pixels
(e.g. ``'clef_treble:96'``). :func:`clef_placement` builds the key;
:func:`image_for_clef_key` resolves it back to a sized :class:`PIL.Image.Image`
(the width follows from the height, preserving aspect). Both sides derive the
size from that single integer height, so the positioned clef and the rendered
image always agree.

The staff renderer also needs Bravura **noteheads and accidentals**, embedded
the same way (base64 RGBA PNGs, SMuFL registration metadata). These extend the
key grammar so the panel's single resolver keeps working unchanged:

- ``'glyph_<name>:<int-height>'`` -- the black-ink glyph at that pixel height,
  where ``<name>`` is ``notehead_whole`` / ``accidental_sharp`` /
  ``accidental_flat`` / ``accidental_natural``.
- ``'glyph_<name>:<int-height>:<rrggbb>'`` -- a *tinted* variant: the ink is
  recolored to the 6-hex color while the glyph's alpha is kept as the mask
  (so a notehead can be drawn in a voice/hand color). Tints are cached by
  ``(name, height, color)``.

:func:`glyph_placement` builds a glyph key (optionally with a tint color) plus
its placement geometry -- the scaled ``origin_x``/``origin_y`` (the SMuFL
registration point: a notehead's origin is vertically centered on its line or
space; an accidental's origin registers to the line/space it alters), so a
painter anchors the image ``'nw'`` at ``(x - origin_x, staff_y - origin_y)``.
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from typing import Dict, NamedTuple, Optional

from PIL import Image

try:  # Pillow >= 9.1
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - very old Pillow
    _LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]

#: Prefix every clef image key starts with (see the module docstring).
_KEY_PREFIX = "clef_"

#: Prefix every staff-glyph (notehead/accidental) image key starts with. Glyph
#: keys extend the clef grammar: ``'glyph_<name>:<int-height>'`` for the plain
#: black-ink glyph and ``'glyph_<name>:<int-height>:<rrggbb>'`` for a tinted
#: variant (the ink recolored to ``rrggbb``, the alpha kept as the mask).
_GLYPH_PREFIX = "glyph_"


class _ClefBase(NamedTuple):
    """One embedded clef blob plus its scaled SMuFL registration metadata."""

    b64: str
    """base64 of the downscaled RGBA PNG."""
    width: int
    """Embedded-image width in px."""
    height: int
    """Embedded-image height in px."""
    px_per_staff_space: float
    """Image pixels spanning one staff space at the embedded size."""
    baseline_y: float
    """y (px from top) of the clef's reference staff line in the embedded image."""


class ClefPlacement(NamedTuple):
    """Where and how big to place a clef on a staff at a given staff-space size.

    ``key`` goes into the ``ops.image`` op; ``width``/``height`` are the placed
    image's pixel size; ``baseline_y`` is the offset (px from the image top) of
    the clef's reference staff line, so a painter anchors the image ``'nw'`` at
    ``(x, reference_line_y - baseline_y)``.
    """

    key: str
    width: int
    height: int
    baseline_y: float


class GlyphPlacement(NamedTuple):
    """Where and how big to place a staff glyph at a given staff-space size.

    ``key`` goes into the ``ops.image`` op; ``width``/``height`` are the placed
    image's pixel size; ``origin_x``/``origin_y`` are the glyph's SMuFL
    registration point (px from the image's top-left), so a painter anchors the
    image ``'nw'`` at ``(staff_x - origin_x, staff_y - origin_y)`` to land the
    glyph's registration point on ``(staff_x, staff_y)``.
    """

    key: str
    width: int
    height: int
    origin_x: float
    origin_y: float


_TREBLE_PNG_B64 = (
    "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"
)

_BASS_PNG_B64 = (
    "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"
    "RU5ErkJggg=="
)

_CLEF_BASE: Dict[str, _ClefBase] = {
    "treble": _ClefBase(
        _TREBLE_PNG_B64,
        98, 256, 36.449388, 160.035595,
    ),
    "bass": _ClefBase(
        _BASS_PNG_B64,
        197, 256, 71.234783, 74.573913,
    ),
}


class _GlyphBase(NamedTuple):
    """One embedded staff-glyph blob plus its scaled SMuFL registration data."""

    b64: str
    """base64 of the downscaled RGBA PNG (black ink + alpha)."""
    width: int
    """Embedded-image width in px."""
    height: int
    """Embedded-image height in px."""
    px_per_staff_space: float
    """Image pixels spanning one staff space at the embedded size."""
    origin_x: float
    """x (px from left) of the glyph's SMuFL origin in the embedded image."""
    origin_y: float
    """y (px from top) of the glyph's SMuFL origin in the embedded image."""


_NOTEHEAD_WHOLE_PNG_B64 = (
    "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"
    "+h+kGAzzSLmXwAAAAABJRU5ErkJggg=="
)

_ACCIDENTAL_SHARP_PNG_B64 = (
    "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"
)

_ACCIDENTAL_FLAT_PNG_B64 = (
    "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"
)

_ACCIDENTAL_NATURAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACgAAACgCAYAAAB+HS7YAAAE8klEQVR4nO2dPagcVRSAv9nZFwn+RE0ikiKiQSVgUAMhBIvnL4ro"
    "aywi0dbW1CqxtNTCxlJQIUVSqAgigoqiSDQGtFCCYqEvjcQYJRB3d8bCc+XkZn7uvDO7s8L54JL3dndmvrlzZ949Z85sALYDbwDn"
    "gRIogBnwK/AC/5IxIG+JmG6F+vkZ+dxoKMEL0mNFJDmR1z4fUnAMbK55bySHdkV+LxfodYnEUuOCVlzQigtacUErLmjFBa24oBUX"
    "tOKCVlzQigtacUErLmjFBa0sveB4aIGITFrouGIZBDOVi5yqDC8M2IO6l2bSADYBe4En5P1XFylYJ7UF2AM8BjwC3KmWuY+KBHpo"
    "M/n3hNpAV0ZylOKT8UrgIeA14MeKBP5EWtl3D8bjqVDjaQtwD/C4yO1Sy4UEfqZ2ilTBrKb3sqjNVM8HdgKrwMNyuHY0SFVuO0Uw"
    "bHhFZfoLtQHNtcBdwL3A/cDdwFUdpS4hRfB64ArgYvT6ZmAbsBs4AOyTdkPFDtJFSpMl3v/4WtrfwDUisRO4ueY+yzQajxsmVbAJ"
    "fWE1C8WkCoYxl6kxlDWcQAsXHIyln824oBUXtOKCVlzQigtaWXrBRUZ1ZTQxSZoJzXs2o8OCvOL9sk1yHoJBKp68lsAZKWKbATdJ"
    "vNIo2ZdgiObyaGPfAieBj4FTwDpwTj67G/gAuFHtUO3KN9oKlU8J7STwErBfUhlNfBklCS5rGz1Jglwu7TzwDvA68KkEV4FcLROO"
    "VujlpKuIpcd+AY7IeNKMWwKo8PqJth7sIqhXsg48H8XAecUYrKN3wbCCKfCyDGwt1jWy61UwLHxa0hkWsd4FdQouJH7GPcTCvQiG"
    "YP0P4FZZ4Ur9Nucj2HSal7Ki09JGklRcKCnXoXLIDETqdGsQOf4P80EXtOKCVlzQigtacUErLthA0gxpSMFSblI2MoRgLnK3A7eo"
    "+WYlixbMZXqfAa+k5GZIDJgwBkqZSvVtAt5UYWxbVDlXwSxKu+0BPusgNzfBUZQc3Qq8CPzZUa5XwdBbelxfDRwGfq5Yb1JLzW6F"
    "jYbrVnxDu1BP1QLcBjwFPC1nKtJr8Q60kipYqB4qayo+dgAPAmvAo6qWYRadJJ1pyiyUkhFdjZbJRWgVeA54Vz6nl590PZxVre3P"
    "TbhGzaTq46ykP66TnODWip4u+yyuSPl72HQh1Ye694oPOqQ0Sl3Tt6iKD4bMuaTi80ErLmjFBa24oBUXtOKCVlzQigtamVflURz8"
    "hKr0UkWISSFCn3UzsUwvWAR1nBKXPZ2Tr8U6JcU968Dvsr1t8rTEQckPbji7VRcrTytyKxeBbySltlZRplLFmtTX6Ec/OuVm4jxN"
    "LPUX8CHwLHBHjURIIo1V2cpY9fh3bfmappMkLKifSZpIZdFx4H3gp2gZXWVURI8MaULIeqGtm2PBeFyF978CjgFvA99HPZSp5Wak"
    "0zr2gmCpVqy7f12Ejsq3l03l9fiSMXc+icbVe8AheT4p3pm+Lh/JZSljOd0PyXj4CPhBrShXH57WbGzhjHqqLmqiUw9mUQa17swb"
    "hPgkWTqWfjbjglZc0IoLWnFBKy5oxQWtuKAVF7TiglZc0IoLWnFBK0MLthYVDS04apAsU7/zaB6ErOxv8vMkulNQSt7ozEB+/w2t"
    "Byqq5nQy9eCQ/61H6MW9wJOqki6TUtKjwBf/ANDeU5tMAPIAAAAAAElFTkSuQmCC"
)

_GLYPH_BASE: Dict[str, _GlyphBase] = {
    "notehead_whole": _GlyphBase(
        _NOTEHEAD_WHOLE_PNG_B64, 108, 64, 64.0, 0.0, 32.0,
    ),
    "accidental_sharp": _GlyphBase(
        _ACCIDENTAL_SHARP_PNG_B64, 57, 160, 57.206704, 0.0, 80.446927,
    ),
    "accidental_flat": _GlyphBase(
        _ACCIDENTAL_FLAT_PNG_B64, 59, 160, 65.015873, 0.0, 114.285714,
    ),
    "accidental_natural": _GlyphBase(
        _ACCIDENTAL_NATURAL_PNG_B64, 40, 160, 59.020173, 0.0, 80.691643,
    ),
}


@lru_cache(maxsize=None)
def _base_image(kind: str) -> Image.Image:
    """Decode the embedded base PNG for ``kind`` once (cached)."""
    raw = base64.b64decode(_CLEF_BASE[kind].b64)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


@lru_cache(maxsize=None)
def _render_at_height(kind: str, height: int) -> Image.Image:
    """Return the clef resized to ``height`` px (width follows aspect), cached."""
    data = _CLEF_BASE[kind]
    width = max(1, round(data.width * height / data.height))
    return _base_image(kind).resize((width, height), _LANCZOS)


def clef_placement(kind: str, staff_space_px: float) -> ClefPlacement:
    """Compute the image key + placement geometry for a clef on a staff.

    Args:
        kind: ``'treble'`` or ``'bass'``.
        staff_space_px: The staff's staff-space size in px (one line-to-line
            gap) at the card's scale.

    Returns:
        A :class:`ClefPlacement`: the ``'clef_<kind>:<height>'`` image key, the
        placed pixel ``width``/``height``, and the ``baseline_y`` offset of the
        clef's reference line from the image top.

    Raises:
        KeyError: if ``kind`` is not ``'treble'`` or ``'bass'``.
    """
    data = _CLEF_BASE[kind]
    scale = staff_space_px / data.px_per_staff_space
    height = max(1, round(data.height * scale))
    ratio = height / data.height
    width = max(1, round(data.width * ratio))
    baseline_y = data.baseline_y * ratio
    return ClefPlacement(f"{_KEY_PREFIX}{kind}:{height}", width, height, baseline_y)


def get_clef_image(kind: str, staff_space_px: float) -> Image.Image:
    """Return the clef image sized for a staff of ``staff_space_px`` (cached).

    Args:
        kind: ``'treble'`` or ``'bass'``.
        staff_space_px: The staff's staff-space size in px.

    Returns:
        A :class:`PIL.Image.Image` scaled so its staff-space matches
        ``staff_space_px`` (same size :func:`image_for_clef_key` yields for the
        matching :attr:`ClefPlacement.key`).
    """
    return _render_at_height(kind, clef_placement(kind, staff_space_px).height)


# -- Staff glyphs (noteheads / accidentals) --------------------------------

@lru_cache(maxsize=None)
def _base_glyph_image(name: str) -> Image.Image:
    """Decode the embedded base PNG for glyph ``name`` once (cached)."""
    raw = base64.b64decode(_GLYPH_BASE[name].b64)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


@lru_cache(maxsize=None)
def _render_glyph_at_height(name: str, height: int) -> Image.Image:
    """Return glyph ``name`` resized to ``height`` px (aspect kept), cached."""
    data = _GLYPH_BASE[name]
    width = max(1, round(data.width * height / data.height))
    return _base_glyph_image(name).resize((width, height), _LANCZOS)


@lru_cache(maxsize=None)
def _render_glyph_tinted(name: str, height: int, color6: str) -> Image.Image:
    """Return glyph ``name`` at ``height`` px recolored to ``color6`` (cached).

    The glyph is black ink + alpha; the tint keeps the alpha as a mask and
    fills the opaque pixels with the ``rrggbb`` color, so an accidental or
    notehead can be drawn in a voice/hand color.
    """
    base = _render_glyph_at_height(name, height)
    rgb = (int(color6[0:2], 16), int(color6[2:4], 16), int(color6[4:6], 16))
    solid = Image.new("RGBA", base.size, rgb + (255,))
    solid.putalpha(base.getchannel("A"))
    return solid


def _normalize_color(color: Optional[str]) -> Optional[str]:
    """Normalize a color to lowercase ``rrggbb``, or ``None`` if malformed.

    Accepts an optional leading ``'#'``; requires exactly six hex digits.
    """
    if not color:
        return None
    c = color.lstrip("#").lower()
    if len(c) == 6 and all(ch in "0123456789abcdef" for ch in c):
        return c
    return None


def glyph_placement(
    name: str, staff_space_px: float, color: Optional[str] = None
) -> GlyphPlacement:
    """Compute the image key + placement geometry for a staff glyph.

    Args:
        name: One of ``'notehead_whole'``, ``'accidental_sharp'``,
            ``'accidental_flat'``, ``'accidental_natural'``.
        staff_space_px: The staff's staff-space size in px at the card's scale.
        color: Optional tint (``'#rrggbb'`` or ``'rrggbb'``); when given, the
            key carries the normalized color so the glyph renders recolored.

    Returns:
        A :class:`GlyphPlacement`: the ``'glyph_<name>:<height>[:<rrggbb>]'``
        image key, the placed pixel ``width``/``height``, and the scaled
        ``origin_x``/``origin_y`` registration point.

    Raises:
        KeyError: if ``name`` is not a known glyph.
    """
    data = _GLYPH_BASE[name]
    scale = staff_space_px / data.px_per_staff_space
    height = max(1, round(data.height * scale))
    ratio = height / data.height
    width = max(1, round(data.width * ratio))
    origin_x = data.origin_x * ratio
    origin_y = data.origin_y * ratio
    color6 = _normalize_color(color)
    if color6:
        key = f"{_GLYPH_PREFIX}{name}:{height}:{color6}"
    else:
        key = f"{_GLYPH_PREFIX}{name}:{height}"
    return GlyphPlacement(key, width, height, origin_x, origin_y)


def image_for_clef_key(key: str) -> Optional[Image.Image]:
    """Resolve an ops image ``key`` to a sized :class:`PIL.Image.Image`.

    The panel calls this while replaying draw ops: it turns the key an
    ``ImageOp`` carries into a concretely sized image (which it then converts to
    a Tk image). Despite the historical name it resolves the whole key grammar:

    - ``'clef_<kind>:<int-height>'`` -- a treble/bass clef.
    - ``'glyph_<name>:<int-height>'`` -- a black-ink notehead/accidental.
    - ``'glyph_<name>:<int-height>:<rrggbb>'`` -- a tinted glyph variant.

    Returns ``None`` for any key that is not well-formed, so an unknown asset is
    skipped rather than crashing a paint.

    Args:
        key: An image key (e.g. ``'clef_treble:96'``,
            ``'glyph_notehead_whole:48'``, ``'glyph_accidental_sharp:120:3a5a8a'``).

    Returns:
        The sized image, or ``None`` if ``key`` is malformed / unknown.
    """
    parts = key.split(":")
    if len(parts) < 2:
        return None
    name = parts[0]
    try:
        height = int(parts[1])
    except ValueError:
        return None
    if height <= 0:
        return None

    if name.startswith(_KEY_PREFIX):
        if len(parts) != 2:
            return None
        kind = name[len(_KEY_PREFIX):]
        if kind not in _CLEF_BASE:
            return None
        return _render_at_height(kind, height)

    if name.startswith(_GLYPH_PREFIX):
        gname = name[len(_GLYPH_PREFIX):]
        if gname not in _GLYPH_BASE:
            return None
        if len(parts) == 2:
            return _render_glyph_at_height(gname, height)
        if len(parts) == 3:
            color6 = _normalize_color(parts[2])
            if color6 is None:
                return None
            return _render_glyph_tinted(gname, height, color6)
        return None

    return None
