"""Headless tests for :class:`viewmodels.settings_viewmodel.SettingsViewModel`.

No Tkinter widgets are instantiated: every assertion runs against the view
model and a real :class:`ConfigService` pointed at a throwaway ``tmp_path``
config file. A single import-smoke test for the Voicings page is guarded by
``pytest.importorskip('tkinter')`` and only imports the module.
"""

import pytest

from models.config import Config
from models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    EnsembleSpec,
    midi_to_note_name,
    parse_note_name,
)
from models.fretboard_spec import BUILTIN_FRETBOARDS
from models.piano_spec import PianoSpec
from services.config_service import ConfigService
from viewmodels.settings_viewmodel import SettingsViewModel


class _StubAppData:
    """Minimal AppDataService stand-in exposing only the config file path."""

    def __init__(self, path):
        self._path = path

    def get_config_file_path(self, filename=None):
        return self._path


def _make_config_service(tmp_path, config: Config = None) -> ConfigService:
    """Build a real ConfigService writing to ``tmp_path`` with ``config`` loaded."""
    service = ConfigService(_StubAppData(tmp_path / "settings.json"))
    service._config = config if config is not None else Config()
    return service


# ---------------------------------------------------------------------------
# midi_to_note_name
# ---------------------------------------------------------------------------


class TestMidiToNoteName:
    def test_spot_values(self):
        assert midi_to_note_name(60) == "C4"
        assert midi_to_note_name(66) == "F#4"
        assert midi_to_note_name(0) == "C-1"
        assert midi_to_note_name(127) == "G9"

    def test_round_trip_full_range(self):
        for midi in range(128):
            assert parse_note_name(midi_to_note_name(midi)) == midi


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------


