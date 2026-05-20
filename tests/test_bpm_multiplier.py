"""Tests for the BPM multiplier feature."""

import pytest
from unittest.mock import Mock

from models.config import Config
from services.playback_service import PlaybackService
from services.config_service import ConfigService


class TestConfigMultiplier:
    def test_default_is_one(self):
        cfg = Config()
        assert cfg.bpm_multiplier == 1.0
        cfg.validate()

    def test_validate_rejects_too_low(self):
        cfg = Config(bpm_multiplier=0.0)
        with pytest.raises(ValueError):
            cfg.validate()

    def test_validate_rejects_too_high(self):
        cfg = Config(bpm_multiplier=10.0)
        with pytest.raises(ValueError):
            cfg.validate()

    def test_validate_accepts_extremes(self):
        Config(bpm_multiplier=0.125).validate()
        Config(bpm_multiplier=4.0).validate()

    def test_roundtrip_via_dict(self):
        cfg = Config(bpm_multiplier=1.5)
        data = cfg.to_dict()
        assert data["bpm_multiplier"] == 1.5
        restored = Config.from_dict(data)
        assert restored.bpm_multiplier == 1.5

    def test_missing_in_dict_defaults_to_one(self):
        cfg = Config.from_dict({})
        assert cfg.bpm_multiplier == 1.0


class TestPlaybackServiceMultiplier:
    def test_set_bpm_multiplier_forwards_to_player_and_config(self):
        config = Mock(spec=ConfigService)
        config.get.return_value = "piano"
        player = Mock()
        service = PlaybackService(config_service=config, player=player)

        service.set_bpm_multiplier(1.5)

        player.set_bpm_multiplier.assert_called_once_with(1.5)
        config.set.assert_any_call("bpm_multiplier", 1.5)


class TestNotePlayerMultiplier:
    """Direct tests on the NotePlayer's multiplier-aware scheduling logic.

    These avoid initializing FluidSynth by patching the constructor.
    """

    def _make_player(self):
        from audio import player as player_mod

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(player_mod.NotePlayer, "_initialize_fluidsynth", lambda *a, **kw: None)
            mp.setattr(player_mod.NotePlayer, "_find_soundfont", lambda self: "fake.sf2")
            mp.setattr(player_mod.os.path, "exists", lambda _p: True)
            return player_mod.NotePlayer(soundfont_path="fake.sf2")

    def test_default_multiplier_is_one(self):
        p = self._make_player()
        assert p._bpm_multiplier == 1.0

    def test_set_bpm_multiplier_updates_field(self):
        p = self._make_player()
        p.set_bpm_multiplier(2.0)
        assert p._bpm_multiplier == 2.0

    def test_set_bpm_multiplier_rejects_nonpositive(self):
        p = self._make_player()
        p.set_bpm_multiplier(0)
        assert p._bpm_multiplier > 0
        p.set_bpm_multiplier(-1)
        assert p._bpm_multiplier > 0
