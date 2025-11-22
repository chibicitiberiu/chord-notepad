"""File I/O operations service."""

import logging
import os
from pathlib import Path
from typing import List, Optional

from exceptions import FileOperationError
from services.config_service import ConfigService


class FileService:
    """Handles file I/O operations and recent files management."""

    def __init__(self, config_service: ConfigService):
        self._config = config_service
        self._logger = logging.getLogger(__name__)

    def open_file(self, path: Path) -> str:
        """Open and read a file.

        Args:
            path: Path to file to open

        Returns:
            File contents as string

        Raises:
            FileOperationError: If file cannot be read
        """
        try:
            self._logger.info(f"Opening file: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Add to recent files
            self.add_recent_file(path)

            self._logger.debug(f"File opened successfully: {len(content)} characters")
            return content

        except FileNotFoundError:
            self._logger.error(f"File not found: {path}")
            raise FileOperationError(f"File not found: {path}")
        except UnicodeDecodeError as e:
            self._logger.error(f"File encoding error: {e}")
            raise FileOperationError(f"Cannot read file (encoding issue): {path}")
        except Exception as e:
            self._logger.error(f"Error reading file: {e}", exc_info=True)
            raise FileOperationError(f"Failed to read file: {e}")

    def save_file(self, path: Path, content: str) -> bool:
        """Save content to a file.

        Args:
            path: Path to save file to
            content: Content to write

        Returns:
            True if saved successfully

        Raises:
            FileOperationError: If file cannot be written
        """
        try:
            self._logger.info(f"Saving file: {path}")

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Add to recent files
            self.add_recent_file(path)

            self._logger.debug(f"File saved successfully: {len(content)} characters")
            return True

        except PermissionError:
            self._logger.error(f"Permission denied: {path}")
            raise FileOperationError(f"Permission denied: {path}")
        except Exception as e:
            self._logger.error(f"Error writing file: {e}", exc_info=True)
            raise FileOperationError(f"Failed to write file: {e}")

    def get_recent_files(self) -> List[Path]:
        """Get list of recently opened files.

        Returns:
            List of file paths (most recent first)
        """
        recent_files_str = self._config.get("recent_files", [])
        recent_files = [Path(p) for p in recent_files_str if p]

        # Filter out files that no longer exist
        existing_files = [f for f in recent_files if f.exists()]

        # Update config if list changed (removed non-existent files)
        if len(existing_files) != len(recent_files):
            self._config.set("recent_files", [str(f) for f in existing_files])

        return existing_files

    def add_recent_file(self, path: Path) -> None:
        """Add a file to the recent files list.

        Args:
            path: File path to add
        """
        recent_files = self.get_recent_files()
        path_str = str(path.resolve())

        # Remove if already in list
        recent_files_str = [str(f) for f in recent_files if str(f) != path_str]

        # Add to front of list
        recent_files_str.insert(0, path_str)

        # Limit to max recent files
        max_recent = self._config.get("max_recent_files", 10)
        recent_files_str = recent_files_str[:max_recent]

        # Save to config
        self._config.set("recent_files", recent_files_str)
        self._logger.debug(f"Added to recent files: {path}")

    def clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self._config.set("recent_files", [])
        self._logger.info("Cleared recent files list")

    def file_exists(self, path: Path) -> bool:
        """Check if a file exists.

        Args:
            path: File path to check

        Returns:
            True if file exists
        """
        return path.exists() and path.is_file()

    def get_file_info(self, path: Path) -> dict:
        """Get information about a file.

        Args:
            path: File path

        Returns:
            Dictionary with file information (size, modified time, etc.)
        """
        if not self.file_exists(path):
            return {}

        stat = path.stat()
        return {
            "path": str(path),
            "name": path.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_readable": os.access(path, os.R_OK),
            "is_writable": os.access(path, os.W_OK),
        }
