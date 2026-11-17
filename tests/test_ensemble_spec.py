"""Tests for the ensemble voicer configuration model (core/chordnotepad/models/ensemble_spec.py)."""

import logging

import pytest

from chordnotepad.exceptions import ConfigurationError
from chordnotepad.models.ensemble_spec import (
    BUILTIN_ENSEMBLES,
    CHOIR_WEIGHTS,
    SSA_WEIGHTS,
    DEFAULT_WEIGHTS,
    PRESET_INVERSION,
    EnsembleSpec,
    QUARTET_WEIGHTS,
    VoiceSpec,
    _merge_weights,
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
        assert v.staff is None

    def test_is_frozen(self):
        v = VoiceSpec(name="Alto", low=53, high=74)
        with pytest.raises(AttributeError):
            v.low = 0

    def test_explicit_staff_construction(self):
        v = VoiceSpec(name="Bass", low=40, high=60, staff="bass")
        assert v.staff == "bass"


# ---------------------------------------------------------------------------
# VoiceSpec.resolved_staff
# ---------------------------------------------------------------------------

class TestResolvedStaff:
    def test_explicit_staff_wins(self):
        # Range center is well above middle C, but staff is pinned to bass.
        v = VoiceSpec(name="X", low=60, high=79, staff="bass")
        assert v.resolved_staff == "bass"

    def test_auto_resolves_to_treble_when_center_at_or_above_middle_c(self):
        v = VoiceSpec(name="X", low=60, high=79)  # center 69.5
        assert v.resolved_staff == "treble"

    def test_auto_resolves_to_bass_when_center_below_middle_c(self):
        v = VoiceSpec(name="X", low=40, high=59)  # center 49.5
        assert v.resolved_staff == "bass"

    def test_auto_boundary_exactly_middle_c_is_treble(self):
        # center == 60 (middle C) is not "below", so it resolves treble.
        v = VoiceSpec(name="X", low=55, high=65)  # center 60
        assert v.resolved_staff == "treble"

    def test_auto_boundary_just_below_middle_c_is_bass(self):
        v = VoiceSpec(name="X", low=54, high=65)  # center 59.5
        assert v.resolved_staff == "bass"

    def test_octave_lower_treble_splits_auto_at_c3(self):
        # A tenor range (center 53.5) sits on the bass staff under a plain
        # treble but on the octave-lower treble, written an octave higher.
        tenor = VoiceSpec(name="T", low=45, high=62)
        assert tenor.staff_under("treble") == "bass"
        assert tenor.staff_under("treble_8vb") == "treble"
        # C3 itself (center 48) goes up; just below it stays on the bass staff.
        assert VoiceSpec(name="X", low=43, high=53).staff_under("treble_8vb") == "treble"
        assert VoiceSpec(name="X", low=42, high=53).staff_under("treble_8vb") == "bass"
        # An explicit staff still wins.
        assert VoiceSpec(name="X", low=45, high=62, staff="bass").staff_under("treble_8vb") == "bass"


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

    def test_voice_without_staff_key_defaults_to_none(self):
        spec = EnsembleSpec.from_dict("plain", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.voices[0].staff is None
        assert spec.voices[1].staff is None

    @pytest.mark.parametrize("staff", ["treble", "bass"])
    def test_explicit_valid_staff_accepted(self, staff):
        spec = EnsembleSpec.from_dict("staffed", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"], "staff": staff},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.voices[0].staff == staff
        assert spec.voices[1].staff is None


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
            {"name": f"V{i}", "range": [61 - i * 3, 63 - i * 3]} for i in range(8)
        ]
        spec = EnsembleSpec.from_dict("eight", {"voices": voices})
        assert len(spec.voices) == 8

    @pytest.mark.parametrize("upper, lower", [
        (["C3", "C4"], ["C4", "C5"]),     # swapped: the Android ↑ on voice 2
        (["C4", "G4"], ["C3", "A4"]),     # the voice below reaches higher
        (["D4", "C5"], ["E4", "C5"]),     # the voice below starts higher
    ])
    def test_a_voice_lower_than_the_one_below_it_raises(self, upper, lower):
        with pytest.raises(ConfigurationError,
                           match="voice 'Upper' .* is lower than voice 'Lower' below it"):
            EnsembleSpec.from_dict("bad", {"voices": [
                {"name": "Upper", "range": upper}, {"name": "Lower", "range": lower}]})

    def test_overlapping_or_equal_ranges_in_order_are_fine(self):
        spec = EnsembleSpec.from_dict("ok", {"voices": [
            {"name": "A", "range": ["C4", "C5"]}, {"name": "B", "range": ["C4", "C5"]},
            {"name": "C", "range": ["G3", "C5"]}, {"name": "D", "range": ["G3", "G4"]}]})
        assert [v.name for v in spec.voices] == ["A", "B", "C", "D"]

    def test_every_builtin_is_in_order(self):
        for spec in BUILTIN_ENSEMBLES.values():
            EnsembleSpec.from_dict(spec.name, spec.to_dict())

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

    def test_bad_staff_value_raises_naming_voice_and_value(self):
        with pytest.raises(ConfigurationError, match="Lead") as excinfo:
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Lead", "range": ["C4", "C5"], "staff": "alto"},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
            })
        assert "alto" in str(excinfo.value)

    def test_wrong_typed_staff_raises(self):
        with pytest.raises(ConfigurationError, match="staff"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Lead", "range": ["C4", "C5"], "staff": 1},
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
        assert DEFAULT_WEIGHTS["tritone_leap_penalty"] == -4.5
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
        # omit is all-negative, in the ensemble's own order (fifth first).
        assert DEFAULT_WEIGHTS["omit"] == {
            "root": -20.0, "third": -40.0, "fifth": -3.0,
            "seventh": -40.0, "color": -30.0, "extension": -6.0,
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
            {"name": f"V{i}", "range": [61 - i * 3, 63 - i * 3]} for i in range(n_voices)
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

    def test_list_of_another_length_is_adapted_with_one_warning(self, caplog):
        spec = self._spec(6, weights={"movement": [-0.8, -0.4, -0.4, -0.15]})
        with caplog.at_level("WARNING"):
            result = spec.movement_per_voice()
        assert result == (-0.8, -0.4, -0.4, -0.4, -0.4, -0.15)
        assert len([r for r in caplog.records if "movement" in r.getMessage()]) == 1
        assert spec.movement_per_voice() == result

    def test_adaptation_by_relative_position(self):
        weights = {"movement": [-1.0, -0.1, -0.2, -0.3, -0.4, -0.5]}
        assert self._spec(4, weights).movement_per_voice() == (-1.0, -0.2, -0.4, -0.5)
        assert self._spec(3, weights).movement_per_voice() == (-1.0, -0.3, -0.5)
        assert self._spec(8, weights).movement_per_voice() == (
            -1.0, -0.1, -0.2, -0.2, -0.3, -0.4, -0.4, -0.5)

    def test_adaptation_of_a_list_of_one_or_two(self):
        assert self._spec(4, {"movement": [-0.5]}).movement_per_voice() == (-0.5,) * 4
        assert self._spec(4, {"movement": [-1.0, -0.2]}).movement_per_voice() == (
            -1.0, -0.6, -0.6, -0.2)
        assert self._spec(3, {"movement": [-0.8, -0.2]}).movement_per_voice() == (-0.8, -0.5, -0.2)
        assert self._spec(2, {"movement": [-0.5]}).movement_per_voice() == (-0.5, -0.5)

    def test_list_that_is_not_numbers_still_raises(self):
        for bad in ([], ["x", 1.0], [None, 1.0]):
            with pytest.raises(ConfigurationError, match="movement"):
                self._spec(3, weights={"movement": bad}).movement_per_voice()

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

    def test_round_trip_preserves_explicit_staff(self):
        original = EnsembleSpec.from_dict("staffed", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"], "staff": "treble"},
                {"name": "Bottom", "range": ["C3", "C4"], "staff": "bass"},
            ],
        })
        rebuilt = EnsembleSpec.from_dict(original.name, original.to_dict())
        assert rebuilt.voices[0].staff == "treble"
        assert rebuilt.voices[1].staff == "bass"
        assert rebuilt == original

    def test_round_trip_preserves_upper_clef(self):
        original = EnsembleSpec.from_dict("tenors", {
            "voices": [
                {"name": "Top", "range": ["C3", "A4"], "staff": "treble"},
                {"name": "Bottom", "range": ["E2", "C4"], "staff": "bass"},
            ],
            "upper_clef": "treble_8vb",
        })
        data = original.to_dict()
        assert data["upper_clef"] == "treble_8vb"
        rebuilt = EnsembleSpec.from_dict(original.name, data)
        assert rebuilt.upper_clef == "treble_8vb"
        assert rebuilt == original

    def test_upper_clef_defaults_to_treble_and_is_not_written(self):
        # Configs from before the option load as a plain treble.
        spec = EnsembleSpec.from_dict("plain", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        assert spec.upper_clef == "treble"
        assert "upper_clef" not in spec.to_dict()
        explicit = EnsembleSpec.from_dict("plain", {**spec.to_dict(), "upper_clef": "treble"})
        assert explicit == spec

    @pytest.mark.parametrize("bad", ["alto", "bass", "Treble", "", 8, True])
    def test_invalid_upper_clef_raises(self, bad):
        with pytest.raises(ConfigurationError, match="upper_clef"):
            EnsembleSpec.from_dict("bad", {
                "voices": [
                    {"name": "Top", "range": ["C4", "C5"]},
                    {"name": "Bottom", "range": ["C3", "C4"]},
                ],
                "upper_clef": bad,
            })

    def test_to_dict_omits_staff_key_when_none(self):
        spec = EnsembleSpec.from_dict("plain", {
            "voices": [
                {"name": "Top", "range": ["C4", "C5"]},
                {"name": "Bottom", "range": ["C3", "C4"]},
            ],
        })
        for voice_dict in spec.to_dict()["voices"]:
            assert "staff" not in voice_dict


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
        if key == "quartet":
            assert spec.weights == _merge_weights(QUARTET_WEIGHTS)
        elif key == "ssa":
            assert spec.weights == _merge_weights(SSA_WEIGHTS)
        else:
            assert spec.weights == _merge_weights(CHOIR_WEIGHTS)

    @pytest.mark.parametrize("key", ["satb", "ttbb", "ssa"])
    def test_choirs_allow_unisons(self, key):
        assert BUILTIN_ENSEMBLES[key].allow_unisons is True

    @pytest.mark.parametrize("key", ["satb", "ttbb", "ssa", "quartet"])
    def test_presets_keep_plain_chords_in_root_position(self, key):
        # The bass plan charges these; the defaults' -1.5 loses to a held bass.
        inversion = BUILTIN_ENSEMBLES[key].weight("inversion")
        assert inversion == {"root": 0.0, "first": -4.0, "second": -8.0, "third": -6.0}
        assert inversion == PRESET_INVERSION
        assert DEFAULT_WEIGHTS["inversion"]["first"] == -1.5   # saved ensembles: unchanged

    @pytest.mark.parametrize("key", ["satb", "ttbb", "ssa"])
    def test_choirs_resolve_harder_over_root_position(self, key):
        spec = BUILTIN_ENSEMBLES[key]
        assert spec.weight("seventh_resolution_bonus") == 3.0
        assert spec.weight("leading_tone_resolution_bonus") == 4.0
        assert spec.weight("middle_range_penalty") == -0.5
        own = SSA_WEIGHTS if key == "ssa" else CHOIR_WEIGHTS
        for weight_key, value in DEFAULT_WEIGHTS.items():
            if weight_key not in own:
                assert spec.weight(weight_key) == value

    def test_ssa_moves_its_top_voice_least(self):
        assert BUILTIN_ENSEMBLES["ssa"].movement_per_voice() == (-0.8, -0.4, -0.15)
        assert BUILTIN_ENSEMBLES["satb"].movement_per_voice() == (-0.4, -0.4, -0.4, -0.15)

    @pytest.mark.parametrize("key", ["satb", "ttbb", "ssa"])
    def test_a_choir_copy_saved_before_the_middle_band_moves_to_it(self, key):
        # voicing_versions 1->2: a copy still on the values the preset had
        # (middle band off, movement -0.4 / bass -0.15) takes the new ones.
        from chordnotepad.models import voicing_versions as vv
        spec = BUILTIN_ENSEMBLES[key]
        entry = {"model": "ensemble", "based_on": f"ensemble:{key}",
                 "voices": [{"name": v.name, "range": [v.low, v.high]} for v in spec.voices],
                 "weights": {"middle_range_penalty": 0.0, "movement": -0.4,
                             "bass_movement": -0.15}}
        vv._migrate_1_to_2(entry)
        assert entry["weights"]["middle_range_penalty"] == -0.5
        moved = EnsembleSpec.from_dict(key, entry)
        assert moved.movement_per_voice() == spec.movement_per_voice()
        # A user's own value stays.
        mine = dict(entry, weights={"middle_range_penalty": -0.2})
        vv._migrate_1_to_2(mine)
        assert mine["weights"]["middle_range_penalty"] == -0.2

    def test_quartet_has_its_own_weights_and_no_unisons(self):
        # A background pad: the top voice moves least, and with the heavier top
        # the leading tone still rises in V-vi; no unisons.
        spec = BUILTIN_ENSEMBLES["quartet"]
        assert spec.allow_unisons is False
        assert spec.movement_per_voice() == (-0.8, -0.4, -0.4, -0.15)
        assert spec.weight("leading_tone_resolution_bonus") == 4.5
        assert spec.weight("seventh_resolution_bonus") == 3.0
        # Everything the quartet doesn't override is the default.
        for key, value in DEFAULT_WEIGHTS.items():
            if key not in QUARTET_WEIGHTS:
                assert spec.weight(key) == value

    def test_a_quartet_copy_keeps_its_weights(self):
        spec = BUILTIN_ENSEMBLES["quartet"]
        rebuilt = EnsembleSpec.from_dict("copy", spec.to_dict())
        assert rebuilt.weights == spec.weights
        assert rebuilt.allow_unisons is False

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

    def test_satb_has_explicit_staff_assignments(self):
        spec = BUILTIN_ENSEMBLES["satb"]
        soprano, alto, tenor, bass = spec.voices
        assert soprano.staff == "treble"
        assert alto.staff == "treble"
        assert tenor.staff == "bass"
        assert bass.staff == "bass"
        # Explicit values also match what auto-resolution would produce,
        # so resolved_staff agrees regardless of how it got there.
        for voice in spec.voices:
            assert voice.resolved_staff == voice.staff

    @pytest.mark.parametrize("key,staffs,upper_clef", [
        # A male choir writes its tenors on the octave-lower treble clef.
        ("satb", ["treble", "treble", "bass", "bass"], "treble"),
        ("ttbb", ["treble", "treble", "bass", "bass"], "treble_8vb"),
        ("ssa", ["treble", "treble", "treble"], "treble"),
        # The viola stays auto until the staff view has a C clef.
        ("quartet", ["treble", "treble", None, "bass"], "treble"),
    ])
    def test_builtin_staffs_and_upper_clef(self, key, staffs, upper_clef):
        spec = BUILTIN_ENSEMBLES[key]
        assert [v.staff for v in spec.voices] == staffs
        assert spec.upper_clef == upper_clef

    def test_builtins_round_trip(self):
        for key, spec in BUILTIN_ENSEMBLES.items():
            assert EnsembleSpec.from_dict(key, spec.to_dict()) == spec


class TestSameBassPenalty:
    """The weight added for the same chord over another bass sounding one bass."""

    def _voices(self):
        return [
            {"name": "Top", "range": ["C4", "C5"]},
            {"name": "Bottom", "range": ["C3", "C4"]},
        ]

    def test_default_is_a_five_point_nudge(self):
        assert DEFAULT_WEIGHTS["same_bass_penalty"] == -8.0

    def test_saved_voicing_without_the_key_gets_the_default(self):
        spec = EnsembleSpec.from_dict("old", {
            "voices": self._voices(),
            "weights": {"leap_penalty": -2.0},
        })
        assert spec.weight("same_bass_penalty") == -8.0

    def test_override_round_trips(self):
        spec = EnsembleSpec.from_dict("mine", {
            "voices": self._voices(),
            "weights": {"same_bass_penalty": -1},
        })
        assert spec.weight("same_bass_penalty") == -1.0
        rebuilt = EnsembleSpec.from_dict(spec.name, spec.to_dict())
        assert rebuilt.weight("same_bass_penalty") == -1.0

    def test_non_numeric_raises(self):
        with pytest.raises(ConfigurationError):
            EnsembleSpec.from_dict("bad", {
                "voices": self._voices(),
                "weights": {"same_bass_penalty": "a lot"},
            })

    @pytest.mark.parametrize("name", sorted(BUILTIN_ENSEMBLES))
    def test_builtins_use_the_default(self, name):
        assert BUILTIN_ENSEMBLES[name].weight("same_bass_penalty") == -8.0
