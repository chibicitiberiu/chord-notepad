"""Tests for the Suggest Capo service seams on PlaybackService.

The Suggest Capo tool resolves a chosen fretboard voicing to a spec and renders
the current document with a picker on that spec (which need not be the active
voicing) to collect the chords it scores. These cover the two seams that make
that possible: ``fretboard_spec_for`` and the ``note_picker`` override on
``render_song``.
"""

from unittest.mock import MagicMock

import pytest

from audio.guitar_chord_picker import GuitarChordPicker
from models.playback_state import PlaybackState
from services.capo_advisor import suggest_capo
from services.capo_insert import insert_capo_directive
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService


def _service(voicings=None):
    store = {
        'voicing': 'guitar:standard',
        'voicings': voicings or {},
        'bpm': 120,
        'time_signature_beats': 4,
        'time_signature_unit': 4,
    }
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: store.get(key, default)
    service = PlaybackService(config)
    service._playback_state = PlaybackState(
        bpm=120, initial_bpm=120, time_signature_beats=4, time_signature_unit=4)
    return service


class TestFretboardSpecFor:
    def test_builtin_guitar_resolves(self):
        service = _service()
        assert service.fretboard_spec_for('guitar:standard').tuning == \
            GuitarChordPicker('standard').spec.tuning

    def test_unknown_builtin_falls_back_to_standard(self):
        service = _service()
        spec = service.fretboard_spec_for('guitar:nonexistent')
        assert spec.tuning == GuitarChordPicker('standard').spec.tuning

    def test_registry_fretboard_resolves(self):
        service = _service(voicings={
            'My 7': {'model': 'fretboard', 'tuning': [35, 40, 45, 50, 55, 59, 64]},
        })
        spec = service.fretboard_spec_for('voicing:My 7')
        assert spec is not None
        assert list(spec.tuning) == [35, 40, 45, 50, 55, 59, 64]

    def test_non_fretboard_returns_none(self):
        service = _service(voicings={'Choir': {'model': 'ensemble', 'voices': []}})
        assert service.fretboard_spec_for('piano') is None
        assert service.fretboard_spec_for('voicing:Choir') is None
        assert service.fretboard_spec_for('ensemble:satb') is None


class TestRenderSongPickerOverride:
    def test_note_picker_override_used(self):
        service = _service()
        lines = SongParserService().detect_chords_in_text("F#  B  C#\n", 'american')
        spec = service.fretboard_spec_for('guitar:standard')
        rendered = service.render_song(
            lines, 'F#', note_picker=GuitarChordPicker(spec))
        assert rendered is not None
        played = [rc for rc in rendered.chords if rc.chord_notes is not None]
        assert [rc.chord_info.chord for rc in played] == ['F#', 'B', 'C#']
        # Fingering data is present (a fretboard picker was used).
        assert all(rc.fingering is not None for rc in played)


class TestEndToEndSuggestion:
    def test_awkward_key_suggests_a_capo_then_inserts(self):
        # A song in F# full of barre chords should get a capo suggestion, and
        # inserting it prepends the directive without disturbing the rest.
        service = _service()
        text = "{key: F#}\nF#  B  C#  D#m  F#  B\n"
        lines = SongParserService().detect_chords_in_text(text, 'american')
        spec = service.fretboard_spec_for('guitar:standard')
        rendered = service.render_song(lines, 'F#', note_picker=GuitarChordPicker(spec))
        sequence = [rc.chord_notes for rc in rendered.chords if rc.chord_notes]

        capo = suggest_capo(spec, sequence)
        assert capo and capo > 0

        new_text, offset = insert_capo_directive(text, capo, None)
        assert new_text == "{capo: %d}\n%s" % (capo, text)
        assert new_text[offset] == '{'
