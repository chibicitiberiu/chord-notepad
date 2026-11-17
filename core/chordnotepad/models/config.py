"""Application configuration model."""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Literal, Dict

from chordnotepad.constants import (
    CONFIG_VERSION, DEFAULT_UI_SCALE, DEFAULT_UI_THEME, LOG_LEVELS, MAX_BEATS, MAX_BPM,
    MAX_FONT_SIZE, MAX_RECENT_LIMIT, MIN_BEATS, MIN_BPM, MIN_FONT_SIZE, TIME_SIGNATURE_UNITS,
    UI_SCALE_MAX, UI_SCALE_MIN, UI_THEMES,
    DEFAULT_SIDEBAR, DEFAULT_SIDEBAR_WIDTH, SIDEBAR_WIDTH_MAX, SIDEBAR_WIDTH_MIN, SIDEBARS,
)
from chordnotepad.models.notation import american_key
from chordnotepad.models.ensemble_spec import BUILTIN_ENSEMBLES
from chordnotepad.models import window_geometry as neutral_geometry
from chordnotepad.audio.volume import (
    check_volume, metronome_volume_from_config, volume_from_config)

logger = logging.getLogger(__name__)


def ui_scale_from_config(raw) -> float:
    """A saved ``ui_scale`` as the window can use it: a number from
    UI_SCALE_MIN to UI_SCALE_MAX, rounded to whole percent; anything else is
    the default (a failed ``validate()`` on load would reset every setting)."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return DEFAULT_UI_SCALE
    value = round(float(raw), 2)
    return value if UI_SCALE_MIN <= value <= UI_SCALE_MAX else DEFAULT_UI_SCALE


def config_version(raw: Any) -> int:
    """A saved ``version`` as the migrations read it: an int, else 1.

    A string, a float or a bool can only come from a damaged or hand-edited
    file; it reads as 1 (with a warning) instead of failing the whole load.
    A missing version is 1 as well: v0.1 and v0.2 wrote one, but a hand-made
    file may not.
    """
    if raw is None:
        return 1
    if isinstance(raw, bool) or not isinstance(raw, int):
        logger.warning(f"Config version {raw!r} is not a whole number; reading it as 1")
        return 1
    return raw


def _is_number(value: Any) -> bool:
    """True for an int or a float, not a bool (a bool is an int)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number_in(low: float, high: float) -> Callable[[Any], bool]:
    return lambda value: _is_number(value) and low <= value <= high


def _int_in(low: int, high: int) -> Callable[[Any], bool]:
    return lambda value: _is_int(value) and low <= value <= high


#: The checks ``Config.from_dict`` makes, key by key: a saved value that
#: fails its check reads as the field's default (with a warning), so one bad
#: value never costs the other settings. They accept what ``validate()``
#: accepts, so a loaded config always validates.
_FIELD_CHECKS: Dict[str, Callable[[Any], bool]] = {
    "bpm": _number_in(MIN_BPM, MAX_BPM),
    "bpm_multiplier": _number_in(0.125, 4.0),
    "font_size": _number_in(MIN_FONT_SIZE, MAX_FONT_SIZE),
    "notation": lambda value: value in ("american", "european"),
    "log_level": lambda value: isinstance(value, str) and value in LOG_LEVELS,
    "instrument": _int_in(0, 127),
    # MIDI octaves run from -1 to 9.
    "default_octave": _int_in(-1, 9),
    "bass_octave": _int_in(-1, 9),
    "time_signature_beats": _int_in(MIN_BEATS, MAX_BEATS),
    "time_signature_unit": lambda value: _is_int(value) and value in TIME_SIGNATURE_UNITS,
    "max_recent_files": _int_in(1, MAX_RECENT_LIMIT),
    "key": lambda value: isinstance(value, str),
}

#: The top-level keys ``from_dict`` reads besides the fields ``to_dict``
#: writes: the legacy voicing registries, moved into ``voicings`` on load.
_LEGACY_KEYS = ("custom_tunings", "custom_ensembles")


