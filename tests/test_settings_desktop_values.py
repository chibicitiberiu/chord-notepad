"""The Qt desktop's Settings values: the desktop-only fields, saved as you go.

DesktopSettingsValues adds the SoundFont, the audio driver, the log level
and the colour scheme (config ``ui_theme``) to the values Android edits. It
stays off the bridge: an Android (or Tk) session still publishes plain
SettingsValues.
"""

import dataclasses
import json

import pytest

from chordnotepad.models.config import Config
from chordnotepad.services.appdata_service import AppDataService
from chordnotepad.session.bootstrap import build_core_services, create_session
from chordnotepad.session.host import HostDispatch
from chordnotepad.session.platform import ANDROID, DESKTOP, DESKTOP_QT
from chordnotepad.session.settings import (
    AUDIO_DRIVER_SUGGESTIONS, DesktopSettingsValues, SettingsValues, values_type,
)
from chordnotepad.session.state import SettingsState
from chordnotepad.session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost


def make(tmp_path, platform=DESKTOP_QT, config=None):
    if config is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(config))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                             platform=platform)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, services, recorder


def saved(tmp_path):
    return json.loads((tmp_path / "config" / "chord-notepad" / "settings.json").read_text())


def test_each_platform_edits_its_own_values():
    assert values_type(DESKTOP_QT) is DesktopSettingsValues
    assert values_type(ANDROID) is SettingsValues
    assert values_type(DESKTOP) is SettingsValues


def test_the_qt_settings_state_has_the_desktop_fields(tmp_path):
    _, _, recorder = make(tmp_path)
    values = recorder.last(SettingsState).values
    assert type(values) is DesktopSettingsValues
    assert (values.soundfont_path, values.audio_driver, values.log_level, values.ui_theme) == (
        None, None, "INFO", "system")


@pytest.mark.parametrize("platform", [ANDROID, DESKTOP])
def test_other_platforms_keep_plain_values(tmp_path, platform):
    session, _, recorder = make(tmp_path, platform=platform)
    assert type(recorder.last(SettingsState).values) is SettingsValues
    assert type(session.settings_values()) is SettingsValues


def test_commit_saves_the_desktop_fields(tmp_path):
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    values = session.settings_values()
    session.commit_settings(dataclasses.replace(
        values, soundfont_path="/music/Big.sf2", audio_driver="jack", log_level="DEBUG",
        ui_theme="dark"))
    on_disk = saved(tmp_path)
    assert (on_disk["soundfont_path"], on_disk["audio_driver"], on_disk["log_level"],
            on_disk["ui_theme"]) == ("/music/Big.sf2", "jack", "DEBUG", "dark")
    assert on_disk["theme"] == "default"          # Tk's ttk theme name, untouched
    assert recorder.last(SettingsState).values.ui_theme == "dark"
    # An empty box is the default again.
    session.commit_settings(dataclasses.replace(
        session.settings_values(), soundfont_path="", audio_driver="  "))
    assert services.config.config.soundfont_path is None
    assert services.config.config.audio_driver is None
    assert saved(tmp_path)["soundfont_path"] is None


def test_a_driver_name_outside_the_suggestions_is_kept(tmp_path):
    assert AUDIO_DRIVER_SUGGESTIONS[0] == "" and "pulseaudio" in AUDIO_DRIVER_SUGGESTIONS
    session, services, _ = make(tmp_path)
    session.begin_settings_edit()
    session.commit_settings(dataclasses.replace(session.settings_values(), audio_driver="pipewire"))
    assert services.config.config.audio_driver == "pipewire"


@pytest.mark.parametrize("change", [
    {"log_level": "VERBOSE"},
    {"ui_theme": "Dark"},
    {"ui_theme": ""},
    {"soundfont_path": "a\nb"},
    {"audio_driver": 3},
])
def test_commit_refuses_wrong_desktop_values_and_writes_nothing(tmp_path, change):
    session, services, _ = make(tmp_path)
    session.begin_settings_edit()
    before = saved(tmp_path)
    with pytest.raises(ValueError):
        session.commit_settings(dataclasses.replace(session.settings_values(), **change))
    assert saved(tmp_path) == before
    assert services.config.config.log_level == "INFO"


def test_plain_values_on_the_qt_desktop_leave_the_desktop_fields_alone(tmp_path):
    session, services, _ = make(tmp_path, config={"log_level": "WARNING", "ui_theme": "light"})
    session.begin_settings_edit()
    plain = SettingsValues.read(services.config.config)
    session.commit_settings(dataclasses.replace(plain, bpm=90))
    config = services.config.config
    assert (config.bpm, config.log_level, config.ui_theme) == (90, "WARNING", "light")


def test_apply_settings_takes_desktop_values(tmp_path):
    session, services, _ = make(tmp_path)
    session.apply_settings(dataclasses.replace(session.settings_values(), ui_theme="light"))
    assert services.config.config.ui_theme == "light"


# -- Q8: Settings never writes an invalid value ------------------------------------


@pytest.mark.parametrize("change", [
    {"max_recent_files": 0}, {"max_recent_files": 51},
    {"time_signature_beats": 0}, {"time_signature_beats": 17},
    {"bpm": 19}, {"bpm": 401}, {"font_size": 5}, {"font_size": 73},
    {"time_signature_unit": 3},
])
def test_q8_out_of_range_numbers_are_never_written(tmp_path, change):
    session, services, _ = make(tmp_path)
    session.begin_settings_edit()
    before = saved(tmp_path)
    with pytest.raises(ValueError):
        session.commit_settings(dataclasses.replace(session.settings_values(), **change))
    assert saved(tmp_path) == before
    # The view keeps what was typed as a staged number instead.
    session.commit_settings(None, invalid_numbers={"max_recent_files": "0"})
    assert saved(tmp_path) == before


@pytest.mark.parametrize("change", [
    {"max_recent_files": 1}, {"max_recent_files": 50},
    {"time_signature_beats": 1}, {"time_signature_beats": 16},
])
def test_q8_the_ends_of_the_ranges_are_written(tmp_path, change):
    session, services, _ = make(tmp_path)
    session.begin_settings_edit()
    session.commit_settings(dataclasses.replace(session.settings_values(), **change))
    (name, value), = change.items()
    assert saved(tmp_path)[name] == value


# -- the config key --------------------------------------------------------------


def test_ui_theme_round_trips_and_junk_falls_back_to_system():
    assert Config.from_dict({"ui_theme": "dark"}).ui_theme == "dark"
    assert Config.from_dict({}).ui_theme == "system"
    for junk in ("Dark", "solarized", 1, None, ["dark"]):
        config = Config.from_dict({"ui_theme": junk, "log_level": "DEBUG"})
        assert config.ui_theme == "system"
        config.validate()                         # nothing else is lost
        assert config.log_level == "DEBUG"
    assert Config(ui_theme="light").to_dict()["ui_theme"] == "light"


def test_saving_a_wrong_ui_theme_is_refused():
    config = Config()
    config.ui_theme = "sepia"
    with pytest.raises(ValueError):
        config.validate()
