"""End-to-end passthrough smoke tests for the ``should_abort`` cooperative-abort
kwarg added for the chord-sheet strip's background render.

These verify only that the kwarg is threaded through every layer and honored
(firing it raises :class:`exceptions.RenderAborted`), and that the default
``should_abort=None`` never aborts. They are deliberately thin -- the exact
voicing behaviour is frozen by the golden characterization tests, which prove
the default path is byte-for-byte unchanged.
"""

from unittest.mock import Mock

import pytest

from audio.chord_picker import ChordNotePicker
from audio.guitar_chord_picker import GuitarChordPicker
from audio.ensemble_voicer import EnsembleVoicer
from models.chord_notes import ChordNotes
from models.ensemble_spec import BUILTIN_ENSEMBLES
from models.fretboard_spec import BUILTIN_FRETBOARDS
from services.capo_advisor import suggest_capo
from services.config_service import ConfigService
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from services.song_renderer import SongRenderer
from exceptions import RenderAborted


def _seq():
    return [
        ChordNotes(notes=["C", "E", "G"], bass_note="C", root="C"),
        ChordNotes(notes=["G", "B", "D"], bass_note="G", root="G"),
        ChordNotes(notes=["A", "C", "E"], bass_note="A", root="A"),
    ]


_ALWAYS = lambda: True
_NEVER = lambda: False


# --------------------------------------------------------------------------
# Pickers
# --------------------------------------------------------------------------


def test_guitar_picker_threads_should_abort():
    picker = GuitarChordPicker("standard")
    with pytest.raises(RenderAborted):
        picker.voice_sequence_details(_seq(), should_abort=_ALWAYS)
    with pytest.raises(RenderAborted):
        picker.voice_sequence(_seq(), should_abort=_ALWAYS)
    with pytest.raises(RenderAborted):
        picker.voice_sequence_score(_seq(), should_abort=_ALWAYS)
    # None / never-abort keep working.
    assert picker.voice_sequence(_seq(), should_abort=_NEVER)
    assert len(picker.voice_sequence_details(_seq())) == 3


def test_piano_picker_threads_should_abort():
    picker = ChordNotePicker()
    with pytest.raises(RenderAborted):
        picker.voice_sequence_details(_seq(), should_abort=_ALWAYS)
    with pytest.raises(RenderAborted):
        picker.voice_sequence(_seq(), should_abort=_ALWAYS)
    assert len(picker.voice_sequence_details(_seq())) == 3


def test_ensemble_voicer_threads_should_abort():
    voicer = EnsembleVoicer(BUILTIN_ENSEMBLES["satb"])
    with pytest.raises(RenderAborted):
        voicer.voice_sequence(_seq(), should_abort=_ALWAYS)
    # voice_sequence_details is inherited from the base and forwards should_abort.
    with pytest.raises(RenderAborted):
        voicer.voice_sequence_details(_seq(), should_abort=_ALWAYS)
    assert len(voicer.voice_sequence(_seq())) == 3


# --------------------------------------------------------------------------
# Renderer / capo / playback service
# --------------------------------------------------------------------------


def test_song_renderer_threads_should_abort():
    lines = SongParserService().detect_chords_in_text("C G Am\n")
    renderer = SongRenderer()
    kwargs = dict(
        lines=lines, initial_key="C", initial_bpm=120, initial_time_sig=(4, 4),
        note_picker=ChordNotePicker(),
    )
    with pytest.raises(RenderAborted):
        renderer.render(should_abort=_ALWAYS, **kwargs)
    # Default None renders normally.
    assert renderer.render(**kwargs) is not None


def test_capo_advisor_threads_should_abort():
    spec = BUILTIN_FRETBOARDS["standard"]
    with pytest.raises(RenderAborted):
        suggest_capo(spec, _seq(), should_abort=_ALWAYS)
    # Default None scores normally (may or may not suggest a capo; just no raise).
    suggest_capo(spec, _seq())


def _playback_service(voicing="piano"):
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: {
        "bpm": 120,
        "time_signature_beats": 4,
        "time_signature_unit": 4,
        "voicing": voicing,
    }.get(key, default)
    return PlaybackService(config_service=config, player=None)


def test_playback_render_song_threads_should_abort_and_private_picker():
    service = _playback_service()
    lines = SongParserService().detect_chords_in_text("C G Am\n")
    with pytest.raises(RenderAborted):
        service.render_song(lines, initial_key="C", should_abort=_ALWAYS)
    # private_picker renders with a fresh picker without raising.
    rendered = service.render_song(lines, initial_key="C", private_picker=True)
    assert rendered is not None
    assert len(rendered.chords) == 3
