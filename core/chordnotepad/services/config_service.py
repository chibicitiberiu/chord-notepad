"""Configuration persistence service."""

import copy
import datetime
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from chordnotepad.models.config import Config, config_version
from chordnotepad.models.voicing_versions import (
    ENSEMBLE_NEGATED_FLAT_KEYS, FRETBOARD_NEGATED_KEYS, migrate_voicing,
)
from chordnotepad.exceptions import ConfigurationError
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.constants import CONFIG_VERSION


#: Fretboard weight keys stored as positive magnitudes under the v1 (pre-signed)
#: convention that must be negated when migrating to the v2 signed convention.
#: (The voicing migration 0->1 repairs voicings this flip hit by mistake, so
#: both share the list.)
_FRETBOARD_NEGATE_KEYS = FRETBOARD_NEGATED_KEYS

#: Flat ensemble weight keys negated for the same reason. ``movement`` may be a
#: scalar or a per-voice list; both are negated element-wise.
_ENSEMBLE_NEGATE_FLAT_KEYS = ENSEMBLE_NEGATED_FLAT_KEYS


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


def _move_ensemble_omission_defaults(data: dict) -> None:
    """Move ensemble voicings from the old to the ensemble ``omit`` defaults, in-place.

    Ensembles used to share the piano's omission weights, which drop the root
    first; they now drop the fifth first (``ENSEMBLE_OMIT_WEIGHTS``). Saved
    voicings persist their weights, so an ``omit`` mapping whose every value
    is still the old default follows the new defaults. One with any value
    changed was tuned by the user and is left alone as a whole.
    """
    from chordnotepad.models.ensemble_spec import ENSEMBLE_OMIT_WEIGHTS, PREVIOUS_ENSEMBLE_OMIT_WEIGHTS

    voicings = data.get('voicings')
    if not isinstance(voicings, dict):
        return

    for entry in voicings.values():
        if not isinstance(entry, dict) or entry.get('model') != 'ensemble':
            continue
        weights = entry.get('weights')
        omit = weights.get('omit') if isinstance(weights, dict) else None
        if not isinstance(omit, dict) or not omit:
            continue
        if all(_is_number(value) and PREVIOUS_ENSEMBLE_OMIT_WEIGHTS.get(role) == value
               for role, value in omit.items()):
            for role in omit:
                omit[role] = ENSEMBLE_OMIT_WEIGHTS[role]


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


def effective_version(data: dict, version: int) -> int:
    """The version a saved config's migrations start from.

    Every release from 0.3.0 to 0.5.4 wrote a new config as version 1 although
    its voicings were already signed, so the v1 sign flip turned the penalties
    of voicings made before the next start into rewards. v0.1 and v0.2 never
    wrote a ``voicings`` key (their tunings are under ``custom_tunings``), so
    a file below version 3 that has a ``voicings`` mapping was written signed:
    it is read as version 3, which skips the sign flip and the interior-mute
    bump (made for unsigned and v2 values) but still moves exact old ``omit``
    defaults. A genuine v1 file keeps its version.
    """
    if version < 3 and isinstance(data.get("voicings"), dict):
        return 3
    return version