@dataclass
class Config:
    """Application configuration model with validation."""

    # Version for migration support. A new config is written at the current
    # version: one saved as 1 would go through the v1 migrations at the next
    # start, which negated the signed weights of voicings made in between.
    version: int = CONFIG_VERSION

    # Appearance
    font_family: str = "TkFixedFont"
    font_size: int = 11
    # A ttk theme name, kept for the Tk front end (nothing sets it today).
    theme: str = "default"
    # The Qt desktop's colour scheme: "system", "light" or "dark" (UI_THEMES).
    ui_theme: str = DEFAULT_UI_THEME
    # The Qt desktop's whole-window zoom, UI_SCALE_MIN-UI_SCALE_MAX (1.0 = 100%).
    ui_scale: float = DEFAULT_UI_SCALE
    # The Qt desktop's menu bar is hidden (Alt shows it) unless this is on
    # ("Show menu bar"). macOS always has its global menu bar.
    menu_bar_shown: bool = False
    # Off: the song scrolls sideways, so a chord line stays over its lyric
    # line however narrow the window. On: long lines wrap at the edge.
    word_wrap: bool = False

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
    # The Qt player bar's volume slider, 0.0-1.0; 1.0 is the loudness the app
    # always had (audio/volume.py). Mute isn't saved.
    volume: float = 1.0
    # Its second slider: the metronome click's level under the volume,
    # 0.0-1.0; 1.0 is the loudest click (audio/volume.py).
    metronome_volume: float = 1.0
    # A chord clicked (tapped) in the text sounds the notes the chord sheet
    # shows for it, as playback plays them. Off: each click is voiced from
    # the chord clicked before it (PlaybackService's click picker).
    click_plays_chart_voicing: bool = True

    # Notation
    notation: Literal["american", "european"] = "american"
    key: str = "C"  # Default key, always American spelling ("G", not "Sol"); "" for none

    # Window. ``window_geometry`` is Tk's "WxH+X+Y" in Tk's pixels;
    # ``window_bounds`` the Qt window's {"width", "height", "x", "y"} in
    # logical pixels (None until Qt saves, and again after Tk does); see
    # models/window_geometry.py for how both front ends keep them in step.
    window_geometry: str = neutral_geometry.TK_DEFAULT_GEOMETRY
    window_maximized: bool = False
    window_bounds: Optional[Dict[str, Optional[int]]] = field(
        default_factory=lambda: dict(neutral_geometry.DEFAULT_BOUNDS))

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
    # Android: the local date (ISO) the support prompt was last dismissed.
    # Not a setting: the Settings screen never writes it.
    support_prompt_last_shown: Optional[str] = None

    # Chord sheet strip (bottom-docked voiced-chord panel)
    chord_sheet_visible: bool = False  # Whether the chord sheet panel is shown
    chord_sheet_view: str = "keyboard"  # Active renderer id ('keyboard', 'staff', 'fret', 'tab')
    chord_sheet_height: int = 160      # Panel height in pixels (paned-window sash position)
    # The Qt Edit sheet's height in logical pixels (None: from chord_sheet_height).
    chord_sheet_logical_height: Optional[int] = 160
    # Per-view display zoom factors, keyed by renderer id (only non-1.0 entries
    # are stored). Values are clamped to [0.5, 2.5]; junk is dropped on load.
    chord_sheet_zoom: Dict[str, float] = field(default_factory=dict)

    # The Qt Edit sidebar that is open (SIDEBARS, or "" when collapsed) and
    # its width in layout units (SIDEBAR_WIDTH_MIN-SIDEBAR_WIDTH_MAX).
    sidebar: str = DEFAULT_SIDEBAR
    sidebar_width: float = DEFAULT_SIDEBAR_WIDTH

    # One-off notices the user dismissed for good, by id (e.g. the Qt staff
    # view's "staff_rhythm"). Not a setting: the Settings screen never writes it.
    dismissed_notices: List[str] = field(default_factory=list)

    # Top-level keys the file had that this release doesn't know (a newer
    # release wrote them). They are written back as they were, after the
    # known keys, so running an older release doesn't trim a newer file.
    extra: Dict[str, Any] = field(default_factory=dict)

    # Not saved: True when ``from_dict`` had to replace a saved value (or drop
    # a voicing entry) because it was unusable. ConfigService then backs the
    # file up before its next write.
    needs_backup: bool = field(default=False, compare=False, repr=False)

    def validate(self) -> None:
        """Validate configuration values."""
        if not (MIN_BPM <= self.bpm <= MAX_BPM):
            raise ValueError(f"BPM must be between {MIN_BPM} and {MAX_BPM}, got {self.bpm}")

        if not (0.125 <= self.bpm_multiplier <= 4.0):
            raise ValueError(
                f"BPM multiplier must be between 0.125 and 4.0, got {self.bpm_multiplier}"
            )

        if not (6 <= self.font_size <= 72):
            raise ValueError(f"Font size must be between 6 and 72, got {self.font_size}")

        if self.notation not in ("american", "european"):
            raise ValueError(f"Notation must be 'american' or 'european', got {self.notation}")

        if self.log_level not in LOG_LEVELS:
            raise ValueError(f"Invalid log level: {self.log_level}")

        check_volume(self.volume)
        check_volume(self.metronome_volume)

        if self.ui_theme not in UI_THEMES:
            raise ValueError(f"UI theme must be one of {UI_THEMES}, got {self.ui_theme!r}")

        if not (UI_SCALE_MIN <= self.ui_scale <= UI_SCALE_MAX):
            raise ValueError(
                f"UI scale must be between {UI_SCALE_MIN} and {UI_SCALE_MAX}, got {self.ui_scale}")
        if self.sidebar not in SIDEBARS + ("",):
            raise ValueError(f"Sidebar must be one of {SIDEBARS} or empty, got {self.sidebar!r}")
        if not (SIDEBAR_WIDTH_MIN <= self.sidebar_width <= SIDEBAR_WIDTH_MAX):
            raise ValueError(f"Sidebar width must be between {SIDEBAR_WIDTH_MIN} and "
                             f"{SIDEBAR_WIDTH_MAX}, got {self.sidebar_width}")

        if len(self.recent_files) > self.max_recent_files:
            self.recent_files = self.recent_files[:self.max_recent_files]

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        # A file from a newer release keeps its higher version; anything
        # older is written at the current one.
        data = {
            "version": max(self.version, CONFIG_VERSION),
            "font_family": self.font_family,
            "font_size": self.font_size,
            "theme": self.theme,
            "ui_theme": self.ui_theme,
            "ui_scale": self.ui_scale,
            "menu_bar_shown": self.menu_bar_shown,
            "word_wrap": self.word_wrap,
            "bpm": self.bpm,
            "bpm_multiplier": self.bpm_multiplier,
            "default_octave": self.default_octave,
            "bass_octave": self.bass_octave,
            "time_signature_beats": self.time_signature_beats,
            "time_signature_unit": self.time_signature_unit,
            "voicing": self.voicing,
            "voicings": self.voicings,
            "instrument": self.instrument,
            "volume": self.volume,
            "metronome_volume": self.metronome_volume,
            "click_plays_chart_voicing": self.click_plays_chart_voicing,
            "notation": self.notation,
            "key": american_key(self.key),
            "window_geometry": self.window_geometry,
            "window_maximized": self.window_maximized,
            "window_bounds": self.window_bounds,
            "recent_files": self.recent_files,
            "max_recent_files": self.max_recent_files,
            "soundfont_path": self.soundfont_path,
            "audio_driver": self.audio_driver,
            "log_level": self.log_level,
            "show_quick_start_on_startup": self.show_quick_start_on_startup,
            "support_prompt_last_shown": self.support_prompt_last_shown,
            "chord_sheet_visible": self.chord_sheet_visible,
            "chord_sheet_view": self.chord_sheet_view,
            "chord_sheet_height": self.chord_sheet_height,
            "chord_sheet_logical_height": self.chord_sheet_logical_height,
            "chord_sheet_zoom": self.chord_sheet_zoom,
            "sidebar": self.sidebar,
            "sidebar_width": self.sidebar_width,
            "dismissed_notices": list(self.dismissed_notices),
        }
        for key, value in self.extra.items():
            if key not in data:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create Config from dictionary.

        Note: Version is extracted but not used in construction here.
        The ConfigService handles version migration before calling this method.

        A default ``key`` saved in European spelling by older versions
        ("Sol") is read as American ("G"): the config stores keys in
        American spelling, whatever the notation.

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

        Values are checked field by field (``_FIELD_CHECKS``): an unusable one
        reads as its default with a warning, and sets ``needs_backup``, so one
        bad value never resets the other settings. Keys this release doesn't
        know are kept in ``extra``.
        """
        fallbacks: List[str] = []
        voicings, voicing = cls._migrate_voicings(data, fallbacks)

        def checked(key: str, default: Any) -> Any:
            if key not in data:
                return default
            value = data[key]
            if _FIELD_CHECKS[key](value):
                return value
            logger.warning(f"Config {key}={value!r} is not usable; using the default {default!r}")
            fallbacks.append(key)
            return default

        config = cls(
            version=config_version(data.get("version", 1)),
            font_family=data.get("font_family", "TkFixedFont"),
            font_size=checked("font_size", 11),
            theme=data.get("theme", "default"),
            # Unknown values fall back here: a failed validate() on load would
            # reset every setting.
            ui_theme=cls._one_of(data.get("ui_theme"), UI_THEMES, DEFAULT_UI_THEME),
            ui_scale=ui_scale_from_config(data.get("ui_scale")),
            menu_bar_shown=data.get("menu_bar_shown", False) is True,
            word_wrap=data.get("word_wrap", False) is True,
            bpm=checked("bpm", 120),
            bpm_multiplier=checked("bpm_multiplier", 1.0),
            default_octave=checked("default_octave", 4),
            bass_octave=checked("bass_octave", 3),
            time_signature_beats=checked("time_signature_beats", 4),
            time_signature_unit=checked("time_signature_unit", 4),
            voicing=voicing,
            voicings=voicings,
            instrument=checked("instrument", 0),
            volume=volume_from_config(data.get("volume", 1.0)),
            metronome_volume=metronome_volume_from_config(data.get("metronome_volume", 1.0)),
            # On unless saved off (a config from before the setting has none).
            click_plays_chart_voicing=data.get("click_plays_chart_voicing", True) is not False,
            notation=checked("notation", "american"),
            # Older versions saved the key in the notation's spelling.
            key=american_key(checked("key", "C")),
            window_geometry=data.get("window_geometry", "900x600"),
            window_maximized=data.get("window_maximized", False),
            # A first start has the neutral defaults; a config Tk wrote
            # before there was a Qt window has none (Qt migrates Tk's values).
            window_bounds=(cls._window_bounds(data["window_bounds"]) if "window_bounds" in data
                           else None if "window_geometry" in data
                           else dict(neutral_geometry.DEFAULT_BOUNDS)),
            recent_files=cls._recent_files(data, fallbacks),
            max_recent_files=checked("max_recent_files", 10),
            soundfont_path=data.get("soundfont_path"),
            audio_driver=data.get("audio_driver"),
            log_level=checked("log_level", "INFO"),
            show_quick_start_on_startup=data.get("show_quick_start_on_startup", True),
            support_prompt_last_shown=cls._iso_date_or_none(data.get("support_prompt_last_shown")),
            chord_sheet_visible=data.get("chord_sheet_visible", False),
            chord_sheet_view=data.get("chord_sheet_view", "keyboard"),
            chord_sheet_height=data.get("chord_sheet_height", 160),
            chord_sheet_logical_height=(
                neutral_geometry.height_from_config(data["chord_sheet_logical_height"])
                if "chord_sheet_logical_height" in data
                else None if "chord_sheet_height" in data else 160),
            chord_sheet_zoom=cls._sanitize_chord_sheet_zoom(data.get("chord_sheet_zoom")),
            # Junk reads as the defaults (a failed validate() would reset everything).
            sidebar=cls._one_of(data.get("sidebar"), SIDEBARS + ("",), DEFAULT_SIDEBAR),
            sidebar_width=cls._sidebar_width(data.get("sidebar_width")),
            dismissed_notices=cls._notice_ids(data.get("dismissed_notices")),
        )
        known = set(config.to_dict()) | set(_LEGACY_KEYS)
        config.extra = {key: value for key, value in data.items() if key not in known}
        config.needs_backup = bool(fallbacks)
        return config

    @staticmethod
    def _recent_files(data: dict, fallbacks: List[str]) -> List[str]:
        """Saved ``recent_files``: the strings of the list; a list that isn't
        one, or entries that aren't strings, are dropped with a warning."""
        raw = data.get("recent_files", [])
        if not isinstance(raw, list):
            logger.warning(f"Config recent_files={raw!r} is not a list; starting it empty")
            fallbacks.append("recent_files")
            return []
        files = [item for item in raw if isinstance(item, str)]
        if len(files) != len(raw):
            logger.warning("Config recent_files had entries that aren't file names; dropped them")
            fallbacks.append("recent_files")
        return files

    @staticmethod
    def _notice_ids(raw) -> List[str]:
        """Saved ``dismissed_notices``: the non-empty strings, each once, in
        order; anything else (not a list, junk entries) is dropped."""
        if not isinstance(raw, list):
            return []
        ids: List[str] = []
        for item in raw:
            if isinstance(item, str) and item and item not in ids:
                ids.append(item)
        return ids

    @staticmethod
    def _window_bounds(raw) -> Optional[Dict[str, Optional[int]]]:
        """The saved ``window_bounds`` cleaned up; None for junk."""
        bounds = neutral_geometry.bounds_from_config(raw)
        return None if bounds is None else neutral_geometry.bounds_to_config(bounds)

    @staticmethod
    def _one_of(raw, choices, default):
        """``raw`` if it is one of ``choices``, else ``default``."""
        return raw if isinstance(raw, str) and raw in choices else default

    @staticmethod
    def _sidebar_width(raw) -> float:
        """A saved ``sidebar_width`` as the Qt window can use it: a number of
        layout units, clamped to SIDEBAR_WIDTH_MIN-SIDEBAR_WIDTH_MAX and
        rounded to a tenth; anything that isn't a number is the default."""
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != raw:
            return float(DEFAULT_SIDEBAR_WIDTH)
        return round(min(max(float(raw), SIDEBAR_WIDTH_MIN), SIDEBAR_WIDTH_MAX), 1)

    @staticmethod
    def _iso_date_or_none(raw) -> Optional[str]:
        """``raw`` if it is an ISO date string (``"2026-10-30"``), else None."""
        if not isinstance(raw, str):
            return None
        try:
            datetime.date.fromisoformat(raw)
        except ValueError:
            return None
        return raw

    @staticmethod
    def _sanitize_chord_sheet_zoom(raw) -> Dict[str, float]:
        """Coerce persisted per-view zoom factors into a clean dict.

        A non-dict becomes ``{}``. Each value must be a real number (bools are
        rejected); it is clamped to ``[0.5, 2.5]`` and rounded to 3 decimals.
        Non-numeric values are dropped.
        """
        if not isinstance(raw, dict):
            return {}
        clean: Dict[str, float] = {}
        for key, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            clamped = min(2.5, max(0.5, float(value)))
            clean[str(key)] = round(clamped, 3)
        return clean

    @staticmethod
    def _migrate_voicings(data: dict, fallbacks: List[str]) -> tuple:
        """Build the ``voicings`` registry, migrating legacy keys if present.

        Returns a ``(voicings, voicing)`` pair: the merged registry, and the
        (possibly rewritten) selected ``voicing`` string. A ``voicings`` that
        isn't a mapping reads as empty, an entry that isn't a mapping is
        dropped, and a ``voicing`` that isn't a string reads as ``piano``,
        each with a warning and a note in ``fallbacks``.
        """
        raw_voicings = data.get("voicings", {})
        if not isinstance(raw_voicings, dict):
            logger.warning(f"Config voicings={raw_voicings!r} is not a mapping; starting it empty")
            fallbacks.append("voicings")
            raw_voicings = {}
        voicings: Dict[str, dict] = {}
        for name, entry in raw_voicings.items():
            if isinstance(entry, dict):
                voicings[name] = entry
            else:
                logger.warning(f"Voicing {name!r} is not a mapping ({entry!r}); dropped it")
                fallbacks.append("voicings")

        voicing = data.get("voicing", "piano")
        if not isinstance(voicing, str):
            logger.warning(f"Config voicing={voicing!r} is not a name; using piano")
            fallbacks.append("voicing")
            voicing = "piano"

        legacy_tunings = data.get("custom_tunings", {}) or {}
        if not isinstance(legacy_tunings, dict):
            logger.warning(f"Config custom_tunings={legacy_tunings!r} is not a mapping; ignored it")
            fallbacks.append("custom_tunings")
            legacy_tunings = {}
        legacy_ensembles = data.get("custom_ensembles", {}) or {}
        if not isinstance(legacy_ensembles, dict):
            logger.warning(f"Config custom_ensembles={legacy_ensembles!r} is not a mapping; "
                           f"ignored it")
            fallbacks.append("custom_ensembles")
            legacy_ensembles = {}

        for name, tuning in legacy_tunings.items():
            if name in voicings:
                logger.warning(
                    f"Voicing '{name}' already exists in the voicings registry; "
                    f"ignoring legacy custom_tunings entry of the same name"
                )
                continue
            voicings[name] = {"model": "fretboard", "tuning": tuning}

        for name, ensemble_data in legacy_ensembles.items():
            if not isinstance(ensemble_data, dict):
                logger.warning(f"Legacy ensemble {name!r} is not a mapping; dropped it")
                fallbacks.append("custom_ensembles")
                continue
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
