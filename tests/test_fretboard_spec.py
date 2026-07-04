"""Tests for the fretboard voicing model configuration (src/models/fretboard_spec.py)."""

import logging

import pytest

from exceptions import ConfigurationError
from models.fretboard_spec import (
    BUILTIN_FRETBOARDS,
    DEFAULT_WEIGHTS,
    FretboardSpec,
)
from models.ensemble_spec import parse_note_name


# ---------------------------------------------------------------------------
# FretboardSpec.from_dict: happy paths
# ---------------------------------------------------------------------------

class TestFromDictMinimal:
    def test_tuning_only_uses_all_defaults(self):
        spec = FretboardSpec.from_dict("standard", {
            "tuning": [40, 45, 50, 55, 59, 64],
        })
        assert spec.name == "standard"
        assert spec.label == "standard"
        assert spec.tuning == (40, 45, 50, 55, 59, 64)
        assert spec.max_fret == 12
        assert spec.fingers == 4
        assert spec.max_span == 4
        assert spec.relaxed_span == 5
        assert spec.allow_barres is True
        assert spec.weights == DEFAULT_WEIGHTS

    def test_note_name_tuning(self):
        spec = FretboardSpec.from_dict("standard", {
            "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
        })
        assert spec.tuning == (40, 45, 50, 55, 59, 64)

    def test_midi_int_tuning(self):
        spec = FretboardSpec.from_dict("standard", {
            "tuning": [40, 45, 50, 55, 59, 64],
        })
        assert spec.tuning == (40, 45, 50, 55, 59, 64)

    def test_mixed_note_name_and_int_tuning(self):
        spec = FretboardSpec.from_dict("mixed", {
            "tuning": ["E2", 45, "D3", 55, "B3", 64],
        })
        assert spec.tuning == (40, 45, 50, 55, 59, 64)

    def test_reentrant_ukulele_tuning_not_sorted(self):
        # G4 is higher in pitch than C4, but tuning preserves string order.
        spec = FretboardSpec.from_dict("ukulele", {
            "tuning": ["G4", "C4", "E4", "A4"],
        })
        assert spec.tuning == (67, 60, 64, 69)

    def test_explicit_label_and_fields(self):
        spec = FretboardSpec.from_dict("custom", {
            "label": "My Custom Fretboard",
            "tuning": [40, 45, 50, 55, 59, 64],
            "max_fret": 15,
            "fingers": 3,
            "max_span": 3,
            "relaxed_span": 6,
            "allow_barres": False,
        })
        assert spec.label == "My Custom Fretboard"
        assert spec.max_fret == 15
        assert spec.fingers == 3
        assert spec.max_span == 3
        assert spec.relaxed_span == 6
        assert spec.allow_barres is False

    def test_min_string_count_three_is_allowed(self):
        spec = FretboardSpec.from_dict("three", {"tuning": [40, 45, 50]})
        assert len(spec.tuning) == 3

    def test_max_string_count_twelve_is_allowed(self):
        spec = FretboardSpec.from_dict("twelve", {"tuning": list(range(40, 52))})
        assert len(spec.tuning) == 12

    def test_relaxed_span_equal_to_max_span_is_allowed(self):
        spec = FretboardSpec.from_dict("equal", {
            "tuning": [40, 45, 50, 55, 59, 64],
            "max_span": 4,
            "relaxed_span": 4,
        })
        assert spec.max_span == 4
        assert spec.relaxed_span == 4


# ---------------------------------------------------------------------------
# FretboardSpec.from_dict: validation errors
# ---------------------------------------------------------------------------

