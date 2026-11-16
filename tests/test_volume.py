"""The playback volume (plan step B3): the music slider and mute.

``volume`` (config, 0.0-1.0) is the music's level only (Tibi, 2026-11-17:
"first should control music, second metronome"): it rides the chords'
channel volume (CC 7), 1.0 being the old loudness (CC 7 100), and the
output gain stays at 0.5. A mute that isn't saved silences everything
without moving the slider. Desktop only: nothing of it crosses the bridge.
"""

import json
import math
from unittest.mock import patch

import pytest

from chordnotepad.audio import volume
from chordnotepad.constants import AUDIO_GAIN
from chordnotepad.models.config import Config
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.session import bridge
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import DESKTOP_QT
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from tests.test_audio_driver_selection import FakeSynth, _bare_player, _init


def test_full_volume_is_the_loudness_the_app_always_had():
    assert AUDIO_GAIN == 0.5
    assert volume.output_gain() == AUDIO_GAIN and volume.output_gain(muted=True) == 0.0
    assert volume.music_cc(1.0) == 100        # General MIDI's default channel volume
    assert volume.music_cc(0.0) == 0
    assert volume.music_cc(0.5) == 50         # amplitude (cc/127)^2: a quarter, as before
    ccs = [volume.music_cc(i / 20) for i in range(21)]
    assert ccs == sorted(ccs) and len(set(ccs)) == 21
    for bad in (-0.01, 1.01, math.nan, True, "1"):
        with pytest.raises(ValueError):
            volume.music_cc(bad)


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf, True, "0.5", None])
def test_a_volume_is_a_number_from_0_to_1(bad):
    with pytest.raises(ValueError):
        volume.check_volume(bad)
    assert volume.volume_from_config(bad) == volume.DEFAULT_VOLUME


def test_the_config_key():
    assert Config().volume == 1.0 and Config().to_dict()["volume"] == 1.0
    assert Config.from_dict({"volume": 0.25}).volume == 0.25
    assert Config.from_dict({"volume": 0}).volume == 0.0
    for junk in (3, -1, "loud", [0.5], False):
        config = Config.from_dict({"volume": junk, "bpm": 90})
        assert config.volume == 1.0 and config.bpm == 90
    config = Config()
    config.volume = 1.5
    with pytest.raises(ValueError):
        config.validate()


# -- the player ---------------------------------------------------------------------


class RecordingSynth(FakeSynth):
    def __init__(self):
        super().__init__()
        self.settings = []

    def setting(self, name, value):
        self.settings.append((name, value))


def test_the_synth_starts_at_the_player_gain_and_follows_it_live():
    player = _bare_player()
    synth = RecordingSynth()
    _init(player, synth, {"pulseaudio": object()})
    assert ("synth.gain", AUDIO_GAIN) in synth.settings
    player.set_gain(0.2)
    assert synth.settings[-1] == ("synth.gain", 0.2) and player.gain == 0.2

    early = _bare_player()
    early.set_gain(0.1)                       # before the synth exists: kept
    synth = RecordingSynth()
    _init(early, synth, {"pulseaudio": object()})
    assert ("synth.gain", 0.1) in synth.settings
    assert ("synth.gain", AUDIO_GAIN) not in synth.settings


@pytest.mark.parametrize("bad", [-0.1, 10.5, True, "1"])
def test_the_player_refuses_a_gain_out_of_fluidsynths_range(bad):
    with pytest.raises(ValueError):
        _bare_player().set_gain(bad)


# -- through the session --------------------------------------------------------------


def make(tmp_path, config=None):
    if config is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(config))
    host = ManualHost()
    player = FakePlayer()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=player)
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=DESKTOP_QT)
    session.subscribe(EventRecorder())
    session.start()
    return session, services, player


def test_the_saved_volume_is_applied_at_start(tmp_path):
    session, _, player = make(tmp_path, {"volume": 0.5})
    assert session.volume == 0.5 and session.muted is False
    assert player.music_volume == 0.5 and player.gain == AUDIO_GAIN


def test_set_volume_saves_and_mute_doesnt(tmp_path):
    session, services, player = make(tmp_path)
    assert (player.gain, player.music_volume) == (AUDIO_GAIN, 1.0)
    session.set_volume(0.8)
    assert services.config.config.volume == 0.8
    assert (player.gain, player.music_volume) == (AUDIO_GAIN, 0.8)
    session.set_muted(True)
    assert (session.muted, session.volume, player.gain) == (True, 0.8, 0.0)
    session.set_volume(0.6)                   # the slider moves, still muted
    assert (session.volume, player.music_volume, player.gain) == (0.6, 0.6, 0.0)
    session.set_muted(False)
    assert (player.gain, player.music_volume) == (AUDIO_GAIN, 0.6)
    services.config.save_config()
    saved = json.loads(services.config.config_file_path.read_text())
    assert saved["volume"] == 0.6 and "muted" not in saved


@pytest.mark.parametrize("bad", [1.2, -0.5, math.nan])
def test_set_volume_refuses_out_of_range(tmp_path, bad):
    session, services, player = make(tmp_path)
    with pytest.raises(ValueError):
        session.set_volume(bad)
    assert services.config.config.volume == 1.0 and player.gain == AUDIO_GAIN
    assert player.music_volume == 1.0


def test_the_wheel_steps_5_percent_within_the_range_and_unmutes(tmp_path):
    session, _, player = make(tmp_path, {"volume": 0.9})
    session.set_muted(True)
    session.step_volume(1)
    assert (session.volume, session.muted) == (0.95, False)
    session.step_volume(3)
    assert session.volume == 1.0
    session.step_volume(-5)
    assert session.volume == 0.75
    session.step_volume(-40)
    assert session.volume == 0.0 and player.music_volume == 0.0
    for _ in range(3):
        session.step_volume(1)               # no float drift: 0.05, 0.1, 0.15
    assert session.volume == 0.15


def test_the_qt_window_reaches_it_through_the_bridge_with_plain_values():
    # The Qt SessionStore submits through the bridge (Android never does).
    assert bridge.SESSION_COMMANDS["set_volume"] == {"volume": "float"}
    assert bridge.SESSION_COMMANDS["step_volume"] == {"steps": "int"}
    assert bridge.SESSION_COMMANDS["set_muted"] == {"muted": "bool"}
    assert {"set_volume", "step_volume"} <= bridge.CONFIG_COMMANDS
    assert "set_muted" not in bridge.CONFIG_COMMANDS          # not saved
