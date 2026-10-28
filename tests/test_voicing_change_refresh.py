"""Regression tests: changing the voicing must re-feed the chord sheet.

The session feeds the chord-sheet strip the parsed song whenever the detected
lines, the key or the voicing change. Before the fix, switching the voicing
(e.g. guitar:standard -> guitar:drop_d, or to a custom fretboard voicing)
rebuilt the note picker silently, so the strip kept showing the previous
voicing's fingerings until the song text changed.
"""

from unittest.mock import MagicMock, Mock

from services.config_service import ConfigService
from services.song_parser_service import SongParserService
from session.host import HostDispatch
from session.session import AppSession
from session.testing import FakeChordSheet, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


def _make_vm(audio=None, application=None):
    config = Mock(spec=ConfigService)
    config.get.side_effect = lambda key, default=None: default
    return MainWindowViewModel(
        config_service=config,
        audio_service=audio if audio is not None else MagicMock(),
        documents=MagicMock(),
        song_parser_service=SongParserService(),
        application=application if application is not None else MagicMock(),
    )


class SessionEnv:
    def __init__(self, start=True):
        self.host = ManualHost()
        self.main = _make_vm(application=HostDispatch(self.host))
        self.sheet = FakeChordSheet()
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()),
            chord_sheet_viewmodel=self.sheet)
        if start:
            self.session.start()

    def load(self, text):
        """Type ``text`` and let the detection debounce run out."""
        self.session.set_text(text)
        self.host.advance(0.5)


# -- the viewmodel contract the feed relies on -----------------------------------


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


# -- the session's chord-sheet feed --------------------------------------------------


class TestChordSheetFeed:
    def test_start_seeds_the_strip_once(self):
        env = SessionEnv(start=False)
        env.main.set_voicing('guitar:drop_d')
        assert env.sheet.fed == []  # nothing before start: it arms a timer

        env.session.start()
        assert env.sheet.fed == [([], None)]

    def test_voicing_change_refeeds_the_current_song(self):
        env = SessionEnv()
        env.load("C G Am")
        env.sheet.fed.clear()

        env.main.set_voicing('guitar:drop_d')

        assert env.sheet.fed == [(["C", "G", "Am"], None)]

    def test_same_voicing_twice_refeeds_twice(self):
        env = SessionEnv()
        env.load("C G")
        env.sheet.fed.clear()

        env.main.set_voicing('voicing:my_seven_string')
        env.main.set_voicing('voicing:my_seven_string')

        assert env.sheet.fed == [(["C", "G"], None)] * 2

    def test_key_change_refeeds_with_the_new_key(self):
        env = SessionEnv()
        env.load("I IV V")
        env.sheet.fed.clear()

        env.main.set_key("D")

        assert env.sheet.fed == [(["I", "IV", "V"], "D")]

    def test_new_detection_feeds_after_the_debounce(self):
        env = SessionEnv()
        env.sheet.fed.clear()

        env.session.set_text("C G")
        assert env.sheet.fed == []
        env.host.advance(0.5)
        assert env.sheet.fed == [(["C", "G"], None)]

    def test_identical_redetection_does_not_refeed(self):
        env = SessionEnv()
        env.load("C G")
        env.sheet.fed.clear()

        env.load("C G")

        assert env.sheet.fed == []

    def test_shutdown_stops_the_feed(self):
        env = SessionEnv()
        env.sheet.fed.clear()
        env.session.shutdown()

        env.main.set_voicing('guitar:drop_d')
        env.main.set_key("D")

        assert env.sheet.fed == []
