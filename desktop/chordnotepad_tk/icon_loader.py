"""PNG icon loading with caching for the toolbar.

PhotoImage references must outlive the widget that displays them, otherwise
Tk drops the image. The loader caches by (path, size, tint) so each unique
variant is decoded once and held for the lifetime of the loader instance.
"""

import logging
import os
from typing import Dict, Optional, Tuple

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

Color = Tuple[int, int, int]


class IconLoader:
    """Load, recolor, and cache PNG icons resolved through a ResourceService."""

    def __init__(self, resource_service) -> None:
        self._resource_service = resource_service
        self._cache: Dict[Tuple[str, int, Optional[Color]], ImageTk.PhotoImage] = {}

    def load(
        self,
        relative_path: str,
        size: int = 22,
        tint: Optional[Color] = None,
    ) -> Optional[ImageTk.PhotoImage]:
        """Return a cached PhotoImage at the given pixel size, or None if missing.

        Args:
            relative_path: Path resolved via ResourceService.
            size: Target square size in pixels.
            tint: If given, recolor the icon to this RGB while preserving the
                original alpha mask. Intended for solid (fill) silhouettes.
        """
        cache_key = (relative_path, size, tint)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        path = self._resource_service.get_resource_path(relative_path)
        if not os.path.exists(path):
            logger.warning(f"Icon not found: {path}")
            return None

        try:
            img = Image.open(path).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            if tint is not None:
                img = self._tint(img, tint)
            photo = ImageTk.PhotoImage(img)
        except Exception as e:
            logger.warning(f"Failed to load icon {path}: {e}")
            return None

        self._cache[cache_key] = photo
        return photo

    @staticmethod
    def _tint(img: Image.Image, color: Color) -> Image.Image:
        """Replace every pixel's RGB with `color`, keep the source alpha.

        Works well for solid silhouette icons (Phosphor's fill variants).
        """
        _, _, _, alpha = img.split()
        solid = Image.new("RGBA", img.size, color + (0,))
        solid.putalpha(alpha)
        return solid
