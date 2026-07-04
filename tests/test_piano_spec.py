"""Tests for the piano voicing model configuration (src/models/piano_spec.py)."""

import logging

import pytest

from exceptions import ConfigurationError
from models.piano_spec import (
    BUILTIN_PIANOS,
    DEFAULT_PIANO,
    DEFAULT_WEIGHTS,
    PianoSpec,
)


# ---------------------------------------------------------------------------
# from_dict: happy paths / defaults
# ---------------------------------------------------------------------------

class TestFromDictMinimal:
    def test_empty_dict_uses_all_defaults(self):
        spec = PianoSpec.from_dict("grand", {})
        assert spec.name == "grand"
        assert spec.label == "grand"
        assert spec.lh_range == (24, 48)
        assert spec.rh_range == (48, 84)
        assert spec.bass_range == (36, 47)
        assert spec.rh_low_anchor == (48, 64)
        assert spec.rh_center == 63.0
        assert spec.rh_low_interval_floor == 52
        assert spec.hand_span == 14
        assert spec.max_notes_per_hand == 5
        assert spec.max_total_notes == 10
        assert spec.hand_gap_floor == 2
        assert spec.add_bass is True
        assert spec.weights == DEFAULT_WEIGHTS

    def test_model_key_is_ignored(self):
        # The registry stores {'model': 'piano', ...}; from_dict tolerates it.
        spec = PianoSpec.from_dict("grand", {"model": "piano"})
        assert spec.weights == DEFAULT_WEIGHTS

    def test_note_name_ranges(self):
        spec = PianoSpec.from_dict("x", {
            "lh_range": ["C1", "C3"],
            "rh_range": ["C3", "C6"],
        })
        assert spec.lh_range == (24, 48)
        assert spec.rh_range == (48, 84)

    def test_mixed_int_and_note_name_range(self):
        spec = PianoSpec.from_dict("x", {"bass_range": [36, "B2"]})
        assert spec.bass_range == (36, 47)

    def test_explicit_label_and_scalars(self):
        spec = PianoSpec.from_dict("custom", {
            "label": "My Piano",
            "rh_center": 60,
            "hand_span": 12,
            "max_notes_per_hand": 4,
            "max_total_notes": 8,
            "hand_gap_floor": 0,
            "rh_low_interval_floor": 48,
            "add_bass": False,
        })
        assert spec.label == "My Piano"
        assert spec.rh_center == 60.0
        assert spec.hand_span == 12
        assert spec.max_notes_per_hand == 4
        assert spec.max_total_notes == 8
        assert spec.hand_gap_floor == 0
        assert spec.rh_low_interval_floor == 48
        assert spec.add_bass is False


# ---------------------------------------------------------------------------
# Signed weight defaults
# ---------------------------------------------------------------------------

class TestWeightDefaults:
    def test_omit_defaults_are_signed_negative(self):
        omit = DEFAULT_WEIGHTS["omit"]
        assert omit == {
            "root": -4.0, "third": -40.0, "fifth": -8.0,
            "seventh": -40.0, "color": -30.0, "extension": -7.0,
        }

    def test_reward_weights_positive_penalties_negative(self):
        w = DEFAULT_WEIGHTS
        assert w["rh_note_bonus"] > 0
        assert w["common_tone_bonus"] > 0
        assert w["rh_center_penalty"] < 0
        assert w["movement_penalty"] < 0
        assert w["muddy_gap_penalty"] < 0


class TestWeightMerge:
    def test_partial_flat_override_merges_over_defaults(self):
        spec = PianoSpec.from_dict("x", {"weights": {"rh_center_penalty": -2.5}})
        assert spec.weight("rh_center_penalty") == -2.5
        # Untouched keys keep their defaults.
        assert spec.weight("rh_note_bonus") == DEFAULT_WEIGHTS["rh_note_bonus"]

    def test_partial_omit_override_merges_per_role(self):
        spec = PianoSpec.from_dict("x", {"weights": {"omit": {"fifth": -1.0}}})
        assert spec.weight("omit")["fifth"] == -1.0
        assert spec.weight("omit")["third"] == DEFAULT_WEIGHTS["omit"]["third"]

    def test_unknown_flat_weight_key_ignored_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            spec = PianoSpec.from_dict("x", {"weights": {"nonsense": 1.0}})
        assert "nonsense" in caplog.text
        assert "nonsense" not in spec.weights

    def test_unknown_omit_role_ignored_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            spec = PianoSpec.from_dict("x", {"weights": {"omit": {"bogus": -1.0}}})
        assert "bogus" in caplog.text
        assert "bogus" not in spec.weight("omit")

    def test_non_numeric_weight_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"weights": {"rh_center_penalty": "loud"}})

    def test_omit_not_a_mapping_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"weights": {"omit": 5}})

    def test_defaults_are_not_shared_between_specs(self):
        a = PianoSpec.from_dict("a", {})
        b = PianoSpec.from_dict("b", {"weights": {"omit": {"root": -1.0}}})
        # Mutating b's merged copy must not leak into a or the module default.
        assert a.weight("omit")["root"] == -4.0
        assert DEFAULT_WEIGHTS["omit"]["root"] == -4.0


# ---------------------------------------------------------------------------
# Validation / errors
# ---------------------------------------------------------------------------

class TestValidation:
    def test_range_low_not_below_high_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"lh_range": ["C3", "C1"]})

    def test_range_equal_endpoints_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"rh_range": [60, 60]})

    def test_range_wrong_length_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"rh_range": [48, 60, 72]})

    def test_out_of_range_pitch_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"lh_range": [-1, 48]})

    def test_invalid_note_name_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"rh_range": ["H9", "C6"]})

    def test_non_int_scalar_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"hand_span": 3.5})

    def test_scalar_below_minimum_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"max_notes_per_hand": 0})

    def test_hand_gap_floor_allows_zero(self):
        spec = PianoSpec.from_dict("x", {"hand_gap_floor": 0})
        assert spec.hand_gap_floor == 0

    def test_bad_rh_center_type_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"rh_center": "middle"})

    def test_bad_add_bass_type_raises(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"add_bass": "yes"})

    def test_bool_is_not_accepted_as_pitch(self):
        with pytest.raises(ConfigurationError):
            PianoSpec.from_dict("x", {"lh_range": [True, 48]})


# ---------------------------------------------------------------------------
# to_dict round-trip and builtins
# ---------------------------------------------------------------------------

class TestRoundTripAndBuiltins:
    def test_to_dict_round_trips(self):
        spec = PianoSpec.from_dict("custom", {
            "label": "RT",
            "rh_center": 61,
            "hand_span": 13,
            "add_bass": False,
            "weights": {"movement_penalty": -0.5, "omit": {"fifth": -2.0}},
        })
        again = PianoSpec.from_dict(spec.name, spec.to_dict())
        assert again == spec

    def test_to_dict_excludes_name(self):
        assert "name" not in DEFAULT_PIANO.to_dict()

    def test_default_piano_is_grand(self):
        assert DEFAULT_PIANO.name == "grand"
        assert DEFAULT_PIANO.label == "Grand Piano"

    def test_builtins_contains_grand(self):
        assert "grand" in BUILTIN_PIANOS
        assert BUILTIN_PIANOS["grand"] is DEFAULT_PIANO

    def test_weight_lookup_helper(self):
        assert DEFAULT_PIANO.weight("rh_note_bonus") == DEFAULT_WEIGHTS["rh_note_bonus"]
