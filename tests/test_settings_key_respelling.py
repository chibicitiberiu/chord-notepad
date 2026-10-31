"""The default key after the AB / Do switch (reported on Android).

The switch stores the new notation but not a respelled key, so a config can
hold European notation with key ``C``. Saving Settings read those values
back and failed with "unknown key 'C' in european notation".
"""

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
    ("european", "C", "Do"),
    ("european", "F#", "Fa#"),
    ("american", "Re", "D"),
    ("american", "Sib", "Bb"),
    ("european", "Do", "Do"),
    ("american", "C", "C"),
    ("european", "", ""),
])
def test_read_spells_the_key_in_the_notation(notation, key, expected):
    values = read(notation, key)
    assert values.key == expected
    values.check()


def test_read_leaves_a_key_it_cant_respell():
    values = read("european", "X")
    assert values.key == "X"
    with pytest.raises(ValueError, match="unknown key"):
        values.check()


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
    assert services.config.config.notation == "european"
    session.begin_settings_edit()
    session.save_settings()
    assert services.config.config.key == "Do"
