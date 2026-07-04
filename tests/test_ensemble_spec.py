"""Tests for the ensemble voicer configuration model (src/models/ensemble_spec.py)."""

import logging

import pytest

from exceptions import ConfigurationError
from models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    DEFAULT_WEIGHTS,
    EnsembleSpec,
    VoiceSpec,
    parse_note_name,
)


# ---------------------------------------------------------------------------
# Note-name parsing (must match the codebase's C4 = MIDI 60 convention)
# ---------------------------------------------------------------------------

class TestParseNoteName:
    @pytest.mark.parametrize("name,expected", [
        ("C4", 60), ("C-1", 0), ("C0", 12), ("A4", 69),
        ("G5", 79), ("E2", 40), ("C3", 48),
    ])
    def test_naturals_match_c4_equals_60_convention(self, name, expected):
        assert parse_note_name(name) == expected

    def test_middle_c_is_60(self):
        # The canonical reference point used throughout the codebase.
        assert parse_note_name("C4") == 60

    @pytest.mark.parametrize("name,expected", [
        ("C#4", 61), ("Db4", 61), ("F#3", 54), ("Bb2", 46),
    ])
    def test_accidentals(self, name, expected):
        assert parse_note_name(name) == expected

    def test_lowercase_letter_accepted(self):
        assert parse_note_name("c4") == 60

    def test_double_accidentals(self):
        assert parse_note_name("C##4") == 62
        assert parse_note_name("Ebb4") == parse_note_name("D4")

    @pytest.mark.parametrize("bad", ["", "H4", "C", "4", "C#x4", "Cx4", None])
    def test_invalid_input_returns_none(self, bad):
        assert parse_note_name(bad) is None

    def test_out_of_midi_range_returns_none(self):
        assert parse_note_name("C10") is None  # way above 127


# ---------------------------------------------------------------------------
# VoiceSpec
# ---------------------------------------------------------------------------

class TestVoiceSpec:
    def test_basic_construction(self):
        v = VoiceSpec(name="Soprano", low=60, high=79)
        assert v.name == "Soprano"
        assert v.low == 60
        assert v.high == 79

    def test_is_frozen(self):
        v = VoiceSpec(name="Alto", low=53, high=74)
        with pytest.raises(AttributeError):
            v.low = 0


# ---------------------------------------------------------------------------
# EnsembleSpec.from_dict: happy paths
# ---------------------------------------------------------------------------

