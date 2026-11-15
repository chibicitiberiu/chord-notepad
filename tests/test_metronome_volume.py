"""The metronome's own volume (Tibi, 2026-11-15: "a second volume slider for
the metronome? realized it's hard to hear").

``metronome_volume`` (config, 0.0-1.0) rides the click channel's CC 7, live;
the volume and mute still apply to the click too. Rendered through the file
driver, the old click (velocity 100, CC 7 100, a wood block panned right)
peaked 4 dB under a piano chord and its loudest 50 ms were 12 dB under; now
the downbeat has full velocity and 100% is CC 7 127, 8 dB louder than
before (the old click is the slider near 60%). Desktop only: nothing of it
is on a bridge state.
"""

import json
import math

import pytest

from chordnotepad.audio import volume
from chordnotepad.audio.player import NotePlayer
from chordnotepad.audio.song_scheduler import ClickSound
from chordnotepad.models.config import Config
from chordnotepad.session import bridge
from tests.test_audio_driver_selection import FakeSynth, _bare_player, _init
from tests.test_volume import make

DRUMS = NotePlayer.METRONOME_DRUM_CHANNEL


def test_the_slider_maps_to_the_click_channels_volume():
    assert volume.metronome_cc(1.0) == 127
    assert volume.metronome_cc(0.0) == 0
    assert volume.metronome_cc(0.5) == 64
    assert volume.metronome_cc(1.0, enabled=False) == 0
    ccs = [volume.metronome_cc(i / 20) for i in range(21)]
    assert ccs == sorted(ccs) and len(set(ccs)) == 21
    for bad in (-0.01, 1.01, math.nan, True, "1"):
        with pytest.raises(ValueError):
            volume.metronome_cc(bad)


def test_the_config_key():
    assert Config().metronome_volume == 1.0 and Config().to_dict()["metronome_volume"] == 1.0
    assert Config.from_dict({"metronome_volume": 0.4}).metronome_volume == 0.4
    for junk in (3, -1, "loud", None, False):
        config = Config.from_dict({"metronome_volume": junk, "volume": 0.5})
        assert config.metronome_volume == 1.0 and config.volume == 0.5
    config = Config()
    config.metronome_volume = 1.5
    with pytest.raises(ValueError):
        config.validate()


# -- the player ---------------------------------------------------------------------


class CcSynth(FakeSynth):
    def __init__(self):
        super().__init__()
        self.ccs = []
        self.gain = None

    def setting(self, name, value):
        if name == "synth.gain":
            self.gain = value

    def cc(self, channel, control, value):
        self.ccs.append((channel, control, value))
        return 0

    def last_cc(self, channel, control=7):
        return [v for c, k, v in self.ccs if (c, k) == (channel, control)][-1]


def started_player():
    player = _bare_player()
    synth = CcSynth()
    _init(player, synth, {"pulseaudio": object()})
    return player, synth


def test_the_music_channel_and_the_gain_are_untouched():
    player, synth = started_player()
    assert [c for c in synth.ccs if c[0] == player.channel] == []
    assert synth.gain == player.gain


def test_the_click_channel_follows_the_switch_and_the_slider_live():
    player, synth = started_player()
    player.set_metronome_enabled(True)
    assert synth.last_cc(DRUMS) == 127        # the default level: full
    player.set_metronome_volume(0.5)
    assert synth.last_cc(DRUMS) == 64
    player.set_metronome_enabled(False)
    assert synth.last_cc(DRUMS) == 0
    player.set_metronome_volume(0.8)          # off: kept, still silent
    assert synth.last_cc(DRUMS) == 0 and player.metronome_volume == 0.8
    player.set_metronome_enabled(True)
    assert synth.last_cc(DRUMS) == volume.metronome_cc(0.8) == 102
    with pytest.raises(ValueError):
        player.set_metronome_volume(1.5)
    assert player.metronome_volume == 0.8


def test_a_level_set_before_the_synth_is_used_when_it_starts():
    player = _bare_player()
    player.set_metronome_volume(0.25)         # no synth yet: kept
    player.set_metronome_enabled(True)
    synth = CcSynth()
    _init(player, synth, {"pulseaudio": object()})
    player._ensure_drum_channel()
    assert synth.last_cc(DRUMS) == volume.metronome_cc(0.25)


def test_the_click_is_louder_full_velocity_on_the_downbeat():
    player, _ = started_player()
    assert player.click_sound == ClickSound(channel=9, downbeat_note=76, offbeat_note=77,
                                            downbeat_velocity=127, offbeat_velocity=102)


# -- through the session --------------------------------------------------------------


def test_the_saved_level_is_applied_at_start(tmp_path):
    session, _, player = make(tmp_path, {"metronome_volume": 0.3})
    assert session.metronome_volume == 0.3 and player.metronome_volume == 0.3


def test_set_metronome_volume_saves_and_is_live_while_playing(tmp_path):
    session, services, player = make(tmp_path)
    assert player.metronome_volume == 1.0
    player.auto_play = False
    session.set_text("{bpm: 120}\nC G Am F\n")
    session.toggle_metronome()
    session.play_pause(None)
    services.playback._render_thread.join(5)
    assert player.is_playing
    session.set_metronome_volume(0.35)
    assert player.metronome_volume == 0.35 and player.is_playing
    assert services.config.config.metronome_volume == 0.35
    gain = player.gain
    session.set_metronome_volume(0.7)         # the music's gain doesn't move
    assert player.gain == gain
    services.config.save_config()
    saved = json.loads(services.config.config_file_path.read_text())
    assert saved["metronome_volume"] == 0.7


@pytest.mark.parametrize("bad", [1.2, -0.5, math.nan])
def test_set_metronome_volume_refuses_out_of_range(tmp_path, bad):
    session, services, player = make(tmp_path)
    with pytest.raises(ValueError):
        session.set_metronome_volume(bad)
    assert services.config.config.metronome_volume == 1.0 and player.metronome_volume == 1.0


def test_the_qt_window_reaches_it_through_the_bridge():
    assert bridge.SESSION_COMMANDS["set_metronome_volume"] == {"volume": "float"}
    assert "set_metronome_volume" in bridge.CONFIG_COMMANDS
