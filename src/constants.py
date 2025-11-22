"""Application constants and configuration values."""

from enum import Enum

# Application metadata
APP_NAME = "Chord Notepad"
APP_ID = "chord-notepad"
CONFIG_FILENAME = "settings.json"
LOG_FILENAME = "chord-notepad.log"

# Configuration versioning
CONFIG_VERSION = 1  # Increment when config structure changes

# Limits
MAX_RECENT_FILES = 10
MIN_BPM = 60
MAX_BPM = 240
DEFAULT_BPM = 120
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
DEFAULT_FONT_SIZE = 11

# Timing (milliseconds)
CHORD_DETECTION_DEBOUNCE_MS = 500
EVENT_QUEUE_POLL_MS = 100
PLAYBACK_THREAD_CHECK_MS = 50

# Text editor tags
TAG_CHORD_VALID = "chord"
TAG_CHORD_INVALID = "chord_invalid"
TAG_CHORD_COMMENT = "chord_comment"
TAG_CHORD_PLAYING = "chord_playing"

# Colors
COLOR_CHORD_VALID = "blue"
COLOR_CHORD_INVALID = "gray"
COLOR_CHORD_COMMENT = "red"
COLOR_CHORD_PLAYING_BG = "yellow"

# Audio settings
DEFAULT_OCTAVE = 4
BASS_OCTAVE = 3
AUDIO_GAIN = 0.5
MIDI_CHANNEL = 0

# Logging
LOG_MAX_BYTES = 1024 * 1024  # 1MB per log file
LOG_BACKUP_COUNT = 10  # Keep 10 old log files
DEFAULT_LOG_LEVEL = "INFO"


class Notation(Enum):
    """Musical notation system."""
    AMERICAN = "american"
    EUROPEAN = "european"


class LineType(Enum):
    """Type of line in the text editor."""
    CHORD = "chord"
    TEXT = "text"
