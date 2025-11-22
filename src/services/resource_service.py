"""Resource path resolution service."""

import sys
import os
from pathlib import Path


class ResourceService:
    """Manages resource path resolution for development and PyInstaller environments.

    Provides a centralized way to locate resources (icons, assets, etc.) that works
    both in development mode and when packaged with PyInstaller.
    """

    def __init__(self):
        self._base_path: Path = self._determine_base_path()

    def _determine_base_path(self) -> Path:
        """Determine the base path for resources.

        Returns:
            Path to the base directory containing resources.
            - In PyInstaller mode: sys._MEIPASS
            - In development mode: project root directory
        """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = Path(sys._MEIPASS)
        except AttributeError:
            # Running in development mode
            # Navigate from src/services/resource_service.py to project root
            base_path = Path(__file__).parent.parent.parent

        return base_path

    def get_resource_path(self, relative_path: str) -> str:
        """Get absolute path to resource.

        Args:
            relative_path: Path relative to project root (e.g., 'resources/icon-32.png')

        Returns:
            Absolute path to the resource as a string
        """
        return os.path.join(self._base_path, relative_path)

    def get_base_path(self) -> Path:
        """Get the base path for resources.

        Returns:
            Path to the base directory
        """
        return self._base_path

    def is_pyinstaller_mode(self) -> bool:
        """Check if running under PyInstaller.

        Returns:
            True if running under PyInstaller, False otherwise
        """
        return hasattr(sys, '_MEIPASS')
