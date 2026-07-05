"""Configuration persistence service."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from models.config import Config
from exceptions import ConfigurationError
from services.appdata_service import AppDataService
from constants import CONFIG_VERSION


#: Fretboard weight keys stored as positive magnitudes under the v1 (pre-signed)
#: convention that must be negated when migrating to the v2 signed convention.
_FRETBOARD_NEGATE_KEYS = (
    'span_penalty', 'position_penalty', 'fretted_finger_penalty',
    'barre_penalty', 'interior_mute_penalty', 'movement_penalty',
)

#: Flat ensemble weight keys negated for the same reason. ``movement`` may be a
#: scalar or a per-voice list; both are negated element-wise.
_ENSEMBLE_NEGATE_FLAT_KEYS = (
    'movement', 'bass_movement', 'leap_penalty', 'octave_leap_penalty',
    'tritone_leap_penalty', 'parallel_perfect_penalty',
    'double_leading_tone_penalty', 'range_comfort_penalty',
    'unison_penalty', 'upper_spacing_penalty',
)


#: v2 default for ``interior_mute_penalty`` and the recalibrated v3 default.
#: The v3 migration bumps only voicings still carrying the old default, so a
#: user who deliberately tuned the weight keeps their value.
_INTERIOR_MUTE_V2_DEFAULT = -2.0
_INTERIOR_MUTE_V3_DEFAULT = -4.0


def _is_number(value: Any) -> bool:
    """True for int/float, excluding bool (a bool is an int subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _bump_default_interior_mute(data: dict) -> None:
    """Move fretboard voicings from the v2 to the v3 ``interior_mute_penalty`` default, in-place.

    Saved voicings persist their full weight dict, so the recalibrated default
    (-2.0 -> -4.0, which makes barre shapes beat contorted interior-mute shapes)
    would never reach existing profiles without this. Only an exact old-default
    value is bumped; any other value is a deliberate user setting and stays.
    """
    voicings = data.get('voicings')
    if not isinstance(voicings, dict):
        return

    for entry in voicings.values():
        if not isinstance(entry, dict) or entry.get('model') != 'fretboard':
            continue
        weights = entry.get('weights')
        if not isinstance(weights, dict):
            continue
        value = weights.get('interior_mute_penalty')
        if _is_number(value) and value == _INTERIOR_MUTE_V2_DEFAULT:
            weights['interior_mute_penalty'] = _INTERIOR_MUTE_V3_DEFAULT


def _negate_signed_weights(data: dict) -> None:
    """Negate v1 positive-magnitude penalty weights in-place for the v2 convention.

    v1 stored voicing penalties as positive magnitudes that the engine
    subtracted; v2 stores every weight as a signed contribution the engine
    adds. This flips the sign of each overridden penalty key so a migrated
    config produces byte-identical voicings. Only keys the user actually
    overrode are touched; missing keys inherit the new negative defaults.
    Bonus keys, ``doubling`` and ``inversion`` (already signed) are left alone.
    """
    voicings = data.get('voicings')
    if not isinstance(voicings, dict):
        return

    for entry in voicings.values():
        if not isinstance(entry, dict):
            continue
        weights = entry.get('weights')
        if not isinstance(weights, dict):
            continue
        model = entry.get('model')

        if model == 'fretboard':
            for key in _FRETBOARD_NEGATE_KEYS:
                if key in weights and _is_number(weights[key]):
                    weights[key] = -weights[key]

        elif model == 'ensemble':
            for key in _ENSEMBLE_NEGATE_FLAT_KEYS:
                if key not in weights:
                    continue
                value = weights[key]
                if isinstance(value, list):
                    weights[key] = [-v if _is_number(v) else v for v in value]
                elif _is_number(value):
                    weights[key] = -value
            omit = weights.get('omit')
            if isinstance(omit, dict):
                for subkey, subval in omit.items():
                    if _is_number(subval):
                        omit[subkey] = -subval


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
        # v1 -> v2: voicing weights moved from positive-magnitude penalties
        # (subtracted by the engine) to signed contributions (added). Negate
        # each overridden penalty key so migrated voicings stay identical.
        if from_version < 2:
            _negate_signed_weights(data)

        # v2 -> v3: interior_mute_penalty's default was recalibrated from -2.0
        # to -4.0 (interior mutes were undervalued, letting contorted shapes
        # beat plain barre chords). Voicings still on the old default follow it;
        # user-tuned values are left alone. Runs after the sign flip so a v1
        # config's +2.0 (the old positive-magnitude default) chains to -4.0.
        if from_version < 3:
            _bump_default_interior_mute(data)

        # Ensure version is set to current
        data["version"] = CONFIG_VERSION

        return data
