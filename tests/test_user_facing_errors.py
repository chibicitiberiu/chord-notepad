"""User-initiated actions that fail must tell the user why.

Covers the "caught" layer: places that used to catch an error and only log
it (or return False with no reason), so File -> Export MIDI, Play, chord
clicks, Help, Settings -> Save etc. looked like they did nothing.

Headless: Tk windows are never built. View methods are called unbound on a
Mock standing in for ``self`` (same approach as test_settings_dialog_wiring),
and ``messagebox`` is patched.
"""

import sys
import tkinter as tk
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from exceptions import (
    AudioInitializationError,
    ChordDetectionError,
    ChordNotepadError,
    ConfigurationError,
    FileOperationError,
)
from models.chord import ChordInfo
from models.rendered_song import RenderedSong
from services.config_service import ConfigService
from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from ui import audio_errors


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
    from viewmodels.main_window_viewmodel import MainWindowViewModel

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
    from services.file_service import FileService
    from session.documents import FileSystemDocumentStore

    return FileSystemDocumentStore(FileService(MagicMock()))


def _out_mid():
    return _fs_store().ref_for_path("/tmp/out.mid")


def _stub_writer(render=None):
    stub = ModuleType("services.midi_file_writer")
    stub.render_midi_bytes = render if render is not None else MagicMock(return_value=b"MIDI")
    stub.PPQ = 480
    return patch.dict(sys.modules, {"services.midi_file_writer": stub})


# ---------------------------------------------------------------------------
# MainWindowViewModel: open / save / export keep the reason
# ---------------------------------------------------------------------------

class TestViewModelFileErrors:

    def test_open_missing_file_reports_reason(self, tmp_path):
        store = _fs_store()
        vm = _viewmodel(documents=store)
        missing = store.ref_for_path(tmp_path / "nope.txt")

        assert vm.open_file(missing) is False
        assert "File not found" in vm.last_error
        assert "nope.txt" in vm.last_error

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
        with patch.dict(sys.modules, {"services.midi_file_writer": None}):
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
        from models.fretboard_spec import BUILTIN_FRETBOARDS

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

        with patch("services.playback_service.NotePlayer",
                   side_effect=FileNotFoundError("Soundfont not found: /x.sf2")):
            with pytest.raises(AudioInitializationError) as info:
                service.play_chord_immediate(chord)
        assert "Soundfont not found: /x.sf2" in str(info.value)
        assert service.audio_error == "Soundfont not found: /x.sf2"

    def test_start_song_playback_raises_when_audio_unavailable(self, song_parser):
        service = PlaybackService(_config(), player=None)
        lines = song_parser.detect_chords_in_text("C G\n", "american")

        with patch("services.playback_service.NotePlayer",
                   side_effect=AudioInitializationError("No audio output could be started")):
            with pytest.raises(AudioInitializationError) as info:
                service.start_song_playback(lines, initial_key=None)
        assert "No audio output" in str(info.value)

    def test_play_note_and_notes_raise_when_audio_unavailable(self):
        service = PlaybackService(_config(), player=None)
        with patch("services.playback_service.NotePlayer", side_effect=RuntimeError("x")):
            with pytest.raises(AudioInitializationError):
                service.play_note("C", 4)
            with pytest.raises(AudioInitializationError):
                service.play_notes_immediate([60])

    def test_successful_init_clears_audio_error(self):
        service = PlaybackService(_config(), player=None)
        with patch("services.playback_service.NotePlayer", side_effect=RuntimeError("x")):
            service.initialize_player()
        assert service.audio_error == "x"
        with patch("services.playback_service.NotePlayer"):
            assert service.initialize_player() is True
        assert service.audio_error is None

    def test_render_thread_failure_resets_and_reports(self, song_parser):
        service = PlaybackService(_config(), player=MagicMock())
        lines = song_parser.detect_chords_in_text("C G\n", "american")
        finished = Mock()
        errors = Mock()

        with patch("services.playback_service.SongRenderer") as renderer:
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

        with patch("services.playback_service.SongRenderer") as renderer:
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
        with patch("audio.player.SynthSequencer"), \
                patch("audio.player.fluidsynth.delete_fluid_audio_driver"):
            yield

    def _bare_player(self):
        from audio.player import NotePlayer

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
        with patch("audio.player.fluidsynth.Synth", return_value=synth):
            with pytest.raises(AudioInitializationError, match="No audio output"):
                player._initialize_fluidsynth("/x.sf2")
        assert player.fs is None
        synth.delete.assert_called_once()

    def test_bad_soundfont_raises(self):
        player = self._bare_player()
        synth = MagicMock()
        synth.start.return_value = 0
        synth.sfload.return_value = -1
        with patch("audio.player.fluidsynth.Synth", return_value=synth):
            with pytest.raises(AudioInitializationError, match="soundfont"):
                player._initialize_fluidsynth("/broken.sf2")

    def test_other_errors_are_wrapped(self):
        player = self._bare_player()
        with patch("audio.player.fluidsynth.Synth", side_effect=OSError("no lib")):
            with pytest.raises(AudioInitializationError, match="no lib"):
                player._initialize_fluidsynth("/x.sf2")

    def test_working_init_is_unchanged(self):
        player = self._bare_player()
        synth = MagicMock()
        synth.start.return_value = 0
        synth.sfload.return_value = 1
        with patch("audio.player.fluidsynth.Synth", return_value=synth):
            player._initialize_fluidsynth("/x.sf2")
        assert player.fs is synth
        assert player.sfid == 1


