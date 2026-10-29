"""Pillow side of the chord-sheet clef and glyph assets (desktop only).

:mod:`chord_sheet.clef_assets` holds the embedded PNG bytes, the placement math
and the image-key grammar without importing Pillow, so it can ship on Android.
This module decodes those PNGs with Pillow, resizes them (LANCZOS) to the
height an image key asks for and tints glyphs, for the Tk panel to wrap in
``ImageTk.PhotoImage``.
"""

from __future__ import annotations

import io
from functools import lru_cache
from typing import Optional

from PIL import Image

from chord_sheet.clef_assets import (
    base_png,
    clef_placement,
    parse_image_key,
    scaled_width,
)

try:  # Pillow >= 9.1
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - very old Pillow
    _LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]


@lru_cache(maxsize=None)
def _base_image(asset: str) -> Image.Image:
    """Decode the embedded base PNG for ``asset`` once (cached)."""
    return Image.open(io.BytesIO(base_png(asset))).convert("RGBA")


@lru_cache(maxsize=None)
def _render_at_height(asset: str, height: int) -> Image.Image:
    """Return ``asset`` resized to ``height`` px (width follows aspect), cached."""
    return _base_image(asset).resize((scaled_width(asset, height), height), _LANCZOS)


@lru_cache(maxsize=None)
def _render_tinted(asset: str, height: int, color6: str) -> Image.Image:
    """Return ``asset`` at ``height`` px recolored to ``color6`` (cached).

    The glyph is black ink + alpha; the tint keeps the alpha as a mask and
    fills the opaque pixels with the ``rrggbb`` color, so an accidental or
    notehead can be drawn in a voice/hand color.
    """
    base = _render_at_height(asset, height)
    rgb = (int(color6[0:2], 16), int(color6[2:4], 16), int(color6[4:6], 16))
    solid = Image.new("RGBA", base.size, rgb + (255,))
    solid.putalpha(base.getchannel("A"))
    return solid


def get_clef_image(kind: str, staff_space_px: float) -> Image.Image:
    """Return the clef image sized for a staff of ``staff_space_px`` (cached).

    Args:
        kind: ``'treble'`` or ``'bass'``.
        staff_space_px: The staff's staff-space size in px.

    Returns:
        A :class:`PIL.Image.Image` scaled so its staff-space matches
        ``staff_space_px`` (same size :func:`image_for_clef_key` yields for the
        matching :attr:`~chord_sheet.clef_assets.ClefPlacement.key`).
    """
    return image_for_clef_key(clef_placement(kind, staff_space_px).key)


def image_for_clef_key(key: str) -> Optional[Image.Image]:
    """Resolve an ops image ``key`` to a sized :class:`PIL.Image.Image`.

    The panel calls this while replaying draw ops: it turns the key an
    ``ImageOp`` carries into a concretely sized image (which it then converts to
    a Tk image). Despite the historical name it resolves the whole key grammar
    (see :func:`chord_sheet.clef_assets.parse_image_key`): clefs, black-ink
    glyphs and tinted glyphs.

    Args:
        key: An image key (e.g. ``'clef_treble:96'``,
            ``'glyph_notehead_whole:48'``, ``'glyph_accidental_sharp:120:3a5a8a'``).

    Returns:
        The sized image, or ``None`` if ``key`` is malformed / unknown, so an
        unknown asset is skipped rather than crashing a paint.
    """
    parsed = parse_image_key(key)
    if parsed is None:
        return None
    if parsed.color is None:
        return _render_at_height(parsed.asset, parsed.height)
    return _render_tinted(parsed.asset, parsed.height, parsed.color)