class TestFromDictMinimal:
    def test_voices_only_uses_all_defaults(self):
        spec = EnsembleSpec.from_dict("duo", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.name == "duo"
        assert spec.label == "duo"
        assert len(spec.voices) == 2
        assert spec.max_spacing == (19,)  # single gap defaults to the "bottom gap" value
        assert spec.allow_unisons is True
        assert spec.weights == DEFAULT_WEIGHTS

    def test_default_spacing_for_three_voices(self):
        spec = EnsembleSpec.from_dict("trio", {
            "voices": [
                {"name": "A", "range": [72, 84]},
                {"name": "B", "range": [60, 72]},
                {"name": "C", "range": [48, 60]},
            ],
        })
        assert spec.max_spacing == (12, 19)

    def test_note_name_ranges(self):
        spec = EnsembleSpec.from_dict("satb_like", {
            "voices": [
                {"name": "Soprano", "range": ["C4", "G5"]},
                {"name": "Bass", "range": ["E2", "C4"]},
            ],
        })
        assert spec.voices[0].low == 60
        assert spec.voices[0].high == 79
        assert spec.voices[1].low == 40
        assert spec.voices[1].high == 60

    def test_midi_int_ranges(self):
        spec = EnsembleSpec.from_dict("ints", {
            "voices": [
                {"name": "Top", "range": [60, 79]},
                {"name": "Bottom", "range": [40, 60]},
            ],
        })
        assert spec.voices[0].low == 60
        assert spec.voices[1].high == 60

    def test_mixed_note_name_and_int_range(self):
        spec = EnsembleSpec.from_dict("mixed", {
            "voices": [
                {"name": "Top", "range": ["C4", 79]},
                {"name": "Bottom", "range": [40, "C4"]},
            ],
        })
        assert spec.voices[0].low == 60
        assert spec.voices[0].high == 79
        assert spec.voices[1].low == 40
        assert spec.voices[1].high == 60

    def test_explicit_label_and_flags(self):
        spec = EnsembleSpec.from_dict("custom", {
            "label": "My Custom Ensemble",
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
            "allow_unisons": False,
        })
        assert spec.label == "My Custom Ensemble"
        assert spec.allow_unisons is False


# ---------------------------------------------------------------------------
# EnsembleSpec.from_dict: validation errors
# ---------------------------------------------------------------------------

class TestFromDictValidation:
    def test_missing_voices_raises(self):
        with pytest.raises(ConfigurationError, match="voices"):
            EnsembleSpec.from_dict("bad", {})

    def test_single_voice_raises(self):
        with pytest.raises(ConfigurationError, match="between 2 and 8"):
            EnsembleSpec.from_dict("bad", {
                "voices": [{"name": "Solo", "range": ["C4", "C5"]}],
            })

    def test_nine_voices_raises(self):
        voices = [
            {"name": f"V{i}", "range": [40 + i * 3, 40 + i * 3 + 2]} for i in range(9)
        ]
        with pytest.raises(ConfigurationError, match="between 2 and 8"):
            EnsembleSpec.from_dict("bad", {"voices": voices})

    def test_eight_voices_is_allowed(self):
        voices = [
            {"name": f"V{i}", "range": [40 + i * 3, 40 + i * 3 + 2]} for i in range(8)
        ]
        spec = EnsembleSpec.from_dict("eight", {"voices": voices})
        assert len(spec.voices) == 8

    def test_low_greater_than_high_raises(self):
        with pytest.raises(ConfigurationError, match="low < high"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C5", "C4"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
            })

    def test_low_equal_high_raises(self):
        with pytest.raises(ConfigurationError, match="low < high"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C4", "C4"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
            })

    def test_wrong_length_max_spacing_raises(self):
        # Documented behaviour: max_spacing must have exactly len(voices) - 1
        # entries; a mismatched length is a hard configuration error rather
        # than being silently padded or truncated.
        with pytest.raises(ConfigurationError, match="max_spacing"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C4", "C5"]},
                    {"name": "Mid", "range": ["C3", "C4"]},
                    {"name": "Bottom", "range": ["C2", "C3"]},
                ],
                "max_spacing": [12],  # needs 2 entries for 3 voices
            })

    def test_non_positive_spacing_entry_raises(self):
        with pytest.raises(ConfigurationError, match="positive"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C4", "C5"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
                "max_spacing": [0],
            })

    def test_invalid_note_name_raises(self):
        with pytest.raises(ConfigurationError, match="invalid note name"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["Hz4", "C5"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
            })

    def test_bad_allow_unisons_type_raises(self):
        with pytest.raises(ConfigurationError, match="allow_unisons"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C4", "C5"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
                "allow_unisons": "yes",
            })

    def test_missing_voice_name_raises(self):
        with pytest.raises(ConfigurationError, match="name"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"range": ["C4", "C5"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
            })


# ---------------------------------------------------------------------------
# Weight merging
# ---------------------------------------------------------------------------

