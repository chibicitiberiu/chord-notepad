"""The editor's font: which family, and the text zoom's steps.

**Family.** The config keeps ``font_family`` as the Tk app wrote it, and its
default is Tk's named font ``"TkFixedFont"``, which Android maps to its
monospace too (``EditorStyles.kt``). Here that name, an empty one, or a
family this machine doesn't have, gives the editor's monospace: Noto Sans
Mono, the approved mockup's editor font, bundled in ``resources/fonts``
(OFL-1.1, like Inter) so it is the same on every OS. A system's own
"monospace" varies a lot (Tibi's Fedora gives Bitstream Vera Sans Mono,
Windows gives Courier New). If the bundled file can't be loaded, the
platform's fixed-pitch font (``QFontDatabase.FixedFont``) is used. A family
the user picked that is installed is used as it is.

Noto Sans Mono keeps the default hinting, unlike Inter: its advances are
fixed, so hinting can't break the columns, and it is crisper at 100%.

**Zoom** (plan resolution 3). The zoom chip shows the size as a percentage
of the default 11 pt in 10% steps; ``font_size`` stays a whole number of
points, 6 to 72. A step goes to the next rung of the ladder
``11 pt × (100% + n × 10%)``, rounded to whole points (12, 13, 14, 15, 17,
18, ... and 10, 9, 8, 7, 6), and a size between rungs (typed in Settings,
or kept from Tk, which stepped by 1 pt) shows its nearest rung's percentage.
Every rung is a different whole size, because a rung is 1.1 pt apart.
"""

import logging
import math
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QFontDatabase

from chordnotepad.constants import DEFAULT_FONT_SIZE, MAX_FONT_SIZE, MIN_FONT_SIZE

logger = logging.getLogger(__name__)

#: The config's sentinel for "the monospace font" (Tk's named font).
TK_FIXED_FONT = "TkFixedFont"
#: The editor's monospace, bundled in resources/fonts (Theme.monoFont).
MONO_FAMILY = "Noto Sans Mono"
#: The bundled files.
MONO_FONT_GLOB = "NotoSansMono-*.ttf"
#: One zoom step, as a fraction of the default size.
ZOOM_STEP = 0.1


def load_mono_font(folder: Optional[Path]) -> bool:
    """Add the bundled Noto Sans Mono to the font database.

    Returns:
        Whether the family is there now (bundled or installed).
    """
    files = sorted(folder.glob(MONO_FONT_GLOB)) if folder is not None and folder.is_dir() else []
    for path in files:
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            logger.warning("Could not load the font %s", path)
    available = MONO_FAMILY in QFontDatabase.families()
    if not available:
        logger.warning("The bundled %s font was not found in %s; the editor uses %s",
                       MONO_FAMILY, folder, platform_monospace())
    return available


def platform_monospace() -> str:
    """The system's fixed-pitch family (the fallback)."""
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def editor_monospace() -> str:
    """The editor's monospace: the bundled Noto Sans Mono, else the system's."""
    if MONO_FAMILY in QFontDatabase.families():
        return MONO_FAMILY
    return platform_monospace()


def resolve_family(configured: Optional[str]) -> str:
    """The family to draw the editor in, for the config's ``font_family``.

    ``"TkFixedFont"``, an empty name, Tk's other named fonts and families
    this machine doesn't have give :func:`editor_monospace`.
    """
    name = (configured or "").strip()
    if not name or name.startswith("Tk"):
        return editor_monospace()
    if name in QFontDatabase.families():
        return name
    logger.info("Editor font %r is not installed; using %s", name, editor_monospace())
    return editor_monospace()


def _rung_of(size: int) -> int:
    """The ladder rung nearest ``size`` (0 is the default size)."""
    return int(math.floor((size - DEFAULT_FONT_SIZE) / (DEFAULT_FONT_SIZE * ZOOM_STEP) + 0.5))


def _size_of(rung: int) -> int:
    size = int(math.floor(DEFAULT_FONT_SIZE * (1 + ZOOM_STEP * rung) + 0.5))
    return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))


def zoom_percent(size: int) -> int:
    """What the zoom chip shows for ``size`` pt: a multiple of 10."""
    return 100 + 10 * _rung_of(int(size))


def zoomed_size(size: int, steps: int) -> int:
    """``size`` pt moved ``steps`` rungs up (positive) or down, within 6-72 pt."""
    size = int(size)
    if steps == 0:
        return max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
    return _size_of(_rung_of(size) + int(steps))
