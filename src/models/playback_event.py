"""
Playback event data model for visual feedback during playback
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum

from models.chord import ChordInfo


class PlaybackEventType(Enum):
    """Type of playback event."""
    CHORD_START = "chord_start"  # A chord starts playing
    CHORD_END = "chord_end"      # A chord finishes playing
    PLAYBACK_FINISHED = "playback_finished"  # Playback has completed


@dataclass
class PlaybackEventArgs:
    """Event arguments for playback events.

    This class carries all relevant information about the current playback state
    to enable visual feedback in the UI.
    """

    event_type: PlaybackEventType
    """Type of playback event"""

    chord_info: Optional[ChordInfo] = None
    """Currently playing chord (None for PLAYBACK_FINISHED event)"""

    bpm: int = 120
    """Current beats per minute"""

    time_signature_beats: int = 4
    """Current time signature numerator (beats per measure)"""

    time_signature_unit: int = 4
    """Current time signature denominator (beat unit)"""

    key: Optional[str] = None
    """Current key signature (e.g., 'C', 'Am', 'D')"""

    current_line: int = 0
    """Current line number (0-indexed)"""

    current_bar: int = 0
    """Current bar/measure number (1-indexed)"""

    total_bars: int = 0
    """Total number of bars/measures in the song"""