class TestScalars:
    def test_scalars_initialized_from_config(self, tmp_path):
        config = Config(font_family="Courier", font_size=18, notation="european",
                        key="G", bpm=90, log_level="DEBUG", soundfont_path="/x.sf2")
        vm = SettingsViewModel(_make_config_service(tmp_path, config))

        assert vm.font_family == "Courier"
        assert vm.font_size == 18
        assert vm.notation == "european"
        assert vm.key == "G"
        assert vm.bpm == 90
        assert vm.log_level == "DEBUG"
        assert vm.soundfont_path == "/x.sf2"

    def test_scalars_round_trip_through_commit(self, tmp_path):
        service = _make_config_service(tmp_path)
        vm = SettingsViewModel(service)

        vm.font_family = "Monospace"
        vm.font_size = 20
        vm.notation = "european"
        vm.key = "D"
        vm.show_quick_start_on_startup = False
        vm.max_recent_files = 5
        vm.log_level = "WARNING"
        vm.bpm = 100
        vm.time_signature_beats = 3
        vm.time_signature_unit = 8
        vm.soundfont_path = "/sound.sf2"
        vm.audio_driver = "pulseaudio"

        vm.commit()
        config = service.config
        assert config.font_family == "Monospace"
        assert config.font_size == 20
        assert config.notation == "european"
        assert config.key == "D"
        assert config.show_quick_start_on_startup is False
        assert config.max_recent_files == 5
        assert config.log_level == "WARNING"
        assert config.bpm == 100
        assert config.time_signature_beats == 3
        assert config.time_signature_unit == 8
        assert config.soundfont_path == "/sound.sf2"
        assert config.audio_driver == "pulseaudio"

    def test_commit_change_flags(self, tmp_path):
        service = _make_config_service(tmp_path)
        vm = SettingsViewModel(service)
        vm.font_size = 30
        vm.notation = "european"
        vm.soundfont_path = "/new.sf2"

        changes = vm.commit()
        assert changes.font_changed is True
        assert changes.general_changed is True
        assert changes.audio_changed is True
        assert changes.voicings_changed is False

    def test_commit_no_changes_all_flags_false(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        changes = vm.commit()
        assert changes.font_changed is False
        assert changes.general_changed is False
        assert changes.audio_changed is False
        assert changes.voicings_changed is False
        assert changes.new_active_voicing is None

    def test_bpm_and_time_signature_map_to_general(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        vm.bpm = 140
        changes = vm.commit()
        assert changes.general_changed is True
        assert changes.font_changed is False
        assert changes.audio_changed is False

    def test_commit_persists_to_file(self, tmp_path):
        service = _make_config_service(tmp_path)
        vm = SettingsViewModel(service)
        vm.font_size = 22
        vm.commit()
        assert (tmp_path / "settings.json").exists()


# ---------------------------------------------------------------------------
# Voicings: add / rename / remove
# ---------------------------------------------------------------------------


class TestAddVoicing:
    def test_add_creates_fretboard_defaults(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        name = vm.add_voicing()
        assert name == "New voicing"
        data = vm.get_voicings()[name]
        assert data["model"] == "fretboard"
        assert data["tuning"] == [40, 45, 50, 55, 59, 64]
        assert vm.validate_voicing(name) is None

    def test_add_unique_naming(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        assert vm.add_voicing() == "New voicing"
        assert vm.add_voicing() == "New voicing 2"
        assert vm.add_voicing() == "New voicing 3"


class TestRename:
    def test_rename_empty_raises(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        name = vm.add_voicing()
        with pytest.raises(ValueError):
            vm.rename_voicing(name, "   ")

    def test_rename_duplicate_raises(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        a = vm.add_voicing()
        b = vm.add_voicing()
        with pytest.raises(ValueError):
            vm.rename_voicing(a, b)

    def test_rename_moves_data(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        old = vm.add_voicing()
        data = vm.get_voicings()[old]
        vm.rename_voicing(old, "Fancy")
        assert "Fancy" in vm.get_voicings()
        assert old not in vm.get_voicings()
        assert vm.get_voicings()["Fancy"] == data

    def test_rename_chain_fixes_active_voicing_on_commit(self, tmp_path):
        config = Config(
            voicing="voicing:A",
            voicings={"A": {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64]}},
        )
        service = _make_config_service(tmp_path, config)
        vm = SettingsViewModel(service)

        vm.rename_voicing("A", "B")
        vm.rename_voicing("B", "C")

        changes = vm.commit()
        assert service.config.voicing == "voicing:C"
        assert changes.new_active_voicing == "voicing:C"
        assert changes.voicings_changed is True

    def test_rename_of_unrelated_voicing_leaves_active_alone(self, tmp_path):
        config = Config(
            voicing="voicing:A",
            voicings={
                "A": {"model": "piano"},
                "X": {"model": "piano"},
            },
        )
        service = _make_config_service(tmp_path, config)
        vm = SettingsViewModel(service)
        vm.rename_voicing("X", "Y")
        changes = vm.commit()
        assert service.config.voicing == "voicing:A"
        assert changes.new_active_voicing is None


class TestRemove:
    def test_delete_active_resets_to_piano(self, tmp_path):
        config = Config(
            voicing="voicing:A",
            voicings={"A": {"model": "piano"}},
        )
        service = _make_config_service(tmp_path, config)
        vm = SettingsViewModel(service)
        vm.remove_voicing("A")
        changes = vm.commit()
        assert service.config.voicing == "piano"
        assert changes.new_active_voicing == "piano"
        assert changes.voicings_changed is True

    def test_rename_then_delete_active_resets_to_piano(self, tmp_path):
        config = Config(
            voicing="voicing:A",
            voicings={"A": {"model": "piano"}},
        )
        service = _make_config_service(tmp_path, config)
        vm = SettingsViewModel(service)
        vm.rename_voicing("A", "B")
        vm.remove_voicing("B")
        changes = vm.commit()
        assert service.config.voicing == "piano"
        assert changes.new_active_voicing == "piano"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_bad_tuning_flagged(self, tmp_path):
        config = Config(voicings={"bad_guitar": {"model": "fretboard", "tuning": ["nope"]}})
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_voicing("bad_guitar") is not None
        errors = dict(vm.validate_all())
        assert "bad_guitar" in errors

    def test_bad_ensemble_voice_range_flagged(self, tmp_path):
        config = Config(voicings={
            "bad_choir": {
                "model": "ensemble",
                "voices": [
                    {"name": "High", "range": ["C4", "C4"]},  # low == high, invalid
                    {"name": "Low", "range": ["C3", "C4"]},
                ],
            }
        })
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_voicing("bad_choir") is not None
        errors = dict(vm.validate_all())
        assert "bad_choir" in errors

    def test_bad_ensemble_voice_staff_flagged(self, tmp_path):
        config = Config(voicings={
            "bad_choir": {
                "model": "ensemble",
                "voices": [
                    {"name": "High", "range": ["C4", "C5"], "staff": "alto"},
                    {"name": "Low", "range": ["C3", "C4"]},
                ],
            }
        })
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        message = vm.validate_voicing("bad_choir")
        assert message is not None
        assert "alto" in message
        errors = dict(vm.validate_all())
        assert "bad_choir" in errors

    def test_piano_always_valid(self, tmp_path):
        config = Config(voicings={"p": {"model": "piano"}})
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_voicing("p") is None

    def test_piano_bare_and_full_params_valid_bad_range_flagged(self, tmp_path):
        config = Config(voicings={
            "bare": {"model": "piano"},
            "full": {
                "model": "piano",
                "lh_range": ["C1", "C3"],
                "rh_range": ["C3", "C6"],
                "bass_range": ["C2", "B2"],
                "rh_low_anchor": ["C3", "E4"],
                "rh_center": 63.0,
                "rh_low_interval_floor": 52,
                "hand_span": 14,
                "max_notes_per_hand": 5,
                "max_total_notes": 10,
                "hand_gap_floor": 2,
                "add_bass": True,
                "weights": {"rh_note_bonus": 0.6},
            },
            "bad": {"model": "piano", "lh_range": ["C3", "C1"]},
        })
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_voicing("bare") is None
        assert vm.validate_voicing("full") is None
        assert vm.validate_voicing("bad") is not None

    def test_unknown_model_flagged(self, tmp_path):
        config = Config(voicings={"weird": {"model": "banjo_hero"}})
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_voicing("weird") is not None

    def test_valid_voicings_have_no_errors(self, tmp_path):
        config = Config(voicings={
            "g": {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64]},
            "p": {"model": "piano"},
        })
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        assert vm.validate_all() == []


# ---------------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------------


class TestLoadSources:
    def test_contains_all_builtins_piano_and_customs(self, tmp_path):
        config = Config(voicings={"mine": {"model": "piano"}})
        vm = SettingsViewModel(_make_config_service(tmp_path, config))
        sources = vm.get_load_sources()

        labels = [label for label, _ in sources]
        # 5 fretboards + 4 ensembles = 9 builtins, + piano + customs.
        assert len(BUILTIN_FRETBOARDS) == 5
        assert len(BUILTIN_ENSEMBLES) == 4
        for spec in BUILTIN_FRETBOARDS.values():
            assert spec.label in labels
        for spec in BUILTIN_ENSEMBLES.values():
            assert spec.label in labels
        assert "Piano (default)" in labels
        assert "mine" in labels

    def test_builtins_come_first_and_have_model(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        sources = vm.get_load_sources()

        # First 5 are fretboards, next 4 ensembles, then piano.
        for _, params in sources[:5]:
            assert params["model"] == "fretboard"
        for _, params in sources[5:9]:
            assert params["model"] == "ensemble"
        label, params = sources[9]
        assert label == "Piano (default)"
        assert params["model"] == "piano"
        PianoSpec.from_dict("piano", params)  # round-trips without error

    def test_builtin_params_match_spec(self, tmp_path):
        vm = SettingsViewModel(_make_config_service(tmp_path))
        by_label = {label: params for label, params in vm.get_load_sources()}
        std = BUILTIN_FRETBOARDS["standard"]
        params = by_label[std.label]
        assert params["model"] == "fretboard"
        assert params["tuning"] == list(std.tuning)

    def test_satb_load_source_round_trips_with_staff(self, tmp_path):
        # SATB's params dict is EnsembleSpec.to_dict()'s output, which now
        # includes a 'staff' key per voice; it must still parse cleanly and
        # preserve every voice's staff.
        vm = SettingsViewModel(_make_config_service(tmp_path))
        by_label = {label: params for label, params in vm.get_load_sources()}
        satb = BUILTIN_ENSEMBLES["satb"]
        params = dict(by_label[satb.label])
        assert params["model"] == "ensemble"
        for voice_dict in params["voices"]:
            assert "staff" in voice_dict

        del params["model"]
        rebuilt = EnsembleSpec.from_dict("satb", params)
        assert [v.staff for v in rebuilt.voices] == [v.staff for v in satb.voices]
        assert rebuilt == satb


# ---------------------------------------------------------------------------
# Voicings persistence
# ---------------------------------------------------------------------------


class TestVoicingsPersistence:
    def test_commit_persists_voicings(self, tmp_path):
        service = _make_config_service(tmp_path)
        vm = SettingsViewModel(service)
        name = vm.add_voicing()
        vm.rename_voicing(name, "MyGuitar")
        changes = vm.commit()

        assert "MyGuitar" in service.config.voicings
        assert changes.voicings_changed is True

    def test_set_voicing_data_replaces_entry(self, tmp_path):
        service = _make_config_service(tmp_path)
        vm = SettingsViewModel(service)
        name = vm.add_voicing()
        vm.set_voicing_data(name, {"model": "piano"})
        assert vm.get_voicings()[name] == {"model": "piano"}


# ---------------------------------------------------------------------------
# Widget import smoke test (no widget instantiation)
# ---------------------------------------------------------------------------


def test_voicings_page_imports():
    pytest.importorskip("tkinter")
    import ui.dialogs.voicings_page as voicings_page

    assert hasattr(voicings_page, "VoicingsPage")
