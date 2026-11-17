"""Export audio: render a song to a WAV file the way Play sounds it.

The timing is song playback's own: the real :class:`SongScheduler` maps the
compiled song onto sequencer ticks, but into an :class:`OfflineSequencer`
that only records what it is sent. A FluidSynth synth with no audio driver
then plays those events and its samples go straight to a 16-bit stereo WAV
(stdlib ``wave``), block by block, with :data:`TAIL_SECONDS` after the last
event for the notes to ring out.

What Play would use is what the export uses: the voicing (the render), the
instrument, the music slider (the chords' CC 7), the metronome (always
scheduled, its channel's CC 7 at 0 while it is off, as live), the speed
multiplier and the SoundFont playback loaded. Mute doesn't apply: an export
is never silent on purpose.

No numpy: the builds leave it out. Samples come from our own ctypes
prototype of ``fluid_synth_write_s16`` (pyfluidsynth's returns a pointer and
its stereo helper needs numpy).
"""

import ctypes
import logging
import os
import time
import uuid
import wave
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from chordnotepad.audio.sequencer import TICKS_PER_SECOND
from chordnotepad.audio.song_scheduler import (
    CLICK_BANK, LOOKAHEAD_TICKS, PLAYER_CLICK, START_LEAD_TICKS, ClickSound, SongScheduler)
from chordnotepad.audio.volume import metronome_cc, music_cc
from chordnotepad.constants import AUDIO_GAIN
from chordnotepad.exceptions import AudioInitializationError, RenderAborted
from chordnotepad.models.playback_event_internal import MidiEvent

logger = logging.getLogger(__name__)

#: The WAV's sample rate.
SAMPLE_RATE = 44100
#: Frames asked of FluidSynth at a time (an abort is checked between blocks).
BLOCK_FRAMES = 4096
#: Silence rendered after the last event, for the release and the reverb.
TAIL_SECONDS = 2.0
#: Progress is reported each time it passes another step of this size.
PROGRESS_STEP = 0.05
#: The temp files an export renders into, in the cache folder.
TEMP_PREFIX = "audio-export-"
TEMP_SUFFIX = ".wav"
#: Temp files older than this are left over from a crash; newer ones may be
#: another instance's export in progress.
STALE_TEMP_SECONDS = 24 * 60 * 60

#: The chords' MIDI channel (the player's).
MUSIC_CHANNEL = 0
#: The sequencer client id the scheduler tags the song with (unused offline).
_SOURCE = 0

NOTE_ON = "on"
NOTE_OFF = "off"


@dataclass(frozen=True)
class PlannedEvent:
    """One event the synth plays, at a tick (ms from the start)."""

    tick: int
    kind: str          # NOTE_ON or NOTE_OFF
    channel: int
    key: int
    velocity: int = 0


@dataclass(frozen=True)
class AudioExportSettings:
    """What Play would sound like now, captured on the session thread.

    Attributes:
        soundfont: The SoundFont file (``PlaybackService.soundfont_in_use``).
        instrument: The chords' General MIDI program (bank 0).
        music_volume: The music slider, 0.0-1.0.
        metronome_volume: The metronome slider, 0.0-1.0.
        metronome_on: Whether the click sounds.
        multiplier: The speed multiplier.
    """

    soundfont: Optional[str]
    instrument: int = 0
    music_volume: float = 1.0
    metronome_volume: float = 1.0
    metronome_on: bool = False
    multiplier: float = 1.0


class OfflineSequencer:
    """A :class:`audio.song_scheduler.Sequencer` that records what it is sent.

    The scheduler only calls ``note_on``, ``note_off`` and ``remove`` (the
    last on pause, stop and a speed change, which an export never does).
    """

    def __init__(self) -> None:
        self.events: List[PlannedEvent] = []
        self._now = 0

    def now(self) -> int:
        """The tick the export has pumped to."""
        return self._now

    def advance(self, tick: int) -> None:
        """Move the clock (the export's pump loop)."""
        self._now = tick

    def note_on(self, tick: int, channel: int, key: int, velocity: int, source: int) -> None:
        self.events.append(PlannedEvent(tick, NOTE_ON, channel, key, velocity))

    def note_off(self, tick: int, channel: int, key: int, source: int) -> None:
        self.events.append(PlannedEvent(tick, NOTE_OFF, channel, key, 0))

    def remove(self, source: int) -> None:
        """Drop what hasn't "played" yet, as FluidSynth's queue would."""
        self.events = [e for e in self.events if e.tick < self._now]


