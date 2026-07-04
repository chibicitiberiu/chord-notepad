"""Tests for the spec-driven piano voicing engine (src/audio/chord_picker.py).

Covers two things the generalization must guarantee:

1. **Behaviour preservation** - the default :class:`PianoSpec` reproduces the
   original hard-coded picker exactly (the pipeline goldens in
   ``test_playback_characterization`` already pin the byte-level output; here we
   pin the resolved constants and default-vs-explicit-default equivalence).
2. **Parametrization** - a custom spec actually reaches the scorer and changes
   the voicing (register, bass inclusion, physical limits).
"""

from audio.chord_picker import ChordNotePicker
from models.piano_spec import DEFAULT_PIANO, PianoSpec
from chord.helper import ChordHelper


PROGRESSION = ["C", "Am", "F", "G", "Cmaj7", "Dm7", "G7"]


def _seq(symbols):
    helper = ChordHelper()
    return [helper.compute_chord_notes(s) for s in symbols]


# ---------------------------------------------------------------------------
# Behaviour preservation
# ---------------------------------------------------------------------------

class TestDefaultSpecPreservesBehaviour:
    def test_default_constants_match_documented_defaults(self):
        p = ChordNotePicker()
        assert p.HAND_SPAN_SEMITONES == 14
        assert p.MAX_NOTES_PER_HAND == 5
        assert p.MAX_TOTAL_NOTES == 10
        assert (p.LH_MIN, p.LH_MAX) == (24, 48)
        assert (p.LH_OCTAVE2_LOW, p.LH_OCTAVE2_HIGH) == (36, 47)
        assert (p.RH_MIN, p.RH_MAX) == (48, 84)
        assert (p.RH_LOW_ANCHOR_MIN, p.RH_LOW_ANCHOR_MAX) == (48, 64)
        assert p.RH_IDEAL_CENTER == 63.0
        assert p.RH_LOW_INTERVAL_FLOOR == 52
        assert p.HAND_GAP_FLOOR == 2
        assert p.add_bass is True

    def test_omit_penalty_is_signed_negative(self):
        p = ChordNotePicker()
        assert p.OMIT_PENALTY["third"] == -40.0
        assert p.OMIT_PENALTY["root"] == -4.0

    def test_no_arg_equals_explicit_default_spec(self):
        default = ChordNotePicker().voice_sequence(_seq(PROGRESSION))
        explicit = ChordNotePicker(DEFAULT_PIANO).voice_sequence(_seq(PROGRESSION))
        assert default == explicit

    def test_spec_attribute_exposed(self):
        assert ChordNotePicker().spec is DEFAULT_PIANO
        custom = PianoSpec.from_dict("c", {"hand_span": 12})
        assert ChordNotePicker(custom).spec is custom


# ---------------------------------------------------------------------------
# Parametrization actually reaches the engine
# ---------------------------------------------------------------------------

class TestSpecDrivesEngine:
    def test_custom_physical_limits_resolve(self):
        spec = PianoSpec.from_dict("tight", {
            "hand_span": 10,
            "max_notes_per_hand": 4,
            "rh_low_interval_floor": 48,
        })
        p = ChordNotePicker(spec)
        assert p.HAND_SPAN_SEMITONES == 10
        assert p.MAX_NOTES_PER_HAND == 4
        assert p.RH_LOW_INTERVAL_FLOOR == 48

    def test_spec_add_bass_false_suppresses_left_hand(self):
        spec = PianoSpec.from_dict("nobass", {"add_bass": False})
        p = ChordNotePicker(spec)
        midi = p.chord_to_midi(_seq(["C"])[0])
        assert midi, "expected a voicing"
        assert min(midi) >= p.RH_MIN, f"bass note present despite add_bass=False: {midi}"

    def test_legacy_add_bass_kwarg_still_suppresses_left_hand(self):
        p = ChordNotePicker(add_bass=False)
        midi = p.chord_to_midi(_seq(["C"])[0])
        assert min(midi) >= p.RH_MIN

    def test_default_includes_a_bass_note(self):
        p = ChordNotePicker()
        midi = p.chord_to_midi(_seq(["C"])[0])
        assert min(midi) < p.RH_MIN, f"expected a left-hand bass below C3: {midi}"

    def test_lower_rh_center_lowers_right_hand_register(self):
        symbol = _seq(["C"])[0]

        default_rh = _rh_mean(ChordNotePicker(), symbol)
        low = PianoSpec.from_dict("low", {"rh_center": 51.0})
        low_rh = _rh_mean(ChordNotePicker(low), symbol)

        assert low_rh < default_rh, (
            f"lowering rh_center did not lower the right hand: {low_rh} !< {default_rh}"
        )


def _rh_mean(picker, chord_notes):
    """Mean pitch of the right-hand notes the picker chooses for one chord."""
    midi = picker.chord_to_midi(chord_notes)
    rh = [m for m in midi if m >= picker.RH_MIN]
    assert rh, f"no right-hand notes in {midi}"
    return sum(rh) / len(rh)
