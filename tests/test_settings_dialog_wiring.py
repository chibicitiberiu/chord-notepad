"""Applying what the Settings dialog saved, and the menus it rebuilds.

The dialog commits its working copy to the config and hands the resulting
``SettingsChanges`` to ``AppSession.apply_settings``. The session re-applies
the font and the voicing in use and republishes the Voicing menu
(``VoicingMenuState``); the Tk window only rebuilds its menus from those
states. Session tests run on a ManualHost over the real viewmodel and
PlaybackService (with a silent FakePlayer); the two view tests call the Tk
window's menu builders unbound against stand-ins, so no widget is built.
"""

from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

import pytest

from services.playback_service import PlaybackService
from services.song_parser_service import SongParserService
from session import formatting
from session.host import HostDispatch
from session.session import AppSession
from session.state import (
    EditorState, InstrumentFamily, InstrumentMenuState, MenuItem, VoicingMenuState,
)
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from viewmodels.main_window_viewmodel import MainWindowViewModel
from viewmodels.settings_viewmodel import SettingsChanges
from viewmodels.text_editor_viewmodel import TextEditorViewModel


# A valid user fretboard voicing (standard tuning).
GUITAR = {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64]}


class FakeConfig:
    """Dict-backed stand-in for ConfigService (the dialog writes it directly)."""

    def __init__(self, **values):
        self.values = dict(values)

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class Env:
    """A started session; ``voicings_set`` counts re-applied voicings."""

    def __init__(self, voicing="piano", voicings=None, **config):
        self.host = ManualHost()
        dispatch = HostDispatch(self.host)
        self.config = FakeConfig(voicing=voicing, voicings=voicings or {}, **config)
        self.player = FakePlayer()
        self.audio = PlaybackService(self.config, player=self.player, application=dispatch)
        self.main = MainWindowViewModel(
            self.config, self.audio, InMemoryDocumentStore(), SongParserService(), dispatch)
        self.session = AppSession(
            self.host, main_window_viewmodel=self.main,
            text_editor_viewmodel=TextEditorViewModel(SongParserService()))
        self.recorder = EventRecorder()
        self.session.subscribe(self.recorder)
        self.session.start()
        self.recorder.clear()
        self.voicings_set = []
        self.main.observe("voicing", self.voicings_set.append)

    def commit(self, **config):
        """What SettingsViewModel.commit does to the config."""
        self.config.values.update(config)

    def voicing_menu(self) -> VoicingMenuState:
        return self.recorder.last(VoicingMenuState)


def _values(state: VoicingMenuState):
    return [item.value for group in state.groups for item in group]


# -- apply_settings: font --------------------------------------------------------------


class TestApplyFont:
    def test_pushes_family_and_size_to_the_editor(self):
        env = Env()
        env.commit(font_family="Consolas", font_size=16)
        env.session.apply_settings(SettingsChanges(font_changed=True))

        state = env.recorder.last(EditorState)
        assert (state.font_family, state.font_size) == ("Consolas", 16)
        assert (env.main.font_family, env.main.font_size) == ("Consolas", 16)

    def test_does_not_touch_the_voicing_menu_or_selection(self):
        env = Env(voicing="voicing:Mine", voicings={"Mine": GUITAR})
        env.commit(font_size=14)
        env.session.apply_settings(SettingsChanges(font_changed=True))

        assert env.recorder.of_type(VoicingMenuState) == []
        assert env.voicings_set == []

    def test_no_flags_set_is_a_no_op(self):
        env = Env(voicing="voicing:Mine", voicings={"Mine": GUITAR})
        env.commit(font_family="Consolas", font_size=16)
        env.session.apply_settings(SettingsChanges())

        assert env.recorder.items == []
        assert env.voicings_set == []
        assert env.main.font_family != "Consolas"

    def test_general_changes_are_left_for_the_next_start(self):
        # As before the session: the dialog saves them as defaults; the
        # running toolbar keeps its values.
        env = Env(bpm=120)
        env.commit(bpm=90, notation="european", key="G")
        env.session.apply_settings(SettingsChanges(general_changed=True, audio_changed=True))

        assert env.recorder.items == []
        assert env.main.bpm == 120
        assert env.main.notation.value == "american"


