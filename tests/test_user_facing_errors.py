"""User-initiated actions that fail must tell the user why.

Covers the "caught" layer: places that used to catch an error and only log
it (or return False with no reason), so File -> Export MIDI, Play, chord
clicks, Help, Settings -> Save etc. looked like they did nothing.

Headless: the viewmodels and services only. The Qt window's dialogs for
these errors are in tests/qt (test_qt_error_presenter.py, test_qt_dialogs.py).
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from chordnotepad.exceptions import (
    AudioInitializationError,
    ChordDetectionError,
    FileOperationError,
)
from chordnotepad.models.chord import ChordInfo
from chordnotepad.models.rendered_song import RenderedSong
from chordnotepad.services.config_service import ConfigService
from chordnotepad.services.playback_service import PlaybackService
from chordnotepad.services.song_parser_service import SongParserService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config(**overrides):
    values = {
        "bpm": 120,
        "time_signature_beats": 4,
        "time_signature_unit": 4,
        "notation": "american",
        "font_size": 11,
        "font_family": "TkFixedFont",
        "bpm_multiplier": 1.0,
        "key": None,
        "instrument": 0,
        "voicing": "piano",
        "soundfont_path": None,
    }
    values.update(overrides)
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: values.get(key, default)
    return config


def _viewmodel(text="C G\n", documents=None, audio=None):
    from chordnotepad.viewmodels.main_window_viewmodel import MainWindowViewModel

    vm = MainWindowViewModel(
        config_service=_config(),
        audio_service=audio if audio is not None else MagicMock(),
        documents=documents if documents is not None else MagicMock(),
        song_parser_service=SongParserService(),
        application=MagicMock(),
    )
    vm._current_text = text
    return vm


def _fs_store():
    from chordnotepad.services.file_service import FileService
    from chordnotepad.session.documents import FileSystemDocumentStore

    return FileSystemDocumentStore(FileService(MagicMock()))


def _out_mid():
    return _fs_store().ref_for_path("/tmp/out.mid")


def _stub_writer(render=None):
    stub = ModuleType("chordnotepad.services.midi_file_writer")
    stub.render_midi_bytes = render if render is not None else MagicMock(return_value=b"MIDI")
    stub.PPQ = 480
    return patch.dict(sys.modules, {"chordnotepad.services.midi_file_writer": stub})


# ---------------------------------------------------------------------------
# MainWindowViewModel: open / save / export keep the reason
# ---------------------------------------------------------------------------

class TestViewModelFileErrors:

    def test_open_missing_file_reports_reason(self, tmp_path):
        store = _fs_store()
        vm = _viewmodel(documents=store)
        missing = store.ref_for_path(tmp_path / "nope.txt")

        assert vm.open_file(missing) is False
        # The dialog names the file (file_error_message); the reason doesn't.
        assert vm.last_error == "File not found"

    def test_open_success_clears_previous_error(self, tmp_path):
        store = _fs_store()
        vm = _viewmodel(documents=store)
        vm.open_file(store.ref_for_path(tmp_path / "nope.txt"))
        song = tmp_path / "song.txt"
        song.write_text("C G\n", encoding="utf-8")

        assert vm.open_file(store.ref_for_path(song)) is True
        assert vm.last_error is None

    def test_save_as_failure_reports_reason(self):
        documents = MagicMock()
        documents.write_text.side_effect = FileOperationError("Permission denied: /ro/song.txt")
        vm = _viewmodel(documents=documents)

        assert vm.save_file_as(_fs_store().ref_for_path("/ro/song.txt")) is False
        assert vm.last_error == "Permission denied: /ro/song.txt"

    def test_save_without_file_is_not_an_error(self):
        vm = _viewmodel()
        vm._last_error = "stale"

        assert vm.save_file() is False
        assert vm.last_error is None

    def test_plain_os_error_text_is_used_as_is(self):
        documents = MagicMock()
        documents.write_text.side_effect = OSError(28, "No space left on device")
        vm = _viewmodel(documents=documents)

        vm.save_file_as(_fs_store().ref_for_path("/tmp/x.txt"))
        assert "No space left on device" in vm.last_error

    def test_export_with_no_chords_says_so(self):
        audio = MagicMock()
        vm = _viewmodel(text="just lyrics here\n", audio=audio)

        with _stub_writer():
            assert vm.export_midi_file(_out_mid()) is False
        assert vm.last_error == "There are no chords to export."
        audio.render_song.assert_not_called()

    def test_export_write_failure_reports_reason(self):
        audio = MagicMock()
        audio.render_song.return_value = RenderedSong()
        vm = _viewmodel(audio=audio)

        vm._documents.write_bytes.side_effect = FileOperationError("disk full")

        with _stub_writer():
            assert vm.export_midi_file(_out_mid()) is False
        assert vm.last_error == "disk full"

    def test_export_missing_module_is_reported_not_raised(self):
        # The bug that started this: an ImportError escaped the menu command
        # and only reached stderr.
        vm = _viewmodel()
        with patch.dict(sys.modules, {"chordnotepad.services.midi_file_writer": None}):
            assert vm.export_midi_file(_out_mid()) is False
        assert "ImportError" in vm.last_error or "ModuleNotFoundError" in vm.last_error

    def test_export_render_failure_reports_reason(self):
        audio = MagicMock()
        audio.render_song.side_effect = ValueError("voicing blew up")
        vm = _viewmodel(audio=audio)

        with _stub_writer():
            assert vm.export_midi_file(_out_mid()) is False
        assert "voicing blew up" in vm.last_error
        assert audio.render_song.call_args.kwargs["raise_errors"] is True

    def test_export_success_clears_error(self):
        audio = MagicMock()
        audio.render_song.return_value = RenderedSong()
        vm = _viewmodel(audio=audio)
        vm._last_error = "stale"

        with _stub_writer():
            assert vm.export_midi_file(_out_mid()) is True
        assert vm.last_error is None


# ---------------------------------------------------------------------------
# MainWindowViewModel: playback errors propagate / are published
# ---------------------------------------------------------------------------

class TestViewModelPlaybackErrors:

    def test_start_playback_raises_when_audio_unavailable(self):
        audio = MagicMock()
        audio.start_song_playback.side_effect = AudioInitializationError("no driver")
        vm = _viewmodel(audio=audio)

        with pytest.raises(AudioInitializationError):
            vm.start_playback()
        assert vm.is_playing is False

    def test_render_error_is_published_on_ui_thread(self):
        audio = MagicMock()
        audio.start_song_playback.return_value = True
        vm = _viewmodel(audio=audio)
        seen = []
        vm.observe("playback_error", seen.append)

        vm.start_playback()
        on_error = audio.start_song_playback.call_args.kwargs["on_error_callback"]
        on_error("render broke")

        # Queued, not delivered on the calling (render) thread.
        assert seen == []
        queued = vm._application.queue_ui_callback.call_args.args[0]
        queued()
        assert seen == ["render broke"]

    def test_chord_click_raises_when_audio_unavailable(self):
        audio = MagicMock()
        audio.play_chord_immediate.side_effect = AudioInitializationError("no driver")
        vm = _viewmodel(audio=audio)
        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)

        with pytest.raises(AudioInitializationError):
            vm.on_chord_clicked(chord)

    def test_suggest_capo_does_not_hide_render_errors(self):
        from chordnotepad.models.fretboard_spec import BUILTIN_FRETBOARDS

        # A real spec, so nothing needs patching: patching GuitarChordPicker
        # leaked the mock into services.capo_advisor when that module was
        # first imported under the patch (later capo tests then failed).
        audio = MagicMock()
        audio.fretboard_spec_for.return_value = BUILTIN_FRETBOARDS["standard"]
        audio.render_song.side_effect = ValueError("boom")
        vm = _viewmodel(audio=audio)

        with pytest.raises(ValueError):
            vm.suggest_capo_for("guitar:standard")


# ---------------------------------------------------------------------------
# PlaybackService
# ---------------------------------------------------------------------------

class TestPlaybackServiceErrors:

    def test_failed_init_reason_reaches_play_chord(self):
        service = PlaybackService(_config(), player=None)
        chord = ChordInfo(chord="C", start=0, end=1, is_valid=True, is_relative=False)

        with patch("chordnotepad.services.playback_service.NotePlayer",
                   side_effect=FileNotFoundError("Soundfont not found: /x.sf2")):
            with pytest.raises(AudioInitializationError) as info:
                service.play_chord_immediate(chord)
        assert "Soundfont not found: /x.sf2" in str(info.value)
        assert service.audio_error == "Soundfont not found: /x.sf2"

    def test_start_song_playback_raises_when_audio_unavailable(self, song_parser):
        service = PlaybackService(_config(), player=None)
        lines = song_parser.detect_chords_in_text("C G\n", "american")

        with patch("chordnotepad.services.playback_service.NotePlayer",
                   side_effect=AudioInitializationError("No audio output could be started")):
            with pytest.raises(AudioInitializationError) as info:
                service.start_song_playback(lines, initial_key=None)
        assert "No audio output" in str(info.value)

    def test_play_note_and_notes_raise_when_audio_unavailable(self):
        service = PlaybackService(_config(), player=None)
        with patch("chordnotepad.services.playback_service.NotePlayer", side_effect=RuntimeError("x")):
            with pytest.raises(AudioInitializationError):
                service.play_note("C", 4)
            with pytest.raises(AudioInitializationError):
                service.play_notes_immediate([60])

    def test_successful_init_clears_audio_error(self):
        service = PlaybackService(_config(), player=None)
        with patch("chordnotepad.services.playback_service.NotePlayer", side_effect=RuntimeError("x")):
            service.initialize_player()
        assert service.audio_error == "x"
        with patch("chordnotepad.services.playback_service.NotePlayer"):
            assert service.initialize_player() is True
        assert service.audio_error is None

    def test_render_thread_failure_resets_and_reports(self, song_parser):
        service = PlaybackService(_config(), player=MagicMock())
        lines = song_parser.detect_chords_in_text("C G\n", "american")
        finished = Mock()
        errors = Mock()

        with patch("chordnotepad.services.playback_service.SongRenderer") as renderer:
            renderer.return_value.render.side_effect = ValueError("render broke")
            assert service.start_song_playback(
                lines, initial_key=None,
                on_finished_callback=finished, on_error_callback=errors) is True
            service._render_thread.join(timeout=5)

        finished.assert_called_once_with()
        errors.assert_called_once_with("render broke")

    def test_render_song_raise_errors_flag(self, song_parser):
        service = PlaybackService(_config(), player=None)
        lines = song_parser.detect_chords_in_text("C G\n", "american")

        with patch("chordnotepad.services.playback_service.SongRenderer") as renderer:
            renderer.return_value.render.side_effect = ValueError("bad")
            # Default (chord-sheet strip): logged, None.
            assert service.render_song(lines, None) is None
            with pytest.raises(ValueError):
                service.render_song(lines, None, raise_errors=True)


# ---------------------------------------------------------------------------
# NotePlayer: FluidSynth failures raise instead of leaving a silent player
# ---------------------------------------------------------------------------

class TestNotePlayerInit:

    @pytest.fixture(autouse=True)
    def _no_sequencer(self):
        # The sequencer needs a real synth (tests/test_player_sequencer.py and
        # tests/test_audio_driver_selection.py cover it).
        with patch("chordnotepad.audio.player.SynthSequencer"), \
                patch("chordnotepad.audio.player.fluid_ctypes.delete_fluid_audio_driver"):
            yield

    def _bare_player(self):
        from chordnotepad.audio.player import NotePlayer

        player = NotePlayer.__new__(NotePlayer)
        player.fs = None
        player.sfid = None
        player.channel = 0
        player.instrument = 0
        return player

    def test_no_audio_driver_raises(self):
        player = self._bare_player()
        synth = MagicMock()
        synth.start.return_value = -1
        with patch("chordnotepad.audio.player.fluid_ctypes.Synth", return_value=synth):
            with pytest.raises(AudioInitializationError, match="No audio output"):
                player._initialize_fluidsynth("/x.sf2")
        assert player.fs is None
        synth.delete.assert_called_once()

    def test_bad_soundfont_raises(self):
        player = self._bare_player()
        synth = MagicMock()
        synth.start.return_value = 0
        synth.sfload.return_value = -1
        with patch("chordnotepad.audio.player.fluid_ctypes.Synth", return_value=synth):
            with pytest.raises(AudioInitializationError, match="soundfont"):
                player._initialize_fluidsynth("/broken.sf2")

    def test_other_errors_are_wrapped(self):
        player = self._bare_player()
        with patch("chordnotepad.audio.player.fluid_ctypes.Synth", side_effect=OSError("no lib")):
            with pytest.raises(AudioInitializationError, match="no lib"):
                player._initialize_fluidsynth("/x.sf2")

    def test_working_init_is_unchanged(self):
        player = self._bare_player()
        synth = MagicMock()
        synth.start.return_value = 0
        synth.sfload.return_value = 1
        with patch("chordnotepad.audio.player.fluid_ctypes.Synth", return_value=synth):
            player._initialize_fluidsynth("/x.sf2")
        assert player.fs is synth
        assert player.sfid == 1


# ---------------------------------------------------------------------------
# The chord identifier's viewmodel
# ---------------------------------------------------------------------------

class TestIdentifierViewModel:

    def test_identifier_viewmodel_raises_for_unknown_chord(self):
        from chordnotepad.viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel

        vm = ChordIdentifierViewModel(song_parser_service=MagicMock(), audio_service=MagicMock())
        with patch.object(vm, "get_chord_midi_notes", return_value=[]):
            with pytest.raises(ChordDetectionError):
                vm.play_chord("Cweird")
