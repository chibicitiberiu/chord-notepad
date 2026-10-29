"""Runtime shims that adapt the desktop core to Android.

M2 spike: each patch here stands in for a core change that the port still
needs (listed in docs/ANDROID.md, "Required core changes"). When the core
change lands, the matching shim is deleted.

Remaining, for the spike only:

1. Data directories: the spike's AppDataService resolves XDG_*, so they are
   pointed at the app's private filesDir. The session host (``host.py``)
   doesn't need this: it passes filesDir as ``AppDataService(root=...)``,
   which gives the same layout (core change 5, done with session step 14).

Gone with M1b (now in the core):
- library lookup: ``audio/fluidsynth_import.py`` accepts the bare soname and
  defaults to ``libfluidsynth.so`` on Android;
- driver list, NULL-driver check, sample rate and Oboe settings:
  ``NotePlayer`` tries ``oboe`` then ``opensles`` and takes the host's
  settings through ``AudioOptions`` (see :func:`audio_options`).
"""

import os

#: Oboe stream settings the spike asked for.
OBOE_SETTINGS = {"audio.oboe.performance-mode": "LowLatency"}

_installed = False


def install(files_dir: str) -> None:
    """Install every shim. Must run before the core creates AppDataService."""
    global _installed
    if _installed:
        return
    _installed = True
    _set_data_dirs(files_dir)


def audio_options(sample_rate: int = 48000, period_size: int = 0):
    """The synth settings the Android host passes to ``initialize_player``.

    Args:
        sample_rate: The device's native output rate (no resampler).
        period_size: ``audio.period-size`` in frames; 0 keeps FluidSynth's.
    """
    from audio.audio_options import AudioOptions

    return AudioOptions(
        sample_rate=sample_rate,
        period_size=period_size or None,
        settings=dict(OBOE_SETTINGS),
    )


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