class TestWeightMerging:
    def _voices(self):
        return [
            {"name": "Top", "range": ["C4", "C5"]},
            {"name": "Bottom", "range": ["C3", "C4"]},
        ]

    def test_partial_override_leaves_others_default(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": self._voices(),
            "weights": {"leap_penalty": 99.0},
        })
        assert spec.weight("leap_penalty") == 99.0
        assert spec.weight("octave_leap_penalty") == DEFAULT_WEIGHTS["octave_leap_penalty"]
        assert spec.weight("common_tone_bonus") == DEFAULT_WEIGHTS["common_tone_bonus"]

    def test_default_weight_signs(self):
        # Signed convention: every weight is added directly to the score.
        # Flat penalties and every omit sub-key are negative; bonuses,
        # doubling and inversion keep their existing signs.
        assert DEFAULT_WEIGHTS["movement"] == -0.4
        assert DEFAULT_WEIGHTS["bass_movement"] == -0.15
        assert DEFAULT_WEIGHTS["leap_penalty"] == -2.0
        assert DEFAULT_WEIGHTS["octave_leap_penalty"] == -6.0
        assert DEFAULT_WEIGHTS["tritone_leap_penalty"] == -3.0
        assert DEFAULT_WEIGHTS["parallel_perfect_penalty"] == -25.0
        assert DEFAULT_WEIGHTS["double_leading_tone_penalty"] == -8.0
        assert DEFAULT_WEIGHTS["range_comfort_penalty"] == -0.5
        assert DEFAULT_WEIGHTS["unison_penalty"] == -0.5
        assert DEFAULT_WEIGHTS["upper_spacing_penalty"] == -0.15
        # Bonuses unchanged (positive).
        assert DEFAULT_WEIGHTS["common_tone_bonus"] == 1.5
        assert DEFAULT_WEIGHTS["contrary_motion_bonus"] == 0.8
        assert DEFAULT_WEIGHTS["seventh_resolution_bonus"] == 1.5
        assert DEFAULT_WEIGHTS["leading_tone_resolution_bonus"] == 1.5
        # omit flipped to all-negative.
        assert DEFAULT_WEIGHTS["omit"] == {
            "root": -4.0, "third": -40.0, "fifth": -8.0,
            "seventh": -40.0, "color": -30.0, "extension": -7.0,
        }
        # doubling and inversion untouched (already signed).
        assert DEFAULT_WEIGHTS["doubling"] == {
            "root": 2.0, "fifth": 0.5, "third": -2.0,
            "seventh": -6.0, "color": -6.0, "extension": -6.0,
        }
        assert DEFAULT_WEIGHTS["inversion"] == {
            "root": 0.0, "first": -1.5, "second": -5.0, "third": -3.0,
        }

    def test_nested_merge_leaves_other_subkeys_default(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": self._voices(),
            "weights": {"doubling": {"root": 10.0}},
        })
        assert spec.weight("doubling")["root"] == 10.0
        assert spec.weight("doubling")["fifth"] == DEFAULT_WEIGHTS["doubling"]["fifth"]
        assert spec.weight("doubling")["third"] == DEFAULT_WEIGHTS["doubling"]["third"]
        # Untouched nested dicts stay fully default.
        assert spec.weight("omit") == DEFAULT_WEIGHTS["omit"]

    def test_unknown_top_level_key_warns_and_is_ignored(self, caplog):
        with caplog.at_level(logging.WARNING):
            spec = EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"totally_made_up_key": 5.0},
            })
        assert "totally_made_up_key" not in spec.weights
        assert any("totally_made_up_key" in record.message for record in caplog.records)

    def test_unknown_nested_key_warns_and_is_ignored(self, caplog):
        with caplog.at_level(logging.WARNING):
            spec = EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"doubling": {"nonexistent_role": 1.0}},
            })
        assert "nonexistent_role" not in spec.weights["doubling"]
        assert any("nonexistent_role" in record.message for record in caplog.records)

    def test_wrong_typed_scalar_weight_raises(self):
        with pytest.raises(ConfigurationError, match="leap_penalty"):
            EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"leap_penalty": "big"},
            })

    def test_wrong_typed_nested_weight_raises(self):
        with pytest.raises(ConfigurationError, match="doubling"):
            EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"doubling": "not a mapping"},
            })

    def test_wrong_typed_nested_subkey_value_raises(self):
        with pytest.raises(ConfigurationError, match="doubling"):
            EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"doubling": {"root": "high"}},
            })

    def test_bool_rejected_as_numeric_weight(self):
        with pytest.raises(ConfigurationError, match="leap_penalty"):
            EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"leap_penalty": True},
            })

    def test_movement_as_list_accepted(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": self._voices(),
            "weights": {"movement": [0.5, 0.2]},
        })
        assert spec.weight("movement") == [0.5, 0.2]

    def test_movement_wrong_type_raises(self):
        with pytest.raises(ConfigurationError, match="movement"):
            EnsembleSpec.from_dict("w", {
                "voices": self._voices(),
                "weights": {"movement": "fast"},
            })


# ---------------------------------------------------------------------------
# movement_per_voice()
# ---------------------------------------------------------------------------

class TestMovementPerVoice:
    def _spec(self, n_voices, weights=None):
        voices = [
            {"name": f"V{i}", "range": [40 + i * 3, 40 + i * 3 + 2]} for i in range(n_voices)
        ]
        data = {"voices": voices}
        if weights is not None:
            data["weights"] = weights
        return EnsembleSpec.from_dict("m", data)

    def test_scalar_broadcasts_to_all_but_bottom(self):
        spec = self._spec(4)
        result = spec.movement_per_voice()
        assert result == (-0.4, -0.4, -0.4, -0.15)

    def test_list_used_verbatim(self):
        spec = self._spec(3, weights={"movement": [1.0, 2.0, 3.0]})
        assert spec.movement_per_voice() == (1.0, 2.0, 3.0)

    def test_list_wrong_length_raises(self):
        spec = self._spec(3, weights={"movement": [1.0, 2.0]})
        with pytest.raises(ConfigurationError, match="movement"):
            spec.movement_per_voice()

    def test_custom_bass_movement_used_for_bottom_voice(self):
        spec = self._spec(2, weights={"bass_movement": 0.9})
        assert spec.movement_per_voice() == (-0.4, 0.9)


