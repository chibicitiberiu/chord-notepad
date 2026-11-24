"""The app's own ctypes binding of libfluidsynth.

Written against FluidSynth 2's public C API (the headers under
``include/fluidsynth/``) and covering only what the core calls: settings, a
synth with an optional audio driver, SoundFont loading and presets, note and
controller events, offline rendering, and the sample-clocked sequencer that
:mod:`audio.sequencer` builds on. FluidSynth itself is LGPL and is only
loaded and called here.

Finding the library
-------------------
The library is loaded once, when this module is imported, so a build that
can't load it fails at import with ``ImportError`` ("Couldn't find the
FluidSynth library.") or the ``OSError`` ctypes raises.

``CHORD_NOTEPAD_LIBFLUIDSYNTH`` overrides the lookup. It holds either a path
(the snap's bundled library isn't in the system linker cache that
``ctypes.util.find_library`` searches; the macOS bundle sets it from the
PyInstaller runtime hook) or a bare soname such as ``libfluidsynth.so``, which
the dynamic linker resolves itself, so no file has to exist at that name. A
path to a missing file is logged and the normal lookup runs instead.

Without the variable:

- Android: the soname, ``libfluidsynth.so``. The native libraries stay inside
  the APK (there is no file path at all) and CPython's ``find_library`` only
  looks in ``/system/lib64``.
- iOS: no default. The library is a framework inside the app bundle and the
  Swift host sets the variable to
  ``<app>/Frameworks/FluidSynth.framework/FluidSynth`` before Python starts
  (the binary inside an iOS framework carries the framework's name). Without
  it the import raises :class:`~chordnotepad.exceptions.AudioInitializationError`.
- Linux and the rest: ``find_library("fluidsynth")``, which finds the system's
  ``libfluidsynth.so.3``.
- Windows: ``libfluidsynth-3.dll`` on ``PATH`` (the launcher puts the
  checkout's ``.tools/bin`` there, the PyInstaller runtime hook the bundle's
  ``fluidsynth`` folder), else in ``C:\\tools\\fluidsynth\\bin``, where a
  manual install goes.
- macOS: ``find_library("fluidsynth")``, else Homebrew's
  ``lib/libfluidsynth.dylib`` (``$HOMEBREW_PREFIX``, ``/opt/homebrew``,
  ``/usr/local``); non-Homebrew Pythons don't search Homebrew's folder.

Lifetimes
---------
Free in this order: the audio driver, then the sequencer (the synth calls its
sample timer), then the synth, then its settings. :meth:`Synth.delete` frees
the driver, synth and settings in that order; the sequencer is the caller's
to free first. Every ``delete`` may be called twice.
"""

import ctypes
import ctypes.util
import logging
import os
import sys
from ctypes import (
    c_char_p, c_double, c_float, c_int, c_int16, c_short, c_uint, c_void_p)
from typing import Any, Callable, Mapping, Optional, Tuple, Union

from chordnotepad.exceptions import AudioInitializationError

logger = logging.getLogger(__name__)

LIBRARY_ENV = "CHORD_NOTEPAD_LIBFLUIDSYNTH"
ANDROID_SONAME = "libfluidsynth.so"
#: Where a manual Windows install of FluidSynth's release zip goes.
WINDOWS_TOOLS_DIR = r"C:\tools\fluidsynth\bin"
#: The Windows DLL of FluidSynth 2.x (the release zips and CI's bundle).
WINDOWS_DLL = "libfluidsynth-3.dll"
HOMEBREW_PREFIXES = ("/opt/homebrew", "/usr/local")
NOT_FOUND = "Couldn't find the FluidSynth library."

FLUID_OK = 0
FLUID_FAILED = -1

SettingValue = Union[str, bytes, int, float]


# -- finding and loading the library -------------------------------------------------


def is_bare_soname(library: str) -> bool:
    """Whether ``library`` is a name for the linker rather than a path."""
    return os.sep not in library and "/" not in library


def requested_library(env: Optional[Mapping[str, str]] = None,
                      platform: Optional[str] = None) -> str:
    """The library the environment or the platform asks for, or "" for the lookup.

    Raises:
        AudioInitializationError: On iOS without ``CHORD_NOTEPAD_LIBFLUIDSYNTH``.
    """
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    library = env.get(LIBRARY_ENV, "")
    if not library and platform == "android":
        return ANDROID_SONAME
    if not library and platform == "ios":
        raise AudioInitializationError(
            f"FluidSynth's location is unknown: {LIBRARY_ENV} is not set. The iOS app must set "
            f"it to <app>/Frameworks/FluidSynth.framework/FluidSynth before Python starts.")
    return library


