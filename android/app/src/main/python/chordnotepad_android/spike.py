"""M2 SPIKE CODE (throwaway): drives the core from the Compose test screen.

Every function takes and returns primitives / JSON strings, and is called on
the single Kotlin "python-dispatch" thread. The real bridge (M3) is the
AppSession event stream; nothing here is meant to survive the spike.

Timing probes (all wall times from time.monotonic_ns, which is the same
CLOCK_MONOTONIC as Kotlin's System.nanoTime):
- Play -> first note: Kotlin click time vs the first noteon of the song.
- Scheduling jitter: for every NOTE_ON event the player pops from its buffer,
  the noteon wall time vs (a) the ideal grid anchored at the first note and
  (b) the previous note (interval error). This is scheduling jitter only; the
  audio output path (Oboe buffers, mixer, DAC) is not included.
"""

import json
import logging
import os
import sys
import threading
import time

from chordnotepad_android import android_shim

logger = logging.getLogger("chordnotepad_android.spike")

_S = {}


def _ms(ns: int) -> float:
    return round(ns / 1e6, 3)


def _log(tag: str, payload) -> None:
    print(f"CNSPIKE {tag} {json.dumps(payload)}", flush=True)


def _proc_status() -> dict:
    out = {}
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith(("VmHWM", "VmRSS")):
                    key, value = line.split(":", 1)
                    out[key] = value.strip()
    except OSError:
        pass
    return out


def init(files_dir: str, soundfont_path: str, sample_rate: int, frames_per_buffer: int) -> str:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)s %(name)s: %(message)s")
    t0 = time.perf_counter_ns()
    android_shim.install(files_dir, sample_rate=int(sample_rate))
    t1 = time.perf_counter_ns()
    import music21  # noqa: F401  (timed on its own: the heaviest import)
    t2 = time.perf_counter_ns()
    from services.appdata_service import AppDataService
    from services.config_service import ConfigService
    from services.playback_service import PlaybackService
    from services.song_parser_service import SongParserService
    t3 = time.perf_counter_ns()

    appdata = AppDataService()
    appdata.ensure_directories_exist()
    config = ConfigService(appdata)
    config.load_config()
    _S["parser"] = SongParserService()
    _S["playback"] = PlaybackService(config)
    t4 = time.perf_counter_ns()
    ok = _S["playback"].initialize_player(soundfont_path)
    t5 = time.perf_counter_ns()

    result = {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "shim_ms": _ms(t1 - t0),
        "music21_import_ms": _ms(t2 - t1),
        "core_import_ms": _ms(t3 - t2),
        "services_ms": _ms(t4 - t3),
        "player_init_ms": _ms(t5 - t4),
        "audio_ok": ok,
        "audio_error": _S["playback"].audio_error,
        "driver": android_shim.STATE["driver"],
        "driver_attempts": android_shim.STATE["driver_attempts"],
        "sample_rate": sample_rate,
        "frames_per_buffer": frames_per_buffer,
        "proc": _proc_status(),
    }
    result["summary"] = (
        f"py {result['python']}, music21 {result['music21_import_ms']:.0f} ms, "
        f"core {result['core_import_ms']:.0f} ms, audio {result['driver']}"
    )
    _log("init", result)
    return json.dumps(result)


def _find_comments(text: str):
    import re
    return [(m.start(), m.end()) for m in re.finditer(r"//[^\n]*", text)]


def detect(text: str) -> str:
    t0 = time.perf_counter_ns()
    lines = _S["parser"].detect_chords_in_text(text, "american")
    t1 = time.perf_counter_ns()
    spans = [[s, e, "comment"] for s, e in _find_comments(text)]
    chords = []
    for line in lines:
        for c in line.chords:
            spans.append([c.start, c.end, "chord" if c.is_valid else "invalid"])
            chords.append(c)
        for d in line.directives:
            spans.append([d.start, d.end, "directive" if d.is_valid else "directive_invalid"])
    _S["lines"] = lines
    _S["chords"] = chords
    result = {"ms": _ms(t1 - t0), "chords": len(chords), "lines": len(lines),
              "spans": spans}
    _log("detect", {k: v for k, v in result.items() if k != "spans"})
    return json.dumps(result)