# ---------------------------------------------------------------------------
# Help launcher
# ---------------------------------------------------------------------------

class TestShowHelp:

    def _docs(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>")
        return str(tmp_path)

    def test_missing_docs_raises_with_location(self, tmp_path):
        from ui.help_window import show_help

        with pytest.raises(ChordNotepadError) as info:
            show_help(str(tmp_path / "missing"))
        assert "missing" in str(info.value)

    def test_no_browser_raises_with_url(self, tmp_path):
        from ui import help_window

        with patch.object(help_window, "is_sandboxed", return_value=False), \
                patch.object(help_window.webbrowser, "open", return_value=False):
            with pytest.raises(ChordNotepadError) as info:
                help_window.show_help(self._docs(tmp_path))
        assert "index.html" in str(info.value)

    def test_browser_error_raises(self, tmp_path):
        from ui import help_window

        with patch.object(help_window, "is_sandboxed", return_value=False), \
                patch.object(help_window.webbrowser, "open",
                             side_effect=RuntimeError("no display")):
            with pytest.raises(ChordNotepadError, match="no display"):
                help_window.show_help(self._docs(tmp_path))

    def test_success_opens_browser(self, tmp_path):
        from ui import help_window

        with patch.object(help_window, "is_sandboxed", return_value=False), \
                patch.object(help_window.webbrowser, "open", return_value=True) as opened:
            assert help_window.show_help(self._docs(tmp_path)) is None
        opened.assert_called_once()


# ---------------------------------------------------------------------------
# present_audio_unavailable: the Tk dialog for the session's AudioUnavailable
# (the once-per-session policy is tested in tests/test_session_menus.py)
# ---------------------------------------------------------------------------

class TestPresentAudioUnavailable:

    def test_shows_the_message_as_an_audio_error(self):
        with patch("ui.audio_errors.messagebox.showerror") as showerror:
            audio_errors.present_audio_unavailable(None, "no driver")
        assert showerror.call_args.args == ("Audio Error", "no driver")


# ---------------------------------------------------------------------------
# MainWindow (unbound, mock self)
# ---------------------------------------------------------------------------

class TestMainWindowDialogs:

    def _window(self):
        window = Mock()
        return window

    # The file flows' errors (open, save, export, a failed save stopping
    # New/Open/close) are UserErrors from the session now:
    # tests/test_session_documents.py. The window shows them like any other
    # (test_user_error_event_is_shown).

    # Playback failures are reported by the session (tests/test_session_playback.py);
    # the window only presents its events.

    def test_chord_click_goes_to_the_session(self):
        from ui.main_window import MainWindow

        window = self._window()
        window.text_editor.offset_at.return_value = 7
        MainWindow.on_chord_click(window, Mock(x=1, y=1))
        window.session.tap_chord_at.assert_called_once_with(7)

    def test_audio_unavailable_event_is_shown(self):
        from session.events import AudioUnavailable
        from ui.main_window import MainWindow

        window = self._window()
        window._dialog_parent.return_value = window
        with patch("ui.audio_errors.messagebox.showerror") as showerror:
            MainWindow._on_session_output(window, AudioUnavailable("no driver", from_click=True))
            MainWindow._on_session_output(window, AudioUnavailable("no driver", from_click=True))
        # The session already applied the once-per-session policy.
        assert showerror.call_count == 2
        assert showerror.call_args.args == ("Audio Error", "no driver")
        assert showerror.call_args.kwargs["parent"] is window

    def test_user_error_event_is_shown(self):
        from session.events import UserError
        from ui.main_window import MainWindow

        window = self._window()
        with patch("ui.main_window.messagebox.showerror") as showerror:
            MainWindow._on_session_output(
                window, UserError("Playback Error", "Could not play the song.\n\nrender broke"))
        assert showerror.call_args.args == ("Playback Error", "Could not play the song.\n\nrender broke")
        assert showerror.call_args.kwargs["parent"] is window

    def test_help_failure_shows_reason(self):
        from ui.main_window import MainWindow

        window = self._window()
        window.resource_service.get_resource_path.return_value = "/nowhere"
        with patch("ui.help_window.show_help",
                   side_effect=ChordNotepadError("Could not open a web browser")), \
                patch("ui.main_window.messagebox.showwarning") as showwarning:
            MainWindow.show_help(window)
        assert "web browser" in showwarning.call_args.args[1]

    def test_insert_from_identifier_failure_is_shown(self):
        from ui.main_window import MainWindow

        window = self._window()
        window.text_editor.offset_of.side_effect = tk.TclError("bad index")
        with patch("ui.main_window.messagebox.showerror") as showerror:
            MainWindow._on_insert_chord_from_identifier(window, "Am")
        assert "bad index" in showerror.call_args.args[1]


# ---------------------------------------------------------------------------
# Dialogs and secondary windows
# ---------------------------------------------------------------------------

class TestDialogs:

    def test_settings_save_failure_keeps_dialog_open(self):
        from ui.dialogs.options_dialog import OptionsDialog

        dialog = Mock()
        dialog._viewmodel.validate_all.return_value = []
        dialog._viewmodel.commit.side_effect = ConfigurationError(
            "Failed to save configuration: read-only file system")

        with patch("ui.dialogs.options_dialog.messagebox.showerror") as showerror:
            OptionsDialog._on_save(dialog)

        assert "read-only file system" in showerror.call_args.args[1]
        dialog.on_apply.assert_not_called()
        dialog.destroy.assert_not_called()

    def test_transpose_invalid_number_is_reported(self):
        from ui.dialogs.transpose_dialog import TransposeDialog

        dialog = Mock()
        dialog.result = None
        dialog.semitones_var.get.side_effect = tk.TclError("expected integer")

        with patch("ui.dialogs.transpose_dialog.messagebox.showerror") as showerror:
            TransposeDialog._on_ok(dialog)

        showerror.assert_called_once()
        dialog.destroy.assert_not_called()
        assert dialog.result is None

    def test_identifier_note_click_reports_audio_error(self):
        from ui.chord_identifier import ChordIdentifierWindow

        window = Mock()
        error = AudioInitializationError("no driver")
        window.viewmodel.play_note.side_effect = error
        ChordIdentifierWindow._on_play_note(window, "C", 4)
        window._report_audio_error.assert_called_once_with(error)

    def test_identifier_hands_audio_errors_to_its_owner(self):
        from ui.chord_identifier import ChordIdentifierWindow

        window = Mock()
        error = AudioInitializationError("no driver")
        ChordIdentifierWindow._report_audio_error(window, error)
        window.on_audio_error.assert_called_once_with(error)

    def test_main_window_reports_identifier_audio_errors_through_the_session(self):
        from ui.main_window import MainWindow

        window = Mock()
        MainWindow._on_identifier_audio_error(window, AudioInitializationError("no driver"))
        window.session.report_audio_failure.assert_called_once_with("no driver", from_click=True)

    def test_identifier_unplayable_chord_is_reported(self):
        from ui.chord_identifier import ChordIdentifierWindow

        window = Mock()
        window.results_listbox.curselection.return_value = (0,)
        window.results_listbox.get.return_value = "Cweird"
        window.viewmodel.play_chord.side_effect = ChordDetectionError(
            "Could not work out the notes of Cweird.")
        with patch("ui.chord_identifier.messagebox.showerror") as showerror:
            ChordIdentifierWindow.play_selected_chord(window)
        assert "Cweird" in showerror.call_args.args[1]

    def test_identifier_viewmodel_raises_for_unknown_chord(self):
        from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel

        vm = ChordIdentifierViewModel(song_parser_service=MagicMock(), audio_service=MagicMock())
        with patch.object(vm, "get_chord_midi_notes", return_value=[]):
            with pytest.raises(ChordDetectionError):
                vm.play_chord("Cweird")

    def test_chord_sheet_click_auditions_through_the_session(self):
        # The session plays it and reports audio failures by its policy.
        from ui.chord_sheet.panel import ChordSheetPanel

        panel = Mock()
        panel._canvas.canvasx.return_value = 5
        panel._layout.slots = [Mock(x=0, width=10, chord_index=0)]
        ChordSheetPanel._on_canvas_click(panel, Mock(x=5))
        panel._session.audition.assert_called_once_with(0)