def find_system_library(platform: Optional[str] = None,
                        env: Optional[Mapping[str, str]] = None,
                        find: Callable[[str], Optional[str]] = ctypes.util.find_library,
                        exists: Callable[[str], bool] = os.path.isfile) -> Optional[str]:
    """The installed libfluidsynth's name or path, or None.

    Args:
        platform: A ``sys.platform`` value (default: this one).
        env: The environment (default: ``os.environ``).
        find: ``ctypes.util.find_library`` (tests replace it).
        exists: ``os.path.isfile`` (tests replace it).
    """
    platform = sys.platform if platform is None else platform
    env = os.environ if env is None else env
    if platform == "win32":
        found = find(WINDOWS_DLL[:-len(".dll")]) or find("fluidsynth")
        if found:
            return found
        candidate = os.path.join(WINDOWS_TOOLS_DIR, WINDOWS_DLL)
        return candidate if exists(candidate) else None
    found = find("fluidsynth")
    if found:
        return found
    if platform == "darwin":
        prefixes = [env["HOMEBREW_PREFIX"]] if env.get("HOMEBREW_PREFIX") else []
        for prefix in prefixes + [p for p in HOMEBREW_PREFIXES if p not in prefixes]:
            candidate = os.path.join(prefix, "lib", "libfluidsynth.dylib")
            if exists(candidate):
                return candidate
    return None


def resolve_library(env: Optional[Mapping[str, str]] = None,
                    platform: Optional[str] = None,
                    find: Callable[[str], Optional[str]] = ctypes.util.find_library,
                    exists: Callable[[str], bool] = os.path.isfile) -> str:
    """What to hand ``ctypes.CDLL``: a path or a soname.

    Raises:
        ImportError: Nothing was found.
        AudioInitializationError: On iOS without ``CHORD_NOTEPAD_LIBFLUIDSYNTH``.
    """
    library = requested_library(env, platform)
    if library and (is_bare_soname(library) or exists(library)):
        return library
    if library:
        logger.warning("%s points at a missing file: %s", LIBRARY_ENV, library)
    found = find_system_library(platform, env, find, exists)
    if not found:
        raise ImportError(NOT_FOUND)
    return found


def load_library(env: Optional[Mapping[str, str]] = None,
                 platform: Optional[str] = None) -> Tuple[ctypes.CDLL, str]:
    """Load libfluidsynth: ``(the library, the name or path it was loaded by)``."""
    library = resolve_library(env, platform)
    loaded = ctypes.CDLL(library)
    logger.debug("Loaded FluidSynth from %s", library)
    return loaded, library


_lib, LIBRARY_PATH = load_library()


def _bind(name: str, restype: Any, *argtypes: Any, required: bool = True) -> Any:
    """A libfluidsynth function with its C prototype, or None if optional and missing."""
    try:
        function = getattr(_lib, name)
    except AttributeError:
        if required:
            raise ImportError(f"{LIBRARY_PATH} has no {name}: FluidSynth 2 is required") from None
        return None
    function.restype = restype
    function.argtypes = list(argtypes)
    return function


# settings.h
_new_settings = _bind("new_fluid_settings", c_void_p)
_delete_settings = _bind("delete_fluid_settings", None, c_void_p)
_settings_setstr = _bind("fluid_settings_setstr", c_int, c_void_p, c_char_p, c_char_p)
_settings_setint = _bind("fluid_settings_setint", c_int, c_void_p, c_char_p, c_int)
_settings_setnum = _bind("fluid_settings_setnum", c_int, c_void_p, c_char_p, c_double)

# synth.h, sfont.h
_new_synth = _bind("new_fluid_synth", c_void_p, c_void_p)
_delete_synth = _bind("delete_fluid_synth", None, c_void_p)
_sfload = _bind("fluid_synth_sfload", c_int, c_void_p, c_char_p, c_int)
_program_select = _bind("fluid_synth_program_select", c_int, c_void_p, c_int, c_int, c_int, c_int)
_noteon = _bind("fluid_synth_noteon", c_int, c_void_p, c_int, c_int, c_int)
_noteoff = _bind("fluid_synth_noteoff", c_int, c_void_p, c_int, c_int)
_cc = _bind("fluid_synth_cc", c_int, c_void_p, c_int, c_int, c_int)
_all_notes_off = _bind("fluid_synth_all_notes_off", c_int, c_void_p, c_int)
_get_sfont_by_id = _bind("fluid_synth_get_sfont_by_id", c_void_p, c_void_p, c_int)
_sfont_get_preset = _bind("fluid_sfont_get_preset", c_void_p, c_void_p, c_int, c_int)
_preset_get_name = _bind("fluid_preset_get_name", c_char_p, c_void_p)
_write_s16 = _bind("fluid_synth_write_s16", c_int, c_void_p, c_int,
                   c_void_p, c_int, c_int, c_void_p, c_int, c_int)
