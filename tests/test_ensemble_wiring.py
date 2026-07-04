"""Tests for wiring the ensemble voicer into config, playback, and the UI.

Headless: no Tkinter. ``audio.ensemble_voicer`` is stubbed via sys.modules
(mirroring the pattern in ``tests/test_midi_export_flow.py`` for the MIDI
writer) so these tests pass whether or not the real module -- owned by a
concurrent task -- exists on disk yet.
"""

import sys
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from services.playback_service import PlaybackService
from services.config_service import ConfigService
from models.chord import ChordInfo
from models.config import Config
from models.ensemble_spec import EnsembleSpec, BUILTIN_ENSEMBLES
from exceptions import ConfigurationError


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


class TestCreateEnsemblePicker:
    """PlaybackService._create_note_picker for 'ensemble:<name>' voicings."""

    def test_builtin_ensemble_resolves_to_ensemble_voicer(self, playback_service, mock_config):
        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            picker = playback_service._create_note_picker("ensemble:satb")

        assert isinstance(picker, stub.EnsembleVoicer)
        assert picker.spec is BUILTIN_ENSEMBLES["satb"]

    def test_all_builtin_ensemble_keys_resolve(self, playback_service):
        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            for key in ("satb", "ttbb", "ssa", "quartet"):
                picker = playback_service._create_note_picker(f"ensemble:{key}")
                assert isinstance(picker, stub.EnsembleVoicer)
                assert picker.spec is BUILTIN_ENSEMBLES[key]

    def test_custom_ensemble_in_voicings_shadows_builtin(self, playback_service, mock_config):
        # Register a custom ensemble in the voicings registry under the
        # *same* name as a builtin, with a different voice layout. Resolved
        # via 'voicing:satb', it wins over BUILTIN_ENSEMBLES; the legacy
        # 'ensemble:satb' prefix is untouched by the registry and keeps
        # resolving to the real builtin (see TestGuitarAndEnsemblePrefixBuiltinsOnly
        # in test_voicing_registry.py).
        mock_config._store["voicings"] = {"satb": {"model": "ensemble", **CUSTOM_TRIO}}

        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            picker = playback_service._create_note_picker("voicing:satb")

        assert isinstance(picker, stub.EnsembleVoicer)
        assert picker.spec is not BUILTIN_ENSEMBLES["satb"]
        assert picker.spec.name == "satb"
        assert picker.spec.label == "Custom Trio"
        assert len(picker.spec.voices) == 3

    def test_custom_ensemble_in_voicings_not_shadowing_a_builtin_resolves(self, playback_service, mock_config):
        mock_config._store["voicings"] = {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}

        patcher, stub = _install_stub_ensemble_voicer_module()
        with patcher:
            picker = playback_service._create_note_picker("voicing:my_trio")

        assert isinstance(picker, stub.EnsembleVoicer)
        assert picker.spec.label == "Custom Trio"

    def test_unknown_ensemble_falls_back_to_piano(self, playback_service, caplog):
        from audio.chord_picker import ChordNotePicker

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("ensemble:nonexistent")

        assert isinstance(picker, ChordNotePicker)
        assert any("nonexistent" in r.message for r in caplog.records)

    def test_invalid_custom_ensemble_in_voicings_falls_back_to_piano(self, playback_service, mock_config, caplog):
        from audio.chord_picker import ChordNotePicker

        # Missing required 'voices' key -> EnsembleSpec.from_dict raises ConfigurationError.
        mock_config._store["voicings"] = {"broken": {"model": "ensemble", "label": "Broken"}}

        with caplog.at_level("WARNING"):
            picker = playback_service._create_note_picker("voicing:broken")

        assert isinstance(picker, ChordNotePicker)
        assert any("broken" in r.message for r in caplog.records)

    def test_set_voicing_stores_ensemble_string(self, playback_service, mock_config):
        patcher, _ = _install_stub_ensemble_voicer_module()
        with patcher:
            playback_service.set_voicing("ensemble:satb")

        mock_config.set.assert_called_once_with("voicing", "ensemble:satb")


