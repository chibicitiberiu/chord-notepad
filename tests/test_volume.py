"""The playback volume (plan step B3): the player's gain, the slider and mute.

The gain was hard-coded at 0.5 in the player. Now ``volume`` (config,
0.0-1.0) sets it through a square curve, 1.0 being the old loudness, and a
mute that isn't saved silences without moving the slider. Desktop only:
nothing of it crosses the bridge.
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
    assert volume.gain_for(1.0) == AUDIO_GAIN
    assert volume.gain_for(0.0) == 0.0
    assert volume.gain_for(0.5) == pytest.approx(0.125)
    assert volume.gain_for(1.0, muted=True) == 0.0
    gains = [volume.gain_for(i / 20) for i in range(21)]
    assert gains == sorted(gains) and len(set(gains)) == 21


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
    assert player.gain == pytest.approx(0.125)


def test_set_volume_saves_and_mute_doesnt(tmp_path):
    session, services, player = make(tmp_path)
    assert player.gain == AUDIO_GAIN
    session.set_volume(0.8)
    assert services.config.config.volume == 0.8
    assert player.gain == pytest.approx(0.32)
    session.set_muted(True)
    assert (session.muted, session.volume, player.gain) == (True, 0.8, 0.0)
    session.set_volume(0.6)                   # the slider moves, still muted
    assert (session.volume, player.gain) == (0.6, 0.0)
    session.set_muted(False)
    assert player.gain == pytest.approx(0.18)
    services.config.save_config()
    saved = json.loads(services.config.config_file_path.read_text())
    assert saved["volume"] == 0.6 and "muted" not in saved


@pytest.mark.parametrize("bad", [1.2, -0.5, math.nan])
def test_set_volume_refuses_out_of_range(tmp_path, bad):
    session, services, player = make(tmp_path)
    with pytest.raises(ValueError):
        session.set_volume(bad)
    assert services.config.config.volume == 1.0 and player.gain == AUDIO_GAIN


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
    assert session.volume == 0.0 and player.gain == 0.0
    for _ in range(3):
        session.step_volume(1)               # no float drift: 0.05, 0.1, 0.15
    assert session.volume == 0.15


def test_volume_stays_off_the_bridge():
    commands = set(bridge.SESSION_COMMANDS) | set(bridge.CONFIG_COMMANDS)
    assert not {"set_volume", "step_volume", "set_muted"} & commands