def backup_name(path: Path, label: str, now: Optional[datetime.datetime] = None) -> str:
    """The name of a copy of ``path`` made before it is changed for good:
    ``settings.json.<label>-<YYYYmmdd-HHMMSS>``."""
    stamp = (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{path.name}.{label}-{stamp}"


def _free_path(path: Path, name: str) -> Path:
    """``name`` next to ``path``, or ``name-1``, ``name-2``... if it is taken:
    a backup never replaces a file already there."""
    candidate = path.with_name(name)
    count = 0
    while candidate.exists():
        count += 1
        candidate = path.with_name(f"{name}-{count}")
    return candidate


class ConfigService:
    """Manages application configuration loading and saving.

    Handles JSON serialization/deserialization and provides type-safe access.

    The file is never lost to an upgrade or a damaged value:

    * a load that migrates the file (the config, or any voicing:
      ``models.voicing_versions``), or that had to replace an unusable value
      with its default, makes the next save first copy the file to
      ``settings.json.bak-v<old version>-<timestamp>`` (once per run; if the
      copy can't be made, nothing is written);
    * a file that can't be read at all (not JSON, not an object, or failing
      to load) is renamed to ``settings.json.corrupt-<timestamp>`` and the app
      starts on the defaults, with :attr:`load_notice` saying so;
    * a save that fails at load keeps the loaded config in memory.

    Backups are never deleted.
    """

    def __init__(self, appdata_service: AppDataService):
        self._appdata_service = appdata_service
        self._config: Optional[Config] = None
        self._config_file_path: Path = appdata_service.get_config_file_path()
        self._logger = logging.getLogger(__name__)
        # The label of the backup the next save makes first ("bak-v3"), or
        # None when the file on disk needs none.
        self._backup_label: Optional[str] = None
        #: Set when the settings file couldn't be read and the app started on
        #: the defaults: what to tell the user, once (see take_load_notice).
        self.load_notice: Optional[str] = None

    def load_config(self) -> Config:
        """Load configuration from file.

        A missing file gives the defaults (saved at once). A file that can't
        be read is set aside (see the class docstring) and also gives the
        defaults; this never raises.

        Returns:
            Config object with loaded or default values
        """
        if self._config is not None:
            return self._config

        if not self._config_file_path.exists():
            self._logger.info("No configuration file found, using defaults")
            self._config = Config()
            self._save_at_load("the default configuration")
            return self._config

        self._logger.info(f"Loading configuration from {self._config_file_path}")
        try:
            with open(self._config_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"the settings are a {type(data).__name__}, not an object")
            version = config_version(data.get("version", 1))
            start = effective_version(data, version)
            migrated = version < CONFIG_VERSION
            if migrated:
                self._logger.info(f"Migrating config from version {version} to {CONFIG_VERSION}"
                                  + (f" (read as version {start})" if start != version else ""))
                data = self._migrate_config(data, start)
            config = Config.from_dict(data)
        except Exception as e:  # noqa: BLE001 - any failure to read keeps the file aside
            self._logger.error(f"Could not read the configuration file: {e}")
            self._set_aside_unreadable()
            self._config = Config()
            return self._config

        self._config = config
        self._logger.debug("Configuration loaded successfully")
        voicings_migrated = self._migrate_voicings(config)
        if migrated or voicings_migrated or config.needs_backup:
            self._backup_label = f"bak-v{version}"
        if migrated or voicings_migrated:
            self._save_at_load("the migrated configuration")
        try:
            self._config.validate()
        except ValueError as e:
            # from_dict checks every value validate() looks at, so this is a
            # bug; the config is kept, and save_config (which validates)
            # leaves the file as it is.
            self._logger.error(f"Loaded configuration does not validate: {e}")
        return self._config

    def _migrate_voicings(self, config: Config) -> bool:
        """Run the voicing migrations on every saved voicing (legacy entries
        are voicings by now); True if any changed. A voicing a migration
        fails on is logged and kept exactly as it was."""
        changed = False
        for name, entry in config.voicings.items():
            before = copy.deepcopy(entry)
            try:
                if migrate_voicing(entry):
                    changed = True
            except Exception as e:  # noqa: BLE001 - never lose a voicing to a migration bug
                self._logger.error(f"Could not migrate voicing {name!r}; kept as it was: {e}")
                entry.clear()
                entry.update(before)
        return changed

    def _save_at_load(self, what: str) -> None:
        """Save during load; a failure (disk full, read-only) is logged and
        the config stays in memory, never reset."""
        self._logger.info(f"Saving {what}")
        try:
            self.save_config()
        except ConfigurationError as e:
            self._logger.error(f"Could not save {what}; keeping it in memory: {e}")

    def _set_aside_unreadable(self) -> None:
        """Rename the unreadable settings file to ``settings.json.corrupt-<ts>``
        and set :attr:`load_notice`. If it can't be renamed, a copy is tried;
        if that fails too, the next save must back it up first (and won't
        write without that backup)."""
        path = self._config_file_path
        target = _free_path(path, backup_name(path, "corrupt"))
        try:
            os.replace(path, target)
        except OSError as e:
            self._logger.error(f"Could not rename {path.name} to {target.name}: {e}")
            try:
                shutil.copyfile(path, target)
            except OSError as e2:
                self._logger.error(f"Could not copy {path.name} to {target.name} either: {e2}")
                self._backup_label = "corrupt"
                self.load_notice = ("Settings couldn't be read. The app started with default "
                                    "settings; the old file was kept as it was.")
                return
            # A copy of the file is kept; the file itself may now be replaced.
        self._logger.warning(f"Kept the unreadable settings file as {target.name}")
        self.load_notice = ("Settings couldn't be read. The app started with default settings; "
                            f"the old file was kept as {target.name}.")

    def take_load_notice(self) -> Optional[str]:
        """:attr:`load_notice`, cleared: the session shows it once."""
        notice, self.load_notice = self.load_notice, None
        return notice

    def _make_backup(self) -> None:
        """Copy the settings file aside before the first write that changes it
        for good (after a migration or a replaced value). Raises
        ConfigurationError, so nothing is written, if the copy fails."""
        if self._backup_label is None:
            return
        path = self._config_file_path
        if path.exists():
            target = _free_path(path, backup_name(path, self._backup_label))
            created = False
            try:
                with open(path, 'rb') as source, open(target, 'xb') as copy:
                    created = True
                    shutil.copyfileobj(source, copy)
                    copy.flush()
                    os.fsync(copy.fileno())
            except OSError as e:
                # A half-made copy is not a backup: remove it (only the file
                # this call created; ``xb`` never opens an existing one).
                if created:
                    try:
                        target.unlink()
                    except OSError:
                        pass
                raise ConfigurationError(
                    f"Could not back up {path.name} before changing it: {e}") from e
            self._logger.info(f"Backed up {path.name} to {target.name}")
        self._backup_label = None

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

            # The file as it was loaded is copied aside before it is first
            # replaced by a migrated or repaired one.
            self._make_backup()

            # Write a temporary file and swap it in, so a crash or a killed
            # process (Android may stop the app any time once it is in the
            # background) never leaves a half-written config behind.
            temp_path = self._config_file_path.with_name(self._config_file_path.name + ".tmp")
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self._config_file_path)
            finally:
                if temp_path.exists():
                    temp_path.unlink()

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
        """Reset configuration to default values; the file is backed up first."""
        self._logger.info("Resetting configuration to defaults")
        old_version = self._config.version if self._config is not None else CONFIG_VERSION
        if self._backup_label is None:
            self._backup_label = f"bak-v{old_version}"
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

        # v3 -> v4: ensembles got their own omission order (the fifth goes
        # first, not the root). Ensembles still on the old omission defaults
        # follow it; tuned ones are left alone. Runs after the sign flip, so
        # a v1 config's positive old defaults chain through.
        if from_version < 4:
            _move_ensemble_omission_defaults(data)

        # Ensure version is set to current
        data["version"] = CONFIG_VERSION

        return data
