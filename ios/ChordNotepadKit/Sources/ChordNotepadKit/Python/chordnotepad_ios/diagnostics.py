"""What the iOS app's diagnostics and self-test ask Python (docs/IOS.md, "Diagnostics").

Swift calls these through ``PythonRuntime.call`` on its bridge thread; each
takes strings and returns a JSON object as a string, so no Python object
crosses to Swift.

- :func:`enable_faulthandler`: a crash in native code (FluidSynth, a C
  extension) dumps every Python thread's stack into a file under Application
  Support, which the app shows in its Diagnostics folder at the next start.
- :func:`offline_render`: the self-test's synth check. It plays a chord on a
  FluidSynth synth with no audio driver (the core's audio export renderer,
  ``services.audio_export.FluidSynthRenderer``) and measures the samples, so
  it proves the framework, pyFluidSynth and the SoundFont work even where no
  audio device exists (CI's simulators).
- :func:`audio_status`: whether the running session's live player started,
  and why not.
"""

import faulthandler
import json
import time
from typing import Optional

#: Kept open for the process: faulthandler writes into it on a crash.
_fault_file = None

#: The chord the render plays: C major around middle C.
RENDER_NOTES = (60, 64, 67)
RENDER_VELOCITY = 100
RENDER_SECONDS = 0.5
RENDER_SAMPLE_RATE = 44100


def enable_faulthandler(path: str) -> str:
    """Dump every thread's traceback into ``path`` (appended) on a fatal signal.

    Returns:
        ``{"path": path}``.
    """
    global _fault_file
    if _fault_file is not None:
        _fault_file.close()
    _fault_file = open(path, "a", encoding="utf-8")
    _fault_file.write(f"-- faulthandler enabled {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    _fault_file.flush()
    faulthandler.enable(file=_fault_file, all_threads=True)
    return json.dumps({"path": path})


def offline_render(soundfont_path: str) -> str:
    """Render :data:`RENDER_NOTES` for :data:`RENDER_SECONDS` with no audio driver.

    Returns:
        ``{"ok", "peak", "frames", "seconds", "error"}``: ``peak`` is the
        largest 16-bit sample magnitude; ``ok`` means it isn't silent.
    """
    from chordnotepad.services import audio_export

    started = time.monotonic()
    result = {"ok": False, "peak": 0, "frames": 0, "seconds": 0.0, "error": None}
    synth: Optional[audio_export.FluidSynthRenderer] = None
    try:
        synth = audio_export.FluidSynthRenderer(soundfont_path, RENDER_SAMPLE_RATE)
        synth.setup(audio_export.AudioExportSettings(soundfont=soundfont_path))
        for key in RENDER_NOTES:
            synth.play(audio_export.PlannedEvent(0, audio_export.NOTE_ON, audio_export.MUSIC_CHANNEL,
                                                 key, RENDER_VELOCITY))
        wanted = int(RENDER_SECONDS * RENDER_SAMPLE_RATE)
        peak = 0
        frames = 0
        while frames < wanted:
            count = min(audio_export.BLOCK_FRAMES, wanted - frames)
            peak = max(peak, audio_export.peak(synth.render(count)))
            frames += count
        result.update(peak=peak, frames=frames, ok=peak >= audio_export.SILENCE_PEAK * 16)
        if not result["ok"]:
            result["error"] = f"The render is silent (peak {peak})"
    except Exception as e:  # reported to the self-test, not raised
        result["error"] = f"{type(e).__name__}: {e}"
    finally:
        if synth is not None:
            synth.delete()
    result["seconds"] = round(time.monotonic() - started, 3)
    return json.dumps(result)


def audio_status() -> str:
    """The running session's live player.

    Returns:
        ``{"session", "initialized", "error", "soundfont"}``; ``session`` is
        false before ``host.start``.
    """
    from chordnotepad_ios import host

    handle = host.current_handle
    if handle is None:
        return json.dumps({"session": False, "initialized": False, "error": "No session", "soundfont": None})
    playback = handle.services.playback
    return json.dumps({
        "session": True,
        "initialized": bool(playback.is_initialized),
        "error": playback.audio_error,
        "soundfont": playback.soundfont_in_use(),
    })
