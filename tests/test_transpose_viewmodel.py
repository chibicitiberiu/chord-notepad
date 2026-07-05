"""Tests for the MainWindowViewModel transpose command."""

from unittest.mock import MagicMock, Mock

from services.config_service import ConfigService
from services.song_parser_service import SongParserService
from viewmodels.main_window_viewmodel import MainWindowViewModel
from models.notation import Notation


def _make_vm(key=None, notation="american"):
    config = Mock(spec=ConfigService)
    values = {"notation": notation, "key": key}
    config.get.side_effect = lambda k, default=None: values.get(k, default)
    return MainWindowViewModel(
        config_service=config,
        audio_service=MagicMock(),
        file_service=MagicMock(),
        song_parser_service=SongParserService(),
        application=MagicMock(),
    )


class TestTransposeCommand:
    def test_whole_doc_replaces_text(self):
        vm = _make_vm()
        vm.on_text_changed("C  Am  F  G\n")
        seen = []
        vm.observe("current_text", seen.append)

        vm.transpose(2, None)

        assert vm.current_text == "D  Bm  G  A\n"
        assert seen == ["D  Bm  G  A\n"]

    def test_whole_doc_shifts_toolbar_key(self):
        vm = _make_vm(key="C")
        vm.on_text_changed("I  IV  V\n")

        vm.transpose(2, None)

        assert vm.key == "D"

    def test_selection_does_not_shift_key(self):
        vm = _make_vm(key="C")
        vm.on_text_changed("C  Am\n")

        # region covering only the first chord
        vm.transpose(2, (0, 1))

        assert vm.key == "C"  # unchanged for a selection transpose
        assert vm.current_text == "D  Am\n"

    def test_zero_is_noop(self):
        vm = _make_vm()
        vm.on_text_changed("C  Am\n")
        seen = []
        vm.observe("current_text", seen.append)

        vm.transpose(0, None)

        assert vm.current_text == "C  Am\n"
        assert seen == []

    def test_marks_modified(self):
        vm = _make_vm()
        vm.new_file()  # resets is_modified to False
        vm.on_text_changed("C\n")
        # on_text_changed sets modified; reset it to isolate transpose's effect
        vm.set_and_notify("is_modified", False)

        vm.transpose(2, None)

        assert vm.is_modified is True

    def test_european_key_shift(self):
        vm = _make_vm(key="Do", notation="european")
        vm.on_text_changed("Do  Lam\n")

        vm.transpose(2, None)

        assert vm.key == "Re"
        assert vm.current_text == "Re  Sim\n"
