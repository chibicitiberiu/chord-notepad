"""Application constants and configuration values."""

from enum import Enum

# Application metadata
APP_NAME = "Chord Notepad"
APP_ID = "chord-notepad"
# X11 window class, matched by StartupWMClass in the .desktop file. Tk
# title-cases it (first letter upper, the rest lower), so this is spelled the
# way it ends up on the window.
WM_CLASS = "Chordnotepad"
CONFIG_FILENAME = "settings.json"
LOG_FILENAME = "chord-notepad.log"

# Configuration versioning
CONFIG_VERSION = 4  # Increment when config structure changes

# Limits
MAX_RECENT_FILES = 10
#: Upper bound of the recent-documents list length (Settings, and a saved
#: ``max_recent_files`` outside 1-MAX_RECENT_LIMIT reads as the default).
MAX_RECENT_LIMIT = 50
# The tempo range: Config, the toolbar scrubber and in-song {bpm} directives
# all use it (a relative tempo change is clamped to it).
MIN_BPM = 20
MAX_BPM = 400
DEFAULT_BPM = 120
# The time signatures the app supports: 1-16 beats over one of these units.
MIN_BEATS = 1
MAX_BEATS = 16
TIME_SIGNATURE_UNITS = (1, 2, 4, 8, 16)
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
DEFAULT_FONT_SIZE = 11

# Timing (milliseconds)
CHORD_DETECTION_DEBOUNCE_MS = 500
CHORD_SHEET_RERENDER_DEBOUNCE_MS = 500
PLAYBACK_THREAD_CHECK_MS = 50

# Chord sheet strip
DEFAULT_CHORD_SHEET_HEIGHT = 160
DEFAULT_CHORD_SHEET_VIEW = "keyboard"

# The Qt desktop's Edit sidebars (config ``sidebar``, ``sidebar_width``): the
# one open ("" when collapsed) and its width in the window's layout units
# (Theme.px: a quarter of the UI font's line height, about 4 logical px at
# 100%), so it follows the UI scale.
SIDEBARS = ("directives", "identifier")
DEFAULT_SIDEBAR = "directives"
SIDEBAR_WIDTH_MIN = 56
SIDEBAR_WIDTH_MAX = 150
DEFAULT_SIDEBAR_WIDTH = 76

# Capo advisor (see services/capo_advisor.py). When "Allow capo" is on and a
# fretboard voicing is active, the advisor scores every capo position 0..MAX
# with the guitar picker's whole-song playability score and suggests the best
# one only if it beats capo 0 by at least MIN_GAIN per chord (the song's
# chords with notes, repeats included), so a long song or a repeated chorus
# needs the same gain per chord as a short one. The score is driven mostly by
# the fretboard weights open_string_bonus / position_penalty / barre_penalty,
# so the gain is roughly "points of playability saved per chord". 1.5 keeps
# the open keys (C, D, E, A, G) capo-free in most progressions while every
# flat key (Bb, Eb, Ab, Db) and F# gets one.
CAPO_MAX_DEFAULT = 7      # Highest capo position considered.
CAPO_MIN_GAIN = 1.5       # Minimum score improvement per chord over capo 0 to suggest a capo.

# Audio settings
DEFAULT_OCTAVE = 4
BASS_OCTAVE = 3
# FluidSynth's synth.gain at full volume (config volume 1.0): the loudness
# the app always had. See audio/volume.py for the volume-to-gain curve.
AUDIO_GAIN = 0.5
MIDI_CHANNEL = 0

# Logging
LOG_MAX_BYTES = 1024 * 1024  # 1MB per log file
LOG_BACKUP_COUNT = 10  # Keep 10 old log files
DEFAULT_LOG_LEVEL = "INFO"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# The Qt desktop's colour scheme (config ``ui_theme``): follow the system, or
# always light or dark. ``theme`` is a different, older key: a ttk theme name.
UI_THEMES = ("system", "light", "dark")
DEFAULT_UI_THEME = "system"
# The Qt desktop's whole-window zoom (config ``ui_scale``, Ctrl+Alt+= / - / 0):
# a factor on every size, in steps of 10%.
UI_SCALE_MIN = 0.7
UI_SCALE_MAX = 2.0
UI_SCALE_STEP = 0.1
DEFAULT_UI_SCALE = 1.0


class Notation(Enum):
    """Musical notation system."""
    AMERICAN = "american"
    EUROPEAN = "european"


#: Seconds between the notes of a rolled chord (lowest first), like a quick
#: strum or a spread chord: the identifier's Shift+▶ and a Shift+click on a
#: chord in the text or the chord sheet.
ROLL_GAP_SECONDS = 0.11


class LineType(Enum):
    """Type of line in the text editor."""
    CHORD = "chord"
    TEXT = "text"