def measure_render() -> str:
    from audio.chord_picker import ChordNotePicker
    from services.event_compiler import compile_events
    from services.song_renderer import SongRenderer

    t0 = time.perf_counter_ns()
    rendered = SongRenderer().render(
        lines=_S["lines"], initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(), cancel_event=threading.Event(),
    )
    t1 = time.perf_counter_ns()
    events = compile_events(rendered, has_callback=True)
    t2 = time.perf_counter_ns()
    result = {"render_ms": _ms(t1 - t0), "compile_ms": _ms(t2 - t1),
              "chords": len(rendered.chords) if hasattr(rendered, "chords") else None,
              "events": len(events)}
    _log("render", result)
    return json.dumps(result)


# --- playback probes --------------------------------------------------------

def _install_probes(click_ns: int) -> None:
    from audio.event_buffer import EventBuffer

    probe = {"click_ns": click_ns, "notes": [], "last_event": {}, "first_note_ns": None,
             "finished": False}
    _S["probe"] = probe
    if not getattr(EventBuffer, "_cn_spike_patched", False):
        original_pop = EventBuffer.pop_event

        def pop_event(self, *args, **kwargs):
            event = original_pop(self, *args, **kwargs)
            if event is not None:
                _S["probe"]["last_event"][threading.get_ident()] = event
            return event

        EventBuffer.pop_event = pop_event
        EventBuffer._cn_spike_patched = True

    player = _S["playback"]._player
    fs = player.fs
    if not getattr(fs, "_cn_spike_patched", False):
        original_noteon = fs.noteon

        def noteon(chan, key, vel):
            now = time.monotonic_ns()
            wall = time.time()
            p = _S["probe"]
            r = original_noteon(chan, key, vel)
            if chan == player.channel:
                ev = p["last_event"].get(threading.get_ident())
                if ev is not None and (not p["notes"] or p["notes"][-1][0] is not ev):
                    p["notes"].append((ev, ev.timestamp, now, wall))
                    if p["first_note_ns"] is None:
                        p["first_note_ns"] = now
                if p.get("tap_click_ns") and p.get("tap_note_ns") is None:
                    p["tap_note_ns"] = now
            return r

        fs.noteon = noteon
        fs._cn_spike_patched = True


def _percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(q / 100 * (len(s) - 1)))))
    return round(s[idx], 3)


def _jitter_stats() -> dict:
    p = _S.get("probe")
    if not p or not p["notes"]:
        return {}
    notes = p["notes"]
    _, ts0, mono0, _ = notes[0]
    drift = []      # actual - ideal grid (ms); the core re-anchors per event, so this accumulates
    interval = []   # (actual gap - scheduled gap) (ms)
    for i, (_, ts, mono, _) in enumerate(notes):
        drift.append((mono - mono0) / 1e6 - (ts - ts0) * 1000.0)
        if i:
            _, pts, pmono, _ = notes[i - 1]
            interval.append((mono - pmono) / 1e6 - (ts - pts) * 1000.0)
    abs_int = [abs(v) for v in interval]
    return {
        "notes": len(notes),
        "span_s": round((notes[-1][2] - mono0) / 1e9, 2),
        "interval_err_ms": {"p50": _percentile(abs_int, 50), "p90": _percentile(abs_int, 90),
                            "p99": _percentile(abs_int, 99), "max": _percentile(abs_int, 100),
                            "mean": round(sum(interval) / len(interval), 3) if interval else None},
        "drift_ms": {"final": round(drift[-1], 3), "max": round(max(drift), 3),
                     "min": round(min(drift), 3)},
    }


def play_song(click_ns: int, lines=None, mode: str = "song") -> str:
    _install_probes(click_ns)
    t0 = time.monotonic_ns()

    def finished():
        _S["probe"]["finished"] = True

    ok = _S["playback"].start_song_playback(lines or _S["lines"], "C",
                                            on_finished_callback=finished)
    t1 = time.monotonic_ns()
    result = {"mode": mode, "started": ok, "click_to_call_ms": _ms(t0 - click_ns),
              "start_call_ms": _ms(t1 - t0)}
    _log("play", result)
    return json.dumps(result)


