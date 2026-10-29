"""Building the core without Tk (session.bootstrap), and what it needs from services.

Also the host-provided data directory (``AppDataService(root=...)``), the
atomic config write and the plain-values settings path Android uses.
"""

import dataclasses
import json
from unittest.mock import patch

import pytest

from exceptions import ConfigurationError
from services.appdata_service import AppDataService
from services.config_service import ConfigService
from session.bootstrap import CoreServices, build_core_services, create_session
from session.host import HostDispatch
from session.settings import SettingsValues
from session.state import EditorState, StatusState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost


def make(tmp_path, chord_sheet=False):
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=chord_sheet)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return host, services, session, recorder


def test_appdata_root_gives_the_xdg_layout_under_it(tmp_path):
    appdata = AppDataService(root=tmp_path)
    assert appdata.get_app_data_dir() == tmp_path / "data" / "chord-notepad"
    assert appdata.get_config_dir() == tmp_path / "config" / "chord-notepad"
    assert appdata.get_logs_dir() == tmp_path / "data" / "chord-notepad" / "logs"
    assert appdata.get_config_file_path().name == "settings.json"


def test_build_core_services_creates_the_directories_and_loads_the_config(tmp_path):
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text(json.dumps({"bpm": 97, "font_size": 15}))
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(ManualHost()))
    assert isinstance(services, CoreServices)
    assert services.config.get("bpm") == 97
    assert (tmp_path / "data" / "chord-notepad" / "logs").is_dir()
    assert services.playback.is_initialized is False  # FluidSynth starts lazily


def test_create_session_with_and_without_the_chord_sheet(tmp_path):
    _, _, session, _ = make(tmp_path)
    assert session.has_chord_sheet is False
    _, _, session, _ = make(tmp_path, chord_sheet=True)
    assert session.has_chord_sheet is True
    session.set_text("C G")
    assert session.text == "C G"


def test_the_session_reaches_its_services(tmp_path):
    _, services, session, _ = make(tmp_path)
    assert session.settings_model() is not None
    assert session.chord_identifier_model() is not None
    values = session.settings_values()
    assert values.bpm == services.config.config.bpm


def test_apply_settings_with_values_commits_like_the_dialog(tmp_path):
    host, services, session, recorder = make(tmp_path)
    values = session.settings_values()
    session.apply_settings(dataclasses.replace(values, font_family="Serif", font_size=18,
                                               notation="european", key="Re"))
    assert recorder.last(EditorState).font_size == 18
    assert recorder.last(EditorState).font_family == "Serif"
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert (saved["font_size"], saved["notation"], saved["key"]) == (18, "european", "Re")


@pytest.mark.parametrize("field,value", [
    ("font_size", 5), ("font_size", 73), ("notation", "german"), ("key", "H"),
    ("max_recent_files", 0), ("bpm", 10), ("time_signature_beats", 17),
    ("time_signature_unit", 3), ("font_family", " "),
])
def test_out_of_range_settings_write_nothing(tmp_path, field, value):
    _, services, session, _ = make(tmp_path)
    before = services.config.config.to_dict()
    with pytest.raises(ValueError, match=field):
        session.apply_settings(dataclasses.replace(session.settings_values(), **{field: value}))
    assert services.config.config.to_dict() == before


def test_settings_values_read_from_a_config():
    from models.config import Config

    values = SettingsValues.read(Config(bpm=77, key="F"))
    assert (values.bpm, values.key) == (77, "F")
    values.check()


def test_save_config_and_pause_commands(tmp_path):
    _, services, session, recorder = make(tmp_path)
    session.set_bpm(140)
    session.save_config()
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert saved["bpm"] == 140
    recorder.clear()
    session.pause()  # idle: nothing happens
    assert recorder.items == []


def test_restore_draft_is_refused_while_playing(tmp_path):
    host, services, session, recorder = make(tmp_path)
    services.playback._player.auto_play = False
    session.set_text("C G")
    host.advance(1)
    session.play_pause()
    services.playback._render_thread.join(10)
    host.run_pending()
    assert session._playback_status().value == "playing"
    session.restore_draft("Am", None, True)
    assert session.text == "C G"
    session.stop()


def test_without_services_the_service_commands_say_so():
    from services.song_parser_service import SongParserService
    from session.session import AppSession
    from viewmodels.main_window_viewmodel import MainWindowViewModel
    from viewmodels.text_editor_viewmodel import TextEditorViewModel
    from unittest.mock import MagicMock

    host = ManualHost()
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: default
    main = MainWindowViewModel(config, MagicMock(), InMemoryDocumentStore(),
                               SongParserService(), HostDispatch(host))
    session = AppSession(host, main_window_viewmodel=main,
                         text_editor_viewmodel=TextEditorViewModel(SongParserService()))
    for call in (session.settings_values, session.save_config):
        with pytest.raises(RuntimeError, match="without services"):
            call()


def test_config_is_written_atomically(tmp_path):
    service = ConfigService(AppDataService(root=tmp_path))
    service.load_config()
    service.set("bpm", 111)
    service.save_config()
    path = service._config_file_path
    assert json.loads(path.read_text())["bpm"] == 111

    service.set("bpm", 122)
    with patch("services.config_service.json.dump", side_effect=OSError("disk full")):
        with pytest.raises(ConfigurationError):
            service.save_config()
    # The old file is intact and no temporary file is left behind.
    assert json.loads(path.read_text())["bpm"] == 111
    assert [p.name for p in path.parent.iterdir()] == ["settings.json"]
