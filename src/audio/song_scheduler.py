"""Map a compiled song onto sequencer ticks, and track its UI pings.

:class:`SongScheduler` is the timing logic of :class:`audio.player.NotePlayer`
without threads or FluidSynth. The player's clock thread calls :meth:`pump`
with the sequencer's current tick; the scheduler sends the events that fall
inside the look-ahead window to the sequencer, at absolute ticks, and hands
back the chord pings whose tick has been reached. Audio timing is therefore
set by FluidSynth's sample clock; only the pings (UI highlighting) depend on
when the Python thread wakes up.

Song time maps to ticks linearly from an anchor::

    tick(t) = anchor_tick + (t - anchor_time) * TICKS_PER_SECOND / multiplier

Pause, resume and speed changes move the anchor. Events already handed to
the sequencer beyond "now" are removed and sent again under the new mapping.
"""

import bisect
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence

from audio.sequencer import TICKS_PER_SECOND
from models.playback_event_internal import MidiEvent, MidiEventType

logger = logging.getLogger(__name__)

#: How far ahead of the sequencer's clock events are sent (ticks = ms). The
#: clock thread can be held up by other Python threads (GIL) for tens of ms;
#: anything within this window still plays on time.
LOOKAHEAD_TICKS = 2000
#: Gap between pressing Play (or Resume) and the first note, so the first
#: events are queued before the synth renders past them.
START_LEAD_TICKS = 20
#: Longest the clock thread sleeps between checks.
MAX_WAIT_TICKS = 100
#: Length of a metronome click.
CLICK_TICKS = 40
#: Log when an event reaches the sequencer this late (it then plays at once).
LATE_WARNING_TICKS = 100


class Sequencer(Protocol):
    """What the scheduler needs from :class:`audio.sequencer.SynthSequencer`."""

    def now(self) -> int: ...
    def note_on(self, tick: int, channel: int, key: int, velocity: int, source: int) -> None: ...
    def note_off(self, tick: int, channel: int, key: int, source: int) -> None: ...
    def remove(self, source: int) -> None: ...


@dataclass(frozen=True)
class ClickSound:
    """The metronome click: GM percussion notes on the drum channel."""

    channel: int = 9
    downbeat_note: int = 76
    offbeat_note: int = 77
    downbeat_velocity: int = 100
    offbeat_velocity: int = 80


@dataclass
class PumpResult:
    """What one :meth:`SongScheduler.pump` call found.

    Attributes:
        pings: NOTE_ON/REST events with a UI callback whose tick has passed.
        finished: The song has played to its last event.
        wait_s: How long the clock thread can sleep before the next check.
    """

    pings: List[MidiEvent] = field(default_factory=list)
    finished: bool = False
    wait_s: float = MAX_WAIT_TICKS / TICKS_PER_SECOND


def _round(value: float) -> int:
    return int(math.floor(value + 0.5))


