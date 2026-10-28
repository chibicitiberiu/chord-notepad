"""Measure playback timing from the rendered audio (manual; not run in CI).

Plays a dense song (4 woodblock notes per second) through the real
``NotePlayer`` and FluidSynth's ``file`` audio driver, which renders in its
own thread at real-time pace and writes raw 16-bit PCM instead of sounding.
Optionally a busy Python thread spins the whole time, as a stand-in for a
chord-sheet render (GIL contention). Onsets are then found in the audio, so
the numbers include everything up to the synth's output, not just when
Python called ``noteon``.

Reported, like the M2 spike's table in docs/ANDROID.md:
- interval error: |actual gap - scheduled gap| between consecutive notes;
- drift: the last note's offset from the ideal grid anchored at the first;
- ping lateness (sequencer player only): how far past its tick each UI ping
  was posted.

Usage (from the repo root)::

    pipenv run python tests/perf/measure_playback_timing.py --seconds 60 [--busy]
    # the pre-Sequencer player, for comparison:
    git show 78a6e98:src/audio/player.py > /tmp/old_player.py
    pipenv run python tests/perf/measure_playback_timing.py --old-player /tmp/old_player.py

Nothing is played on the speakers. The raw file goes to ``--out``.
"""

import argparse
import array
import importlib.util
import os
import statistics
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from audio.audio_options import AudioOptions  # noqa: E402
from audio.event_buffer import EventBuffer  # noqa: E402
from models.playback_event_internal import MidiEvent, MidiEventType  # noqa: E402

SAMPLE_RATE = 44100
WOODBLOCK = 115  # GM program: short, sharp attack, decays in well under 250 ms
NOTE_KEY = 76


def dense_song(seconds: float, per_second: int = 4):
    """NOTE_ON/NOTE_OFF pairs on a regular grid, each pinging the UI."""
    events = []
    step = 1.0 / per_second
    count = int(seconds * per_second)
    for i in range(count):
        t = i * step
        meta = {'has_callback': True, 'chord_index': i}
        events.append(MidiEvent(t, MidiEventType.NOTE_ON, [NOTE_KEY], 110, meta))
        events.append(MidiEvent(t + 0.1, MidiEventType.NOTE_OFF, [NOTE_KEY], 0, {}))
    events.append(MidiEvent(count * step, MidiEventType.END_OF_SONG))
    return events, step


def busy_loop(stop: threading.Event) -> None:
    """Pure-Python work that holds the GIL as much as it can."""
    x = 0
    while not stop.is_set():
        for i in range(10000):
            x = (x * 31 + i) % 1000003


def make_old_player(path: str, raw: str):
    """The pre-Sequencer NotePlayer, on the file driver (bypassing its init)."""
    spec = importlib.util.spec_from_file_location("old_player", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from audio.fluidsynth_import import fluidsynth

    player = module.NotePlayer.__new__(module.NotePlayer)
    # Run __init__ with FluidSynth setup replaced, then set the synth up here.
    original = module.NotePlayer._initialize_fluidsynth
    module.NotePlayer._initialize_fluidsynth = lambda self, *a, **k: None
    try:
        player.__init__(soundfont_path=os.path.join(ROOT, "resources/soundfont/GeneralUser-GS.sf2"))
    finally:
        module.NotePlayer._initialize_fluidsynth = original
    fs = fluidsynth.Synth(gain=0.5, **{"audio.file.name": raw, "audio.file.type": "raw"})
    fs.start(driver="file")
    player.fs = fs
    player.sfid = fs.sfload(os.path.join(ROOT, "resources/soundfont/GeneralUser-GS.sf2"))
    fs.program_select(0, player.sfid, 0, 0)
    return player


def make_new_player(raw: str):
    from audio.player import NotePlayer

    options = AudioOptions(driver="file", settings={"audio.file.name": raw, "audio.file.type": "raw"})
    player = NotePlayer(options=options)
    assert player.driver_name == "file", player.driver_name
    return player


def onsets(raw: str, threshold: int = 2000, quiet_ms: float = 80.0):
    """Sample indices where the signal rises above ``threshold`` after quiet."""
    data = array.array("h")
    with open(raw, "rb") as fh:
        data.frombytes(fh.read())
    if sys.byteorder == "big":
        data.byteswap()
    left = data[0::2]
    quiet = int(SAMPLE_RATE * quiet_ms / 1000)
    found = []
    last_loud = -quiet - 1
    for i, v in enumerate(left):
        if v > threshold or v < -threshold:
            if i - last_loud > quiet:
                found.append(i)
            last_loud = i
    return found


def percentile(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, max(0, int(round(q / 100 * (len(s) - 1)))))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--busy", action="store_true", help="spin a busy Python thread meanwhile")
    parser.add_argument("--old-player", help="path to the pre-Sequencer player.py")
    parser.add_argument("--out", default=None, help="raw PCM output path")
    args = parser.parse_args()

    out = args.out or os.path.join(tempfile.mkdtemp(prefix="cn-timing-"), "out.raw")
    events, step = dense_song(args.seconds)

    player = make_old_player(args.old_player, out) if args.old_player else make_new_player(out)
    player.set_instrument(WOODBLOCK)

    ping_late = []
    seq = getattr(player, "_sequencer", None)

    def on_ping(ev):
        if seq is not None and player._scheduler is not None:
            due = player._scheduler.tick_of(ev.chord_index * step)
            ping_late.append(seq.now() - due)

    class App:
        def queue_ui_callback(self, cb):
            cb()

    buffer = EventBuffer(capacity=len(events) + 1)
    for e in events:
        buffer.push_event(e)
    player.set_event_buffer(buffer)
    player.set_event_callback(on_ping, App())
    done = threading.Event()
    player.set_playback_finished_callback(done.set)

    stop_busy = threading.Event()
    busy = threading.Thread(target=busy_loop, args=(stop_busy,), daemon=True)
    if args.busy:
        busy.start()
    time.sleep(0.3)
    player.start_playback()
    done.wait(args.seconds * 3 + 10)
    time.sleep(0.4)
    stop_busy.set()
    player.cleanup()

    found = onsets(out)
    expected = int(args.seconds / step)
    gaps = [(b - a) / SAMPLE_RATE * 1000 for a, b in zip(found, found[1:])]
    errors = [abs(g - step * 1000) for g in gaps]
    drift = ((found[-1] - found[0]) / SAMPLE_RATE - (len(found) - 1) * step) * 1000 if found else 0.0
    label = "old sleep loop" if args.old_player else "sequencer"
    print(f"{label}{' + busy thread' if args.busy else ''}: {len(found)}/{expected} notes, "
          f"{args.seconds:.0f} s")
    if errors:
        print("  interval error p50 / p90 / p99 / max (ms): "
              f"{percentile(errors, 50):.2f} / {percentile(errors, 90):.2f} / "
              f"{percentile(errors, 99):.2f} / {max(errors):.2f}")
        print(f"  drift after {args.seconds:.0f} s: {drift:+.1f} ms "
              f"(mean gap {statistics.mean(gaps):.3f} ms, scheduled {step * 1000:.0f})")
    if ping_late:
        print("  ping lateness p50 / p99 / max (ms): "
              f"{percentile(ping_late, 50)} / {percentile(ping_late, 99)} / {max(ping_late)}")
    print(f"  raw audio: {out}")


if __name__ == "__main__":
    main()
