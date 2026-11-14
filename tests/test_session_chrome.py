"""The Qt window's chrome in the core: the whole-window zoom, the menu bar
kept shown, the colours set from the ☰ menu (config keys plus bridge
commands), the refused-edit event (Q9) and the texts the desktop's menus,
toolbar and file pickers share with Tk."""

import json

import pytest

from chordnotepad.constants import DEFAULT_UI_SCALE, UI_SCALE_MAX, UI_SCALE_MIN
from chordnotepad.models.config import Config, ui_scale_from_config
from chordnotepad.session import formatting, toolbar_texts
from chordnotepad.session.bridge import SESSION_COMMANDS, encode
from chordnotepad.session.events import EditRefused
from chordnotepad.session.state import SettingsState
from tests.test_session_editing import Env


@pytest.fixture
def session(tmp_path):
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services, create_session
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.platform import DESKTOP_QT
    from chordnotepad.session.testing import (
        EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost,
    )

    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), platform=DESKTOP_QT)
    session.recorder = EventRecorder()
    session.subscribe(session.recorder)
    session.start()
    session.config = services.config
    yield session
    session.shutdown()


# -- config ------------------------------------------------------------------------------


def test_the_new_keys_default_and_round_trip():
    config = Config()
    assert (config.ui_scale, config.menu_bar_shown) == (DEFAULT_UI_SCALE, False)
    again = Config.from_dict(Config(ui_scale=1.3, menu_bar_shown=True).to_dict())
    assert (again.ui_scale, again.menu_bar_shown) == (1.3, True)


@pytest.mark.parametrize("raw, read", [
    (None, 1.0), ("1.2", 1.0), (True, 1.0), (0.5, 1.0), (2.5, 1.0), (float("nan"), 1.0),
    (UI_SCALE_MIN, UI_SCALE_MIN), (UI_SCALE_MAX, UI_SCALE_MAX), (1.2345, 1.23), (1, 1.0),
])
def test_a_saved_ui_scale_is_read_back_sane(raw, read):
    assert ui_scale_from_config(raw) == read
    Config.from_dict({"ui_scale": raw}).validate()


def test_junk_menu_bar_values_read_as_hidden():
    assert Config.from_dict({"menu_bar_shown": "yes"}).menu_bar_shown is False
    assert Config.from_dict({}).menu_bar_shown is False


# -- commands --------------------------------------------------------------------------------


def test_the_ui_scale_is_kept_and_read_back(session):
    assert session.ui_scale == 1.0
    session.set_ui_scale(1.1000000001)
    assert session.ui_scale == 1.1
    assert session.config.config.to_dict()["ui_scale"] == 1.1


@pytest.mark.parametrize("bad", [0.6, 2.1])
def test_an_out_of_range_ui_scale_is_refused(session, bad):
    with pytest.raises(ValueError):
        session.set_ui_scale(bad)
    assert session.ui_scale == 1.0


def test_the_menu_bar_choice_is_kept(session):
    assert session.menu_bar_shown is False
    session.set_menu_bar_shown(True)
    assert session.menu_bar_shown is True
    assert session.config.get("menu_bar_shown") is True


def test_the_dark_theme_toggle_publishes_the_settings(session):
    session.recorder.clear()
    session.set_ui_theme("dark")
    assert session.recorder.last(SettingsState).values.ui_theme == "dark"
    assert session.settings_values().ui_theme == "dark"
    with pytest.raises(ValueError):
        session.set_ui_theme("purple")


def test_the_chrome_commands_are_on_the_bridge():
    assert SESSION_COMMANDS["set_ui_scale"] == {"scale": "float"}
    assert SESSION_COMMANDS["set_menu_bar_shown"] == {"shown": "bool"}
    assert SESSION_COMMANDS["set_ui_theme"] == {"theme": "str"}


# -- Q9: a refused edit says so ---------------------------------------------------------------


def test_a_refused_edit_is_an_event_with_the_message():
    env = Env("C G Am F")
    env.play()
    env.session.transpose(2, None)
    assert env.recorder.items == [EditRefused(formatting.EDIT_REFUSED_MESSAGE)]
    assert env.session.text == "C G Am F"
    name, payload = encode(env.recorder.items[0])
    assert (name, json.loads(payload)) == ("EditRefused", {"message": formatting.EDIT_REFUSED_MESSAGE})


def test_edits_while_idle_are_not_refused():
    env = Env("C G Am F")
    env.session.transpose(2, None)
    assert env.recorder.of_type(EditRefused) == []


# -- texts the desktop front ends share --------------------------------------------------------


def test_the_tk_window_uses_the_shared_texts():
    pytest.importorskip("tkinter")
    from chordnotepad.session.events import PickMode
    from chordnotepad_tk import main_window

    assert main_window._TEXT_FILE_TYPES == [("Text Files", "*.txt"), ("All Files", "*.*")]
    assert main_window._PICKERS[PickMode.SAVE] == (
        "Save File As", ".txt", [("Text Files", "*.txt"), ("All Files", "*.*")])
    assert main_window._PICKERS[PickMode.EXPORT_MIDI] == (
        "Export MIDI", ".mid", [("MIDI files", "*.mid"), ("All files", "*.*")])


def test_the_notation_texts():
    assert toolbar_texts.AMERICAN_TOOLTIP == "American notation (C, D, E...)"
    assert toolbar_texts.EUROPEAN_TOOLTIP == "European notation (Do, Re, Mi...)"
    assert "European" in toolbar_texts.convert_tooltip("european")
    assert "American" in toolbar_texts.convert_tooltip("american")
    assert formatting.confirm_replace_message("a.txt") == (
        "a.txt already exists.\nDo you want to replace it?")
