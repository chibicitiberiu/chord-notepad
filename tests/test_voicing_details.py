"""Tests for model-specific voicing detail (fingering / hand_split) plumbing.

Covers the ``VoicedChord`` / ``INotePicker.voice_sequence_details`` seam and the
way ``SongRenderer`` distributes each model's display detail onto the rendered
chords:

* Guitar (fretboard) model -> per-chord ``fingering``; ``None`` on rests.
* Piano model -> per-chord ``hand_split``; ``0`` when ``add_bass`` is off.
* Ensemble model -> neither detail (both ``None``); ``voice_notes`` unchanged.
* The detail-less default ``voice_sequence_details`` for a custom picker.
* Loop repeats: the repeated passes also get their detail.
"""
from typing import List, Optional

from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from audio.ensemble_voicer import EnsembleVoicer
from audio.note_picker_interface import INotePicker, VoicedChord
from models.chord_notes import ChordNotes
from models.ensemble_spec import BUILTIN_ENSEMBLES
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


def _render(text, note_picker, initial_key="C"):
    lines = SongParserService().detect_chords_in_text(text)
    rendered = SongRenderer().render(
        lines=lines,
        initial_key=initial_key,
        initial_bpm=120,
        initial_time_sig=(4, 4),
        note_picker=note_picker,
    )
    assert rendered is not None
    return rendered


def _played(rendered):
    return [rc for rc in rendered.chords if not rc.is_rest and not rc.skipped]


class TestGuitarFingering:
    """The fretboard model reports a fingering per sounding chord."""

    def test_every_sounding_chord_has_fingering_rest_has_none(self):
        rendered = _render("C G\nAm F\n", GuitarChordPicker())
        played = _played(rendered)
        assert played, "expected voiced chords"
        assert all(rc.fingering is not None for rc in played)
        # Guitar is not a piano; hand_split stays None.
        assert all(rc.hand_split is None for rc in played)

    def test_rest_has_no_fingering(self):
        rendered = _render("C NC\n", GuitarChordPicker())
        rests = [rc for rc in rendered.chords if rc.is_rest]
        assert rests, "expected a rest in the fixture"
        assert all(rc.fingering is None for rc in rests)
        assert all(rc.hand_split is None for rc in rests)

    def test_fingering_reconstructs_midi_notes_through_tuning(self):
        picker = GuitarChordPicker()
        tuning = picker.tuning_midi
        rendered = _render("C G Am F D\n", picker)
        for rc in _played(rendered):
            fingering = rc.fingering
            assert len(fingering) == len(tuning)
            fretted = sorted(tuning[s] + fingering[s]
                             for s in range(len(tuning)) if fingering[s] >= 0)
            assert fretted == rc.midi_notes

    def test_fingering_entries_are_valid_frets(self):
        rendered = _render("C G Am F\n", GuitarChordPicker())
        for rc in _played(rendered):
            for fret in rc.fingering:
                assert fret >= -1


class TestPianoHandSplit:
    """The piano model reports a left/right hand split per chord."""

    def test_hand_split_present_and_lh_below_range_bound(self):
        picker = ChordNotePicker()
        rendered = _render("C G Am F\n", picker)
        played = _played(rendered)
        assert played
        for rc in played:
            assert rc.hand_split is not None
            assert rc.fingering is None  # piano is not a fretboard model
            lh = rc.midi_notes[:rc.hand_split]
            # Left-hand notes sit inside the spec's LH range.
            assert all(note <= picker.LH_MAX for note in lh)
            assert all(note >= picker.LH_MIN for note in lh)
            # Split really separates lh (below) from rh (above).
            rh = rc.midi_notes[rc.hand_split:]
            if lh and rh:
                assert max(lh) < min(rh)

    def test_add_bass_off_gives_zero_split(self):
        rendered = _render("C G Am F\n", ChordNotePicker(add_bass=False))
        played = _played(rendered)
        assert played
        assert all(rc.hand_split == 0 for rc in played)
        # With no bass, the whole voicing is the right hand.
        assert all(rc.midi_notes[:rc.hand_split] == [] for rc in played)

    def test_rest_has_no_hand_split(self):
        rendered = _render("C NC\n", ChordNotePicker())
        rests = [rc for rc in rendered.chords if rc.is_rest]
        assert rests
        assert all(rc.hand_split is None for rc in rests)
        assert all(rc.fingering is None for rc in rests)


class TestEnsembleNoModelDetail:
    """The ensemble model carries neither fingering nor hand_split."""

    def test_fingering_and_hand_split_none_voice_notes_intact(self):
        picker = EnsembleVoicer(BUILTIN_ENSEMBLES['satb'])
        rendered = _render("C G Am F\n", picker)
        played = _played(rendered)
        assert played
        assert all(rc.fingering is None for rc in played)
        assert all(rc.hand_split is None for rc in played)
        # The per-voice plumbing is unaffected.
        assert rendered.voice_labels is not None
        n_voices = len(picker.voice_labels)
        assert all(rc.voice_notes is not None for rc in played)
        assert all(len(rc.voice_notes) == n_voices for rc in played)


class _MinimalPicker(INotePicker):
    """Smallest possible custom picker: only the abstract API, no overrides.

    Used to exercise the default ``voice_sequence_details`` (which wraps
    ``voice_sequence`` with detail-less entries).
    """

    def __init__(self):
        self._state = None

    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        return [60, 64, 67]

    def reset(self) -> None:
        self._state = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value) -> None:
        self._state = value


class TestDefaultVoiceSequenceDetails:
    """The default voice_sequence_details wraps voice_sequence, detail-less."""

    def test_default_returns_detail_less_voiced_chords(self):
        picker = _MinimalPicker()
        seq = [ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'),
               ChordNotes(notes=['D', 'F', 'A'], bass_note='D', root='D')]
        details = picker.voice_sequence_details(seq)
        plain = picker.voice_sequence(seq)
        assert [d.midi_notes for d in details] == plain
        assert all(isinstance(d, VoicedChord) for d in details)
        assert all(d.fingering is None for d in details)
        assert all(d.hand_split is None for d in details)

    def test_details_midi_notes_match_voice_sequence_for_real_pickers(self):
        seq = [ChordNotes(notes=['C', 'E', 'G'], bass_note='C', root='C'),
               ChordNotes(notes=['A', 'C', 'E'], bass_note='A', root='A'),
               ChordNotes(notes=['G', 'B', 'D'], bass_note='G', root='G')]
        for picker in (GuitarChordPicker(), ChordNotePicker()):
            details = picker.voice_sequence_details(seq)
            plain = picker.voice_sequence(seq)
            assert [d.midi_notes for d in details] == plain


class TestLoopDetail:
    """Repeated loop passes also receive their model detail."""

    def test_guitar_fingering_on_repeated_passes(self):
        text = (
            "{label: verse}\n"
            "C G\n"
            "{loop: verse 2}\n"
        )
        rendered = _render(text, GuitarChordPicker())
        played = _played(rendered)
        # Two chords per pass, two passes -> four voiced chords.
        assert [rc.chord_info.chord for rc in played] == ["C", "G", "C", "G"]
        assert all(rc.fingering is not None for rc in played)

    def test_piano_hand_split_on_repeated_passes(self):
        text = (
            "{label: verse}\n"
            "C G\n"
            "{loop: verse 2}\n"
        )
        rendered = _render(text, ChordNotePicker())
        played = _played(rendered)
        assert len(played) == 4
        assert all(rc.hand_split is not None for rc in played)
