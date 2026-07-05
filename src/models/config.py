"""Application configuration model."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict

from models.ensemble_spec import BUILTIN_ENSEMBLES

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration model with validation."""

    # Version for migration support
    version: int = 1

    # Appearance
    font_family: str = "TkFixedFont"
    font_size: int = 11
    theme: str = "default"

    # Playback
    bpm: int = 120
    bpm_multiplier: float = 1.0  # Speed multiplier applied on top of BPM/directives
    default_octave: int = 4
    bass_octave: int = 3
    time_signature_beats: int = 4  # Beats per measure
    time_signature_unit: int = 4   # Beat unit (e.g., 4 = quarter note)
    voicing: str = "piano"  # Voice leading style: 'piano', 'guitar:<name>', 'ensemble:<name>', or 'voicing:<name>'
    # Registry of named voicing configurations. Each value is
    # {"model": "fretboard" | "ensemble" | "piano", ...model-specific parameters}.
    # Replaces the older custom_tunings/custom_ensembles fields (see from_dict
    # for the one-time migration of those legacy keys).
    voicings: Dict[str, dict] = field(default_factory=dict)
    instrument: int = 0  # MIDI program number (0-127), 0 = Acoustic Grand Piano
    # When true and a fretboard voicing is active, the chord-sheet strip suggests
    # the easiest capo position for the song (advice only; nothing is re-voiced).
    allow_capo: bool = False

    # Notation
    notation: Literal["american", "european"] = "american"
    key: str = "C"  # Default key signature

    # Window
    window_geometry: str = "900x600"
    window_maximized: bool = False

    # Files
    recent_files: List[str] = field(default_factory=list)
    max_recent_files: int = 10

    # Audio
    soundfont_path: Optional[str] = None
    audio_driver: Optional[str] = None

    # Logging
    log_level: str = "INFO"

    # UI/UX
    show_quick_start_on_startup: bool = True  # Show quick start dialog on first launch

    # Chord sheet strip (bottom-docked voiced-chord panel)
    chord_sheet_visible: bool = False  # Whether the chord sheet panel is shown
    chord_sheet_view: str = "keyboard"  # Active renderer id ('keyboard', 'staff', 'fret', 'tab')
    chord_sheet_height: int = 160      # Panel height in pixels (paned-window sash position)

    def validate(self) -> None:
        """Validate configuration values."""
        if not (20 <= self.bpm <= 400):
            raise ValueError(f"BPM must be between 20 and 400, got {self.bpm}")

        if not (0.125 <= self.bpm_multiplier <= 4.0):
            raise ValueError(
                f"BPM multiplier must be between 0.125 and 4.0, got {self.bpm_multiplier}"
            )

        if not (6 <= self.font_size <= 72):
            raise ValueError(f"Font size must be between 6 and 72, got {self.font_size}")

        if self.notation not in ("american", "european"):
            raise ValueError(f"Notation must be 'american' or 'european', got {self.notation}")

        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {self.log_level}")

        if len(self.recent_files) > self.max_recent_files:
            self.recent_files = self.recent_files[:self.max_recent_files]

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "theme": self.theme,
            "bpm": self.bpm,
            "bpm_multiplier": self.bpm_multiplier,
            "default_octave": self.default_octave,
            "bass_octave": self.bass_octave,
            "time_signature_beats": self.time_signature_beats,
            "time_signature_unit": self.time_signature_unit,
            "voicing": self.voicing,
            "voicings": self.voicings,
            "instrument": self.instrument,
            "allow_capo": self.allow_capo,
            "notation": self.notation,
            "key": self.key,
            "window_geometry": self.window_geometry,
            "window_maximized": self.window_maximized,
            "recent_files": self.recent_files,
            "max_recent_files": self.max_recent_files,
            "soundfont_path": self.soundfont_path,
            "audio_driver": self.audio_driver,
            "log_level": self.log_level,
            "show_quick_start_on_startup": self.show_quick_start_on_startup,
            "chord_sheet_visible": self.chord_sheet_visible,
            "chord_sheet_view": self.chord_sheet_view,
            "chord_sheet_height": self.chord_sheet_height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create Config from dictionary.

        Note: Version is extracted but not used in construction here.
        The ConfigService handles version migration before calling this method.

        Migrates the legacy ``custom_tunings``/``custom_ensembles`` keys (if
        present) into the unified ``voicings`` registry: each
        ``custom_tunings[name]`` becomes ``{"model": "fretboard", "tuning": ...}``
        and each ``custom_ensembles[name]`` becomes
        ``{"model": "ensemble", **data}``. On a name collision with an entry
        already in ``voicings``, the ``voicings`` entry wins and a warning is
        logged. The selected ``voicing`` string is also rewritten from
        ``"guitar:<name>"``/``"ensemble:<name>"`` to ``"voicing:<name>"`` when
        it referred to a migrated legacy entry (built-in ensemble names are
        left alone even if shadowed by a same-named custom entry).
        """
        voicings, voicing = cls._migrate_voicings(data)

        return cls(
            version=data.get("version", 1),
            font_family=data.get("font_family", "TkFixedFont"),
            font_size=data.get("font_size", 11),
            theme=data.get("theme", "default"),
            bpm=data.get("bpm", 120),
            bpm_multiplier=data.get("bpm_multiplier", 1.0),
            default_octave=data.get("default_octave", 4),
            bass_octave=data.get("bass_octave", 3),
            time_signature_beats=data.get("time_signature_beats", 4),
            time_signature_unit=data.get("time_signature_unit", 4),
            voicing=voicing,
            voicings=voicings,
            instrument=data.get("instrument", 0),
            allow_capo=data.get("allow_capo", False),
            notation=data.get("notation", "american"),
            key=data.get("key", "C"),
            window_geometry=data.get("window_geometry", "900x600"),
            window_maximized=data.get("window_maximized", False),
            recent_files=data.get("recent_files", []),
            max_recent_files=data.get("max_recent_files", 10),
            soundfont_path=data.get("soundfont_path"),
            audio_driver=data.get("audio_driver"),
            log_level=data.get("log_level", "INFO"),
            show_quick_start_on_startup=data.get("show_quick_start_on_startup", True),
            chord_sheet_visible=data.get("chord_sheet_visible", False),
            chord_sheet_view=data.get("chord_sheet_view", "keyboard"),
            chord_sheet_height=data.get("chord_sheet_height", 160),
        )

    @staticmethod
    def _migrate_voicings(data: dict) -> tuple:
        """Build the ``voicings`` registry, migrating legacy keys if present.

        Returns a ``(voicings, voicing)`` pair: the merged registry, and the
        (possibly rewritten) selected ``voicing`` string.
        """
        voicings: Dict[str, dict] = dict(data.get("voicings", {}))
        voicing: str = data.get("voicing", "piano")

        legacy_tunings: Dict[str, list] = data.get("custom_tunings", {}) or {}
        legacy_ensembles: Dict[str, dict] = data.get("custom_ensembles", {}) or {}

        for name, tuning in legacy_tunings.items():
            if name in voicings:
                logger.warning(
                    f"Voicing '{name}' already exists in the voicings registry; "
                    f"ignoring legacy custom_tunings entry of the same name"
                )
                continue
            voicings[name] = {"model": "fretboard", "tuning": tuning}

        for name, ensemble_data in legacy_ensembles.items():
            if name in voicings:
                logger.warning(
                    f"Voicing '{name}' already exists in the voicings registry; "
                    f"ignoring legacy custom_ensembles entry of the same name"
                )
                continue
            voicings[name] = {"model": "ensemble", **ensemble_data}

        if voicing.startswith("guitar:"):
            tuning_name = voicing.split(":", 1)[1]
            if tuning_name in legacy_tunings:
                voicing = f"voicing:{tuning_name}"
        elif voicing.startswith("ensemble:"):
            ensemble_name = voicing.split(":", 1)[1]
            if ensemble_name in legacy_ensembles and ensemble_name not in BUILTIN_ENSEMBLES:
                voicing = f"voicing:{ensemble_name}"

        return voicings, voicing
