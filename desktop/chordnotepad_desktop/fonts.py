"""Text set-up at start-up: native text rendering, the bundled Inter, no hinting.

Tibi chose this recipe on 2026-11-14 with the shift test
(``/mnt/data_linux/Bin/qt-spike/fonttest/fonttest.py``) at 125%:

* **Native text rendering** (FreeType glyphs, as in Widgets apps) instead of
  Qt Quick's distance-field default, which looks soft and uneven at small
  sizes and fractional scales. The Qt and Curve renderers look a little worse.
* **No hinting for Inter.** The bundled TTFs carry ttfautohint bytecode, and
  KDE's ``XftHintStyle=hintfull`` gave uneven spacing and a malformed "t" at
  1.25. Hinting isn't inherited (Qt Quick pitfall 11): setting it on the
  application font isn't enough, so Theme.qml sets ``hintingPreference`` on
  every ``Qt.font`` too (``tests/qt/test_qt_theme.py`` checks each one). The
  editor's Noto Sans Mono keeps default hinting (D1).
* **Whole device pixels.** Without snapping, glyphs change shape and spacing
  at a fractional x; ``SText``, ``Label`` and the controls' labels snap their
  origin (``SnapTranslate``).
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQuick import QQuickWindow

from chordnotepad.app_paths import AppPaths

logger = logging.getLogger(__name__)

#: The UI font's family (Theme.uiFont), bundled in resources/fonts (OFL).
UI_FAMILY = "Inter"
#: The bundled UI font files.
UI_FONT_GLOB = "Inter-*.ttf"


def font_folder(paths: AppPaths) -> Optional[Path]:
    """``resources/fonts``, or None without resources."""
    return paths.resources / "fonts" if paths.resources is not None else None


def use_native_text_rendering():
    """FreeType glyphs for every Qt Quick window. Call before the first window."""
    QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)


def load_bundled_fonts(folder: Optional[Path]) -> list:
    """Add the bundled Inter files to the font database.

    Returns:
        The families they added (``["Inter"]`` normally). A missing file or
        folder is logged; Qt then falls back to another sans font.
    """
    families = []
    files = sorted(folder.glob(UI_FONT_GLOB)) if folder is not None and folder.is_dir() else []
    for path in files:
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            logger.warning("Could not load the font %s", path)
            continue
        families += [f for f in QFontDatabase.applicationFontFamilies(font_id) if f not in families]
    if UI_FAMILY not in families:
        logger.warning("The bundled %s font was not found in %s; the UI uses a fallback font",
                       UI_FAMILY, folder)
    return families


def unhinted(font: QFont) -> QFont:
    """``font`` with hinting off (the Inter recipe)."""
    font = QFont(font)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def set_application_font(app: QGuiApplication):
    """Turn hinting off on the application font, the default of QML text.

    Only a start: QML fonts that set a family or size don't reliably inherit
    it, hence Theme.qml's own ``hintingPreference`` on every font.
    """
    app.setFont(unhinted(app.font()))
