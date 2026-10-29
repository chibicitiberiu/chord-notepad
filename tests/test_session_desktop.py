"""What the Tk window gets from the session instead of the viewmodels.

Window preferences (geometry, Quick Start at startup), the chord
identifier's insert, picker answers as refs, and the models the Settings
dialog and the chord identifier keep for as long as they are open.
"""

from unittest.mock import MagicMock

import pytest

from services.song_parser_service import SongParserService
from session.bootstrap import CoreServices
from session.host import HostDispatch
from session.session import AppSession
from session.state import StatusState
from session.testing import EventRecorder, FakeChordSheet, InMemoryDocumentStore, ManualHost
from viewmodels.chord_identifier_viewmodel import ChordIdentifierViewModel
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.settings_viewmodel import SettingsViewModel
from viewmodels.text_editor_viewmodel import TextEditorViewModel


class FakeConfig:
    """Dict-backed stand-in for ConfigService."""

    def __init__(self, **values):
        self.values = dict(values)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def make_session(sheet=None, **services):
    host = ManualHost()
    config = FakeConfig(window_geometry="1000x700+5+5")
    parser = SongParserService()
    main = MainWindowViewModel(config, MagicMock(), InMemoryDocumentStore(), parser,
                               HostDispatch(host))
    session = AppSession(host, main_window_viewmodel=main,
                         text_editor_viewmodel=TextEditorViewModel(parser),
                         chord_sheet_viewmodel=sheet, **services)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    recorder.clear()
    return session, config, recorder


def test_window_geometry_is_read_and_saved_through_the_session():
    session, config, _ = make_session()
    assert session.window_geometry == "1000x700+5+5"
    session.set_window_geometry("800x600+0+0")
    assert config.values["window_geometry"] == "800x600+0+0"


def test_quick_start_at_startup_preference():
    session, config, _ = make_session()
    assert session.show_quick_start_on_startup is True
    session.set_show_quick_start_on_startup(False)
    assert config.values["show_quick_start_on_startup"] is False
    assert session.show_quick_start_on_startup is False


def test_insert_chord_splices_and_says_so():
    session, _, recorder = make_session()
    session.set_text("C ")
    session.insert_chord(2, "Am")
    assert session.text == "C Am "
    assert recorder.last(StatusState).text == "Inserted chord: Am"
    with pytest.raises(ValueError):
        session.insert_chord(99, "G")


def test_document_ref_comes_from_the_store():
    session, _, _ = make_session()
    assert session.document_ref("song.txt") == InMemoryDocumentStore.ref("song.txt")


def test_dialog_models_are_new_each_time_and_use_the_services():
    from models.config import Config

    config = MagicMock()
    config.config = Config(font_size=17)
    audio = MagicMock()
    services = CoreServices(appdata=MagicMock(), config=config, song_parser=SongParserService(),
                            playback=audio, files=MagicMock())
    session, _, _ = make_session(services=services)
    settings = session.settings_model()
    assert isinstance(settings, SettingsViewModel)
    assert settings.font_size == 17
    assert session.settings_model() is not settings
    identifier = session.chord_identifier_model()
    assert isinstance(identifier, ChordIdentifierViewModel)
    identifier.play_note("C", 4)
    audio.play_note.assert_called_once()


def test_dialog_models_need_their_services():
    session, _, _ = make_session()
    with pytest.raises(RuntimeError):
        session.settings_model()
    with pytest.raises(RuntimeError):
        session.chord_identifier_model()


def test_the_chord_sheet_painting_read_path():
    session, _, _ = make_session()
    assert session.has_chord_sheet is False and session.chord_sheet_model is None
    sheet = FakeChordSheet()
    session, _, _ = make_session(sheet=sheet)
    assert session.has_chord_sheet is True and session.chord_sheet_model is sheet
