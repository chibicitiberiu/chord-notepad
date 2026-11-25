"""Following the system's default audio output when the driver doesn't.

Some FluidSynth drivers open the output device that is the default when they
start and stay on it. On macOS, FluidSynth's ``coreaudio`` driver uses a HAL
output unit, which keeps playing into the device it opened: switch the Mac's
output from a headset to the speakers and the app keeps playing into the
headset (seen on a MacBook Air, 2026-11-26). The other desktop drivers follow on
their own: PulseAudio and PipeWire move a stream opened without a device,
Windows moves DirectSound streams (stream routing, since Windows 7), and
Oboe reopens its stream when the device goes away. ``wasapi`` (the Windows
fallback) also stays on the endpoint it opened, but the default device isn't
read there yet, so it isn't watched.

:class:`OutputDeviceWatcher` polls the default output device and calls back
when it changes; the player then restarts its driver, which opens the new
default.
"""

import ctypes
import logging
import sys
import threading
from typing import Callable, Hashable, Optional

logger = logging.getLogger(__name__)

#: How often the default output device is read, in seconds.
POLL_INTERVAL_S = 1.0

#: Drivers that stay on the device they opened, by ``sys.platform`` value,
#: for which the default device can be read.
PINNED_DRIVERS = {
    "darwin": frozenset({"coreaudio"}),
}

_COREAUDIO = "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"


def _fourcc(code: str) -> int:
    """A CoreAudio four-character code as its UInt32."""
    return int.from_bytes(code.encode("ascii"), "big")


class _AudioObjectPropertyAddress(ctypes.Structure):
    _fields_ = [("mSelector", ctypes.c_uint32),
                ("mScope", ctypes.c_uint32),
                ("mElement", ctypes.c_uint32)]


_kAudioObjectSystemObject = 1
_kAudioHardwarePropertyDefaultOutputDevice = _fourcc("dOut")
_kAudioObjectPropertyScopeGlobal = _fourcc("glob")
_kAudioObjectPropertyElementMain = 0

_get_property_data: Optional[Callable[..., int]] = None
_coreaudio_tried = False


def _coreaudio_get_property_data() -> Optional[Callable[..., int]]:
    """CoreAudio's ``AudioObjectGetPropertyData``, or None if it can't be loaded."""
    global _get_property_data, _coreaudio_tried
    if not _coreaudio_tried:
        _coreaudio_tried = True
        try:
            library = ctypes.CDLL(_COREAUDIO)
            function = library.AudioObjectGetPropertyData
            function.restype = ctypes.c_int32
            function.argtypes = [ctypes.c_uint32, ctypes.POINTER(_AudioObjectPropertyAddress),
                                 ctypes.c_uint32, ctypes.c_void_p,
                                 ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
            _get_property_data = function
        except (OSError, AttributeError):
            logger.info("CoreAudio could not be loaded; the default output device isn't followed",
                        exc_info=True)
    return _get_property_data


def _macos_default_output() -> Optional[int]:
    """The ``AudioDeviceID`` of macOS's default output device, or None."""
    get = _coreaudio_get_property_data()
    if get is None:
        return None
    address = _AudioObjectPropertyAddress(_kAudioHardwarePropertyDefaultOutputDevice,
                                          _kAudioObjectPropertyScopeGlobal,
                                          _kAudioObjectPropertyElementMain)
    device = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(device))
    status = get(_kAudioObjectSystemObject, ctypes.byref(address), 0, None,
                 ctypes.byref(size), ctypes.byref(device))
    if status != 0 or device.value == 0:   # 0 is kAudioObjectUnknown: no output device
        return None
    return device.value


def default_output_device(platform: Optional[str] = None) -> Optional[Hashable]:
    """Something that identifies the system's default output device, or None.

    Two calls return equal values while the default device stays the same.

    Args:
        platform: A ``sys.platform`` value (default: this one).

    Returns:
        A device identifier, or None where it can't be read (another
        platform, no output device, or an error).
    """
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        try:
            return _macos_default_output()
        except Exception:
            logger.debug("Could not read the default output device", exc_info=True)
    return None


def needs_watch(platform: str, driver: Optional[str]) -> bool:
    """Whether ``driver`` on ``platform`` stays on the device it opened (and
    the default device can be read there)."""
    return driver in PINNED_DRIVERS.get(platform, ())


class OutputDeviceWatcher:
    """Calls back on a background thread when the default output device changes.

    The thread checks every :data:`POLL_INTERVAL_S`; a check that can't read
    the device (None) is skipped, so a moment with no output device doesn't
    count as a change, and the callback runs once the new device is there.
    """

    def __init__(self, on_change: Callable[[], None],
                 read: Callable[[], Optional[Hashable]] = default_output_device,
                 interval_s: float = POLL_INTERVAL_S) -> None:
        """
        Args:
            on_change: Called (on the watcher's thread) after the default
                device changed. An exception it raises is logged.
            read: Reads the current device (:func:`default_output_device`;
                tests replace it).
            interval_s: Seconds between checks.
        """
        self._on_change = on_change
        self._read = read
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._device: Optional[Hashable] = None

    @property
    def device(self) -> Optional[Hashable]:
        """The default device last seen."""
        return self._device

    def start(self) -> bool:
        """Read the current device and start watching.

        Returns:
            True if watching; False if the device can't be read here (then
            there is no thread).
        """
        if self._thread is not None:
            return True
        self._device = self._read()
        if self._device is None:
            return False
        self._thread = threading.Thread(target=self._run, name="OutputDeviceWatch", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop watching and wait for the thread (unless called from it)."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def check(self) -> bool:
        """Read the device once and call back if it changed.

        Returns:
            True if it changed (and the callback ran).
        """
        device = self._read()
        if device is None or device == self._device:
            return False
        logger.info("The default audio output changed (%s -> %s)", self._device, device)
        self._device = device
        try:
            self._on_change()
        except Exception:
            logger.error("Could not follow the new audio output", exc_info=True)
        return True

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            self.check()
