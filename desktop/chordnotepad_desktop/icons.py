"""Pixel-exact icons for QML: ``image://icons/<name>?c=<colour>&s=<device px>&d=<ratio>``.

QML's IconImage loads an SVG at ``sourceSize`` (whole logical pixels) times
the device pixel ratio, so at 125% an 18 px icon becomes 22.5 device pixels,
is rounded, and is scaled again on screen: it blurs (Qt Quick pitfall 14).
Here ``PixelIcon.qml`` asks for a whole number of device pixels, and the
image comes back tagged with the ratio, so it is drawn 1:1 and never
resampled. The SVG is tinted to one colour, as IconImage does.

The icons are in ``resources/qt-icons/`` (``mdi/`` for Material Design
Icons, ``own/`` for ours; the README there says which is which). Each
rendered size and colour is kept in a small LRU cache: a theme switch or a
ratio change asks for a new set, and the old one ages out.
"""

import logging
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import parse_qs

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

from chordnotepad.app_paths import AppPaths

logger = logging.getLogger(__name__)

#: The provider's id: ``engine.addImageProvider(PROVIDER_ID, ...)``.
PROVIDER_ID = "icons"
#: Icon names are file names without ``.svg``; nothing else reaches the disk.
ICON_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
#: Icons Qt's own controls ask for by their file name (the CNStyle buttons
#: pass any icon.source through here): Qt Quick's file dialog's "up a
#: folder" button (QtQuick/Dialogs/quickimpl, FolderBreadcrumbBar.qml).
ALIASES = {"up-icon-round.png": "chevron-up"}
#: Rendered images kept (name, size, colour, ratio). A window uses ~150.
CACHE_SIZE = 512
#: The largest icon drawn, in device pixels (a sanity limit on ``s``).
MAX_DEVICE_PX = 1024


def icon_folders(paths: AppPaths) -> list:
    """``resources/qt-icons/mdi`` and ``.../own``; empty without resources."""
    if paths.resources is None:
        return []
    root = paths.resources / "qt-icons"
    return [root / "mdi", root / "own"]


class IconProvider(QQuickImageProvider):
    """Rasterises the app's SVG icons at whole device pixels, tinted.

    ``requestImage`` may run on QML's image-loading thread (an Image with
    ``asynchronous: true``), so the cache and the renderers are behind a lock.
    """

    def __init__(self, folders: Iterable[Path], cache_size: int = CACHE_SIZE):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._folders = [Path(f) for f in folders]
        self._cache_size = cache_size
        self._images: "OrderedDict[tuple, QImage]" = OrderedDict()
        self._renderers = {}
        self._missing = set()
        self._lock = threading.Lock()

    def find(self, name: str) -> Optional[Path]:
        """The SVG file of icon ``name``, or None."""
        if not ICON_NAME.match(name):
            return None
        for folder in self._folders:
            path = folder / f"{name}.svg"
            if path.is_file():
                return path
        return None

    def cached_count(self) -> int:
        with self._lock:
            return len(self._images)

    def requestImage(self, ident: str, size: QSize, requested: QSize) -> QImage:  # noqa: N802 (Qt)
        name, _, query = ident.partition("?")
        q = parse_qs(query)
        try:
            px = min(MAX_DEVICE_PX, max(1, int(q.get("s", ["24"])[0])))
            ratio = max(0.1, float(q.get("d", ["1"])[0]))
        except ValueError:
            px, ratio = 24, 1.0
        color = q.get("c", ["#000000"])[0]
        key = (name, px, color, ratio)
        with self._lock:
            image = self._images.get(key)
            if image is not None:
                self._images.move_to_end(key)
            else:
                image = self._render(name, px, color, ratio)
                self._images[key] = image
                while len(self._images) > self._cache_size:
                    self._images.popitem(last=False)
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image

    def _render(self, name: str, px: int, color: str, ratio: float) -> QImage:
        image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        renderer = self._renderer(name)
        if renderer is not None:
            tint = QColor(color)
            if not tint.isValid():
                logger.warning("Icon %s: %r is not a colour", name, color)
                tint = QColor("#000000")
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            renderer.render(painter, QRectF(0, 0, px, px))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), tint)
            painter.end()
        # Tagged after painting: px device pixels are px / ratio logical, the
        # item's exact size. A QPainter on a tagged image works in logical
        # pixels, so tagging first drew the SVG `ratio` times too big and cut
        # it at the right and bottom edges (at 1.25, 2.0, ...).
        image.setDevicePixelRatio(ratio)
        return image

    def _renderer(self, name: str) -> Optional[QSvgRenderer]:
        name = ALIASES.get(name, name)
        renderer = self._renderers.get(name)
        if renderer is None and name not in self._missing:
            path = self.find(name)
            renderer = QSvgRenderer(str(path)) if path is not None else None
            if renderer is None or not renderer.isValid():
                # Logged once; the icon draws as nothing (QML gets an empty image).
                logger.warning("No icon named %r in %s", name, [str(f) for f in self._folders])
                self._missing.add(name)
                return None
            self._renderers[name] = renderer
        return renderer
