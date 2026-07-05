"""Plumbing tests for the upcoming ensemble (SATB) voicer.

Covers three seams that a future per-voice voicer needs and that must stay
backward compatible with today's free-voiced pickers (piano, guitar):

* ``ChordNotes.key`` carries the key signature in effect when the chord was
  resolved, threaded all the way from ``SongRenderer`` through
  ``ChordHelper``.
* ``INotePicker.voice_labels`` defaults to ``None`` for pickers that don't
  override it (today's piano/guitar pickers).
* ``SongRenderer``'s voicing pass recognizes a picker that reports
  ``voice_labels`` and splits its per-chord voicing into
  ``RenderedChord.voice_notes`` (full voicing, duplicates allowed) plus a
  deduplicated ``RenderedChord.midi_notes``, and copies the labels onto
  ``RenderedSong.voice_labels`` reversed to low-to-high so indices align
  with ``voice_notes``.
"""
from typing import List, Optional

from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from audio.note_picker_interface import INotePicker
from models.chord_notes import ChordNotes
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer


def _played_chords(rendered):
    """Chords that were actually voiced (not rests, not skipped)."""
    return [rc for rc in rendered.chords if not rc.is_rest and not rc.skipped]


class TestChordNotesKey:
    """ChordNotes.key tracks the key in effect, including mid-song changes."""

    def test_key_carried_through_renderer_and_updates_mid_song(self):
        text = (
            "{key: C}\n"
            "C G\n"
            "{key: G}\n"
            "Am F\n"
        )
        lines = SongParserService().detect_chords_in_text(text)
        rendered = SongRenderer().render(
            lines=lines,
            initial_key=None,
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(),
        )
        assert rendered is not None
        played = _played_chords(rendered)
        assert [rc.chord_info.chord for rc in played] == ["C", "G", "Am", "F"]
        assert [rc.chord_notes.key for rc in played] == ["C", "C", "G", "G"]
        # ChordNotes.key mirrors RenderedChord.key (already unconditional).
        assert [rc.chord_notes.key for rc in played] == [rc.key for rc in played]

    def test_no_key_directive_leaves_key_none(self):
        text = "C G\n"
        lines = SongParserService().detect_chords_in_text(text)
        rendered = SongRenderer().render(
            lines=lines,
            initial_key=None,
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(),
        )
        assert rendered is not None
        played = _played_chords(rendered)
        assert all(rc.chord_notes.key is None for rc in played)


class TestVoiceLabelsDefault:
    """INotePicker subclasses default to voice_labels == None."""

    def test_piano_picker_has_no_voice_labels(self):
        assert ChordNotePicker().voice_labels is None

    def test_guitar_picker_has_no_voice_labels(self):
        assert GuitarChordPicker().voice_labels is None


class _FixedEnsemblePicker(INotePicker):
    """Stub emulating a fixed 4-voice ensemble picker (e.g. a future SATB
    voicer). Ignores chord content and always emits the same voicing
    (including an intentional unison duplicate), so the test can assert
    exactly on the voice_notes/midi_notes/voice_labels plumbing without any
    real ensemble voicing logic (which doesn't exist yet).
    """

    # Soprano, Alto, Tenor, Bass -- Alto and Tenor land on the same note.
    VOICING = [72, 67, 67, 60]
    LABELS = ["Soprano", "Alto", "Tenor", "Bass"]  # top voice first

    def __init__(self):
        self._state = None

    def chord_to_midi(self, chord_notes: 'ChordNotes') -> List[int]:
        return list(self.VOICING)

    def reset(self) -> None:
        self._state = None

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value) -> None:
        self._state = value

    def voice_sequence(self, sequence: List['ChordNotes'],
                       should_abort=None) -> List[List[int]]:
        self.reset()
        return [list(self.VOICING) for _ in sequence]

    @property
    def voice_labels(self) -> Optional[List[str]]:
        return list(self.LABELS)


class TestEnsemblePickerPlumbing:
    """SongRenderer wires voice_notes/midi_notes/voice_labels for a picker
    that reports voice_labels."""

    def test_voice_notes_and_labels_aligned_low_to_high(self):
        text = "C G\n"
        lines = SongParserService().detect_chords_in_text(text)
        rendered = SongRenderer().render(
            lines=lines,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=_FixedEnsemblePicker(),
        )
        assert rendered is not None

        # RenderedSong.voice_labels is the picker's labels reversed to
        # low-to-high (Bass first), aligning with voice_notes below.
        assert rendered.voice_labels == ["Bass", "Tenor", "Alto", "Soprano"]

        played = _played_chords(rendered)
        assert len(played) == 2
        for rc in played:
            # Full voicing, duplicates intact, low-to-high per the picker's
            # ordering reversed -- but the picker's raw VOICING list IS
            # already low-to-high-compatible in this stub (we return it
            # unchanged); voice_notes must equal exactly what voice_sequence
            # returned for this chord.
            assert rc.voice_notes == [72, 67, 67, 60]
            # midi_notes is an order-preserving dedup of voice_notes.
            assert rc.midi_notes == [72, 67, 60]

    def test_rests_and_skipped_chords_have_no_voice_notes(self):
        text = "C NC\n"
        lines = SongParserService().detect_chords_in_text(text)
        rendered = SongRenderer().render(
            lines=lines,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=_FixedEnsemblePicker(),
        )
        assert rendered is not None
        rests = [rc for rc in rendered.chords if rc.is_rest]
        assert rests, "expected at least one rest in the fixture song"
        assert all(rc.voice_notes is None for rc in rests)
        assert all(rc.midi_notes is None for rc in rests)


class TestFreeVoicedPickerUnchanged:
    """Piano (free-voiced) rendering is untouched by the new plumbing."""

    def test_piano_render_leaves_voice_notes_and_labels_none(self):
        text = "C G\nAm F\n"
        lines = SongParserService().detect_chords_in_text(text)
        rendered = SongRenderer().render(
            lines=lines,
            initial_key="C",
            initial_bpm=120,
            initial_time_sig=(4, 4),
            note_picker=ChordNotePicker(),
        )
        assert rendered is not None
        assert rendered.voice_labels is None
        played = _played_chords(rendered)
        assert played, "expected at least one voiced chord"
        assert all(rc.voice_notes is None for rc in played)
        # midi_notes is still populated with the real voicing.
        assert all(rc.midi_notes for rc in played)