class TestResolveChordNotesKeyStamping:
    """PlaybackService._resolve_chord_notes: key is stamped unconditionally."""

    def test_absolute_chord_is_stamped_with_current_key(self, playback_service):
        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)

        chord_notes = playback_service._resolve_chord_notes(chord, current_key="G")

        assert chord_notes is not None
        assert chord_notes.key == "G"
        # Notes are still C major regardless of the key context.
        assert chord_notes.root == "C"

    def test_absolute_chord_with_no_key_stamps_none(self, playback_service):
        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)

        chord_notes = playback_service._resolve_chord_notes(chord, current_key=None)

        assert chord_notes is not None
        assert chord_notes.key is None

    def test_relative_chord_still_resolves_and_stamps_key(self, playback_service):
        chord = ChordInfo(chord="I", start=0, end=1, is_valid=True, is_relative=True)

        chord_notes = playback_service._resolve_chord_notes(chord, current_key="G")

        assert chord_notes is not None
        assert chord_notes.key == "G"
        assert chord_notes.root == "G"


class TestConfigEnsembleVoicingsRoundTrip:
    """A voicings registry entry with model 'ensemble' survives to_dict/from_dict.

    (Config's dedicated custom_ensembles field is gone; ensemble specs now
    live as {"model": "ensemble", **spec_data} entries in the unified
    voicings registry. See tests/test_voicing_registry.py for the legacy-key
    migration itself.)
    """

    def test_default_is_empty_dict(self):
        config = Config()
        assert config.voicings == {}

    def test_round_trips_through_to_dict_from_dict(self):
        config = Config(voicings={"my_trio": {"model": "ensemble", **CUSTOM_TRIO}})

        data = config.to_dict()
        assert data["voicings"] == {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}

        restored = Config.from_dict(data)
        assert restored.voicings == {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}

    def test_missing_key_defaults_to_empty_dict_on_load(self):
        # Simulates loading an older config file written before this field existed.
        data = Config().to_dict()
        del data["voicings"]

        restored = Config.from_dict(data)
        assert restored.voicings == {}

    def test_ensemble_voicing_dict_is_a_valid_ensemble_spec(self):
        """Sanity check: the round-tripped dict (minus 'model') still parses via EnsembleSpec."""
        config = Config(voicings={"my_trio": {"model": "ensemble", **CUSTOM_TRIO}})
        data = config.to_dict()
        restored = Config.from_dict(data)

        params = dict(restored.voicings["my_trio"])
        params.pop("model")
        spec = EnsembleSpec.from_dict("my_trio", params)
        assert spec.label == "Custom Trio"
        assert len(spec.voices) == 3


class TestViewModelGetVoicings:
    """MainWindowViewModel.get_voicings returns the raw voicings registry."""

    def test_returns_configured_voicings(self):
        from viewmodels.main_window_viewmodel import MainWindowViewModel
        from services.song_parser_service import SongParserService
        from unittest.mock import MagicMock

        voicings = {"my_trio": {"model": "ensemble", **CUSTOM_TRIO}}
        config = Mock(spec=ConfigService)
        config.get.side_effect = lambda key, default=None: {
            "voicings": voicings,
        }.get(key, default)

        vm = MainWindowViewModel(
            config_service=config,
            audio_service=MagicMock(),
            file_service=MagicMock(),
            song_parser_service=SongParserService(),
            application=MagicMock(),
        )

        assert vm.get_voicings() == voicings

    def test_defaults_to_empty_dict(self):
        from viewmodels.main_window_viewmodel import MainWindowViewModel
        from services.song_parser_service import SongParserService
        from unittest.mock import MagicMock

        config = Mock(spec=ConfigService)
        config.get.side_effect = lambda key, default=None: default

        vm = MainWindowViewModel(
            config_service=config,
            audio_service=MagicMock(),
            file_service=MagicMock(),
            song_parser_service=SongParserService(),
            application=MagicMock(),
        )

        assert vm.get_voicings() == {}
