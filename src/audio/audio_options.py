"""Synth and audio-driver options a host passes to the player.

The desktop passes nothing and gets FluidSynth's defaults. Android passes the
device's native sample rate and Oboe settings, so FluidSynth doesn't run a
resampler and asks for a low-latency stream.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Union

SettingValue = Union[str, int, float]

#: Audio drivers tried, in order, when the preferred one is unset or fails.
PLATFORM_DRIVERS: Dict[str, List[str]] = {
    "win32": ["dsound", "wasapi", "waveout"],
    "darwin": ["coreaudio"],
    "android": ["oboe", "opensles"],
}
#: Linux and anything else not listed above.
DEFAULT_DRIVERS: List[str] = ["pulseaudio", "alsa", "oss"]


def platform_drivers(platform: str) -> List[str]:
    """The fallback driver list for a ``sys.platform`` value.

    Args:
        platform: A ``sys.platform`` string, e.g. ``"linux"`` or ``"android"``.

    Returns:
        A fresh list of FluidSynth audio driver names.
    """
    return list(PLATFORM_DRIVERS.get(platform, DEFAULT_DRIVERS))


@dataclass(frozen=True)
class AudioOptions:
    """How to create the synth and which audio driver to try first.

    Attributes:
        driver: Audio driver to try before the platform list (``None``: just
            the platform list).
        sample_rate: Synth sample rate in Hz (``None``: pyfluidsynth's
            44.1 kHz default).
        period_size: ``audio.period-size`` in frames (``None``: FluidSynth's
            default).
        settings: Any other FluidSynth settings, by name, e.g.
            ``{"audio.oboe.performance-mode": "LowLatency"}``. Applied before
            the synth is created.
    """

    driver: Optional[str] = None
    sample_rate: Optional[float] = None
    period_size: Optional[int] = None
    settings: Mapping[str, SettingValue] = field(default_factory=dict)

    def synth_settings(self) -> Dict[str, SettingValue]:
        """FluidSynth settings to apply when creating the synth.

        Returns:
            ``settings`` plus ``audio.period-size`` when ``period_size`` is set.
        """
        result: Dict[str, SettingValue] = dict(self.settings)
        if self.period_size:
            result["audio.period-size"] = int(self.period_size)
        return result

    def driver_candidates(self, platform: str) -> List[str]:
        """Drivers to try in order: the preferred one, then the platform list.

        Args:
            platform: A ``sys.platform`` string.

        Returns:
            Driver names without duplicates.
        """
        drivers = platform_drivers(platform)
        if self.driver:
            return [self.driver] + [d for d in drivers if d != self.driver]
        return drivers
