"""Tests for the MIDI export flow: PlaybackService.render_song and
MainWindowViewModel.export_midi_file.

Headless: no Tkinter, no real audio. `services.midi_file_writer` is stubbed
via sys.modules so these tests pass whether or not the real module (owned by
another concurrent task) exists on disk yet.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from types import ModuleType

import pytest

from services.playback_service import PlaybackService
from services.config_service import ConfigService
from services.song_parser_service import SongParserService
from models.notation import Notation
from models.rendered_song import RenderedSong
from exceptions import FileOperationError


TWO_CHORD_TEXT = "C G\n"
NO_CHORD_TEXT = "just some lyrics, no chords here\n"


@pytest.fixture
def mock_config():
    """Minimal fake config service (constructor-injected, no real file I/O)."""
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: {
        "bpm": 120,
        "time_signature_beats": 4,
        "time_signature_unit": 4,
        "soundfont_path": None,
        "voicing": "piano",
        "instrument": 0,
    }.get(key, default)
    return config


@pytest.fixture
def playback_service(mock_config):
    """PlaybackService with no real player -- render_song must not need one."""
    return PlaybackService(config_service=mock_config, player=None)


@pytest.fixture
def parser():
    return SongParserService()


class TestRenderSong:
    """PlaybackService.render_song: synchronous whole-song render for export."""

    def test_returns_rendered_song_with_voiced_chords(self, playback_service, parser):
        lines = parser.detect_chords_in_text(TWO_CHORD_TEXT, Notation.AMERICAN)

        rendered = playback_service.render_song(lines, initial_key=None)

        assert rendered is not None
        assert isinstance(rendered, RenderedSong)
        assert len(rendered.chords) == 2
        for chord in rendered.chords:
            assert chord.midi_notes
            assert len(chord.midi_notes) > 0

    def test_returns_none_for_chordless_text(self, playback_service, parser):
        lines = parser.detect_chords_in_text(NO_CHORD_TEXT, Notation.AMERICAN)

        rendered = playback_service.render_song(lines, initial_key=None)

        assert rendered is None

    def test_deterministic_across_calls(self, playback_service, parser):
        lines = parser.detect_chords_in_text(TWO_CHORD_TEXT, Notation.AMERICAN)

        first = playback_service.render_song(lines, initial_key=None)
        second = playback_service.render_song(lines, initial_key=None)

        assert first is not None and second is not None
        first_notes = [c.midi_notes for c in first.chords]
        second_notes = [c.midi_notes for c in second.chords]
        assert first_notes == second_notes

    def test_does_not_require_player_initialization(self, playback_service):
        # No player was passed and initialize_player() was never called.
        assert not playback_service.is_initialized


def _install_stub_writer_module(mock_write=None):
    """Install a stub 'services.midi_file_writer' module into sys.modules.

    Returns (context_manager, mock_write). The stub is used so tests pass
    whether or not the real writer module exists on disk during this run.
    """
    stub = ModuleType("services.midi_file_writer")
    stub.write_midi_file = mock_write if mock_write is not None else MagicMock()
    stub.PPQ = 480
    return patch.dict(sys.modules, {"services.midi_file_writer": stub}), stub


class TestExportMidiFile:
    """MainWindowViewModel.export_midi_file."""

    def _make_viewmodel(self, current_text="C G\n", current_file=None, instrument=5):
        """Build a MainWindowViewModel with fully mocked services."""
        from viewmodels.main_window_viewmodel import MainWindowViewModel

        config = Mock(spec=ConfigService)
        config.get.side_effect = lambda key, default=None: {
            "bpm": 120,
            "time_signature_beats": 4,
            "time_signature_unit": 4,
            "notation": "american",
            "font_size": 11,
            "font_family": "TkFixedFont",
            "bpm_multiplier": 1.0,
            "key": None,
            "instrument": instrument,
        }.get(key, default)

        audio = MagicMock()
        file_service = MagicMock()
        song_parser = SongParserService()
        application = MagicMock()

        vm = MainWindowViewModel(
            config_service=config,
            audio_service=audio,
            file_service=file_service,
            song_parser_service=song_parser,
            application=application,
        )
        vm._current_text = current_text
        if current_file is not None:
            vm._current_file = Path(current_file)

        return vm, audio

    def test_calls_write_midi_file_with_rendered_song_path_program_title(self):
        vm, audio = self._make_viewmodel(
            current_text="C G\n", current_file="/tmp/mysong.txt", instrument=12
        )
        rendered = RenderedSong()
        audio.render_song.return_value = rendered

        patcher, stub = _install_stub_writer_module()
        with patcher:
            result = vm.export_midi_file(Path("/tmp/out.mid"))

            assert result is True
            stub.write_midi_file.assert_called_once_with(
                rendered, Path("/tmp/out.mid"), program=12, title="mysong"
            )

    def test_uses_untitled_when_no_current_file(self):
        vm, audio = self._make_viewmodel(current_text="C G\n", current_file=None, instrument=0)
        rendered = RenderedSong()
        audio.render_song.return_value = rendered

        patcher, stub = _install_stub_writer_module()
        with patcher:
            result = vm.export_midi_file(Path("/tmp/out.mid"))

            assert result is True
            stub.write_midi_file.assert_called_once_with(
                rendered, Path("/tmp/out.mid"), program=0, title="Untitled"
            )

    def test_returns_false_when_render_song_returns_none(self):
        vm, audio = self._make_viewmodel(current_text="no chords here\n")
        audio.render_song.return_value = None

        patcher, stub = _install_stub_writer_module()
        with patcher:
            result = vm.export_midi_file(Path("/tmp/out.mid"))

            assert result is False
            stub.write_midi_file.assert_not_called()

    def test_returns_false_and_does_not_raise_on_file_operation_error(self):
        vm, audio = self._make_viewmodel(current_text="C G\n")
        rendered = RenderedSong()
        audio.render_song.return_value = rendered

        failing_write = MagicMock(side_effect=FileOperationError("disk full"))
        patcher, stub = _install_stub_writer_module(mock_write=failing_write)
        with patcher:
            result = vm.export_midi_file(Path("/tmp/out.mid"))

            assert result is False