def play_dense(click_ns: int, seconds: int, metronome: bool, load: bool) -> str:
    """Play 4 chords per second (eighth notes at 120 BPM) for jitter statistics.

    ``metronome`` also schedules the click track (a threading.Timer per tick in
    today's player); ``load`` re-renders the sample song in a loop on another
    Python thread meanwhile, as a stand-in for a concurrent chord-sheet render
    competing for the GIL.
    """
    bars = max(1, int(seconds) // 2 + 1)
    text = "{bpm: 120} {time: 4/4}\n" + "C*0.5 G*0.5 Am*0.5 F*0.5 C*0.5 G*0.5 Am*0.5 F*0.5\n" * bars
    lines = _S["parser"].detect_chords_in_text(text, "american")
    _S["playback"].set_metronome_enabled(bool(metronome))
    _stop_load()
    if load:
        _start_load()
    mode = f"dense metronome={bool(metronome)} load={bool(load)}"
    return play_song(click_ns, lines=lines, mode=mode)


def _start_load() -> None:
    from audio.chord_picker import ChordNotePicker
    from services.song_renderer import SongRenderer

    stop_flag = threading.Event()
    counter = {"renders": 0}

    def loop():
        while not stop_flag.is_set():
            SongRenderer().render(
                lines=_S["lines"], initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
                note_picker=ChordNotePicker(), cancel_event=threading.Event(),
            )
            counter["renders"] += 1

    thread = threading.Thread(target=loop, daemon=True, name="spike-load")
    _S["load"] = (stop_flag, counter)
    thread.start()


def _stop_load() -> dict:
    load = _S.pop("load", None)
    if not load:
        return {}
    load[0].set()
    return {"background_renders": load[1]["renders"]}


def play_chord_at(offset: int, click_ns: int) -> str:
    chords = _S.get("chords") or []
    chord = next((c for c in chords if c.start <= offset < c.end), None)
    if chord is None:
        chord = next((c for c in chords if c.start >= offset), None)
    if chord is None:
        return json.dumps({"chord": None})
    probe = _S.get("probe")
    if probe is None:
        _install_probes(0)
        probe = _S["probe"]
    probe["tap_click_ns"] = click_ns
    probe["tap_note_ns"] = None
    t0 = time.monotonic_ns()
    _S["playback"].play_chord_immediate(chord, "C")
    t1 = time.monotonic_ns()
    tap_note = probe.get("tap_note_ns")
    probe["tap_click_ns"] = None
    result = {"chord": chord.chord,
              "click_to_python_ms": _ms(t0 - click_ns),
              "python_call_ms": _ms(t1 - t0),
              "tap_to_noteon_ms": _ms(tap_note - click_ns) if tap_note else None}
    _log("chord", result)
    return json.dumps(result)


def stop() -> str:
    t0 = time.monotonic_ns()
    _S["playback"].stop_playback()
    result = {"stop_ms": _ms(time.monotonic_ns() - t0)}
    result.update(_stop_load())
    _S["playback"].set_metronome_enabled(False)
    return json.dumps(result)


def report() -> str:
    p = _S.get("probe") or {}
    first = p.get("first_note_ns")
    click = p.get("click_ns")
    result = {
        "playing": bool(_S.get("playback") and _S["playback"].is_playing),
        "finished": p.get("finished"),
        "play_to_first_note_ms": _ms(first - click) if first and click else None,
        "jitter": _jitter_stats(),
        "proc": _proc_status(),
        "threads": threading.active_count(),
    }
    return json.dumps(result)


def set_switch_interval(ms: float) -> str:
    """Experiment: a shorter GIL switch interval (default 5 ms) for the player thread."""
    sys.setswitchinterval(float(ms) / 1000.0)
    return json.dumps({"switch_interval_ms": sys.getswitchinterval() * 1000.0})


def op_buffer() -> str:
    """Optional op-buffer probe: the chord-sheet renderers live in src/ui/chord_sheet,
    which the APK excludes (ui/**), and clef_assets imports PIL at module level."""
    try:
        import ui.chord_sheet.staff_card  # noqa: F401
    except Exception as exc:  # expected in the M2 build
        return json.dumps({"available": False, "error": f"{type(exc).__name__}: {exc}"})
    return json.dumps({"available": True})
