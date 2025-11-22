"""Configuration persistence service."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from models.config import Config
from exceptions import ConfigurationError
from services.appdata_service import AppDataService
from constants import CONFIG_VERSION


class ConfigService:
    """Manages application configuration loading and saving.

    Handles JSON serialization/deserialization and provides type-safe access.
    """

    def __init__(self, appdata_service: AppDataService):
        self._appdata_service = appdata_service
        self._config: Optional[Config] = None
        self._config_file_path: Path = appdata_service.get_config_file_path()
        self._logger = logging.getLogger(__name__)

    def load_config(self) -> Config:
        """Load configuration from file.

        Returns:
            Config object with loaded or default values

        Raises:
            ConfigurationError: If config file is corrupted
        """
        if self._config is not None:
            return self._config

        try:
            if self._config_file_path.exists():
                self._logger.info(f"Loading configuration from {self._config_file_path}")
                with open(self._config_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if migration is needed
                config_version = data.get("version", 1)
                if config_version < CONFIG_VERSION:
                    self._logger.info(f"Migrating config from version {config_version} to {CONFIG_VERSION}")
                    data = self._migrate_config(data, config_version)

                self._config = Config.from_dict(data)
                self._logger.debug(f"Configuration loaded successfully")

                # Save if migration occurred
                if config_version < CONFIG_VERSION:
                    self._logger.info("Saving migrated configuration")
                    self.save_config()
            else:
                self._logger.info("No configuration file found, using defaults")
                self._config = Config()
                # Save the default config
                self.save_config()

            # Validate the config
            self._config.validate()

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse configuration file: {e}")
            raise ConfigurationError(f"Configuration file is corrupted: {e}")
        except Exception as e:
            self._logger.error(f"Error loading configuration: {e}")
            # Fall back to defaults on any error
            self._config = Config()

        return self._config

    def save_config(self, config: Optional[Config] = None) -> None:
        """Save configuration to file.

        Args:
            config: Config object to save (uses current config if None)

        Raises:
            ConfigurationError: If save operation fails
        """
        if config is not None:
            self._config = config

        if self._config is None:
            raise ConfigurationError("No configuration to save")

        try:
            # Validate before saving
            self._config.validate()

            self._logger.debug(f"Saving configuration to {self._config_file_path}")

            # Ensure directory exists
            self._config_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file with pretty formatting
            with open(self._config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)

            self._logger.debug("Configuration saved successfully")

        except Exception as e:
            self._logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key.

        Args:
            key: Configuration key (attribute name)
            default: Default value if key doesn't exist

        Returns:
            Configuration value or default
        """
        if self._config is None:
            self.load_config()

        return getattr(self._config, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key (attribute name)
            value: New value

        Raises:
            ConfigurationError: If key doesn't exist or value is invalid
        """
        if self._config is None:
            self.load_config()

        if not hasattr(self._config, key):
            raise ConfigurationError(f"Unknown configuration key: {key}")

        setattr(self._config, key, value)
        self._logger.debug(f"Configuration updated: {key} = {value}")

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._logger.info("Resetting configuration to defaults")
        self._config = Config()
        self.save_config()

    @property
    def config(self) -> Config:
        """Get the current configuration object.

        Returns:
            Config object (loads if not already loaded)
        """
        if self._config is None:
            self.load_config()
        return self._config

    @property
    def config_file_path(self) -> Path:
        """Get the configuration file path."""
        return self._config_file_path

    def _migrate_config(self, data: dict, from_version: int) -> dict:
        """Migrate configuration from an older version to the current version.

        Args:
            data: Configuration data dictionary
            from_version: Version to migrate from

        Returns:
            Migrated configuration data
        """
        # Add migrations here when config structure changes
        # Example:
        # if from_version < 2:
        #     data["new_field"] = "default_value"
        # if from_version < 3:
        #     data["renamed_field"] = data.pop("old_field_name")

        # Ensure version is set to current
        data["version"] = CONFIG_VERSION

        return data
