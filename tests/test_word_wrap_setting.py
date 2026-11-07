"""Word wrap: one setting both apps read, off by default.

With wrap off the song scrolls sideways and a chord line stays over its
lyric line however narrow the window (L7). The config key is
``word_wrap``; it is in :class:`SettingsValues` (Android's Settings screen)
and in :class:`EditorState` (both editors follow it at once). The desktop's
View > Word Wrap and the Settings dialog write the same key.
"""

import json

import pytest

from models.config import Config
from services.appdata_service import AppDataService
from services.config_service import ConfigService
from session.bootstrap import build_core_services, create_session
from session.host import HostDispatch
from session.settings import SettingsValues
from session.state import EditorState, SettingsState
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.settings_viewmodel import SettingsViewModel


def make(tmp_path, config=None):
    if config is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(config))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, services, recorder


def saved(tmp_path) -> dict:
    return json.loads((tmp_path / "config" / "chord-notepad" / "settings.json").read_text())


# -- the config ----------------------------------------------------------------


def test_off_by_default_and_written_with_the_config():
    assert Config().word_wrap is False
    assert Config().to_dict()["word_wrap"] is False
    assert Config.from_dict({}).word_wrap is False
    assert Config.from_dict({"word_wrap": True}).word_wrap is True
    assert Config.from_dict(Config(word_wrap=True).to_dict()).word_wrap is True


@pytest.mark.parametrize("junk", ["true", 1, None, [], {}])
def test_a_value_that_isnt_a_bool_reads_as_off(junk):
    assert Config.from_dict({"word_wrap": junk}).word_wrap is False


def test_persists_through_the_config_file(tmp_path):
    service = ConfigService(AppDataService(root=tmp_path))
    service.load_config()
    service.set("word_wrap", True)
    service.save_config()
    again = ConfigService(AppDataService(root=tmp_path))
    assert again.load_config().word_wrap is True


# -- the Settings values and dialog model --------------------------------------


def test_settings_values_carry_it():
    assert SettingsValues.read(Config()).word_wrap is False
    assert SettingsValues.read(Config(word_wrap=True)).word_wrap is True
    assert SettingsValues.read(Config()).as_dict()["word_wrap"] is False


def test_the_dialog_model_commits_it_and_flags_the_change(tmp_path):
    service = ConfigService(AppDataService(root=tmp_path))
    service.load_config()
    model = SettingsViewModel(service)
    assert model.word_wrap is False
    assert SettingsViewModel(service).commit().wrap_changed is False
    model = SettingsViewModel(service)
    model.word_wrap = True
    changes = model.commit()
    assert changes.wrap_changed is True
    assert changes.font_changed is False and changes.general_changed is False
    assert service.config.word_wrap is True
    assert saved(tmp_path)["word_wrap"] is True


# -- the session: EditorState and the commands --------------------------------


def test_editor_state_says_off_at_start(tmp_path):
    _, _, recorder = make(tmp_path)
    assert recorder.last(EditorState).word_wrap is False


def test_editor_state_reads_a_saved_on(tmp_path):
    _, _, recorder = make(tmp_path, config={"word_wrap": True})
    assert recorder.last(EditorState).word_wrap is True
    assert recorder.last(SettingsState).values.word_wrap is True


def test_set_word_wrap_switches_the_editor_and_the_settings(tmp_path):
    session, services, recorder = make(tmp_path)
    session.set_word_wrap(True)
    assert recorder.last(EditorState).word_wrap is True
    assert recorder.last(SettingsState).values.word_wrap is True
    assert services.config.config.word_wrap is True
    session.save_config()
    assert saved(tmp_path)["word_wrap"] is True
    session.set_word_wrap(False)
    assert recorder.last(EditorState).word_wrap is False


def test_android_settings_commit_takes_effect_at_once_and_is_saved(tmp_path):
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    values = session.settings_values()
    session.commit_settings(SettingsValues(**{**values.as_dict(), "word_wrap": True}))
    assert recorder.last(EditorState).word_wrap is True
    assert saved(tmp_path)["word_wrap"] is True
    session.commit_settings(SettingsValues(**{**values.as_dict(), "word_wrap": False}))
    assert recorder.last(EditorState).word_wrap is False
    assert saved(tmp_path)["word_wrap"] is False


def test_desktop_dialog_commit_applies_it(tmp_path):
    session, _, recorder = make(tmp_path)
    model = session.settings_model()
    model.word_wrap = True
    session.apply_settings(model.commit())
    assert recorder.last(EditorState).word_wrap is True


def test_apply_settings_with_values(tmp_path):
    session, _, recorder = make(tmp_path)
    values = session.settings_values()
    session.apply_settings(SettingsValues(**{**values.as_dict(), "word_wrap": True}))
    assert recorder.last(EditorState).word_wrap is True


def test_the_bridge_carries_it():
    from session import bridge

    assert bridge.SESSION_COMMANDS["set_word_wrap"] == {"on": "bool"}
    assert "set_word_wrap" in bridge.CONFIG_COMMANDS
    schema = bridge.schema()
    assert schema["types"]["SettingsValues"]["fields"]["word_wrap"] == "bool"
    assert schema["types"]["EditorState"]["fields"]["word_wrap"] == "bool"