_write_float = _bind("fluid_synth_write_float", c_int, c_void_p, c_int,
                     c_void_p, c_int, c_int, c_void_p, c_int, c_int)

# audio.h
_new_audio_driver = _bind("new_fluid_audio_driver", c_void_p, c_void_p, c_void_p)
_delete_audio_driver = _bind("delete_fluid_audio_driver", None, c_void_p)

# seq.h, seqbind.h, event.h (fluid_seq_id_t is a short). Optional: without
# them SynthSequencer refuses to start, as with FluidSynth 1.
_new_sequencer2 = _bind("new_fluid_sequencer2", c_void_p, c_int, required=False)
_delete_sequencer = _bind("delete_fluid_sequencer", None, c_void_p, required=False)
_set_time_scale = _bind("fluid_sequencer_set_time_scale", None, c_void_p, c_double, required=False)
_register_fluidsynth = _bind("fluid_sequencer_register_fluidsynth", c_short, c_void_p, c_void_p,
                             required=False)
_register_client = _bind("fluid_sequencer_register_client", c_short,
                         c_void_p, c_char_p, c_void_p, c_void_p, required=False)
_get_tick = _bind("fluid_sequencer_get_tick", c_uint, c_void_p, required=False)
_send_at = _bind("fluid_sequencer_send_at", c_int, c_void_p, c_void_p, c_uint, c_int, required=False)
_remove_events = _bind("fluid_sequencer_remove_events", None, c_void_p, c_short, c_short, c_int,
                       required=False)
_new_event = _bind("new_fluid_event", c_void_p, required=False)
_delete_event = _bind("delete_fluid_event", None, c_void_p, required=False)
_event_set_source = _bind("fluid_event_set_source", None, c_void_p, c_short, required=False)
_event_set_dest = _bind("fluid_event_set_dest", None, c_void_p, c_short, required=False)
_event_noteon = _bind("fluid_event_noteon", None, c_void_p, c_int, c_short, c_short, required=False)
_event_noteoff = _bind("fluid_event_noteoff", None, c_void_p, c_int, c_short, required=False)

#: Whether this libfluidsynth has every sequencer function :class:`Sequencer` uses.
HAS_SEQUENCER = all(f is not None for f in (
    _new_sequencer2, _delete_sequencer, _set_time_scale, _register_fluidsynth, _register_client,
    _get_tick, _send_at, _remove_events, _new_event, _delete_event, _event_set_source,
    _event_set_dest, _event_noteon, _event_noteoff))


def _path_bytes(path: str) -> bytes:
    """A file name as FluidSynth opens it (UTF-8 on Windows)."""
    return path.encode("utf-8") if sys.platform == "win32" else os.fsencode(path)


def delete_fluid_audio_driver(driver: Optional[int]) -> None:
    """Stop and free an audio driver handle (None is ignored)."""
    if driver:
        _delete_audio_driver(driver)


# -- the synth ------------------------------------------------------------------------