class TestFromDictValidation:
    def test_missing_tuning_raises(self):
        with pytest.raises(ConfigurationError, match="tuning"):
            FretboardSpec.from_dict("bad", {})

    def test_empty_tuning_raises(self):
        with pytest.raises(ConfigurationError, match="tuning"):
            FretboardSpec.from_dict("bad", {"tuning": []})

    def test_two_strings_raises(self):
        with pytest.raises(ConfigurationError, match="between 3 and 12"):
            FretboardSpec.from_dict("bad", {"tuning": [40, 45]})

    def test_thirteen_strings_raises(self):
        with pytest.raises(ConfigurationError, match="between 3 and 12"):
            FretboardSpec.from_dict("bad", {"tuning": list(range(40, 53))})

    def test_invalid_note_name_raises(self):
        with pytest.raises(ConfigurationError, match="invalid note name"):
            FretboardSpec.from_dict("bad", {
                "tuning": ["Hz4", 45, 50, 55, 59, 64],
            })

    def test_tuning_entry_wrong_type_raises(self):
        with pytest.raises(ConfigurationError, match="MIDI int or note-name string"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40.5, 45, 50, 55, 59, 64],
            })

    def test_tuning_entry_bool_raises(self):
        with pytest.raises(ConfigurationError, match="MIDI int or note-name string"):
            FretboardSpec.from_dict("bad", {
                "tuning": [True, 45, 50, 55, 59, 64],
            })

    def test_tuning_entry_out_of_midi_range_raises(self):
        with pytest.raises(ConfigurationError, match="out of range"):
            FretboardSpec.from_dict("bad", {
                "tuning": [200, 45, 50, 55, 59, 64],
            })

    @pytest.mark.parametrize("value", [4, 25, 4.0, "12", True])
    def test_max_fret_out_of_bounds_or_wrong_type_raises(self, value):
        with pytest.raises(ConfigurationError, match="max_fret"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "max_fret": value,
            })

    @pytest.mark.parametrize("value", [0, 6, 1.0, "4", True])
    def test_fingers_out_of_bounds_or_wrong_type_raises(self, value):
        with pytest.raises(ConfigurationError, match="fingers"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "fingers": value,
            })

    @pytest.mark.parametrize("value", [0, -1, 2.0, "4", True])
    def test_max_span_invalid_raises(self, value):
        with pytest.raises(ConfigurationError, match="max_span"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "max_span": value,
            })

    @pytest.mark.parametrize("value", [0, -1, 2.0, "5", True])
    def test_relaxed_span_invalid_type_raises(self, value):
        with pytest.raises(ConfigurationError, match="relaxed_span"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "relaxed_span": value,
            })

    def test_relaxed_span_less_than_max_span_raises(self):
        with pytest.raises(ConfigurationError, match="relaxed_span"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "max_span": 5,
                "relaxed_span": 4,
            })

    def test_bad_allow_barres_type_raises(self):
        with pytest.raises(ConfigurationError, match="allow_barres"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "allow_barres": "yes",
            })

    def test_bad_label_type_raises(self):
        with pytest.raises(ConfigurationError, match="label"):
            FretboardSpec.from_dict("bad", {
                "tuning": [40, 45, 50, 55, 59, 64],
                "label": 123,
            })


# ---------------------------------------------------------------------------
# Weight merging
# ---------------------------------------------------------------------------

class TestWeightMerging:
    def _tuning(self):
        return [40, 45, 50, 55, 59, 64]

    def test_partial_override_leaves_others_default(self):
        spec = FretboardSpec.from_dict("w", {
            "tuning": self._tuning(),
            "weights": {"span_penalty": 99.0},
        })
        assert spec.weight("span_penalty") == 99.0
        assert spec.weight("barre_penalty") == DEFAULT_WEIGHTS["barre_penalty"]
        assert spec.weight("bass_note_bonus") == DEFAULT_WEIGHTS["bass_note_bonus"]

    def test_unknown_key_warns_and_is_ignored(self, caplog):
        with caplog.at_level(logging.WARNING):
            spec = FretboardSpec.from_dict("w", {
                "tuning": self._tuning(),
                "weights": {"totally_made_up_key": 5.0},
            })
        assert "totally_made_up_key" not in spec.weights
        assert any("totally_made_up_key" in record.message for record in caplog.records)

    def test_wrong_typed_weight_raises(self):
        with pytest.raises(ConfigurationError, match="span_penalty"):
            FretboardSpec.from_dict("w", {
                "tuning": self._tuning(),
                "weights": {"span_penalty": "big"},
            })

    def test_bool_rejected_as_numeric_weight(self):
        with pytest.raises(ConfigurationError, match="span_penalty"):
            FretboardSpec.from_dict("w", {
                "tuning": self._tuning(),
                "weights": {"span_penalty": True},
            })

    def test_all_weight_keys_are_positive_by_default(self):
        # Documented behaviour: weights hold magnitudes, not signed scores;
        # the picker applies the sign itself.
        for value in DEFAULT_WEIGHTS.values():
            assert value > 0


# ---------------------------------------------------------------------------
# weight() accessor
# ---------------------------------------------------------------------------

