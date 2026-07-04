"""Tests for the unified ``voicings`` config registry and its dispatch.

Covers three things:

1. ``Config.from_dict`` migrating the legacy ``custom_tunings``/
   ``custom_ensembles`` keys into the new ``voicings`` registry (and
   rewriting the selected ``voicing`` string when it referenced a migrated
   entry), plus ``Config.to_dict`` no longer writing the legacy keys.
2. ``PlaybackService._create_note_picker`` dispatching ``"voicing:<name>"``
   to the right model (fretboard/ensemble/piano), with fallbacks for unknown
   names/models and invalid parameters, plus the now-builtins-only
   ``"guitar:<name>"``/``"ensemble:<name>"`` resolution.
3. Round-tripping an arbitrary ``voicings`` registry through
   ``to_dict``/``from_dict`` unchanged.

Headless: no Tkinter. ``audio.ensemble_voicer`` is stubbed via sys.modules
(mirroring ``tests/test_ensemble_wiring.py``) so the ensemble-model dispatch
tests pass whether or not the real module -- owned by a concurrent task --
exists on disk. ``GuitarChordPicker`` is mocked via ``mock.patch`` on the
``services.playback_service`` import so the fretboard-model dispatch tests
don't depend on the concurrently-refactored picker's exact constructor
signature.
"""

import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from services.playback_service import PlaybackService
from services.config_service import ConfigService
from models.config import Config
from models.ensemble_spec import BUILTIN_ENSEMBLES
from models.fretboard_spec import BUILTIN_FRETBOARDS


CUSTOM_TUNING = [40, 45, 50, 55, 59, 64]

CUSTOM_TRIO = {
    "label": "Custom Trio",
    "voices": [
        {"name": "Top", "range": ["C4", "G5"]},
        {"name": "Mid", "range": ["F3", "D5"]},
        {"name": "Bottom", "range": ["E2", "C4"]},
    ],
}


def _install_stub_ensemble_voicer_module():
    """Install a stub 'audio.ensemble_voicer' module into sys.modules.

    The stub ``EnsembleVoicer`` just records the spec it was constructed
    with, so tests can assert on resolution without needing the real
    (concurrently-developed) voicing engine.
    """
    stub = ModuleType("audio.ensemble_voicer")

    class _StubEnsembleVoicer:
        def __init__(self, spec):
            self.spec = spec

        def chord_to_midi(self, chord_notes):
            return []

        def reset(self):
            pass

        @property
        def state(self):
            return None

        @state.setter
        def state(self, value):
            pass

    stub.EnsembleVoicer = _StubEnsembleVoicer
    return patch.dict(sys.modules, {"audio.ensemble_voicer": stub}), stub


# ---------------------------------------------------------------------------
# Config migration
# ---------------------------------------------------------------------------


class TestConfigVoicingsMigration:
    """Config.from_dict migrates legacy custom_tunings/custom_ensembles."""

    def test_custom_tunings_migrate_to_fretboard_voicings(self):
        data = Config().to_dict()
        data["custom_tunings"] = {"my_tuning": CUSTOM_TUNING}

        restored = Config.from_dict(data)

        assert restored.voicings["my_tuning"] == {"model": "fretboard", "tuning": CUSTOM_TUNING}
        assert "custom_tunings" not in restored.to_dict()

    def test_custom_ensembles_migrate_to_ensemble_voicings(self):
        data = Config().to_dict()
        data["custom_ensembles"] = {"my_trio": CUSTOM_TRIO}

        restored = Config.from_dict(data)

        assert restored.voicings["my_trio"] == {"model": "ensemble", **CUSTOM_TRIO}
        assert "custom_ensembles" not in restored.to_dict()

    def test_to_dict_never_writes_legacy_keys(self):
        data = Config().to_dict()
        assert "custom_tunings" not in data
        assert "custom_ensembles" not in data
        assert "voicings" in data

    def test_migration_collision_keeps_voicings_entry_and_warns(self, caplog):
        data = Config().to_dict()
        data["voicings"] = {"foo": {"model": "piano"}}
        data["custom_tunings"] = {"foo": CUSTOM_TUNING}

        with caplog.at_level("WARNING"):
            restored = Config.from_dict(data)

        assert restored.voicings["foo"] == {"model": "piano"}
        assert any("foo" in r.message for r in caplog.records)

    def test_ensemble_collision_keeps_voicings_entry_and_warns(self, caplog):
        data = Config().to_dict()
        data["voicings"] = {"bar": {"model": "piano"}}
        data["custom_ensembles"] = {"bar": CUSTOM_TRIO}

        with caplog.at_level("WARNING"):
            restored = Config.from_dict(data)

        assert restored.voicings["bar"] == {"model": "piano"}
        assert any("bar" in r.message for r in caplog.records)

    def test_selected_guitar_voicing_rewritten_to_voicing_prefix(self):
        data = Config().to_dict()
        data["voicing"] = "guitar:my_tuning"
        data["custom_tunings"] = {"my_tuning": CUSTOM_TUNING}

        restored = Config.from_dict(data)

        assert restored.voicing == "voicing:my_tuning"

    def test_selected_ensemble_voicing_rewritten_to_voicing_prefix(self):
        data = Config().to_dict()
        data["voicing"] = "ensemble:my_trio"
        data["custom_ensembles"] = {"my_trio": CUSTOM_TRIO}

        restored = Config.from_dict(data)

        assert restored.voicing == "voicing:my_trio"

    def test_builtin_guitar_selection_not_rewritten(self):
        data = Config().to_dict()
        data["voicing"] = "guitar:standard"

        restored = Config.from_dict(data)

        assert restored.voicing == "guitar:standard"

    def test_builtin_ensemble_selection_not_rewritten_even_if_shadowed(self):
        # A custom_ensembles entry sharing a builtin's name must not steal
        # the selection: "satb" is a builtin, so the voicing string stays
        # 'ensemble:satb' rather than being rewritten to 'voicing:satb'.
        data = Config().to_dict()
        data["voicing"] = "ensemble:satb"
        data["custom_ensembles"] = {"satb": CUSTOM_TRIO}

        restored = Config.from_dict(data)

        assert restored.voicing == "ensemble:satb"

    def test_missing_legacy_keys_is_a_noop(self):
        data = Config().to_dict()

        restored = Config.from_dict(data)

        assert restored.voicings == {}
        assert restored.voicing == "piano"

    def test_no_legacy_fields_remain_on_config(self):
        config = Config()
        assert not hasattr(config, "custom_tunings")
        assert not hasattr(config, "custom_ensembles")


