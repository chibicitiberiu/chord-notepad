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


def image_for_clef_key(key: str) -> Optional[Image.Image]:
    """Resolve an ops image ``key`` (``'clef_<kind>:<int-height>'``) to an image.

    The panel calls this while replaying draw ops: it turns the key an
    ``ImageOp`` carries into a concretely sized :class:`PIL.Image.Image` (which
    it then converts to a Tk image). Returns ``None`` for any key that is not a
    well-formed clef key, so an unknown asset is skipped rather than crashing a
    paint.

    Args:
        key: An image key of the form ``'clef_treble:96'`` / ``'clef_bass:60'``.

    Returns:
        The sized clef image, or ``None`` if ``key`` is malformed / unknown.
    """
    prefix, sep, height_str = key.partition(":")
    if sep != ":" or not prefix.startswith(_KEY_PREFIX):
        return None
    kind = prefix[len(_KEY_PREFIX):]
    if kind not in _CLEF_BASE:
        return None
    try:
        height = int(height_str)
    except ValueError:
        return None
    if height <= 0:
        return None
    return _render_at_height(kind, height)
