"""Settings as plain values, for views that can't hold the Settings viewmodel.

The desktop Settings dialog edits a live ``SettingsViewModel`` (handed out by
``AppSession.settings_model``) and passes what its ``commit`` reported to
``AppSession.apply_settings``. A view on the other side of the bridge can't
hold a live object, so it reads :class:`SettingsValues` (``AppSession
.settings_values``) and sends a whole new :class:`SettingsValues` back to
``apply_settings``; the session then commits it through the same viewmodel,
so the config writes and change flags are the desktop's.

Only the settings that carry over to Android are here (the "settings
visibility rule" in ``docs/ANDROID.md``): not the log level, the
audio driver, the SoundFont path or the window geometry. The voicings
registry has its own editor (M5) and isn't here either.
"""

from dataclasses import dataclass, fields, replace
from typing import Any, Dict

from constants import MAX_FONT_SIZE, MIN_FONT_SIZE, TIME_SIGNATURE_UNITS  # noqa: F401
from models.notation import AMERICAN_KEYS, american_key
from session import toolbar

#: Upper bound of the recent-documents list length.
MAX_RECENT_LIMIT = 50

#: The whole-number settings a view types in (General and Playback). While
#: the text of one isn't valid, the view sends it to ``commit_settings`` as
#: ``invalid_numbers`` so it can be kept for next time.
NUMBER_SETTINGS = ('font_size', 'max_recent_files', 'bpm', 'time_signature_beats')


@dataclass(frozen=True)
class SettingsValues:
    """The settings a mobile Settings screen shows (General and Playback).

    Attributes:
        font_family: The editor font's family (Android maps it to
            Monospace, Sans or Serif).
        font_size: The editor font's size, 6-72 points.
        notation: Chord notation at startup: ``american`` or ``european``.
        key: Key at startup for roman numerals ("" for none), in American
            spelling whatever the notation ("G", shown as "Sol" in European).
        show_quick_start_on_startup: Whether Quick Start opens at startup.
        max_recent_files: How many recent documents to keep, 1-50.
        bpm: Tempo at startup, 20-400.
        time_signature_beats: Time-signature numerator at startup, 1-16.
        time_signature_unit: Its denominator: 1, 2, 4, 8 or 16.
        word_wrap: Whether long lines wrap at the editor's edge (off: the
            text scrolls sideways and chords stay over their lyrics).
    """

    font_family: str
    font_size: int
    notation: str
    key: str
    show_quick_start_on_startup: bool
    max_recent_files: int
    bpm: int
    time_signature_beats: int
    time_signature_unit: int
    word_wrap: bool = False

    def check(self) -> None:
        """Raise ValueError naming the first value that is out of range."""
        if not self.font_family.strip():
            raise ValueError("font_family must not be empty")
        if not MIN_FONT_SIZE <= self.font_size <= MAX_FONT_SIZE:
            raise ValueError(f"font_size {self.font_size} outside {MIN_FONT_SIZE}-{MAX_FONT_SIZE}")
        if self.notation not in ("american", "european"):
            raise ValueError(f"notation must be 'american' or 'european', not {self.notation!r}")
        if self.key and self.key not in AMERICAN_KEYS:
            raise ValueError(f"unknown key {self.key!r} (keys are in American spelling)")
        if not 1 <= self.max_recent_files <= MAX_RECENT_LIMIT:
            raise ValueError(f"max_recent_files {self.max_recent_files} outside 1-{MAX_RECENT_LIMIT}")
        bpm_scale = toolbar.BPM_SCALE
        if not bpm_scale.min_value <= self.bpm <= bpm_scale.max_value:
            raise ValueError(
                f"bpm {self.bpm} outside {bpm_scale.min_value:g}-{bpm_scale.max_value:g}")
        if not 1 <= self.time_signature_beats <= 16:
            raise ValueError(f"time_signature_beats {self.time_signature_beats} outside 1-16")
        if self.time_signature_unit not in TIME_SIGNATURE_UNITS:
            raise ValueError(f"time_signature_unit {self.time_signature_unit} must be one of "
                             f"{TIME_SIGNATURE_UNITS}")

    def as_dict(self) -> Dict[str, Any]:
        """The values by field name."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def read(cls, source: Any) -> "SettingsValues":
        """Take the values from anything with these attributes (a ``Config``,
        a ``SettingsViewModel``).

        The key comes in American spelling whatever the notation (an older
        config may hold "Sol"); views show it in their notation.
        """
        values = cls(**{f.name: getattr(source, f.name) for f in fields(cls)})
        return replace(values, key=american_key(values.key))
