"""audio/fluid_ctypes.py: finding libfluidsynth, and the binding on the real library.

The lookup tests run everywhere (the platform, environment and file checks
are passed in). The rest needs the system's libfluidsynth and the bundled
SoundFont, and renders offline: no audio driver, nothing plays.
"""

import array
import ctypes
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from chordnotepad.exceptions import AudioInitializationError

REPO = Path(__file__).resolve().parent.parent
SOUNDFONT = REPO / "resources" / "soundfont" / "GeneralUser-GS.sf2"
RATE = 44100

try:
    from chordnotepad.audio import fluid_ctypes
except (ImportError, OSError) as e:      # no libfluidsynth here
    fluid_ctypes = None
    LOAD_ERROR = e

needs_library = pytest.mark.skipif(fluid_ctypes is None, reason="libfluidsynth not installed")
needs_soundfont = pytest.mark.skipif(fluid_ctypes is None or not SOUNDFONT.exists(),
                                     reason="needs libfluidsynth and the bundled SoundFont")


def _loader():
    if fluid_ctypes is None:
        pytest.skip("libfluidsynth not installed")
    return fluid_ctypes


def _no_library(name):
    return None


# -- finding the library ------------------------------------------------------------


def test_the_env_path_wins_when_the_file_exists():
    fc = _loader()
    env = {fc.LIBRARY_ENV: "/snap/app/usr/lib/libfluidsynth.so.3"}
    assert fc.resolve_library(env, "linux", find=_no_library,
                              exists=lambda p: p == env[fc.LIBRARY_ENV]) == env[fc.LIBRARY_ENV]


def test_a_missing_env_path_falls_back_to_the_lookup(caplog):
    fc = _loader()
    env = {fc.LIBRARY_ENV: "/nonexistent/libfluidsynth.so.3"}
    found = fc.resolve_library(env, "linux", find=lambda name: "libfluidsynth.so.3",
                               exists=lambda p: False)
    assert found == "libfluidsynth.so.3"
    assert "missing file" in caplog.text


def test_a_bare_soname_goes_to_the_linker_as_it_is():
    fc = _loader()
    env = {fc.LIBRARY_ENV: "libfluidsynth-custom.so"}
    assert fc.resolve_library(env, "linux", find=_no_library, exists=lambda p: False) == \
        "libfluidsynth-custom.so"


def test_android_defaults_to_the_soname_and_the_env_wins():
    fc = _loader()
    assert fc.requested_library({}, "android") == fc.ANDROID_SONAME
    assert fc.requested_library({fc.LIBRARY_ENV: "libfluidsynth-custom.so"}, "android") == \
        "libfluidsynth-custom.so"


def test_ios_without_the_env_is_an_audio_error():
    fc = _loader()
    with pytest.raises(AudioInitializationError, match="CHORD_NOTEPAD_LIBFLUIDSYNTH is not set"):
        fc.resolve_library({}, "ios", find=_no_library)
    path = "/var/app/Frameworks/FluidSynth.framework/FluidSynth"
    assert fc.resolve_library({fc.LIBRARY_ENV: path}, "ios", exists=lambda p: True) == path


def test_the_desktop_without_env_uses_the_lookup():
    fc = _loader()
    assert fc.requested_library({}, "linux") == ""
    assert fc.resolve_library({}, "linux", find=lambda name: f"lib{name}.so.3") == "libfluidsynth.so.3"


def test_windows_finds_the_dll_on_path_then_in_the_tools_folder():
    fc = _loader()
    asked = []

    def find(name):
        asked.append(name)
        return r"C:\app\fluidsynth\libfluidsynth-3.dll" if name == "libfluidsynth-3" else None

    assert fc.find_system_library("win32", {}, find=find) == r"C:\app\fluidsynth\libfluidsynth-3.dll"
    assert asked == ["libfluidsynth-3"]
    tools = os.path.join(fc.WINDOWS_TOOLS_DIR, "libfluidsynth-3.dll")
    assert fc.find_system_library("win32", {}, find=_no_library, exists=lambda p: p == tools) == tools
    assert fc.find_system_library("win32", {}, find=_no_library, exists=lambda p: False) is None


