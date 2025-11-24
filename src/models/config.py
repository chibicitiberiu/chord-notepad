"""Application configuration model."""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict


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
    default_octave: int = 4
    bass_octave: int = 3
    time_signature_beats: int = 4  # Beats per measure
    time_signature_unit: int = 4   # Beat unit (e.g., 4 = quarter note)
    voicing: str = "piano"  # Voice leading style: 'piano' or 'guitar:<tuning_name>'
    custom_tunings: Dict[str, List[str]] = field(default_factory=dict)  # Custom guitar tunings

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

    def validate(self) -> None:
        """Validate configuration values."""
        if not (40 <= self.bpm <= 300):
            raise ValueError(f"BPM must be between 40 and 300, got {self.bpm}")

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
            "default_octave": self.default_octave,
            "bass_octave": self.bass_octave,
            "time_signature_beats": self.time_signature_beats,
            "time_signature_unit": self.time_signature_unit,
            "voicing": self.voicing,
            "custom_tunings": self.custom_tunings,
            "notation": self.notation,
            "key": self.key,
            "window_geometry": self.window_geometry,
            "window_maximized": self.window_maximized,
            "recent_files": self.recent_files,
            "max_recent_files": self.max_recent_files,
            "soundfont_path": self.soundfont_path,
            "audio_driver": self.audio_driver,
            "log_level": self.log_level,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create Config from dictionary.

        Note: Version is extracted but not used in construction here.
        The ConfigService handles version migration before calling this method.
        """
        return cls(
            version=data.get("version", 1),
            font_family=data.get("font_family", "TkFixedFont"),
            font_size=data.get("font_size", 11),
            theme=data.get("theme", "default"),
            bpm=data.get("bpm", 120),
            default_octave=data.get("default_octave", 4),
            bass_octave=data.get("bass_octave", 3),
            time_signature_beats=data.get("time_signature_beats", 4),
            time_signature_unit=data.get("time_signature_unit", 4),
            voicing=data.get("voicing", "piano"),
            custom_tunings=data.get("custom_tunings", {}),
            notation=data.get("notation", "american"),
            key=data.get("key", "C"),
            window_geometry=data.get("window_geometry", "900x600"),
            window_maximized=data.get("window_maximized", False),
            recent_files=data.get("recent_files", []),
            max_recent_files=data.get("max_recent_files", 10),
            soundfont_path=data.get("soundfont_path"),
            audio_driver=data.get("audio_driver"),
            log_level=data.get("log_level", "INFO"),
        )
