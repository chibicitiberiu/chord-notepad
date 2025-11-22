"""Application data directory management service."""

import sys
from pathlib import Path
from typing import Optional

from constants import APP_ID, CONFIG_FILENAME, LOG_FILENAME


class AppDataService:
    """Manages application data directories and paths.

    Provides platform-specific directory resolution for config, logs, and cache.
    """

    def __init__(self):
        self._app_data_dir: Optional[Path] = None
        self._config_dir: Optional[Path] = None
        self._logs_dir: Optional[Path] = None
        self._cache_dir: Optional[Path] = None

    def get_app_data_dir(self) -> Path:
        """Get the main application data directory.

        Returns:
            Path to the application data directory based on platform:
            - Linux: ~/.local/share/chord-notepad
            - macOS: ~/Library/Application Support/ChordNotepad
            - Windows: %APPDATA%/ChordNotepad
        """
        if self._app_data_dir is None:
            if sys.platform == "win32":
                base = Path.home() / "AppData" / "Roaming"
                self._app_data_dir = base / "ChordNotepad"
            elif sys.platform == "darwin":
                base = Path.home() / "Library" / "Application Support"
                self._app_data_dir = base / "ChordNotepad"
            else:  # Linux and other Unix-like systems
                base = Path.home() / ".local" / "share"
                self._app_data_dir = base / APP_ID

        return self._app_data_dir

    def get_config_dir(self) -> Path:
        """Get the configuration directory.

        Returns:
            Path to the config directory based on platform:
            - Linux: ~/.config/chord-notepad
            - macOS: ~/Library/Application Support/ChordNotepad
            - Windows: %APPDATA%/ChordNotepad
        """
        if self._config_dir is None:
            if sys.platform == "win32" or sys.platform == "darwin":
                # On Windows and macOS, config is in the same location as app data
                self._config_dir = self.get_app_data_dir()
            else:  # Linux
                self._config_dir = Path.home() / ".config" / APP_ID

        return self._config_dir

    def get_logs_dir(self) -> Path:
        """Get the logs directory.

        Returns:
            Path: {app_data_dir}/logs
        """
        if self._logs_dir is None:
            self._logs_dir = self.get_app_data_dir() / "logs"

        return self._logs_dir

    def get_cache_dir(self) -> Path:
        """Get the cache directory.

        Returns:
            Path: {app_data_dir}/cache
        """
        if self._cache_dir is None:
            self._cache_dir = self.get_app_data_dir() / "cache"

        return self._cache_dir

    def ensure_directories_exist(self) -> None:
        """Create all necessary directories if they don't exist."""
        directories = [
            self.get_app_data_dir(),
            self.get_config_dir(),
            self.get_logs_dir(),
            self.get_cache_dir(),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_config_file_path(self, filename: str = CONFIG_FILENAME) -> Path:
        """Get the full path to a config file.

        Args:
            filename: Name of the config file (default: settings.json)

        Returns:
            Path: Full path to the config file
        """
        return self.get_config_dir() / filename

    def get_log_file_path(self, filename: str = LOG_FILENAME) -> Path:
        """Get the full path to a log file.

        Args:
            filename: Name of the log file (default: chord-notepad.log)

        Returns:
            Path: Full path to the log file
        """
        return self.get_logs_dir() / filename