def test_macos_falls_back_to_homebrew():
    fc = _loader()
    brew = "/opt/custom-brew/lib/libfluidsynth.dylib"
    assert fc.find_system_library("darwin", {"HOMEBREW_PREFIX": "/opt/custom-brew"},
                                  find=_no_library, exists=lambda p: p == brew) == brew
    default = "/opt/homebrew/lib/libfluidsynth.dylib"
    assert fc.find_system_library("darwin", {}, find=_no_library,
                                  exists=lambda p: p == default) == default
    assert fc.find_system_library("darwin", {}, find=lambda name: "/usr/local/lib/libfluidsynth.3.dylib") == \
        "/usr/local/lib/libfluidsynth.3.dylib"


def test_nothing_found_is_an_import_error_with_the_message_the_smoke_test_reads():
    fc = _loader()
    with pytest.raises(ImportError, match="Couldn't find the FluidSynth library"):
        fc.resolve_library({}, "linux", find=_no_library, exists=lambda p: False)
    # packaging/macos/smoke_test.sh greps the app's log for it.
    assert fc.NOT_FOUND.rstrip(".") in (REPO / "packaging/macos/smoke_test.sh").read_text(encoding="utf-8")


@needs_library
def test_the_env_path_loads_the_real_library():
    real = fluid_ctypes.LIBRARY_PATH
    library, used = fluid_ctypes.load_library({fluid_ctypes.LIBRARY_ENV: real}, sys.platform)
    assert used == real and hasattr(library, "new_fluid_synth")


# -- the synth, rendered offline ------------------------------------------------------


def _float_block(frames):
    return (ctypes.c_float * (2 * frames))()


def _render(synth, frames, block=512):
    """``frames`` of interleaved stereo floats, rendered block by block."""
    out = array.array("f")
    buffer = _float_block(block)
    left = frames
    while left > 0:
        n = min(block, left)
        assert synth.write_float(n, buffer) == fluid_ctypes.FLUID_OK
        out.extend(buffer[:2 * n])
        left -= n
    return out


#: Below this a float block counts as silence (no note has started).
SILENT = 1e-4


def _peak(samples):
    return max((abs(s) for s in samples), default=0.0)


@pytest.fixture
def synth():
    synth = fluid_ctypes.Synth(gain=0.5, samplerate=RATE)
    yield synth
    synth.delete()


@needs_library
def test_a_synth_with_no_driver(synth):
    assert synth.synth and synth.settings and synth.audio_driver is None
    assert synth.setting("synth.gain", 0.3) is True
    assert synth.setting("no.such.setting", 1) is False
    assert synth.setting("synth.gain", 1) is False      # an int for a number setting, as before
    with pytest.raises(TypeError):
        synth.setting("synth.gain", None)


