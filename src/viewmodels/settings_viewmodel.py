"""View model backing the Settings window.

Holds a mutable *working copy* of the settings the user is editing (scalar
options plus the ``voicings`` registry) that is only pushed into the real
:class:`~services.config_service.ConfigService` when :meth:`SettingsViewModel.commit`
is called. This keeps the dialog fully headless-testable: every decision the
UI makes -- unique naming, rename chains, load sources, validation, and the
final commit/flag computation -- lives here rather than in a Tkinter widget.

Terminology: a *voicing* is a named configuration (a *model* plus that
model's parameters); a *model* is the rendering engine, one of ``'fretboard'``,
``'ensemble'`` or ``'piano'``.
"""

import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from models.ensemble_spec import BUILTIN_ENSEMBLES, EnsembleSpec
from models.fretboard_spec import BUILTIN_FRETBOARDS, FretboardSpec
from models.piano_spec import DEFAULT_PIANO, PianoSpec
from services.config_service import ConfigService

logger = logging.getLogger(__name__)


#: Standard six-string guitar tuning (EADGBE), lowest string first, as MIDI
#: note numbers. Used as the default parameters for a freshly added voicing.
_STANDARD_GUITAR_TUNING = [40, 45, 50, 55, 59, 64]

#: Scalar config attributes mirrored on the view model, grouped by the change
#: flag they feed on :meth:`SettingsViewModel.commit`. See ``SettingsChanges``.
_FONT_FIELDS = ('font_family', 'font_size')
_GENERAL_FIELDS = (
    'notation', 'key', 'show_quick_start_on_startup', 'max_recent_files',
    'log_level', 'bpm', 'time_signature_beats', 'time_signature_unit',
)
_AUDIO_FIELDS = ('soundfont_path', 'audio_driver')
_GUITAR_FIELDS = ('allow_capo',)
_ALL_SCALAR_FIELDS = _FONT_FIELDS + _GENERAL_FIELDS + _AUDIO_FIELDS + _GUITAR_FIELDS


@dataclass
class SettingsChanges:
    """What changed when settings were committed, so the caller can react.

    Each flag is set only when at least one field in its group actually
    differs from the config the view model was constructed against.
    ``guitar_changed`` covers the guitar/fretboard playback flags (currently
    just ``allow_capo``), which the chord-sheet strip reacts to by recomputing
    its capo suggestion. ``new_active_voicing`` is set only when the selected
    voicing string had to be rewritten because the voicing it pointed at was
    renamed or deleted.
    """

    font_changed: bool = False
    general_changed: bool = False
    audio_changed: bool = False
    guitar_changed: bool = False
    voicings_changed: bool = False
    new_active_voicing: Optional[str] = None