# -- apply_settings: voicings ------------------------------------------------------------


class TestApplyVoicingsChanged:
    def test_rebuilds_the_menu_from_the_new_registry(self):
        env = Env()
        env.commit(voicings={"MyGuitar": GUITAR})
        env.session.apply_settings(SettingsChanges(voicings_changed=True))

        assert "voicing:MyGuitar" in _values(env.voicing_menu())

    def test_does_not_reapply_a_builtin_voicing(self):
        env = Env(voicing="piano")
        env.commit(voicings={"MyGuitar": GUITAR})
        env.session.apply_settings(SettingsChanges(voicings_changed=True))

        assert env.voicings_set == []

    def test_reapplies_the_custom_voicing_in_use(self):
        """An edited custom voicing definition takes effect immediately."""
        env = Env(voicing="voicing:MyGuitar", voicings={"MyGuitar": GUITAR})
        env.commit(voicings={"MyGuitar": {**GUITAR, "tuning": [38, 45, 50, 55, 59, 64]}})
        env.session.apply_settings(SettingsChanges(voicings_changed=True))

        assert env.voicings_set == ["voicing:MyGuitar"]

    def test_font_untouched_when_only_voicings_changed(self):
        env = Env()
        env.commit(font_family="Consolas")
        env.session.apply_settings(SettingsChanges(voicings_changed=True))

        assert env.main.font_family != "Consolas"
        assert env.recorder.of_type(EditorState) == []


class TestApplyNewActiveVoicing:
    def test_switches_the_selection_and_reapplies(self):
        env = Env(voicing="voicing:OldName", voicings={"OldName": GUITAR})
        env.commit(voicing="voicing:NewName", voicings={"NewName": GUITAR})
        env.session.apply_settings(SettingsChanges(new_active_voicing="voicing:NewName"))

        assert env.voicings_set == ["voicing:NewName"]
        assert env.voicing_menu().selected == "voicing:NewName"

    def test_combined_with_voicings_changed_applies_once(self):
        """Rebuild + rename in one commit: the voicing is re-applied once."""
        env = Env(voicing="voicing:OldName", voicings={"OldName": GUITAR})
        env.commit(voicing="voicing:NewName", voicings={"NewName": GUITAR})
        env.session.apply_settings(SettingsChanges(
            voicings_changed=True, new_active_voicing="voicing:NewName"))

        assert env.voicings_set == ["voicing:NewName"]
        menu = env.voicing_menu()
        assert menu.selected == "voicing:NewName"
        assert "voicing:NewName" in _values(menu)
        assert "voicing:OldName" not in _values(menu)

    def test_reset_to_piano_when_the_voicing_in_use_was_deleted(self):
        env = Env(voicing="voicing:Deleted", voicings={"Deleted": GUITAR})
        env.commit(voicing="piano", voicings={})
        env.session.apply_settings(SettingsChanges(
            voicings_changed=True, new_active_voicing="piano"))

        assert env.voicings_set == ["piano"]
        menu = env.voicing_menu()
        assert menu.selected == "piano"
        assert not any(v.startswith("voicing:") for v in _values(menu))


# -- the menu models ---------------------------------------------------------------------


class TestVoicingMenuModel:
    def test_piano_first_then_fretboards_then_ensembles(self):
        groups = formatting.voicing_menu_groups({})
        assert [item.value for item in groups[0]] == ["piano"]
        assert [item.value for item in groups[1]] == [
            "guitar:standard", "guitar:drop_d", "guitar:dadgad", "guitar:open_g",
            "guitar:ukulele"]
        assert [item.value for item in groups[2]] == [
            "ensemble:satb", "ensemble:ttbb", "ensemble:ssa", "ensemble:quartet"]
        assert groups[0][0].label == "Piano"

    def test_omits_the_custom_group_when_the_registry_is_empty(self):
        assert len(formatting.voicing_menu_groups({})) == 3

    def test_custom_voicings_by_model_then_name(self):
        groups = formatting.voicing_menu_groups({
            "zeta": GUITAR, "Alpha": GUITAR,
            "choir": {"model": "ensemble"},
        })
        assert groups[3] == (
            MenuItem("choir", "voicing:choir"),
            MenuItem("Alpha", "voicing:Alpha"),
            MenuItem("zeta", "voicing:zeta"),
        )

    def test_set_voicing_takes_only_menu_values(self):
        env = Env()
        env.session.set_voicing("guitar:drop_d")
        assert env.voicing_menu().selected == "guitar:drop_d"
        assert env.config.get("voicing") == "guitar:drop_d"
        with pytest.raises(ValueError):
            env.session.set_voicing("voicing:Nope")

    def test_choosing_the_same_voicing_again_reapplies_it(self):
        env = Env(voicing="guitar:drop_d")
        env.session.set_voicing("guitar:drop_d")
        assert env.voicings_set == ["guitar:drop_d"]


