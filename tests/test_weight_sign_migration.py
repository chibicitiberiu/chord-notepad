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

These steps are tested here on ``_migrate_config`` itself. ConfigService
reaches them only for a file that was really written unsigned: every release
from 0.3.0 to 0.5.4 saved a new config as version 1 with signed voicings, so
a file below version 3 that has a ``voicings`` mapping is read as version 3
(``effective_version``): no sign flip, no interior-mute bump. v0.1 and v0.2
kept their tunings under ``custom_tunings``, which carries no weights.
"""

import copy
import json
from pathlib import Path

from chordnotepad.constants import CONFIG_VERSION
from chordnotepad.services.config_service import ConfigService, effective_version


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

    # omit sub-keys all negated; that lands on the old defaults, which the v4
    # step then moves to the ensemble's own omission order.
    assert w["omit"] == {"root": -20.0, "third": -40.0, "fifth": -3.0}


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
    assert migrated["version"] == CONFIG_VERSION


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
    assert migrated["version"] == CONFIG_VERSION


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


_OLD_ENSEMBLE_OMIT = {"root": -4.0, "third": -40.0, "fifth": -8.0,
                      "seventh": -40.0, "color": -30.0, "extension": -7.0}


def _choir(omit):
    return {"model": "ensemble",
            "voices": [{"name": "S", "range": ["C4", "G5"]},
                       {"name": "A", "range": ["F3", "D5"]}],
            "weights": {"omit": dict(omit), "movement": -0.4}}


def test_v3_ensemble_omission_moves_to_the_ensemble_order(tmp_path):
    """Ensembles got their own omission order (fifth first, todo #14). Saved
    ensembles still on the old (piano) defaults follow it; tuned ones stay."""
    from chordnotepad.models.ensemble_spec import ENSEMBLE_OMIT_WEIGHTS
    service = _service(tmp_path)
    tuned = dict(_OLD_ENSEMBLE_OMIT, third=-35.0)
    data = {
        "version": 3,
        "voicings": {
            "copied_defaults": _choir(_OLD_ENSEMBLE_OMIT),
            "partial_defaults": _choir({"root": -4.0}),
            "tuned": _choir(tuned),
            "a_piano": {"model": "piano", "weights": {"omit": dict(_OLD_ENSEMBLE_OMIT)}},
        },
    }
    migrated = service._migrate_config(data, 3)
    v = migrated["voicings"]
    assert v["copied_defaults"]["weights"]["omit"] == ENSEMBLE_OMIT_WEIGHTS
    assert v["copied_defaults"]["weights"]["movement"] == -0.4
    assert v["partial_defaults"]["weights"]["omit"] == {"root": ENSEMBLE_OMIT_WEIGHTS["root"]}
    assert v["tuned"]["weights"]["omit"] == tuned
    assert v["a_piano"]["weights"]["omit"] == _OLD_ENSEMBLE_OMIT
    assert migrated["version"] == CONFIG_VERSION


def test_v1_ensemble_omission_chains_to_the_ensemble_order(tmp_path):
    from chordnotepad.models.ensemble_spec import ENSEMBLE_OMIT_WEIGHTS
    service = _service(tmp_path)
    v1_magnitudes = {role: -value for role, value in _OLD_ENSEMBLE_OMIT.items()}
    data = {"version": 1, "voicings": {"c": _choir(v1_magnitudes)}}
    data["voicings"]["c"]["weights"]["movement"] = 0.4
    migrated = service._migrate_config(data, 1)
    assert migrated["voicings"]["c"]["weights"]["omit"] == ENSEMBLE_OMIT_WEIGHTS


#: The fretboard weights a v4 config can carry (DEFAULT_WEIGHTS at v4), with
#: their v4 defaults. Saved voicings persist this whole dict.
_V4_FRETBOARD_WEIGHTS = {
    'sounding_string_bonus': 1.2, 'open_string_bonus': 0.5, 'bass_note_bonus': 8.0,
    'slash_bass_bonus': 12.0, 'span_penalty': -1.2, 'stretch_penalty': -0.7,
    'awkward_stretch_penalty': -6.0, 'position_penalty': -0.6,
    'fretted_finger_penalty': -0.5, 'barre_penalty': -1.0, 'finger_barre_penalty': -0.5,
    'interior_mute_penalty': -4.0, 'movement_penalty': -1.0, 'kept_finger_bonus': 0.4,
}


def test_v4_fretboard_voicing_gets_the_acoustic_tuning_weights(tmp_path):
    """The acoustic tuning added weights and changed no v4 default, so a v4
    config needs no migration: a saved voicing with its full v4 weight dict
    takes the new weights from the defaults, in the engine and the editor."""
    from chordnotepad.models.fretboard_spec import DEFAULT_WEIGHTS, FretboardSpec
    from chordnotepad.settings_forms.voicing_form import values_from_voicing
    assert {k: DEFAULT_WEIGHTS[k] for k in _V4_FRETBOARD_WEIGHTS} == _V4_FRETBOARD_WEIGHTS
    added = set(DEFAULT_WEIGHTS) - set(_V4_FRETBOARD_WEIGHTS)
    assert added == {'omitted_fifth_penalty', 'damped_mute_penalty', 'bass_register_penalty',
                     'thin_shape_penalty', 'low_interval_penalty', 'muted_treble_penalty'}

    entry = {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64],
             "weights": dict(_V4_FRETBOARD_WEIGHTS, span_penalty=-1.5)}
    data = {"version": 4, "voicings": {"mine": copy.deepcopy(entry)}}
    migrated = _service(tmp_path)._migrate_config(data, 4)
    assert migrated["voicings"]["mine"] == entry

    spec = FretboardSpec.from_dict("mine", entry)
    assert spec.weights == dict(DEFAULT_WEIGHTS, span_penalty=-1.5)
    values = values_from_voicing("fretboard", entry)
    for key in added:
        assert float(values[f"weight:{key}"]) == DEFAULT_WEIGHTS[key]


#: The ensemble weights a v4 config can carry (DEFAULT_WEIGHTS at v4), with
#: their v4 defaults. Saved ensembles persist this whole dict.
_V4_ENSEMBLE_WEIGHTS = {
    'movement': -0.4, 'bass_movement': -0.15, 'leap_penalty': -2.0,
    'octave_leap_penalty': -6.0, 'tritone_leap_penalty': -3.0, 'common_tone_bonus': 1.5,
    'parallel_perfect_penalty': -25.0, 'contrary_motion_bonus': 0.8,
    'seventh_resolution_bonus': 1.5, 'leading_tone_resolution_bonus': 1.5,
    'double_leading_tone_penalty': -8.0,
    'doubling': {'root': 2.0, 'fifth': 0.5, 'third': -2.0, 'seventh': -6.0,
                 'color': -6.0, 'extension': -6.0},
    'omit': {'root': -20.0, 'third': -40.0, 'fifth': -3.0, 'seventh': -40.0,
             'color': -30.0, 'extension': -6.0},
    'inversion': {'root': 0.0, 'first': -1.5, 'second': -5.0, 'third': -3.0},
    'range_comfort_penalty': -0.5, 'unison_penalty': -0.5, 'upper_spacing_penalty': -0.15,
    'same_bass_penalty': -8.0,
}


def test_v4_ensemble_gets_the_background_weights(tmp_path):
    """The background-texture work added ensemble weights and the engine
    review changed one v4 default (the tritone leap, -3.0 to -4.5), so a v4
    config needs no config migration: a saved ensemble with its full v4
    weight dict takes the new weights from the defaults, in the engine and
    the editor, and the voicing migration 1->2 moves the tritone."""
    from chordnotepad.models import voicing_versions as vv
    from chordnotepad.models.ensemble_spec import DEFAULT_WEIGHTS, EnsembleSpec
    from chordnotepad.settings_forms.voicing_form import values_from_voicing
    moved = vv.DEFAULT_MOVES['ensemble']
    assert {k: DEFAULT_WEIGHTS[k] for k in _V4_ENSEMBLE_WEIGHTS if k not in moved} \
        == {k: v for k, v in _V4_ENSEMBLE_WEIGHTS.items() if k not in moved}
    assert moved == {'tritone_leap_penalty': [(-3.0, -4.5)]}
    assert _V4_ENSEMBLE_WEIGHTS['tritone_leap_penalty'] == -3.0
    added = set(DEFAULT_WEIGHTS) - set(_V4_ENSEMBLE_WEIGHTS)
    assert added == {'upper_spacing_threshold', 'outer_leap_penalty', 'middle_range_penalty',
                     'hidden_perfect_penalty', 'low_interval_limit_penalty',
                     'augmented_second_penalty', 'voice_overlap_penalty'}

    entry = {"model": "ensemble",
             "voices": [{"name": "S", "range": [60, 79]}, {"name": "B", "range": [40, 60]}],
             "weights": dict(copy.deepcopy(_V4_ENSEMBLE_WEIGHTS), unison_penalty=-1.0)}
    data = {"version": 4, "voicings": {"mine": copy.deepcopy(entry)}}
    migrated = _service(tmp_path)._migrate_config(data, 4)
    assert migrated["voicings"]["mine"] == entry

    spec = EnsembleSpec.from_dict("mine", entry)
    assert spec.weights == dict(copy.deepcopy(DEFAULT_WEIGHTS), unison_penalty=-1.0,
                                tritone_leap_penalty=-3.0)
    values = values_from_voicing("ensemble", entry)
    for key in added:
        assert float(values[f"weight:{key}"]) == DEFAULT_WEIGHTS[key]
    vv._migrate_1_to_2(entry)
    assert EnsembleSpec.from_dict("mine", entry).weights == dict(
        copy.deepcopy(DEFAULT_WEIGHTS), unison_penalty=-1.0)


# -- what ConfigService does with a file below version 3 ---------------------------------


def _write_and_load(tmp_path, data):
    (tmp_path / "settings.json").write_text(json.dumps(data))
    return _service(tmp_path).load_config()


def test_a_file_below_v3_with_voicings_is_read_as_v3(tmp_path):
    """A first-session file of 0.3.0-0.5.4 (version 1, or 2 from a nightly):
    its voicings are signed already, so loading it flips no sign. The choir
    has no ``omit`` and the guitar only some penalties, so the voicing
    migration's sign repair (which needs every omit value, or all six
    fretboard penalties) can't undo a flip: only the rule keeps them."""
    signed = {
        "c": {"model": "ensemble",
              "voices": [{"name": "S", "range": ["C4", "G5"]},
                         {"name": "B", "range": ["E2", "C4"]}],
              "weights": {"movement": [-0.4, -0.15], "leap_penalty": -2.5,
                          "common_tone_bonus": 1.5}},
        "g": {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64],
              "weights": {"span_penalty": -1.2, "barre_penalty": -1.0, "bass_note_bonus": 8.0}},
    }
    for version in (1, 2):
        root = tmp_path / f"v{version}"
        root.mkdir()
        loaded = _write_and_load(root, {"version": version, "voicings": copy.deepcopy(signed)})
        for name, entry in signed.items():
            assert loaded.voicings[name]["weights"] == entry["weights"], (version, name)