class SettingsViewModel:
    """Editable working copy of the application settings for the Settings window."""

    def __init__(self, config_service: ConfigService) -> None:
        """Snapshot the current config into an editable working copy.

        Args:
            config_service: The service whose ``config`` is read now and
                written back on :meth:`commit`.
        """
        self._config_service = config_service
        config = config_service.config

        # Scalar working copy.
        self.font_family: str = config.font_family
        self.font_size: int = config.font_size
        self.notation: str = config.notation
        self.key: str = config.key
        self.show_quick_start_on_startup: bool = config.show_quick_start_on_startup
        self.max_recent_files: int = config.max_recent_files
        self.log_level: str = config.log_level
        self.bpm: int = config.bpm
        self.time_signature_beats: int = config.time_signature_beats
        self.time_signature_unit: int = config.time_signature_unit
        self.soundfont_path: Optional[str] = config.soundfont_path
        self.audio_driver: Optional[str] = config.audio_driver
        self.allow_capo: bool = config.allow_capo

        # Deep working copy of the voicings registry.
        self._working_voicings: Dict[str, dict] = copy.deepcopy(config.voicings)

        # Snapshots for change detection at commit time.
        self._orig_scalars: Dict[str, Any] = {
            field: getattr(config, field) for field in _ALL_SCALAR_FIELDS
        }
        self._orig_voicings: Dict[str, dict] = copy.deepcopy(config.voicings)

        # Rename bookkeeping: maps an *original* config voicing name to its
        # current (possibly repeatedly renamed) name, so the selected voicing
        # string can be followed through a rename chain at commit.
        self._original_names = set(config.voicings.keys())
        self._rename_map: Dict[str, str] = {}

    # -- Voicings registry ---------------------------------------------------

    def get_voicings(self) -> Dict[str, dict]:
        """Return the live working copy of the voicings registry.

        The returned mapping is the view model's own dict: reads reflect
        adds/removes/renames immediately, and writes must go through
        :meth:`set_voicing_data` (not by mutating this dict).
        """
        return self._working_voicings

    def add_voicing(self) -> str:
        """Add a new fretboard voicing with a unique name and standard defaults.

        The new entry uses the fretboard model with standard six-string guitar
        tuning (EADGBE); every other parameter falls back to the engine
        defaults.

        Returns:
            The unique name assigned to the new voicing.
        """
        name = self._unique_name("New voicing")
        self._working_voicings[name] = {
            'model': 'fretboard',
            'tuning': list(_STANDARD_GUITAR_TUNING),
        }
        return name

    def remove_voicing(self, name: str) -> None:
        """Remove a voicing from the working copy (no-op if it is absent)."""
        self._working_voicings.pop(name, None)

    def rename_voicing(self, old: str, new: str) -> None:
        """Rename a working-copy voicing, tracking the change for commit.

        Args:
            old: The current name of the voicing to rename.
            new: The requested new name.

        Raises:
            ValueError: if ``new`` is empty/whitespace, or already names a
                different voicing, or if ``old`` does not exist.
        """
        new = (new or '').strip()
        if not new:
            raise ValueError("Voicing name cannot be empty.")
        if old not in self._working_voicings:
            raise ValueError(f"No voicing named '{old}'.")
        if new == old:
            return
        if new in self._working_voicings:
            raise ValueError(f"A voicing named '{new}' already exists.")

        # Preserve insertion order by rebuilding the dict with the key renamed.
        self._working_voicings = {
            (new if key == old else key): value
            for key, value in self._working_voicings.items()
        }

        # Update rename tracking so the selected voicing can be followed.
        reverse = {current: original for original, current in self._rename_map.items()}
        if old in reverse:
            self._rename_map[reverse[old]] = new
        elif old in self._original_names:
            self._rename_map[old] = new
        # else: `old` was an added-this-session voicing; nothing to track.

    def set_voicing_data(self, name: str, data: dict) -> None:
        """Replace a voicing's entry wholesale (``data`` must include ``'model'``)."""
        self._working_voicings[name] = data

    def get_load_sources(self) -> List[Tuple[str, dict]]:
        """Return ``(display_label, params)`` pairs for the "Load config" menu.

        Order is stable: every built-in fretboard, then every built-in
        ensemble, then a single piano entry, then the current custom voicings
        sorted by name. Each ``params`` dict includes its ``'model'`` and is a
        complete parameter set ready to load into the editor form.
        """
        sources: List[Tuple[str, dict]] = []

        for spec in BUILTIN_FRETBOARDS.values():
            sources.append((spec.label, {'model': 'fretboard', **spec.to_dict()}))
        for spec in BUILTIN_ENSEMBLES.values():
            sources.append((spec.label, {'model': 'ensemble', **spec.to_dict()}))
        sources.append(('Piano (default)', {'model': 'piano', **DEFAULT_PIANO.to_dict()}))

        for name in sorted(self._working_voicings):
            sources.append((name, copy.deepcopy(self._working_voicings[name])))

        return sources

    def validate_voicing(self, name: str) -> Optional[str]:
        """Validate one working voicing; return an error message, or ``None`` if valid.

        A ``'fretboard'``/``'ensemble'``/``'piano'`` model is parsed through
        its spec's ``from_dict`` and any :class:`~exceptions.ConfigurationError`
        message is returned verbatim. An unknown model returns a descriptive
        message.
        """
        data = self._working_voicings.get(name)
        if data is None:
            return f"No voicing named '{name}'."
        model = data.get('model')
        try:
            if model == 'fretboard':
                FretboardSpec.from_dict(name, data)
            elif model == 'ensemble':
                EnsembleSpec.from_dict(name, data)
            elif model == 'piano':
                PianoSpec.from_dict(name, data)
            else:
                return f"Unknown voicing model: {model!r}"
        except Exception as exc:  # noqa: BLE001 - surface any parse failure as text
            return str(exc)
        return None

    def validate_all(self) -> List[Tuple[str, str]]:
        """Return ``(name, error_message)`` for every invalid working voicing."""
        errors: List[Tuple[str, str]] = []
        for name in self._working_voicings:
            message = self.validate_voicing(name)
            if message is not None:
                errors.append((name, message))
        return errors

    # -- Commit --------------------------------------------------------------

    def commit(self) -> SettingsChanges:
        """Write the working copy into the config, save it, and report changes.

        Scalars and the voicings registry are pushed into
        ``config_service.config``. The selected ``voicing`` string is fixed up
        if it pointed at a renamed voicing (rewritten to the new name, even
        through a rename chain) or a deleted one (reset to ``"piano"``); either
        case is reported via ``new_active_voicing``. Finally the config is
        saved. Intended to be called once.
        """
        config = self._config_service.config

        changes = SettingsChanges()
        changes.font_changed = self._group_changed(_FONT_FIELDS)
        changes.general_changed = self._group_changed(_GENERAL_FIELDS)
        changes.audio_changed = self._group_changed(_AUDIO_FIELDS)
        changes.guitar_changed = self._group_changed(_GUITAR_FIELDS)

        # Push scalars.
        for field in _ALL_SCALAR_FIELDS:
            setattr(config, field, getattr(self, field))

        # Push voicings registry.
        config.voicings = copy.deepcopy(self._working_voicings)

        # Fix up the selected voicing pointer if it was renamed/deleted.
        new_active = self._resolve_active_voicing(config.voicing)
        if new_active is not None:
            config.voicing = new_active
            changes.new_active_voicing = new_active

        changes.voicings_changed = (
            self._working_voicings != self._orig_voicings
            or changes.new_active_voicing is not None
        )

        self._config_service.save_config()
        return changes

    # -- Internal helpers ----------------------------------------------------

    def _group_changed(self, fields: Tuple[str, ...]) -> bool:
        """True if any working scalar in ``fields`` differs from the original snapshot."""
        return any(getattr(self, field) != self._orig_scalars[field] for field in fields)

    def _resolve_active_voicing(self, current: str) -> Optional[str]:
        """Compute a rewritten ``voicing`` string, or ``None`` if it stays put.

        Only ``"voicing:<name>"`` strings are subject to rewriting; built-in
        prefixes (``guitar:``/``ensemble:``) and plain ``"piano"`` are left
        alone. A renamed target follows the rename chain; a deleted target
        (renamed-then-removed, or removed outright) resets to ``"piano"``.
        """
        if not current.startswith("voicing:"):
            return None
        name = current.split(":", 1)[1]

        target = self._rename_map.get(name, name)
        if target in self._working_voicings:
            new_string = f"voicing:{target}"
            return new_string if new_string != current else None
        # Target no longer exists (deleted, possibly after a rename).
        return "piano"

    def _unique_name(self, base: str) -> str:
        """Return ``base``, or ``base 2``/``base 3``/... if already taken."""
        if base not in self._working_voicings:
            return base
        index = 2
        while f"{base} {index}" in self._working_voicings:
            index += 1
        return f"{base} {index}"
