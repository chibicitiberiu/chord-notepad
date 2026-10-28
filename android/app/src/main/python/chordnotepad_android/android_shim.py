"""Runtime shims that adapt the desktop core to Android.

M2 spike: each patch here stands in for a core change that the port still
needs (listed in docs/ANDROID.md, "Required core changes"). When the core
change lands, the matching shim is deleted.

1. Data directories: AppDataService resolves XDG_* on non-Windows/macOS
   platforms, so point those at the app's private filesDir.
2. Library lookup: CPython's ctypes.util.find_library on Android only searches
   /system/lib64, and the core's CHORD_NOTEPAD_LIBFLUIDSYNTH override requires
   an existing file path. Native libraries stay inside the APK (not extracted),
   so the only usable name is the bare soname, which dlopen resolves from the
   app's library namespace.
3. Audio driver: NotePlayer tries pulseaudio/alsa/oss on anything that isn't
   Windows or macOS. On Android it must try oboe, then opensles.
4. NULL driver: pyfluidsynth's Synth.start() returns FLUID_OK even when
   new_fluid_audio_driver() returned NULL; treat that as a failure.
5. Sample rate / Oboe settings: create the synth at the device's native output
   rate and ask Oboe for a low-latency stream.
"""

import ctypes.util
import logging
import os
import sys

logger = logging.getLogger(__name__)

FLUIDSYNTH_SONAME = "libfluidsynth.so"
ANDROID_DRIVERS = ("oboe", "opensles")
DESKTOP_DRIVERS = (None, "pulseaudio", "alsa", "oss")

#: What the shims did, for the spike report.
STATE = {"driver": None, "driver_attempts": [], "sample_rate": None}

_installed = False


def install(files_dir: str, sample_rate: int = 48000, period_size: int = 0) -> None:
    """Install every shim. Must run before the core imports audio.player."""
    global _installed
    if _installed:
        return
    _installed = True
    _set_data_dirs(files_dir)
    _patch_find_library()
    _patch_synth(sample_rate, period_size)


def _set_data_dirs(files_dir: str) -> None:
    os.environ.setdefault("HOME", files_dir)
    for var, sub in (
        ("XDG_DATA_HOME", "data"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        path = os.path.join(files_dir, sub)
        os.makedirs(path, exist_ok=True)
        os.environ[var] = path


def _patch_find_library() -> None:
    original = ctypes.util.find_library

    def find_library(name):
        if "fluidsynth" in name:
            return FLUIDSYNTH_SONAME
        return original(name)

    ctypes.util.find_library = find_library


def _patch_synth(sample_rate: int, period_size: int) -> None:
    import fluidsynth  # resolves libfluidsynth.so through the patched lookup

    STATE["sample_rate"] = sample_rate
    original_init = fluidsynth.Synth.__init__
    original_start = fluidsynth.Synth.start

    def __init__(self, gain=0.2, samplerate=None, channels=256, **kwargs):
        settings = {"audio.oboe.performance-mode": "LowLatency"}
        if period_size:
            settings["audio.period-size"] = int(period_size)
        settings.update(kwargs)
        original_init(self, gain=gain, samplerate=samplerate or sample_rate,
                      channels=channels, **settings)

    def start(self, driver=None, device=None, midi_driver=None, midi_router=None):
        if sys.platform == "android" and driver in DESKTOP_DRIVERS:
            if STATE["driver_attempts"]:
                return -1  # the Android list was already tried for this start
            candidates = ANDROID_DRIVERS
        else:
            candidates = (driver,)
        for name in candidates:
            original_start(self, driver=name, device=device,
                           midi_driver=midi_driver, midi_router=midi_router)
            STATE["driver_attempts"].append(name)
            if self.audio_driver:
                STATE["driver"] = name
                logger.info("FluidSynth audio driver: %s", name)
                return 0
            logger.warning("FluidSynth audio driver %s returned NULL", name)
        return -1

    fluidsynth.Synth.__init__ = __init__
    fluidsynth.Synth.start = start