class TestVoicingsRoundTrip:
    """An arbitrary voicings registry survives to_dict/from_dict unchanged."""

    def test_round_trips_unchanged(self):
        voicings = {
            "my_tuning": {"model": "fretboard", "tuning": CUSTOM_TUNING},
            "my_trio": {"model": "ensemble", **CUSTOM_TRIO},
            "plain_piano": {"model": "piano"},
        }
        config = Config(voicings=voicings)

        data = config.to_dict()
        assert data["voicings"] == voicings

        restored = Config.from_dict(data)
        assert restored.voicings == voicings

    def test_default_is_empty_dict(self):
        assert Config().voicings == {}


# ---------------------------------------------------------------------------
# PlaybackService dispatch
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config():
    """Fake config service; ``voicings`` defaults to empty."""
    config = Mock(spec=ConfigService)
    config._store = {
        "bpm": 120,
        "time_signature_beats": 4,
        "time_signature_unit": 4,
        "soundfont_path": None,
        "voicing": "piano",
        "instrument": 0,
        "voicings": {},
    }
    config.get.side_effect = lambda key, default=None: config._store.get(key, default)
    return config


@pytest.fixture
def playback_service(mock_config):
    return PlaybackService(config_service=mock_config, player=None)


class TestRegistryDispatchFretboard:
    """'voicing:<name>' entries with model 'fretboard'."""

    def test_builds_guitar_chord_picker_from_fretboard_spec(self, playback_service, mock_config):
        mock_config._store["voicings"] = {
            "my_tuning": {"model": "fretboard", "tuning": CUSTOM_TUNING}
        }
        sentinel = Mock(name="picker")
        with patch("services.playback_service.GuitarChordPicker", return_value=sentinel) as mock_cls:
            picker = playback_service._create_note_picker("voicing:my_tuning")

        assert picker is sentinel
        mock_cls.assert_called_once()
        (spec_arg,), kwargs = mock_cls.call_args
        assert kwargs == {}
        assert spec_arg.name == "my_tuning"
        assert tuple(spec_arg.tuning) == tuple(CUSTOM_TUNING)

    def test_invalid_fretboard_params_falls_back_to_piano(self, playback_service, mock_config, caplog):
        from audio.chord_picker import ChordNotePicker

        # Missing required 'tuning' key -> FretboardSpec.from_dict raises ConfigurationError.
        mock_config._store["voicings"] = {"broken": {"model": "fretboard"}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:broken")

        assert isinstance(picker, ChordNotePicker)
        assert any("broken" in r.message for r in caplog.records)


class TestRegistryDispatchEnsemble:
    """'voicing:<name>' entries with model 'ensemble'."""

    def test_builds_ensemble_voicer_from_ensemble_spec(self, playback_service, mock_config):
        mock_config._store["voicings"] = {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}

        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            picker = playback_service._create_note_picker("voicing:my_trio")

        assert isinstance(picker, stub.EnsembleVoicer)
        assert picker.spec.name == "my_trio"
        assert picker.spec.label == "Custom Trio"
        assert len(picker.spec.voices) == 3

    def test_invalid_ensemble_params_falls_back_to_piano(self, playback_service, mock_config, caplog):
        from audio.chord_picker import ChordNotePicker

        # Missing required 'voices' key -> EnsembleSpec.from_dict raises ConfigurationError.
        mock_config._store["voicings"] = {"broken": {"model": "ensemble", "label": "Broken"}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:broken")

        assert isinstance(picker, ChordNotePicker)
        assert any("broken" in r.message for r in caplog.records)


class TestRegistryDispatchPiano:
    """'voicing:<name>' entries with model 'piano'."""

    def test_bare_piano_builds_default_picker(self, playback_service, mock_config):
        from audio.chord_picker import ChordNotePicker

        # A bare {'model': 'piano'} entry resolves to the default piano spec,
        # named after the voicing.
        mock_config._store["voicings"] = {"plain": {"model": "piano"}}

        picker = playback_service._create_note_picker("voicing:plain")

        assert isinstance(picker, ChordNotePicker)
        assert picker.spec.name == "plain"
        assert picker.HAND_SPAN_SEMITONES == 14  # default reproduced

    def test_custom_piano_params_flow_into_spec(self, playback_service, mock_config):
        from audio.chord_picker import ChordNotePicker

        mock_config._store["voicings"] = {
            "tight": {
                "model": "piano",
                "label": "Tight",
                "hand_span": 10,
                "add_bass": False,
                "rh_center": 60,
            }
        }

        picker = playback_service._create_note_picker("voicing:tight")

        assert isinstance(picker, ChordNotePicker)
        assert picker.spec.label == "Tight"
        assert picker.HAND_SPAN_SEMITONES == 10
        assert picker.RH_IDEAL_CENTER == 60.0
        assert picker.add_bass is False

    def test_invalid_piano_params_falls_back_to_piano(self, playback_service, mock_config, caplog):
        from audio.chord_picker import ChordNotePicker

        # A range with low >= high -> PianoSpec.from_dict raises ConfigurationError.
        mock_config._store["voicings"] = {"broken": {"model": "piano", "lh_range": ["C3", "C1"]}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:broken")

        assert isinstance(picker, ChordNotePicker)
        assert picker.spec.name == "grand"  # default fallback, not the broken entry
        assert any("broken" in r.message for r in caplog.records)


class TestRegistryDispatchFallbacks:
    """Unknown voicing name / unknown model both fall back to piano with a warning."""

    def test_unknown_name_falls_back_to_piano(self, playback_service, caplog):
        from audio.chord_picker import ChordNotePicker

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:nonexistent")

        assert isinstance(picker, ChordNotePicker)
        assert any("nonexistent" in r.message for r in caplog.records)

    def test_unknown_model_falls_back_to_piano(self, playback_service, mock_config, caplog):
        from audio.chord_picker import ChordNotePicker

        mock_config._store["voicings"] = {"weird": {"model": "banjo_hero"}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:weird")

        assert isinstance(picker, ChordNotePicker)
        assert any("weird" in r.message for r in caplog.records)


class TestGuitarPrefixBuiltinsOnly:
    """'guitar:<name>' now only resolves BUILTIN_FRETBOARDS (no custom lookup)."""

    def test_ukulele_resolves_via_builtins(self, playback_service):
        sentinel = Mock(name="picker")
        with patch("services.playback_service.GuitarChordPicker", return_value=sentinel) as mock_cls:
            picker = playback_service._create_note_picker("guitar:ukulele")

        assert picker is sentinel
        mock_cls.assert_called_once_with(BUILTIN_FRETBOARDS["ukulele"])

    def test_all_builtin_fretboard_keys_resolve(self, playback_service):
        with patch("services.playback_service.GuitarChordPicker") as mock_cls:
            for key in BUILTIN_FRETBOARDS:
                playback_service._create_note_picker(f"guitar:{key}")
                mock_cls.assert_called_with(BUILTIN_FRETBOARDS[key])

    def test_unknown_guitar_name_falls_back_to_standard_with_warning(self, playback_service, caplog):
        with patch("services.playback_service.GuitarChordPicker") as mock_cls:
            with caplog.at_level("WARNING"):
                playback_service._create_note_picker("guitar:nonexistent")

        mock_cls.assert_called_once_with(BUILTIN_FRETBOARDS["standard"])
        assert any("nonexistent" in r.message for r in caplog.records)


class TestEnsemblePrefixBuiltinsOnly:
    """'ensemble:<name>' now only resolves BUILTIN_ENSEMBLES (no custom lookup)."""

    def test_builtin_ensemble_resolves(self, playback_service):
        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            picker = playback_service._create_note_picker("ensemble:satb")

        assert isinstance(picker, stub.EnsembleVoicer)
        assert picker.spec is BUILTIN_ENSEMBLES["satb"]

    def test_unknown_ensemble_falls_back_to_piano_even_if_registered_as_voicing(
        self, playback_service, mock_config, caplog
    ):
        from audio.chord_picker import ChordNotePicker

        # Registering "my_trio" in the new voicings registry must NOT make it
        # resolvable through the legacy 'ensemble:' prefix anymore -- only
        # 'voicing:my_trio' (or a builtin ensemble name) does that now.
        mock_config._store["voicings"] = {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("ensemble:my_trio")

        assert isinstance(picker, ChordNotePicker)
        assert any("my_trio" in r.message for r in caplog.records)
