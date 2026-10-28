"""FluidSynth's sequencer, driven by the synth's sample clock.

The sequencer is created with ``use_system_timer=False`` and registered with
the synth, so its clock advances by the audio FluidSynth renders (1 tick =
1 ms of rendered audio). Notes sent to it at absolute ticks are played by the
audio thread at that point in the rendered stream, so Python's scheduling
latency (sleep granularity, GIL waits) no longer moves them.

pyfluidsynth 1.4 binds most of the sequencer API. This module adds what it
lacks, with small ctypes prototypes on the library pyfluidsynth already
loaded:

- registering a *source-only* client (no callback, so FluidSynth never calls
  back into Python from the audio thread);
- ``fluid_sequencer_remove_events``, to drop pending events on pause, stop
  and speed changes.
"""

import logging
from ctypes import CFUNCTYPE, c_char_p, c_int, c_short, c_void_p
from typing import Any

from audio.fluidsynth_import import fluidsynth

logger = logging.getLogger(__name__)

#: Sequencer ticks per second of rendered audio.
TICKS_PER_SECOND = 1000


def _prototype(name: str, restype: Any, *argtypes: Any) -> Any:
    """Bind a libfluidsynth function, or return None if it's missing."""
    library = getattr(fluidsynth, "_fl", None)
    if library is None or not hasattr(library, name):
        return None
    return CFUNCTYPE(restype, *argtypes)((name, library))


_register_client = _prototype(
    "fluid_sequencer_register_client", c_short, c_void_p, c_char_p, c_void_p, c_void_p
)
_remove_events = _prototype(
    "fluid_sequencer_remove_events", None, c_void_p, c_short, c_short, c_int
)


class SynthSequencer:
    """A sample-clocked FluidSynth sequencer bound to one synth.

    Thread safety: FluidSynth locks its event queue, so any thread may send
    or remove events while the audio thread processes them.
    """

    def __init__(self, synth: Any) -> None:
        """Create the sequencer and register the synth as its destination.

        Call this before the audio driver starts, so the synth's sample
        timer is added while nothing is rendering.

        Args:
            synth: A ``fluidsynth.Synth``.

        Raises:
            RuntimeError: If this FluidSynth lacks the sequencer API.
        """
        if fluidsynth.new_fluid_sequencer2 is None or _register_client is None or _remove_events is None:
            raise RuntimeError("This FluidSynth version has no usable sequencer (FluidSynth 2 is required)")
        self._seq = fluidsynth.Sequencer(time_scale=TICKS_PER_SECOND, use_system_timer=False)
        try:
            self._synth_id = self._seq.register_fluidsynth(synth)
        except Exception:
            self._seq.delete()
            raise

    def new_source(self, name: str) -> int:
        """Register a source-only client, used to tag (and remove) events.

        Args:
            name: Client name, for FluidSynth's debugging output.

        Returns:
            The client id.
        """
        client = _register_client(self._seq.sequencer, name.encode(), None, None)
        if client < 0:
            raise RuntimeError(f"Could not register sequencer client {name!r}")
        return client

    def now(self) -> int:
        """The current tick: milliseconds of audio rendered since creation."""
        return int(self._seq.get_tick())

    def note_on(self, tick: int, channel: int, key: int, velocity: int, source: int) -> None:
        """Schedule a note-on at an absolute tick (past ticks play at once)."""
        self._seq.note_on(max(0, int(tick)), channel, key, velocity,
                          source=source, dest=self._synth_id, absolute=True)

    def note_off(self, tick: int, channel: int, key: int, source: int) -> None:
        """Schedule a note-off at an absolute tick (past ticks play at once).

        At the same tick FluidSynth handles note-offs before note-ons, so a
        chord's release and the next chord's attack on the same key retrigger
        the note instead of cutting it.
        """
        self._seq.note_off(max(0, int(tick)), channel, key,
                           source=source, dest=self._synth_id, absolute=True)

    def remove(self, source: int) -> None:
        """Drop every pending event sent by ``source``."""
        _remove_events(self._seq.sequencer, source, -1, -1)

    def delete(self) -> None:
        """Free the sequencer. Stop the audio driver first."""
        self._seq.delete()