# ---------------------------------------------------------------------------
# weight() accessor
# ---------------------------------------------------------------------------

class TestWeightAccessor:
    def test_returns_scalar(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.weight("common_tone_bonus") == 1.5

    def test_returns_nested_mapping(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.weight("inversion")["second"] == -5.0

    def test_unknown_key_raises_key_error(self):
        spec = EnsembleSpec.from_dict("w", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        with pytest.raises(KeyError):
            spec.weight("nope")


# ---------------------------------------------------------------------------
# to_dict / from_dict round trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_round_trip_preserves_everything(self):
        original = EnsembleSpec.from_dict("roundtrip", {
            "label": "Round Trip Ensemble",
            "voices": [
                {"name": "Top", "range": ["C4", "G5"]},
                {"name": "Mid", "range": ["F3", "D5"]},
                {"name": "Bottom", "range": ["E2", "C4"]},
            ],
            "max_spacing": [10, 20],
            "allow_unisons": False,
            "weights": {"leap_penalty": 7.0, "doubling": {"root": 3.0}},
        })

        rebuilt = EnsembleSpec.from_dict(original.name, original.to_dict())

        assert rebuilt.name == original.name
        assert rebuilt.label == original.label
        assert rebuilt.voices == original.voices
        assert rebuilt.max_spacing == original.max_spacing
        assert rebuilt.allow_unisons == original.allow_unisons
        assert rebuilt.weights == original.weights

    def test_round_trip_of_default_weights(self):
        original = EnsembleSpec.from_dict("plain", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        rebuilt = EnsembleSpec.from_dict(original.name, original.to_dict())
        assert rebuilt == original


# ---------------------------------------------------------------------------
# Built-in ensembles
# ---------------------------------------------------------------------------

class TestBuiltinEnsembles:
    def test_expected_keys_present(self):
        assert set(BUILTIN_ENSEMBLES.keys()) == {"satb", "ttbb", "ssa", "quartet"}

    @pytest.mark.parametrize("key", ["satb", "ttbb", "ssa", "quartet"])
    def test_each_builtin_is_internally_consistent(self, key):
        spec = BUILTIN_ENSEMBLES[key]
        assert isinstance(spec, EnsembleSpec)
        assert 2 <= len(spec.voices) <= 8
        assert len(spec.max_spacing) == len(spec.voices) - 1
        for voice in spec.voices:
            assert voice.low < voice.high
            assert 0 <= voice.low <= 127
            assert 0 <= voice.high <= 127
        for gap in spec.max_spacing:
            assert gap > 0
        assert spec.weights == DEFAULT_WEIGHTS

    def test_satb_voice_names_and_label(self):
        spec = BUILTIN_ENSEMBLES["satb"]
        assert spec.label == "Choir (SATB)"
        assert [v.name for v in spec.voices] == ["Soprano", "Alto", "Tenor", "Bass"]
        assert spec.max_spacing == (12, 12, 19)

    def test_ttbb_voice_names_and_label(self):
        spec = BUILTIN_ENSEMBLES["ttbb"]
        assert spec.label == "Male Choir (TTBB)"
        assert [v.name for v in spec.voices] == ["Tenor 1", "Tenor 2", "Baritone", "Bass"]
        assert spec.max_spacing == (12, 12, 12)

    def test_ssa_voice_names_and_label(self):
        spec = BUILTIN_ENSEMBLES["ssa"]
        assert spec.label == "Treble Choir (SSA)"
        assert [v.name for v in spec.voices] == ["Soprano 1", "Soprano 2", "Alto"]
        assert spec.max_spacing == (12, 12)

    def test_quartet_voice_names_and_label(self):
        spec = BUILTIN_ENSEMBLES["quartet"]
        assert spec.label == "String Quartet"
        assert [v.name for v in spec.voices] == ["Violin I", "Violin II", "Viola", "Cello"]
        assert spec.max_spacing == (14, 14, 24)

    def test_satb_ranges_match_note_names(self):
        spec = BUILTIN_ENSEMBLES["satb"]
        soprano, alto, tenor, bass = spec.voices
        assert (soprano.low, soprano.high) == (parse_note_name("C4"), parse_note_name("G5"))
        assert (alto.low, alto.high) == (parse_note_name("F3"), parse_note_name("D5"))
        assert (tenor.low, tenor.high) == (parse_note_name("C3"), parse_note_name("G4"))
        assert (bass.low, bass.high) == (parse_note_name("E2"), parse_note_name("C4"))
