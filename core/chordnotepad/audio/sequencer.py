"""FluidSynth's sequencer, driven by the synth's sample clock.

The sequencer is created with ``use_system_timer=False`` and registered with
the synth, so its clock advances by the audio FluidSynth renders (1 tick =
1 ms of rendered audio). Notes sent to it at absolute ticks are played by the
audio thread at that point in the rendered stream, so Python's scheduling
latency (sleep granularity, GIL waits) no longer moves them.

The song and click-to-hear events come from *source-only* clients (no
callback, so FluidSynth never calls back into Python from the audio thread),
which is what lets pause, stop and speed changes drop one source's pending
events. The C calls are in :mod:`audio.fluid_ctypes`.
"""

import logging
from typing import Any

from chordnotepad.audio import fluid_ctypes

logger = logging.getLogger(__name__)

#: Sequencer ticks per second of rendered audio.
TICKS_PER_SECOND = 1000


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
            synth: A :class:`audio.fluid_ctypes.Synth`.

        Raises:
            RuntimeError: If this FluidSynth lacks the sequencer API.
        """
        self._seq = fluid_ctypes.Sequencer(time_scale=TICKS_PER_SECOND, use_system_timer=False)
        try:
            self._synth_id = self._seq.register_synth(synth)
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
        return self._seq.register_source(name)

    def now(self) -> int:
        """The current tick: milliseconds of audio rendered since creation."""
        return int(self._seq.get_tick())

    def note_on(self, tick: int, channel: int, key: int, velocity: int, source: int) -> None:
        """Schedule a note-on at an absolute tick (past ticks play at once)."""
        self._seq.note_on(max(0, int(tick)), channel, key, velocity,
                          source=source, dest=self._synth_id)

    def note_off(self, tick: int, channel: int, key: int, source: int) -> None:
        """Schedule a note-off at an absolute tick (past ticks play at once).

        At the same tick FluidSynth handles note-offs before note-ons, so a
        chord's release and the next chord's attack on the same key retrigger
        the note instead of cutting it.
        """
        self._seq.note_off(max(0, int(tick)), channel, key,
                           source=source, dest=self._synth_id)

    def remove(self, source: int) -> None:
        """Drop every pending event sent by ``source``."""
        self._seq.remove_events(source, -1, -1)

    def delete(self) -> None:
        """Free the sequencer. Stop the audio driver first."""
        self._seq.delete()
