"""The playback volume: what the Qt player bar's slider and mute set.

``volume`` (config, 0.0-1.0) is the slider's position; 1.0 is the loudness
the app always had (``synth.gain`` :data:`~constants.AUDIO_GAIN`), so a
config without the key sounds as before. The gain follows the square of the
position: loudness is heard roughly on a log scale, so a linear gain would
crowd every audible change into the bottom of the slider. Mute is not a
volume: it silences without moving the slider, and isn't saved.
"""

import math
from typing import Any

from chordnotepad.constants import AUDIO_GAIN

MIN_VOLUME = 0.0
MAX_VOLUME = 1.0
DEFAULT_VOLUME = 1.0
#: The slider's step (and the wheel's): 5%.
VOLUME_STEP = 0.05


def check_volume(volume: Any) -> float:
    """``volume`` as a float, if it is a number from 0.0 to 1.0.

    Raises:
        ValueError: For anything else (a bool is not a number here).
    """
    if isinstance(volume, bool) or not isinstance(volume, (int, float)):
        raise ValueError(f"volume must be a number from 0.0 to 1.0, not {volume!r}")
    if not math.isfinite(volume) or not MIN_VOLUME <= volume <= MAX_VOLUME:
        raise ValueError(f"volume must be from 0.0 to 1.0, not {volume!r}")
    return float(volume)


def volume_from_config(raw: Any) -> float:
    """The config's ``volume``: a number in range (rounded to 3 places),
    else the default."""
    try:
        return round(check_volume(raw), 3)
    except ValueError:
        return DEFAULT_VOLUME


def gain_for(volume: float, muted: bool = False) -> float:
    """FluidSynth's ``synth.gain`` for a slider position (0 when muted)."""
    if muted:
        return 0.0
    volume = check_volume(volume)
    return AUDIO_GAIN * volume * volume
