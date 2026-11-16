"""The playback volume: what the Qt player bar's sliders and mute set.

``volume`` (config, 0.0-1.0) is the music slider's position: the chords'
channel volume (CC 7), so the metronome keeps its own level (Tibi,
2026-11-17: "first should control music, second metronome"). 1.0 is the
loudness the music always had (CC 7 100, the General MIDI default, under
``synth.gain`` :data:`~constants.AUDIO_GAIN`), so a config without the key
sounds as before. FluidSynth's CC 7 curve is 40·log10(cc/127) dB, so the
amplitude follows the square of the position, as the output gain did:
loudness is heard roughly on a log scale, and a linear curve would crowd
every audible change into the bottom of the slider. Mute is not a volume: it
silences everything (the output gain goes to 0) without moving the slider,
and isn't saved.
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


#: The music channel's CC 7 at full volume: General MIDI's default, the
#: level the chords always played at.
MUSIC_CC_FULL = 100


def output_gain(muted: bool = False) -> float:
    """FluidSynth's ``synth.gain``: the app's fixed level, 0 when muted.
    The sliders don't move it (each rides its own channel's CC 7)."""
    return 0.0 if muted else AUDIO_GAIN


def music_cc(volume: float) -> int:
    """The music channel's volume (CC 7) for the music slider at ``volume``."""
    return int(round(MUSIC_CC_FULL * check_volume(volume)))


# -- the metronome's own level -------------------------------------------------------
#
# ``metronome_volume`` (config, 0.0-1.0) is the second slider in the Qt
# volume popup: the click's own level. The music slider above doesn't move
# it (Tibi, 2026-11-17); mute silences both. 1.0 is the loudest click MIDI allows (full velocity on the downbeat,
# channel volume 127), about 8 dB louder than the click before this slider,
# which sits near 60%.

DEFAULT_METRONOME_VOLUME = 1.0
#: CC 7 is 0-127.
_CC_MAX = 127


def metronome_volume_from_config(raw: Any) -> float:
    """The config's ``metronome_volume``: a number in range (rounded to 3
    places), else the default."""
    try:
        return round(check_volume(raw), 3)
    except ValueError:
        return DEFAULT_METRONOME_VOLUME


def metronome_cc(level: float, enabled: bool = True) -> int:
    """The click channel's volume (CC 7) for the metronome slider at
    ``level``; 0 while the metronome is off.

    127 × level: FluidSynth's CC 7 curve is 40·log10(cc/127) dB, so the
    click's amplitude follows the square of the slider, like the volume's gain.
    """
    if not enabled:
        return 0
    return int(round(_CC_MAX * check_volume(level)))