@needs_soundfont
def test_sfload_presets_and_a_note_render_sound(synth):
    sfid = synth.sfload(str(SOUNDFONT))
    assert sfid >= 1
    assert synth.sfload(str(REPO / "no-such.sf2")) == fluid_ctypes.FLUID_FAILED
    assert synth.program_select(0, sfid, 0, 0) == fluid_ctypes.FLUID_OK
    assert "piano" in synth.sfpreset_name(sfid, 0, 0).lower()
    assert synth.sfpreset_name(sfid, 77, 0) is None
    assert synth.sfpreset_name(sfid + 50, 0, 0) is None

    assert _peak(_render(synth, 2048)) < SILENT
    assert synth.cc(0, 7, 100) == fluid_ctypes.FLUID_OK
    assert synth.noteon(0, 60, 100) == fluid_ctypes.FLUID_OK
    sounding = _render(synth, RATE // 4)
    assert _peak(sounding) > 0.01
    assert synth.noteoff(0, 60) == fluid_ctypes.FLUID_OK
    assert synth.all_notes_off(-1) == fluid_ctypes.FLUID_OK


@needs_soundfont
def test_write_s16_fills_a_ctypes_buffer(synth):
    sfid = synth.sfload(str(SOUNDFONT))
    synth.program_select(0, sfid, 0, 0)
    synth.noteon(0, 64, 110)
    buffer = (ctypes.c_int16 * 2048)()
    assert synth.write_s16(1024, buffer) == fluid_ctypes.FLUID_OK
    assert max(abs(s) for s in buffer) > 100
    with pytest.raises(ValueError):
        synth.write_s16(2048, buffer)       # too small
    with pytest.raises(ValueError):
        synth.write_s16(16, _float_block(16))   # the wrong sample type


@needs_library
def test_an_unknown_driver_fails_and_leaves_no_handle(synth):
    assert synth.start(driver="no-such-driver") == fluid_ctypes.FLUID_FAILED
    assert synth.audio_driver is None
    synth.stop()


@needs_soundfont
def test_the_sequencer_plays_a_note_at_its_tick(synth):
    if not fluid_ctypes.HAS_SEQUENCER:
        pytest.skip("this FluidSynth has no sequencer")
    sfid = synth.sfload(str(SOUNDFONT))
    synth.program_select(0, sfid, 0, 0)
    sequencer = fluid_ctypes.Sequencer(time_scale=1000, use_system_timer=False)
    try:
        dest = sequencer.register_synth(synth)
        source = sequencer.register_source("test-source")
        other = sequencer.register_source("test-other")
        assert len({dest, source, other}) == 3
        assert sequencer.get_tick() == 0
        assert sequencer.note_on(500, 0, 60, 110, source, dest) == fluid_ctypes.FLUID_OK
        assert sequencer.note_off(800, 0, 60, source, dest) == fluid_ctypes.FLUID_OK
        # Removed before it plays: only the first source's note sounds.
        sequencer.note_on(200, 0, 72, 110, other, dest)
        sequencer.remove_events(other)

        samples = _render(synth, RATE)          # one second
        assert 990 <= sequencer.get_tick() <= 1010   # the clock follows the rendered audio
        onset = RATE // 2                       # tick 500
        # Events land on FluidSynth's 64-frame blocks, so allow two blocks early.
        assert _peak(samples[:2 * (onset - 128)]) < SILENT
        assert _peak(samples[2 * onset:2 * (onset + RATE // 50)]) > 0.01   # within 20 ms
    finally:
        sequencer.delete()
        sequencer.delete()                      # safe twice


@needs_library
def test_cleanup_is_safe_twice():
    synth = fluid_ctypes.Synth()
    sequencer = fluid_ctypes.Sequencer()
    sequencer.register_synth(synth)
    sequencer.delete()                          # before the synth: it calls the sequencer's timer
    sequencer.delete()
    synth.delete()
    synth.delete()
    assert synth.synth is None and synth.settings is None and synth.audio_driver is None
    fluid_ctypes.delete_fluid_audio_driver(None)


# -- nothing imports pyFluidSynth -----------------------------------------------------

_BLOCK_PROBE = r"""
import os, sys
sys.path[:0] = sys.argv[1].split(os.pathsep)
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == "fluidsynth" or name.startswith("fluidsynth."):
            raise ModuleNotFoundError("fluidsynth is blocked")
        return None
sys.meta_path.insert(0, _Block())
import chordnotepad.audio.fluid_ctypes
import chordnotepad.audio.player, chordnotepad.audio.sequencer
import chordnotepad.services, chordnotepad.services.playback_service, chordnotepad.services.audio_export
import chordnotepad.session.session, chordnotepad.session.bootstrap, chordnotepad.session.embedded_host
from chordnotepad.services.audio_export import FluidSynthRenderer
FluidSynthRenderer(sys.argv[2]).delete()
print("fluidsynth" in sys.modules)
"""


@needs_soundfont
def test_the_core_runs_with_pyfluidsynth_blocked():
    paths = os.pathsep.join(str(REPO / p) for p in ("core", "desktop"))
    out = subprocess.run([sys.executable, "-I", "-c", _BLOCK_PROBE, paths, str(SOUNDFONT)],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines()[-1:] == ["False"]


_PYTHON_TREES = ["core", "desktop", "android/app/src/main/python", "ios", "hooks", "packaging", "tests"]
_IMPORTS = re.compile(r"^\s*(import\s+fluidsynth\b|from\s+fluidsynth\b)", re.MULTILINE)


def _python_sources():
    """The tracked .py files under _PYTHON_TREES (every one, outside a git checkout)."""
    try:
        listed = subprocess.run(["git", "-C", str(REPO), "ls-files", "--", *_PYTHON_TREES],
                                capture_output=True, text=True, timeout=60, check=True).stdout
        return [REPO / name for name in listed.splitlines() if name.endswith(".py")]
    except (OSError, subprocess.SubprocessError):
        return [path for tree in _PYTHON_TREES for path in (REPO / tree).rglob("*.py")
                if "build" not in path.relative_to(REPO).parts]


def test_no_source_imports_the_fluidsynth_package():
    sources = _python_sources()
    assert any(p.name == "fluid_ctypes.py" for p in sources)
    hits = [str(p.relative_to(REPO)) for p in sources
            if p.exists() and _IMPORTS.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert hits == []
