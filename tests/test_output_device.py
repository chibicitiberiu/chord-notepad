"""Following the default output device (audio.output_device) and the player's
driver restart (no real FluidSynth; one real CoreAudio read on macOS)."""

import sys
import threading
from unittest.mock import patch

import pytest

from chordnotepad.audio import output_device
from chordnotepad.audio.output_device import OutputDeviceWatcher, default_output_device, needs_watch
from tests.test_audio_driver_selection import FakeSynth, _bare_player, _init


class Reads:
    """A ``read`` that returns the given values in turn, then the last one."""

    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class TestNeedsWatch:

    def test_only_macos_coreaudio_is_pinned(self):
        assert needs_watch("darwin", "coreaudio")
        assert not needs_watch("ios", "coreaudio")          # RemoteIO follows the route
        assert not needs_watch("linux", "pulseaudio")       # the sound server moves the stream
        assert not needs_watch("win32", "dsound")           # Windows stream routing
        assert not needs_watch("android", "oboe")           # Oboe reopens on disconnect
        assert not needs_watch("darwin", None)


class TestDefaultOutputDevice:

    def test_other_platforms_read_nothing(self):
        assert default_output_device("linux") is None
        assert default_output_device("win32") is None

    def test_a_coreaudio_error_reads_nothing(self):
        with patch.object(output_device, "_macos_default_output", side_effect=OSError("boom")):
            assert default_output_device("darwin") is None

    @pytest.mark.skipif(sys.platform != "darwin", reason="reads CoreAudio")
    def test_macos_reads_a_stable_device_id(self):
        first = default_output_device()
        if first is None:
            pytest.skip("this Mac has no output device")
        assert isinstance(first, int) and first > 0
        assert default_output_device() == first


class TestWatcher:

    def test_start_reads_the_current_device(self):
        watcher = OutputDeviceWatcher(lambda: None, read=lambda: 41, interval_s=60)
        assert watcher.start() and watcher.device == 41
        watcher.stop()

    def test_unreadable_device_means_no_thread(self):
        watcher = OutputDeviceWatcher(lambda: None, read=lambda: None)
        assert watcher.start() is False
        assert watcher._thread is None
        watcher.stop()  # harmless

    def test_change_calls_back_once(self):
        calls = []
        watcher = OutputDeviceWatcher(lambda: calls.append(1), read=Reads(1, 1, 2, 2))
        watcher._device = watcher._read()
        assert watcher.check() is False
        assert watcher.check() is True
        assert watcher.check() is False
        assert calls == [1] and watcher.device == 2

    def test_a_moment_without_a_device_is_not_a_change(self):
        calls = []
        watcher = OutputDeviceWatcher(lambda: calls.append(1), read=Reads(1, None, 1, None, 3))
        watcher._device = watcher._read()
        results = [watcher.check() for _ in range(4)]
        assert results == [False, False, False, True]
        assert calls == [1] and watcher.device == 3

    def test_callback_errors_are_logged_not_raised(self, caplog):
        def fail():
            raise RuntimeError("no driver")

        watcher = OutputDeviceWatcher(fail, read=Reads(1, 2))
        watcher._device = watcher._read()
        assert watcher.check() is True
        assert "Could not follow the new audio output" in caplog.text

    def test_thread_calls_back_and_stops(self):
        changed = threading.Event()
        watcher = OutputDeviceWatcher(changed.set, read=Reads(1, 2), interval_s=0.01)
        assert watcher.start()
        assert changed.wait(2.0)
        thread = watcher._thread
        watcher.stop()
        assert not thread.is_alive()


class FakeWatcher:
    instances = []

    def __init__(self, on_change, device=5):
        self.on_change = on_change
        self.device = device
        self.started = self.stopped = False
        FakeWatcher.instances.append(self)

    def start(self):
        self.started = True
        return self.device is not None

    def stop(self):
        self.stopped = True


@pytest.fixture
def fake_watcher():
    FakeWatcher.instances = []
    with patch("chordnotepad.audio.player.OutputDeviceWatcher", FakeWatcher):
        yield FakeWatcher


def _ready(platform="darwin", handles=None):
    player = _bare_player()
    player.is_playing = False
    player.is_paused = False
    player._audio_suspended = False
    player._driver_candidates = []
    player.driver_name = None
    synth = FakeSynth()
    synth.all_notes_off = lambda ch: None
    log = []
    _init(player, synth, handles or {"coreaudio": 7, "pulseaudio": 7}, platform=platform, log=log)
    player._sequencer.remove = lambda source: None
    player._click_source = 0
    return player, synth, log


class TestPlayerFollowsTheDevice:

    def test_macos_coreaudio_starts_a_watcher(self, fake_watcher):
        player, _, _ = _ready("darwin")
        assert player.driver_name == "coreaudio"
        [watcher] = fake_watcher.instances
        assert watcher.started and player._device_watcher is watcher
        assert watcher.on_change == player.restart_audio_driver

    def test_other_platforms_start_none(self, fake_watcher):
        player, _, _ = _ready("linux")
        assert fake_watcher.instances == [] and player._device_watcher is None

    def test_no_watcher_when_the_device_cant_be_read(self):
        class Unreadable(FakeWatcher):
            def __init__(self, on_change):
                super().__init__(on_change, device=None)

        with patch("chordnotepad.audio.player.OutputDeviceWatcher", Unreadable):
            player, _, _ = _ready("darwin")
        assert player._device_watcher is None

    def test_restart_reopens_the_same_driver(self, fake_watcher):
        player, synth, log = _ready("darwin")
        synth.started.clear()
        synth.handles = {"coreaudio": 9}
        with patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver",
                   side_effect=lambda h: log.append(("delete driver", h))):
            assert player.restart_audio_driver() is True
        assert log[-1] == ("delete driver", 7)
        assert synth.started == ["coreaudio"] and synth.audio_driver == 9
        assert player.fs is synth and not synth.deleted and player.sfid == 1

    def test_restart_works_while_a_song_plays(self, fake_watcher):
        player, synth, _ = _ready("darwin")
        player.is_playing = True
        synth.handles = {"coreaudio": 9}
        with patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver"):
            assert player.restart_audio_driver() is True
        assert synth.audio_driver == 9

    def test_restart_failure_leaves_no_driver_and_tries_again_later(self, fake_watcher):
        player, synth, _ = _ready("darwin")
        synth.handles = {}
        with patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver"):
            assert player.restart_audio_driver() is False
            assert synth.audio_driver is None and not player.audio_suspended
            synth.handles = {"coreaudio": 11}
            assert player.restart_audio_driver() is True
        assert synth.audio_driver == 11

    def test_restart_is_refused_while_suspended(self, fake_watcher):
        player, synth, _ = _ready("darwin")
        with patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver"):
            player.suspend_audio()
        synth.started.clear()
        assert player.restart_audio_driver() is False
        assert synth.started == []

    def test_restart_without_a_synth(self):
        assert _bare_player().restart_audio_driver() is False

    def test_release_stops_the_watcher_first(self, fake_watcher):
        player, synth, _ = _ready("darwin")
        [watcher] = fake_watcher.instances
        with patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver"):
            player._release_synth()
        assert watcher.stopped and player._device_watcher is None
        assert synth.deleted and player.fs is None
