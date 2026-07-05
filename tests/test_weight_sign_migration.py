"""Tests for the config-version migrations of voicing weights.

v1 -> v2: v1 stored voicing penalty weights as positive magnitudes that the
engine subtracted; v2 stores every weight as a signed contribution the engine
adds. The migration negates each overridden penalty key (fretboard penalties,
ensemble flat penalties, and every ``omit`` sub-key) so a migrated config
produces byte-identical voicings, while leaving bonuses, ``doubling`` and
``inversion`` untouched.

v2 -> v3: ``interior_mute_penalty``'s default was recalibrated from -2.0 to
-4.0; fretboard voicings still carrying the exact old default follow it, while
user-tuned values stay. A v1 config chains through both steps (+2.0 -> -2.0 ->
-4.0). The version gate makes the whole pipeline idempotent.
"""

import copy
from pathlib import Path

from services.config_service import ConfigService


class _FakeAppData:
    """Minimal stand-in exposing only what ConfigService touches."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get_config_file_path(self) -> Path:
        return self._path


def _service(tmp_path) -> ConfigService:
    return ConfigService(_FakeAppData(tmp_path / "settings.json"))


def _v1_config() -> dict:
    return {
        "version": 1,
        "voicings": {
            "my_guitar": {
                "model": "fretboard",
                "tuning": [40, 45, 50, 55, 59, 64],
                "weights": {
                    # penalties (positive magnitudes under v1)
                    "span_penalty": 1.2,
                    "position_penalty": 0.6,
                    "fretted_finger_penalty": 0.5,
                    "barre_penalty": 1.0,
                    "interior_mute_penalty": 2.0,
                    "movement_penalty": 1.0,
                    # bonuses stay positive
                    "bass_note_bonus": 8.0,
                    "sounding_string_bonus": 1.2,
                },
            },
            "my_choir": {
                "model": "ensemble",
                "voices": [
                    {"name": "S", "range": ["C4", "G5"]},
                    {"name": "A", "range": ["F3", "D5"]},
                    {"name": "T", "range": ["C3", "G4"]},
                    {"name": "B", "range": ["E2", "C4"]},
                ],
                "weights": {
                    "movement": 0.4,
                    "bass_movement": 0.15,
                    "leap_penalty": 2.0,
                    "octave_leap_penalty": 6.0,
                    "tritone_leap_penalty": 3.0,
                    "parallel_perfect_penalty": 25.0,
                    "double_leading_tone_penalty": 8.0,
                    "range_comfort_penalty": 0.5,
                    "unison_penalty": 0.5,
                    "upper_spacing_penalty": 0.15,
                    # bonuses unchanged
                    "common_tone_bonus": 1.5,
                    "contrary_motion_bonus": 0.8,
                    # nested: omit flips, doubling/inversion do not
                    "omit": {"root": 4.0, "third": 40.0, "fifth": 8.0},
                    "doubling": {"root": 2.0, "third": -2.0},
                    "inversion": {"first": -1.5, "second": -5.0},
                },
            },
            "list_movement": {
                "model": "ensemble",
                "voices": [
                    {"name": "T", "range": ["C4", "C5"]},
                    {"name": "B", "range": ["C3", "C4"]},
                ],
                "weights": {"movement": [0.4, 0.15]},
            },
            "a_piano": {
                "model": "piano",
                "weights": {"span_penalty": 1.2},  # unknown model: untouched
            },
        },
    }


def test_fretboard_penalties_negated(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    w = migrated["voicings"]["my_guitar"]["weights"]
    assert w["span_penalty"] == -1.2
    assert w["position_penalty"] == -0.6
    assert w["fretted_finger_penalty"] == -0.5
    assert w["barre_penalty"] == -1.0
    # Chains through v3: the sign flip lands on -2.0 (the old default), which
    # the interior-mute recalibration then bumps to the new -4.0 default.
    assert w["interior_mute_penalty"] == -4.0
    assert w["movement_penalty"] == -1.0
    # Bonuses stay positive.
    assert w["bass_note_bonus"] == 8.0
    assert w["sounding_string_bonus"] == 1.2


def test_ensemble_flat_penalties_and_omit_negated(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    w = migrated["voicings"]["my_choir"]["weights"]
    assert w["movement"] == -0.4
    assert w["bass_movement"] == -0.15
    assert w["leap_penalty"] == -2.0
    assert w["octave_leap_penalty"] == -6.0
    assert w["tritone_leap_penalty"] == -3.0
    assert w["parallel_perfect_penalty"] == -25.0
    assert w["double_leading_tone_penalty"] == -8.0
    assert w["range_comfort_penalty"] == -0.5
    assert w["unison_penalty"] == -0.5
    assert w["upper_spacing_penalty"] == -0.15

    # omit sub-keys all negated.
    assert w["omit"] == {"root": -4.0, "third": -40.0, "fifth": -8.0}


def test_ensemble_bonuses_doubling_inversion_untouched(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    w = migrated["voicings"]["my_choir"]["weights"]
    assert w["common_tone_bonus"] == 1.5
    assert w["contrary_motion_bonus"] == 0.8
    # doubling and inversion are already signed, left exactly as-is.
    assert w["doubling"] == {"root": 2.0, "third": -2.0}
    assert w["inversion"] == {"first": -1.5, "second": -5.0}


def test_movement_list_negated_elementwise(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    w = migrated["voicings"]["list_movement"]["weights"]
    assert w["movement"] == [-0.4, -0.15]


def test_unknown_model_untouched(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    # 'piano' is neither fretboard nor ensemble: no keys are negated.
    assert migrated["voicings"]["a_piano"]["weights"]["span_penalty"] == 1.2


def test_version_bumped_to_current(tmp_path):
    service = _service(tmp_path)
    migrated = service._migrate_config(copy.deepcopy(_v1_config()), 1)
    assert migrated["version"] == 3


def test_migration_is_idempotent_via_version_gate(tmp_path):
    service = _service(tmp_path)
    once = service._migrate_config(copy.deepcopy(_v1_config()), 1)

    # Re-running with the migrated data's own (already-current) version does not
    # negate again: the from_version >= 2 gate short-circuits the flip.
    twice = service._migrate_config(copy.deepcopy(once), once["version"])

    assert twice["voicings"]["my_guitar"]["weights"]["span_penalty"] == -1.2
    assert twice["voicings"]["my_choir"]["weights"]["omit"]["third"] == -40.0
    assert twice["voicings"]["my_choir"]["weights"]["movement"] == -0.4
    assert twice == once


def test_v2_interior_mute_default_bumped_to_v3(tmp_path):
    """A v2 config still on the old -2.0 interior-mute default follows the
    recalibrated -4.0 default; a user-tuned value is left alone."""
    service = _service(tmp_path)
    data = {
        "version": 2,
        "voicings": {
            "seven_string": {
                "model": "fretboard",
                "tuning": [35, 40, 45, 50, 55, 59, 64],
                "weights": {"interior_mute_penalty": -2.0, "barre_penalty": -1.0},
            },
            "tuned_by_hand": {
                "model": "fretboard",
                "tuning": [40, 45, 50, 55, 59, 64],
                "weights": {"interior_mute_penalty": -2.5},
            },
            "my_choir": {
                "model": "ensemble",
                "voices": [{"name": "B", "range": ["C3", "C4"]}],
                "weights": {"movement": -0.4},
            },
        },
    }
    migrated = service._migrate_config(data, 2)

    assert migrated["voicings"]["seven_string"]["weights"]["interior_mute_penalty"] == -4.0
    # Other weights and non-default values are untouched.
    assert migrated["voicings"]["seven_string"]["weights"]["barre_penalty"] == -1.0
    assert migrated["voicings"]["tuned_by_hand"]["weights"]["interior_mute_penalty"] == -2.5
    # Non-fretboard models are never touched.
    assert migrated["voicings"]["my_choir"]["weights"] == {"movement": -0.4}
    assert migrated["version"] == 3


def test_v2_to_v3_does_not_renegate_signs(tmp_path):
    """Migrating from v2 skips the sign flip entirely."""
    service = _service(tmp_path)
    data = {
        "version": 2,
        "voicings": {
            "my_guitar": {
                "model": "fretboard",
                "tuning": [40, 45, 50, 55, 59, 64],
                "weights": {"span_penalty": -1.2, "bass_note_bonus": 8.0},
            },
        },
    }
    migrated = service._migrate_config(data, 2)
    w = migrated["voicings"]["my_guitar"]["weights"]
    assert w == {"span_penalty": -1.2, "bass_note_bonus": 8.0}


def test_only_overridden_keys_negated_missing_inherit_defaults(tmp_path):
    """A voicing that overrode only some keys leaves the rest absent (they
    inherit the new negative defaults at spec-build time, not here)."""
    service = _service(tmp_path)
    data = {
        "version": 1,
        "voicings": {
            "sparse": {
                "model": "fretboard",
                "tuning": [40, 45, 50, 55, 59, 64],
                "weights": {"barre_penalty": 1.0},
            },
        },
    }
    migrated = service._migrate_config(data, 1)
    w = migrated["voicings"]["sparse"]["weights"]
    assert w == {"barre_penalty": -1.0}
    assert "span_penalty" not in w
