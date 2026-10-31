"""The default key is stored in American spelling, whatever the notation.

Reported on Android: the AB / Do switch stored the new notation but not a
respelled key, so a config held European notation with key ``C``, and
saving Settings failed with "unknown key 'C' in european notation". Now the
config (and ``SettingsValues``) always hold the American spelling; views show
it in their notation. Older configs that saved "Sol" are read as "G".
"""

import dataclasses
import json
from types import SimpleNamespace

import pytest

from services.appdata_service import AppDataService
from session.bootstrap import build_core_services, create_session
from session.host import HostDispatch
from session.settings import SettingsValues
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost

DEFAULTS = dict(font_family="TkFixedFont", font_size=11, show_quick_start_on_startup=True,
                max_recent_files=10, bpm=120, time_signature_beats=4, time_signature_unit=4)


def read(notation, key):
    return SettingsValues.read(SimpleNamespace(notation=notation, key=key, **DEFAULTS))


@pytest.mark.parametrize("notation, key, expected", [
    ("european", "C", "C"),
    ("european", "F#", "F#"),
    ("american", "Re", "D"),
    ("american", "Sib", "Bb"),
    ("european", "Do", "C"),
    ("european", "Solb", "Gb"),
    ("american", "C", "C"),
    ("european", "", ""),
])
def test_read_gives_the_key_in_american_spelling(notation, key, expected):
    values = read(notation, key)
    assert values.key == expected
    values.check()


def test_read_leaves_an_unknown_key_and_check_refuses_it():
    values = read("european", "X")
    assert values.key == "X"
    with pytest.raises(ValueError, match="unknown key"):
        values.check()
    with pytest.raises(ValueError, match="American spelling"):
        dataclasses.replace(values, key="Sol").check()


def test_settings_save_after_the_notation_switch(tmp_path):
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text(json.dumps({"key": "C", "notation": "american"}))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False)
    session.subscribe(EventRecorder())
    session.start()

    session.set_notation("european")
    assert services.config.config.notation == "american"   # the switch is for the song only
    session.begin_settings_edit()
    session.save_settings()
    assert services.config.config.key == "C"
    session.begin_settings_edit()
    session.commit_settings(dataclasses.replace(session.settings_values(), key="G"))
    assert services.config.config.key == "G"
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert saved["key"] == "G" and saved["notation"] == "american"


def test_an_older_config_with_a_european_key_reads_as_american(tmp_path):
    config_dir = tmp_path / "config" / "chord-notepad"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.json").write_text(json.dumps({"key": "Sol", "notation": "european"}))
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(ManualHost()),
                                   player=FakePlayer())
    assert services.config.config.key == "G"


@pytest.mark.parametrize("stored, expected", [
    ("Do", "C"), ("Sol#", "G#"), ("Sib", "Bb"), ("G", "G"), ("", ""), ("X", "X")])
def test_config_from_dict_migrates_a_european_key(stored, expected):
    from models.config import Config

    config = Config.from_dict({"key": stored})
    assert config.key == expected
    assert config.to_dict()["key"] == expected


def test_to_dict_writes_american_even_if_set_european():
    from models.config import Config

    config = Config()
    config.key = "La"
    assert config.to_dict()["key"] == "A"


def test_desktop_settings_viewmodel_shows_the_notation_and_saves_american(tmp_path):
    from viewmodels.settings_viewmodel import SettingsViewModel

    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(ManualHost()),
                                   player=FakePlayer())
    services.config.config.key = "G"
    services.config.config.notation = "european"
    model = SettingsViewModel(services.config)
    assert model.key_choices()[0] == "Do" and model.shown_key == "Sol"
    model.shown_key = "La"                      # picked from the European list
    assert model.key == "A"
    model.notation = "american"                  # the key stays, its spelling changes
    assert model.shown_key == "A" and model.key_choices()[0] == "C"
    model.notation = "european"
    model.commit()
    assert services.config.config.key == "A"
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert saved["key"] == "A"
    # A new dialog shows it in the saved notation.
    assert SettingsViewModel(services.config).shown_key == "La"