def plan_events(events: Sequence[MidiEvent], multiplier: float = 1.0,
                click: ClickSound = PLAYER_CLICK) -> List[PlannedEvent]:
    """The synth events song playback would send for ``events``, in play order.

    The first event is at tick 0 (the scheduler is started
    :data:`START_LEAD_TICKS` early). At one tick, note-offs come before
    note-ons, as FluidSynth's sequencer plays them.

    Args:
        events: The compiled song (``compile_events``).
        multiplier: The speed multiplier.
        click: The metronome sound.
    """
    sequencer = OfflineSequencer()
    scheduler = SongScheduler(events, sequencer, source=_SOURCE, channel=MUSIC_CHANNEL,
                              click=click, multiplier=multiplier)
    scheduler.start(-START_LEAD_TICKS)
    now = 0
    while True:
        sequencer.advance(now)
        if scheduler.pump(now).finished:
            break
        now += LOOKAHEAD_TICKS
    order = sorted(range(len(sequencer.events)),
                   key=lambda i: (sequencer.events[i].tick,
                                  0 if sequencer.events[i].kind == NOTE_OFF else 1, i))
    return [sequencer.events[i] for i in order]


def frame_of(tick: int, sample_rate: int = SAMPLE_RATE) -> int:
    """The sample frame a tick falls on."""
    return max(0, int(round(tick * sample_rate / TICKS_PER_SECOND)))


def total_frames(planned: Sequence[PlannedEvent], sample_rate: int = SAMPLE_RATE) -> int:
    """How long the WAV of ``planned`` is: up to the last event, plus the tail."""
    end = frame_of(planned[-1].tick, sample_rate) if planned else 0
    return end + int(round(TAIL_SECONDS * sample_rate))


class FluidSynthRenderer:
    """A FluidSynth synth with no audio driver, rendered on demand.

    Args:
        soundfont: The .sf2 to load.
        sample_rate: Frames per second.

    Raises:
        AudioInitializationError: FluidSynth can't be loaded or the
            SoundFont can't be read.
    """

    def __init__(self, soundfont: str, sample_rate: int = SAMPLE_RATE) -> None:
        try:
            from chordnotepad.audio.fluidsynth_import import fluidsynth
        except Exception as e:      # no libfluidsynth: ImportError, OSError...
            raise AudioInitializationError(f"FluidSynth could not be loaded: {e}") from e
        self._synth = fluidsynth.Synth(gain=AUDIO_GAIN, samplerate=sample_rate)
        try:
            self._write = _write_s16(fluidsynth)
            self._sfid = self._synth.sfload(soundfont)
            if self._sfid is None or self._sfid < 0:
                raise AudioInitializationError(f"Could not load the soundfont: {soundfont}")
        except Exception:
            self.delete()
            raise
        self._buffer = (ctypes.c_int16 * (2 * BLOCK_FRAMES))()

    def setup(self, settings: AudioExportSettings) -> None:
        """Select the instrument and the click, at the sliders' levels."""
        self._synth.program_select(MUSIC_CHANNEL, self._sfid, 0, settings.instrument)
        self._synth.cc(MUSIC_CHANNEL, 7, music_cc(settings.music_volume))
        self._synth.program_select(PLAYER_CLICK.channel, self._sfid, CLICK_BANK, 0)
        self._synth.cc(PLAYER_CLICK.channel, 7,
                       metronome_cc(settings.metronome_volume, settings.metronome_on))

    def play(self, event: PlannedEvent) -> None:
        """Send one event to the synth, now."""
        if event.kind == NOTE_ON:
            self._synth.noteon(event.channel, event.key, event.velocity)
        else:
            self._synth.noteoff(event.channel, event.key)

    def render(self, frames: int) -> bytes:
        """The next ``frames`` (at most :data:`BLOCK_FRAMES`) as 16-bit
        little-endian interleaved stereo."""
        buffer = self._buffer
        result = self._write(self._synth.synth, frames, buffer, 0, 2, buffer, 1, 2)
        if result != 0:
            raise AudioInitializationError("FluidSynth failed to render audio.")
        return ctypes.string_at(buffer, frames * 4)

    def delete(self) -> None:
        """Free the synth (and its SoundFont)."""
        synth, self._synth = self._synth, None
        if synth is not None:
            synth.delete()