class Synth:
    """A FluidSynth synth with its settings and, after :meth:`start`, an audio driver.

    Attributes:
        settings: The ``fluid_settings_t *`` (an int; None once deleted).
        synth: The ``fluid_synth_t *`` (an int; None once deleted).
        audio_driver: The ``fluid_audio_driver_t *`` while one runs, else None.

    Args:
        gain: ``synth.gain``.
        samplerate: ``synth.sample-rate`` in Hz.
        channels: ``synth.midi-channels``.
        **settings: Any other FluidSynth settings by their full name, e.g.
            ``**{"audio.period-size": 96}``; see :meth:`setting`.

    Raises:
        AudioInitializationError: FluidSynth couldn't create the settings or the synth.
    """

    def __init__(self, gain: float = 0.2, samplerate: float = 44100.0, channels: int = 256,
                 **settings: SettingValue) -> None:
        self.synth: Optional[int] = None
        self.audio_driver: Optional[int] = None
        self.settings: Optional[int] = _new_settings()
        if not self.settings:
            self.settings = None
            raise AudioInitializationError("FluidSynth could not create its settings.")
        self.setting("synth.gain", float(gain))
        self.setting("synth.sample-rate", float(samplerate))
        self.setting("synth.midi-channels", int(channels))
        for name, value in settings.items():
            self.setting(name, value)
        self.synth = _new_synth(self.settings)
        if not self.synth:
            self.synth = None
            self.delete()
            raise AudioInitializationError("FluidSynth could not create a synth.")

    def setting(self, name: str, value: SettingValue) -> bool:
        """Set a FluidSynth setting, by the value's Python type.

        A str (or bytes) is a string setting, an int an integer one and a
        float a number one; FluidSynth refuses a value of the wrong kind (and
        unknown names), which is logged and returns False. Real-time settings
        such as ``synth.gain`` take effect at once.
        """
        key = name.encode()
        if isinstance(value, (str, bytes)):
            result = _settings_setstr(self.settings, key, value.encode() if isinstance(value, str) else value)
        elif isinstance(value, int):
            result = _settings_setint(self.settings, key, value)
        elif isinstance(value, float):
            result = _settings_setnum(self.settings, key, value)
        else:
            raise TypeError(f"FluidSynth setting {name!r}: {type(value).__name__} is not str, int or float")
        if result != FLUID_OK:
            logger.debug("FluidSynth refused the setting %s = %r", name, value)
            return False
        return True

    def start(self, driver: Optional[str] = None) -> int:
        """Start an audio driver, which renders the synth on its own thread.

        Args:
            driver: ``audio.driver`` to use, e.g. ``"pulseaudio"`` (None:
                the setting as it is).

        Returns:
            ``FLUID_OK`` with :attr:`audio_driver` set, or ``FLUID_FAILED``
            (FluidSynth couldn't open the driver) with it None. No MIDI
            input driver is created.
        """
        self.stop()
        if driver:
            self.setting("audio.driver", driver)
        self.audio_driver = _new_audio_driver(self.settings, self.synth) or None
        return FLUID_OK if self.audio_driver else FLUID_FAILED

    def stop(self) -> None:
        """Free the audio driver, if one runs; the synth stays."""
        driver, self.audio_driver = self.audio_driver, None
        delete_fluid_audio_driver(driver)

    def delete(self) -> None:
        """Free the audio driver, the synth (and its SoundFonts), then the settings.

        Free a sequencer the synth is registered with before this.
        """
        self.stop()
        synth, self.synth = self.synth, None
        if synth:
            _delete_synth(synth)
        settings, self.settings = self.settings, None
        if settings:
            _delete_settings(settings)

    def sfload(self, path: str, reset_presets: bool = False) -> int:
        """Load a SoundFont; its id, or ``FLUID_FAILED`` (-1)."""
        return _sfload(self.synth, _path_bytes(path), int(bool(reset_presets)))

    def program_select(self, channel: int, sfont_id: int, bank: int, preset: int) -> int:
        """Select a SoundFont's preset on a channel; ``FLUID_OK`` or ``FLUID_FAILED``."""
        return _program_select(self.synth, channel, sfont_id, bank, preset)

    def sfpreset_name(self, sfont_id: int, bank: int, preset: int) -> Optional[str]:
        """The name of a loaded SoundFont's preset, or None if it has none there."""
        sfont = _get_sfont_by_id(self.synth, sfont_id)
        if not sfont:
            return None
        found = _sfont_get_preset(sfont, bank, preset)
        if not found:
            return None
        name = _preset_get_name(found)
        return name.decode("utf-8", errors="replace") if name is not None else None

    def noteon(self, channel: int, key: int, velocity: int) -> int:
        """Start a note now (velocity 0 is a note-off)."""
        return _noteon(self.synth, channel, key, velocity)

    def noteoff(self, channel: int, key: int) -> int:
        """Release a note now (``FLUID_FAILED`` if it wasn't sounding)."""
        return _noteoff(self.synth, channel, key)

    def cc(self, channel: int, control: int, value: int) -> int:
        """Send a MIDI control change, e.g. CC 7 (channel volume)."""
        return _cc(self.synth, channel, control, value)

    def all_notes_off(self, channel: int) -> int:
        """Release every note on a channel (-1: on every channel)."""
        return _all_notes_off(self.synth, channel)

    def write_s16(self, frames: int, buffer: Any) -> int:
        """Render ``frames`` into ``buffer`` as interleaved 16-bit stereo.

        Only without an audio driver: the driver renders on its own thread.

        Args:
            frames: Frames to render.
            buffer: A ctypes ``c_int16`` array of at least ``2 * frames``.

        Returns:
            ``FLUID_OK`` or ``FLUID_FAILED``.
        """
        self._check_buffer(frames, buffer, c_int16)
        return _write_s16(self.synth, frames, buffer, 0, 2, buffer, 1, 2)

    def write_float(self, frames: int, buffer: Any) -> int:
        """Like :meth:`write_s16` into a ``c_float`` array (samples in -1.0..1.0)."""
        self._check_buffer(frames, buffer, c_float)
        return _write_float(self.synth, frames, buffer, 0, 2, buffer, 1, 2)

    @staticmethod
    def _check_buffer(frames: int, buffer: Any, sample: Any) -> None:
        if getattr(buffer, "_type_", None) is not sample or len(buffer) < 2 * frames:
            raise ValueError(f"need a {sample.__name__} array of {2 * frames} samples")