class TestWeightAccessor:
    def test_returns_scalar(self):
        spec = FretboardSpec.from_dict("w", {"tuning": [40, 45, 50, 55, 59, 64]})
        assert spec.weight("kept_finger_bonus") == 0.4

    def test_unknown_key_raises_key_error(self):
        spec = FretboardSpec.from_dict("w", {"tuning": [40, 45, 50, 55, 59, 64]})
        with pytest.raises(KeyError):
            spec.weight("nope")


# ---------------------------------------------------------------------------
# to_dict / from_dict round trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_round_trip_preserves_everything(self):
        original = FretboardSpec.from_dict("roundtrip", {
            "label": "Round Trip Fretboard",
            "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
            "max_fret": 15,
            "fingers": 3,
            "max_span": 3,
            "relaxed_span": 6,
            "allow_barres": False,
            "weights": {"span_penalty": 7.0, "barre_penalty": 3.0},
        })

        rebuilt = FretboardSpec.from_dict(original.name, original.to_dict())

        assert rebuilt.name == original.name
        assert rebuilt.label == original.label
        assert rebuilt.tuning == original.tuning
        assert rebuilt.max_fret == original.max_fret
        assert rebuilt.fingers == original.fingers
        assert rebuilt.max_span == original.max_span
        assert rebuilt.relaxed_span == original.relaxed_span
        assert rebuilt.allow_barres == original.allow_barres
        assert rebuilt.weights == original.weights

    def test_round_trip_of_default_weights(self):
        original = FretboardSpec.from_dict("plain", {"tuning": [40, 45, 50, 55, 59, 64]})
        rebuilt = FretboardSpec.from_dict(original.name, original.to_dict())
        assert rebuilt == original

    def test_round_trip_preserves_reentrant_ukulele_order(self):
        original = FretboardSpec.from_dict("ukulele", {"tuning": ["G4", "C4", "E4", "A4"]})
        rebuilt = FretboardSpec.from_dict(original.name, original.to_dict())
        assert rebuilt.tuning == original.tuning == (67, 60, 64, 69)


# ---------------------------------------------------------------------------
# Built-in fretboards
# ---------------------------------------------------------------------------

class TestBuiltinFretboards:
    def test_expected_keys_present(self):
        assert set(BUILTIN_FRETBOARDS.keys()) == {
            "standard", "drop_d", "dadgad", "open_g", "ukulele",
        }

    @pytest.mark.parametrize("key", ["standard", "drop_d", "dadgad", "open_g", "ukulele"])
    def test_each_builtin_is_internally_consistent(self, key):
        spec = BUILTIN_FRETBOARDS[key]
        assert isinstance(spec, FretboardSpec)
        assert 3 <= len(spec.tuning) <= 12
        for midi in spec.tuning:
            assert 0 <= midi <= 127
        assert spec.max_fret == 12
        assert spec.fingers == 4
        assert spec.max_span == 4
        assert spec.relaxed_span == 5
        assert spec.allow_barres is True
        assert spec.weights == DEFAULT_WEIGHTS

    def test_standard_tuning_and_label(self):
        spec = BUILTIN_FRETBOARDS["standard"]
        assert spec.label == "Guitar (Standard - EADGBE)"
        assert spec.tuning == (40, 45, 50, 55, 59, 64)

    def test_drop_d_tuning_and_label(self):
        spec = BUILTIN_FRETBOARDS["drop_d"]
        assert spec.label == "Guitar (Drop D)"
        assert spec.tuning == (38, 45, 50, 55, 59, 64)

    def test_dadgad_tuning_and_label(self):
        spec = BUILTIN_FRETBOARDS["dadgad"]
        assert spec.label == "Guitar (DADGAD)"
        assert spec.tuning == (38, 45, 50, 55, 57, 62)

    def test_open_g_tuning_and_label(self):
        spec = BUILTIN_FRETBOARDS["open_g"]
        assert spec.label == "Guitar (Open G)"
        assert spec.tuning == (38, 43, 50, 55, 59, 62)

    def test_ukulele_tuning_and_label(self):
        spec = BUILTIN_FRETBOARDS["ukulele"]
        assert spec.label == "Ukulele"
        # Re-entrant: G4 is higher in pitch than C4 immediately after it.
        assert spec.tuning == (67, 60, 64, 69)
        assert spec.tuning[0] > spec.tuning[1]

    def test_builtin_tunings_match_note_names(self):
        spec = BUILTIN_FRETBOARDS["standard"]
        expected = tuple(parse_note_name(n) for n in ["E2", "A2", "D3", "G3", "B3", "E4"])
        assert spec.tuning == expected