def _write_s16(module) -> Callable[..., int]:
    """``fluid_synth_write_s16`` with its real signature.

    A function pointer of our own (indexing the CDLL makes a new one), so
    pyfluidsynth's prototype stays as it is.
    """
    function = module._fl["fluid_synth_write_s16"]
    function.argtypes = [ctypes.c_void_p, ctypes.c_int,
                         ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                         ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    function.restype = ctypes.c_int
    return function


#: Builds the synth an export plays on (tests replace it).
open_synth: Callable[[str, int], FluidSynthRenderer] = FluidSynthRenderer


def write_wav(planned: Sequence[PlannedEvent], path: str, settings: AudioExportSettings,
              should_abort: Callable[[], bool] = lambda: False,
              progress: Callable[[float], None] = lambda fraction: None,
              sample_rate: int = SAMPLE_RATE) -> None:
    """Play ``planned`` on a synth and write the samples to ``path``.

    Args:
        planned: :func:`plan_events`' output.
        path: The WAV to write (replaced).
        settings: The SoundFont, instrument and levels.
        should_abort: Checked before every block.
        progress: Called with the fraction done (0.0-1.0) each time it
            passes another :data:`PROGRESS_STEP`, and with 1.0 at the end.

    Raises:
        AudioInitializationError: No SoundFont, or FluidSynth failed.
        RenderAborted: ``should_abort()`` said so; the file is left as it is.
        OSError: The file can't be written.
    """
    if not settings.soundfont or not os.path.exists(settings.soundfont):
        raise AudioInitializationError(
            f"Soundfont not found: {settings.soundfont}" if settings.soundfont
            else "No soundfont found. Choose one in Settings.")
    synth = open_synth(settings.soundfont, sample_rate)
    try:
        synth.setup(settings)
        total = total_frames(planned, sample_rate)
        written = 0
        reported = 0          # PROGRESS_STEPs reported so far
        with wave.open(path, "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(sample_rate)

            def render_to(frame: int) -> None:
                nonlocal written, reported
                while written < frame:
                    if should_abort():
                        raise RenderAborted("The audio export was stopped.")
                    count = min(BLOCK_FRAMES, frame - written)
                    out.writeframes(synth.render(count))
                    written += count
                    steps = int(written / total / PROGRESS_STEP + 1e-9)
                    if steps > reported and written < total:
                        reported = steps
                        progress(min(1.0, round(steps * PROGRESS_STEP, 6)))

            for event in planned:
                render_to(frame_of(event.tick, sample_rate))
                synth.play(event)
            render_to(total)
        progress(1.0)
    finally:
        synth.delete()


def temp_path(directory: str) -> str:
    """A new temp file name for an export, in ``directory`` (created)."""
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{TEMP_PREFIX}{uuid.uuid4().hex}{TEMP_SUFFIX}")


def remove_stale_temp_files(directory: str, max_age_s: float = STALE_TEMP_SECONDS,
                            now: Optional[float] = None) -> int:
    """Delete export temp files older than ``max_age_s`` (left by a crash).

    Newer ones stay: another instance may be exporting into them.

    Returns:
        How many were deleted.
    """
    now = time.time() if now is None else now
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    removed = 0
    for name in names:
        if not (name.startswith(TEMP_PREFIX) and name.endswith(TEMP_SUFFIX)):
            continue
        path = os.path.join(directory, name)
        try:
            if now - os.path.getmtime(path) > max_age_s:
                os.remove(path)
                removed += 1
        except OSError as e:
            logger.debug("Couldn't remove %s: %s", path, e)
    return removed
