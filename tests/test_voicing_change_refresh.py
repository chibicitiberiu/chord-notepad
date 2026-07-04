"""Regression tests: changing the voicing must notify observers.

The chord-sheet strip re-renders on this notification (see
``MainWindow._on_voicing_for_chord_sheet``). Before the fix, switching the
voicing (e.g. guitar:standard -> guitar:drop_d, or to a custom fretboard
voicing) rebuilt the note picker silently, so the strip kept showing the
previous voicing's fingerings until the song text changed.
"""

from unittest.mock import MagicMock, Mock

from services.config_service import ConfigService
from services.song_parser_service import SongParserService
from viewmodels.main_window_viewmodel import MainWindowViewModel


def _make_vm(audio=None):
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: default
    return MainWindowViewModel(
        config_service=config,
        audio_service=audio if audio is not None else MagicMock(),
        file_service=MagicMock(),
        song_parser_service=SongParserService(),
        application=MagicMock(),
    )


class TestSetVoicingNotifies:
    def test_notifies_voicing_observers(self):
        vm = _make_vm()
        seen = []
        vm.observe('voicing', seen.append)

        vm.set_voicing('guitar:drop_d')

        assert seen == ['guitar:drop_d']

    def test_forwards_to_audio_service(self):
        audio = MagicMock()
        vm = _make_vm(audio)

        vm.set_voicing('voicing:my_seven_string')

        audio.set_voicing.assert_called_once_with('voicing:my_seven_string')

    def test_notification_is_unconditional_for_same_value(self):
        # Editing the active voicing's parameters in Settings re-invokes the
        # voicing-change path with the SAME selection string; the picker was
        # still rebuilt, so observers must fire every time (set_and_notify
        # would swallow the repeat).
        vm = _make_vm()
        seen = []
        vm.observe('voicing', seen.append)

        vm.set_voicing('voicing:my_seven_string')
        vm.set_voicing('voicing:my_seven_string')

        assert seen == ['voicing:my_seven_string', 'voicing:my_seven_string']