def test_a_signed_v1_file_keeps_its_penalties_negative(tmp_path):
    data = {"version": 1, "voicings": {"g": {
        "model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64],
        "weights": {"span_penalty": -1.2, "interior_mute_penalty": -2.0,
                    "bass_note_bonus": 8.0}}}}
    weights = _write_and_load(tmp_path, data).voicings["g"]["weights"]
    # Not flipped, and not bumped either (the bump was for v2 files).
    assert weights == {"span_penalty": -1.2, "interior_mute_penalty": -2.0,
                       "bass_note_bonus": 8.0}


def test_a_v1_file_with_voicings_still_moves_the_old_omit_defaults(tmp_path):
    from chordnotepad.models.ensemble_spec import ENSEMBLE_OMIT_WEIGHTS
    data = {"version": 1, "voicings": {"c": _choir(_OLD_ENSEMBLE_OMIT)}}
    loaded = _write_and_load(tmp_path, data)
    assert loaded.voicings["c"]["weights"]["omit"] == ENSEMBLE_OMIT_WEIGHTS
    assert loaded.voicings["c"]["weights"]["movement"] == -0.4


def test_a_genuine_v1_file_has_no_voicings_key(tmp_path):
    assert effective_version({"version": 1, "custom_tunings": {"T": ["E2"]}}, 1) == 1
    assert effective_version({"version": 1, "voicings": {}}, 1) == 3
    assert effective_version({"version": 2, "voicings": {"x": {}}}, 2) == 3
    loaded = _write_and_load(tmp_path, {"version": 1, "custom_tunings": {"T": ["E2", "A2"]}})
    assert loaded.voicings["T"]["tuning"] == ["E2", "A2"]