class SongScheduler:
    """Schedules one song's events on a sequencer. Not thread-safe: the
    player calls every method under its own lock."""

    def __init__(
        self,
        events: Sequence[MidiEvent],
        sequencer: Sequencer,
        source: int,
        channel: int = 0,
        click: ClickSound = ClickSound(),
        multiplier: float = 1.0,
    ) -> None:
        """Prepare a song.

        Args:
            events: The compiled event list (``compile_events``); an
                END_OF_SONG event is ignored, the song ends at its last event.
            sequencer: Where notes are sent.
            source: Sequencer client id that tags this song's events, so they
                can be removed without touching click-to-hear notes.
            channel: MIDI channel for chord notes.
            click: The metronome sound.
            multiplier: Initial speed multiplier.
        """
        playable = [e for e in events if e.event_type != MidiEventType.END_OF_SONG]
        # Stable: events at the same time keep their compiled order.
        self._events: List[MidiEvent] = sorted(playable, key=lambda e: e.timestamp)
        self._times: List[float] = [e.timestamp for e in self._events]
        self._pings: List[MidiEvent] = [
            e for e in self._events
            if e.event_type in (MidiEventType.NOTE_ON, MidiEventType.REST) and e.metadata.get('has_callback')
        ]
        self._ping_times: List[float] = [e.timestamp for e in self._pings]
        self._start_time = self._times[0] if self._times else 0.0
        self._end_time = self._times[-1] if self._times else 0.0

        self._seq = sequencer
        self._source = source
        self._channel = channel
        self._click = click
        self._mult = max(0.001, float(multiplier))

        self._anchor_tick: Optional[int] = None
        self._anchor_time = self._start_time
        self._paused_at: Optional[float] = None
        self._next = 0       # next event to send to the sequencer
        self._next_ping = 0  # next ping to hand out
        self._last_on: Dict[int, int] = {}

    # -- mapping -------------------------------------------------------------

    @property
    def started(self) -> bool:
        """Whether :meth:`start` has run."""
        return self._anchor_tick is not None

    @property
    def paused(self) -> bool:
        """Whether the song is paused."""
        return self._paused_at is not None

    @property
    def multiplier(self) -> float:
        """The current speed multiplier."""
        return self._mult

    def tick_of(self, song_time: float) -> int:
        """The sequencer tick a song time maps to under the current anchor."""
        assert self._anchor_tick is not None
        return self._anchor_tick + _round((song_time - self._anchor_time) * TICKS_PER_SECOND / self._mult)

    def time_of(self, tick: int) -> float:
        """The song time at a sequencer tick under the current anchor."""
        assert self._anchor_tick is not None
        return self._anchor_time + (tick - self._anchor_tick) * self._mult / TICKS_PER_SECOND

    # -- transport -----------------------------------------------------------

    def start(self, now: int) -> None:
        """Anchor the first event shortly after ``now``."""
        self._anchor_tick = now + START_LEAD_TICKS
        self._anchor_time = self._start_time

    def pump(self, now: int) -> PumpResult:
        """Send events inside the look-ahead window and collect due pings.

        Args:
            now: The sequencer's current tick.
        """
        if not self.started or self.paused:
            return PumpResult()

        horizon = now + LOOKAHEAD_TICKS
        while self._next < len(self._events):
            event = self._events[self._next]
            tick = self.tick_of(event.timestamp)
            if tick > horizon:
                break
            if tick < now - LATE_WARNING_TICKS:
                logger.warning(f"Playback event {(now - tick) / TICKS_PER_SECOND:.3f}s late: {event}")
            self._send(event, tick)
            self._next += 1

        pings = self._take_pings(now)

        end_tick = self.tick_of(self._end_time)
        finished = (
            self._next >= len(self._events)
            and self._next_ping >= len(self._pings)
            and now >= end_tick
        )

        waits = [end_tick - now]
        if self._next_ping < len(self._pings):
            waits.append(self.tick_of(self._ping_times[self._next_ping]) - now)
        if self._next < len(self._events):
            waits.append(self.tick_of(self._times[self._next]) - horizon)
        wait = min(MAX_WAIT_TICKS, max(1, min(waits)))
        return PumpResult(pings=pings, finished=finished, wait_s=wait / TICKS_PER_SECOND)

    def pause(self, now: int) -> List[MidiEvent]:
        """Stop sending and drop what's queued; remember the song position.

        Args:
            now: The sequencer's current tick, read just before this call.

        Returns:
            Pings that were already due (their notes have sounded).
        """
        if not self.started or self.paused:
            return []
        self._seq.remove(self._source)
        pings = self._take_pings(now)
        self._rewind(now)
        self._paused_at = max(self._start_time, self.time_of(now))
        return pings

    def resume(self, now: int) -> None:
        """Continue from the paused position shortly after ``now``."""
        if self._paused_at is None:
            return
        self._anchor_tick = now + START_LEAD_TICKS
        self._anchor_time = self._paused_at
        self._paused_at = None
        self._last_on.clear()

    def set_multiplier(self, multiplier: float, now: int) -> None:
        """Change speed from ``now`` on: the rest of the song is re-sent.

        While paused (or before start) this only stores the value; resume
        anchors with it.
        """
        multiplier = max(0.001, float(multiplier))
        if not self.started or self.paused:
            self._mult = multiplier
            return
        self._seq.remove(self._source)
        self._rewind(now)
        self._anchor_time = self.time_of(now)
        self._anchor_tick = now
        self._mult = multiplier

    def stop(self, now: int) -> None:
        """Drop everything still queued for this song."""
        self._seq.remove(self._source)
        if self.started and not self.paused:
            self._release_clicks(now)

    # -- internals -----------------------------------------------------------

    def _take_pings(self, now: int) -> List[MidiEvent]:
        pings = []
        while self._next_ping < len(self._pings) and self.tick_of(self._ping_times[self._next_ping]) <= now:
            pings.append(self._pings[self._next_ping])
            self._next_ping += 1
        return pings

    def _rewind(self, now: int) -> None:
        """After removing queued events, send again from the first event at
        or after ``now``.

        Events before ``now`` were played by the synth. An event exactly at
        ``now`` may or may not have been; sending it again at worst repeats a
        note-on at the same instant, while skipping it could leave a note
        hanging.
        """
        index = bisect.bisect_left(self._times, True, key=lambda t: self.tick_of(t) >= now)
        self._release_clicks(now, before=index)
        self._next = min(self._next, index)
        # Those note-ons were removed; their ticks must not delay note-offs.
        self._last_on.clear()

    def _release_clicks(self, now: int, before: Optional[int] = None) -> None:
        """Re-send note-offs for metronome clicks still ringing at ``now``.

        Their note-offs were among the removed events, but their note-ons
        come before the resend point.
        """
        i = (self._next if before is None else before) - 1
        while i >= 0 and self.tick_of(self._times[i]) + CLICK_TICKS > now:
            event = self._events[i]
            if event.event_type == MidiEventType.METRONOME_TICK and self.tick_of(event.timestamp) < now:
                self._seq.note_off(now, self._click.channel, self._click_note(event), self._source)
            i -= 1

    def _click_note(self, event: MidiEvent) -> int:
        if event.metadata.get('is_downbeat'):
            return self._click.downbeat_note
        return self._click.offbeat_note

    def _send(self, event: MidiEvent, tick: int) -> None:
        kind = event.event_type
        if kind == MidiEventType.NOTE_ON:
            for key in event.midi_notes:
                self._seq.note_on(tick, self._channel, key, event.velocity, self._source)
                self._last_on[key] = tick
        elif kind == MidiEventType.NOTE_OFF:
            for key in event.midi_notes:
                # FluidSynth plays a note-off before a note-on at the same
                # tick; keep a chord that rounds to zero length from hanging.
                off = max(tick, self._last_on.get(key, -1) + 1)
                self._seq.note_off(off, self._channel, key, self._source)
        elif kind == MidiEventType.METRONOME_TICK:
            downbeat = bool(event.metadata.get('is_downbeat'))
            velocity = self._click.downbeat_velocity if downbeat else self._click.offbeat_velocity
            note = self._click_note(event)
            self._seq.note_on(tick, self._click.channel, note, velocity, self._source)
            self._seq.note_off(tick + CLICK_TICKS, self._click.channel, note, self._source)
        # REST: silence; only its ping matters.