# -- the sequencer --------------------------------------------------------------------


class Sequencer:
    """FluidSynth's event sequencer.

    Sending and removing events may happen on any thread: FluidSynth locks
    the queue the audio thread reads.

    Args:
        time_scale: Ticks per second.
        use_system_timer: True: the clock is the system's; False: the clock
            advances with the audio a registered synth renders.

    Raises:
        RuntimeError: This FluidSynth lacks the sequencer API (FluidSynth 1),
            or couldn't create one.
    """

    def __init__(self, time_scale: float = 1000.0, use_system_timer: bool = False) -> None:
        self.sequencer: Optional[int] = None
        if not HAS_SEQUENCER:
            raise RuntimeError("This FluidSynth version has no usable sequencer (FluidSynth 2 is required)")
        self.sequencer = _new_sequencer2(int(bool(use_system_timer))) or None
        if self.sequencer is None:
            raise RuntimeError("FluidSynth could not create a sequencer")
        _set_time_scale(self.sequencer, float(time_scale))

    def register_synth(self, synth: Synth) -> int:
        """Make ``synth`` a destination; with no system timer it also drives the clock.

        Returns:
            The destination's client id.
        """
        client = _register_fluidsynth(self.sequencer, synth.synth)
        if client < 0:
            raise RuntimeError("Could not register the synth with the sequencer")
        return client

    def register_source(self, name: str) -> int:
        """Register a client with no callback, only to tag (and remove) events.

        FluidSynth never calls back into Python for it.
        """
        client = _register_client(self.sequencer, name.encode(), None, None)
        if client < 0:
            raise RuntimeError(f"Could not register sequencer client {name!r}")
        return client

    def get_tick(self) -> int:
        """The sequencer's current tick."""
        return int(_get_tick(self.sequencer))

    def note_on(self, tick: int, channel: int, key: int, velocity: int,
                source: int, dest: int) -> int:
        """Queue a note-on at an absolute tick; ``FLUID_OK`` or ``FLUID_FAILED``."""
        return self._send(tick, source, dest, lambda event: _event_noteon(event, channel, key, velocity))

    def note_off(self, tick: int, channel: int, key: int, source: int, dest: int) -> int:
        """Queue a note-off at an absolute tick; ``FLUID_OK`` or ``FLUID_FAILED``."""
        return self._send(tick, source, dest, lambda event: _event_noteoff(event, channel, key))

    def _send(self, tick: int, source: int, dest: int, fill: Callable[[int], None]) -> int:
        event = _new_event()
        if not event:
            raise MemoryError("FluidSynth could not allocate an event")
        try:
            _event_set_source(event, source)
            _event_set_dest(event, dest)
            fill(event)
            # The sequencer copies the event, so it is freed right after.
            return _send_at(self.sequencer, event, max(0, int(tick)), 1)
        finally:
            _delete_event(event)

    def remove_events(self, source: int = -1, dest: int = -1, event_type: int = -1) -> None:
        """Drop queued events matching source, destination and type (-1: any)."""
        _remove_events(self.sequencer, source, dest, event_type)

    def delete(self) -> None:
        """Free the sequencer and unregister its clients. Stop the audio driver first."""
        sequencer, self.sequencer = self.sequencer, None
        if sequencer:
            _delete_sequencer(sequencer)


__all__ = [
    "ANDROID_SONAME", "FLUID_FAILED", "FLUID_OK", "HAS_SEQUENCER", "LIBRARY_ENV", "LIBRARY_PATH",
    "NOT_FOUND", "Sequencer", "Synth", "delete_fluid_audio_driver", "find_system_library",
    "load_library", "requested_library", "resolve_library",
]
