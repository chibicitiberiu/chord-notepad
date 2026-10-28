"""Audio driver selection and host synth settings (no real FluidSynth).

pyfluidsynth's ``Synth.start()`` reports success even when the driver could
not be created, so the player creates the driver itself and checks the
handle; these tests drive that with a fake synth.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from audio.audio_options import AudioOptions, platform_drivers
from exceptions import AudioInitializationError


class FakeSynth:
    """Just enough of ``fluidsynth.Synth`` for ``_initialize_fluidsynth``.

    ``start()`` behaves like pyfluidsynth's: it always returns OK and leaves
    ``audio_driver`` as whatever FluidSynth returned (None for NULL).
    """

    def __init__(self, handles=None):
        self.kwargs = {}
        self.handles = handles or {}
        self.started = []
        self.audio_driver = None
        self.midi_driver = None
        self.deleted = False
        self.sfload_result = 1

    def setting(self, name, value):
        pass

    def start(self, driver=None, **kwargs):
        self.started.append(driver)
        self.audio_driver = self.handles.get(driver)
        self.midi_driver = None
        return 0

    def sfload(self, path):
        return self.sfload_result

    def program_select(self, *args):
        return 0

    def delete(self):
        self.deleted = True


def _bare_player():
    from audio.player import NotePlayer

    player = NotePlayer.__new__(NotePlayer)
    player.fs = None
    player.sfid = None
    player.channel = 0
    player.instrument = 0
    return player


def _init(player, synth, handles, options=None, platform="linux"):
    """Run _initialize_fluidsynth; ``handles`` maps driver name -> handle."""
    synth.handles = handles

    def make(**kwargs):
        synth.kwargs = kwargs
        return synth

    with patch("audio.player.fluidsynth.Synth", side_effect=make), \
            patch("audio.player.sys.platform", platform):
        player._initialize_fluidsynth("/x.sf2", options)
    return synth.started


class TestAudioOptions:

    def test_platform_lists(self):
        assert platform_drivers("linux") == ["pulseaudio", "alsa", "oss"]
        assert platform_drivers("android") == ["oboe", "opensles"]
        assert platform_drivers("win32") == ["dsound", "wasapi", "waveout"]
        assert platform_drivers("darwin") == ["coreaudio"]
        assert platform_drivers("freebsd14") == ["pulseaudio", "alsa", "oss"]

    def test_preferred_driver_goes_first_without_duplicates(self):
        assert AudioOptions(driver="alsa").driver_candidates("linux") == ["alsa", "pulseaudio", "oss"]
        assert AudioOptions(driver="jack").driver_candidates("linux") == ["jack", "pulseaudio", "alsa", "oss"]

    def test_no_preference_is_the_platform_list(self):
        assert AudioOptions().driver_candidates("android") == ["oboe", "opensles"]

    def test_synth_settings(self):
        options = AudioOptions(period_size=192, settings={"audio.oboe.performance-mode": "LowLatency"})
        assert options.synth_settings() == {
            "audio.oboe.performance-mode": "LowLatency",
            "audio.period-size": 192,
        }
        assert AudioOptions().synth_settings() == {}


class TestDriverSelection:

    def test_first_working_driver_is_used(self):
        player, synth = _bare_player(), FakeSynth()
        created = _init(player, synth, {"pulseaudio": 1234})
        assert created == ["pulseaudio"]
        assert player.driver_name == "pulseaudio"
        assert synth.audio_driver == 1234

    def test_null_driver_falls_back(self):
        # pulseaudio "starts" but FluidSynth returned NULL: try the next one
        player, synth = _bare_player(), FakeSynth()
        created = _init(player, synth, {"pulseaudio": None, "alsa": 99})
        assert created == ["pulseaudio", "alsa"]
        assert player.driver_name == "alsa"
        assert synth.audio_driver == 99

    def test_all_null_raises_and_releases_the_synth(self):
        player, synth = _bare_player(), FakeSynth()
        with pytest.raises(AudioInitializationError, match="No audio output.*pulseaudio, alsa, oss"):
            _init(player, synth, {})
        assert synth.deleted
        assert player.fs is None

    def test_configured_driver_is_tried_first(self):
        player, synth = _bare_player(), FakeSynth()
        created = _init(player, synth, {"jack": 7, "pulseaudio": 1}, AudioOptions(driver="jack"))
        assert created == ["jack"]
        assert player.driver_name == "jack"

    def test_failing_configured_driver_falls_back_to_platform_list(self):
        player, synth = _bare_player(), FakeSynth()
        created = _init(player, synth, {"pulseaudio": 5}, AudioOptions(driver="jack"))
        assert created == ["jack", "pulseaudio"]
        assert player.driver_name == "pulseaudio"

    def test_failed_start_frees_its_midi_driver(self):
        player, synth = _bare_player(), FakeSynth()
        original_start = synth.start

        def start(driver=None, **kwargs):
            result = original_start(driver, **kwargs)
            synth.midi_driver = f"midi-{driver}"
            return result

        synth.start = start
        with patch("audio.player.fluidsynth.delete_fluid_midi_driver") as delete:
            _init(player, synth, {"alsa": 2})
        delete.assert_called_once_with("midi-pulseaudio")
        assert synth.midi_driver == "midi-alsa"

    def test_android_tries_oboe_then_opensles(self):
        player, synth = _bare_player(), FakeSynth()
        created = _init(player, synth, {"opensles": 3}, platform="android")
        assert created == ["oboe", "opensles"]
        assert player.driver_name == "opensles"

    def test_host_settings_reach_the_synth(self):
        player, synth = _bare_player(), FakeSynth()
        options = AudioOptions(sample_rate=48000, period_size=96,
                               settings={"audio.oboe.performance-mode": "LowLatency"})
        _init(player, synth, {"pulseaudio": 1}, options)
        assert synth.kwargs == {
            "samplerate": 48000.0,
            "audio.period-size": 96,
            "audio.oboe.performance-mode": "LowLatency",
        }

    def test_desktop_default_passes_no_settings(self):
        player, synth = _bare_player(), FakeSynth()
        _init(player, synth, {"pulseaudio": 1})
        assert synth.kwargs == {}

    def test_bad_soundfont_raises(self):
        player, synth = _bare_player(), FakeSynth()
        synth.sfload_result = -1
        with pytest.raises(AudioInitializationError, match="soundfont"):
            _init(player, synth, {"pulseaudio": 1})
        assert synth.deleted

    def test_other_errors_are_wrapped(self):
        player = _bare_player()
        with patch("audio.player.fluidsynth.Synth", side_effect=OSError("no lib")):
            with pytest.raises(AudioInitializationError, match="no lib"):
                player._initialize_fluidsynth("/x.sf2")


class TestPlaybackServiceOptions:

    def _service(self, config_values, **kwargs):
        from services.config_service import ConfigService
        from services.playback_service import PlaybackService

        config = Mock(spec=ConfigService)
        config.get.side_effect = lambda key, default=None: config_values.get(key, default)
        return PlaybackService(config, **kwargs)

    def test_settings_driver_is_passed_first(self):
        service = self._service({"audio_driver": "alsa"})
        with patch("services.playback_service.NotePlayer") as cls:
            cls.return_value = MagicMock()
            assert service.initialize_player()
        assert cls.call_args.kwargs["options"] == AudioOptions(driver="alsa")

    def test_empty_settings_driver_means_platform_list(self):
        service = self._service({"audio_driver": None})
        with patch("services.playback_service.NotePlayer") as cls:
            cls.return_value = MagicMock()
            service.initialize_player()
        assert cls.call_args.kwargs["options"] == AudioOptions()

    def test_host_options_are_kept_for_lazy_init(self):
        host = AudioOptions(sample_rate=48000, settings={"audio.oboe.performance-mode": "LowLatency"})
        service = self._service({}, audio_options=host)
        with patch("services.playback_service.NotePlayer") as cls:
            cls.return_value = MagicMock()
            service.initialize_player()
        assert cls.call_args.kwargs["options"] == host

    def test_initialize_player_options_override_and_settings_driver_wins(self):
        service = self._service({"audio_driver": "opensles"})
        host = AudioOptions(driver="oboe", sample_rate=48000)
        with patch("services.playback_service.NotePlayer") as cls:
            cls.return_value = MagicMock()
            service.initialize_player(audio_options=host)
        assert cls.call_args.kwargs["options"] == AudioOptions(driver="opensles", sample_rate=48000)
