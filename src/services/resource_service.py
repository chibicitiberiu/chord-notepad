"""Resource path resolution service."""

import os
from pathlib import Path

from app_paths import AppPaths


class ResourceService:
    """Resolves the paths of bundled files (icons, images, the help).

    The front end works out where they are (``AppPaths``: a checkout, a
    PyInstaller bundle, the Flatpak or the snap); this only joins paths.
    """

    def __init__(self, paths: AppPaths):
        """Create the service.

        Args:
            paths: Where the app's files are; its ``root`` is the folder the
                relative paths below start from.
        """
        if paths.root is None:
            raise ValueError("ResourceService needs AppPaths with a root folder")
        self._paths = paths
        self._base_path: Path = paths.root

    @property
    def paths(self) -> AppPaths:
        """Where the app's files are."""
        return self._paths

    def get_resource_path(self, relative_path: str) -> str:
        """Get absolute path to resource.

        Args:
            relative_path: Path relative to the app root (e.g., 'resources/icon-32.png')

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