class TestInstrumentMenuModel:
    def test_sixteen_general_midi_families_with_the_current_one_marked(self):
        families = formatting.instrument_families([(0, "Grand"), (25, "Steel")], 25)
        assert len(families) == 16
        assert families[0] == InstrumentFamily("Piano", False, (MenuItem("  0 - Grand", "0"),))
        assert families[3] == InstrumentFamily("Guitar", True, (MenuItem(" 25 - Steel", "25"),))
        assert families[1].items == ()

    def test_set_instrument_moves_the_mark(self):
        env = Env()
        env.player.get_available_instruments = lambda: [(0, "Grand"), (40, "Violin")]
        env.session.set_instrument(40)
        state = env.recorder.last(InstrumentMenuState)
        assert state.current == 40
        assert [f.name for f in state.families if f.is_current] == ["Strings"]
        assert env.player.instrument == 40
        assert env.config.get("instrument") == 40
        with pytest.raises(ValueError):
            env.session.set_instrument(128)


# -- the Tk menus are rebuilt from the states -----------------------------------------------


def test_tk_voicing_menu_is_rebuilt_from_the_state():
    from ui.main_window import MainWindow

    window = SimpleNamespace(voicing_menu=Mock(), voicing_var=Mock(), _voicing_groups=None,
                             on_voicing_change=Mock())
    groups = formatting.voicing_menu_groups({"MyGuitar": GUITAR})
    MainWindow.rebuild_voicing_menu(window, VoicingMenuState("voicing:MyGuitar", groups))

    window.voicing_menu.delete.assert_called_once_with(0, ANY)
    calls = window.voicing_menu.add_radiobutton.call_args_list
    assert [c.kwargs["label"] for c in calls][:2] == ["Piano", "Guitar (Standard - EADGBE)"]
    assert calls[-1].kwargs["value"] == "voicing:MyGuitar"
    assert window.voicing_menu.add_separator.call_count == 3
    window.voicing_var.set.assert_called_with("voicing:MyGuitar")

    # Only the selection moves while the choices stay the same.
    window.voicing_menu.reset_mock()
    MainWindow.rebuild_voicing_menu(window, VoicingMenuState("piano", groups))
    window.voicing_menu.delete.assert_not_called()
    window.voicing_var.set.assert_called_with("piano")


def test_tk_instrument_menu_is_rebuilt_from_the_state():
    from ui.main_window import MainWindow

    window = SimpleNamespace(instrument_menu=Mock(), instrument_var=Mock(),
                             _category_markers=("blank", "dot"),
                             on_instrument_change=Mock())
    window.instrument_menu.winfo_children.return_value = []
    state = InstrumentMenuState(25, formatting.instrument_families(
        [(0, "Grand"), (25, "Steel")], 25))
    submenus = []

    def make_menu(*args, **kwargs):
        submenus.append(Mock())
        return submenus[-1]

    with patch("ui.main_window.tk.Menu", side_effect=make_menu), \
            patch("ui.main_window.style_menu"):
        MainWindow.build_instrument_menu(window, state)

    window.instrument_menu.delete.assert_called_once_with(0, ANY)
    cascades = window.instrument_menu.add_cascade.call_args_list
    assert len(cascades) == 16
    assert [c.kwargs["image"] for c in cascades][:4] == ["blank", "blank", "blank", "dot"]
    guitar = submenus[3].add_radiobutton.call_args.kwargs
    assert (guitar["label"], guitar["value"]) == (" 25 - Steel", 25)
    window.instrument_var.set.assert_called_with(25)
