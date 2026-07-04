"""Headless tests for MainWindow's Settings-dialog apply wiring.

MainWindow is a tk.Tk subclass, so it is never instantiated here -- these
tests call MainWindow._on_options_apply / MainWindow.rebuild_voicing_menu as
plain functions against a lightweight stub standing in for `self`, with all
Tk-touching collaborators (viewmodel, voicing_var, voicing_menu,
application.config_service) replaced by Mocks. No Tkinter widget is ever
constructed.
"""

from unittest.mock import ANY, Mock

from ui.main_window import MainWindow
from viewmodels.settings_viewmodel import SettingsChanges


def _make_stub(voicing_selection: str = "piano", voicings: dict = None):
    """Build a minimal stand-in for `self` with the attributes MainWindow's
    apply-wiring and menu-rebuild methods touch.
    """
    stub = Mock()
    stub.viewmodel.get_voicings.return_value = voicings or {}
    stub.voicing_var.get.return_value = voicing_selection
    stub.voicing_menu = Mock()
    return stub


class TestOnOptionsApplyFontChanged:
    """SettingsChanges(font_changed=True) should only push font values."""

    def test_pushes_family_and_size_through_viewmodel(self):
        stub = _make_stub()
        stub.application.config_service.get.side_effect = lambda key, default=None: {
            "font_family": "Consolas",
            "font_size": 16,
        }.get(key, default)

        changes = SettingsChanges(font_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.viewmodel.set_font_family.assert_called_once_with("Consolas")
        stub.viewmodel.set_font_size.assert_called_once_with(16)

    def test_does_not_touch_voicing_menu_or_selection(self):
        stub = _make_stub()
        stub.application.config_service.get.side_effect = lambda key, default=None: default

        changes = SettingsChanges(font_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.rebuild_voicing_menu.assert_not_called()
        stub.voicing_var.set.assert_not_called()
        stub.on_voicing_change.assert_not_called()

    def test_no_flags_set_is_a_no_op(self):
        stub = _make_stub()

        changes = SettingsChanges()
        MainWindow._on_options_apply(stub, changes)

        stub.viewmodel.set_font_family.assert_not_called()
        stub.viewmodel.set_font_size.assert_not_called()
        stub.rebuild_voicing_menu.assert_not_called()
        stub.voicing_var.set.assert_not_called()
        stub.on_voicing_change.assert_not_called()


class TestOnOptionsApplyVoicingsChanged:
    """SettingsChanges(voicings_changed=True) should rebuild the menu."""

    def test_rebuilds_menu(self):
        stub = _make_stub(voicing_selection="piano")

        changes = SettingsChanges(voicings_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.rebuild_voicing_menu.assert_called_once_with()

    def test_does_not_replay_selection_for_builtin_voicing(self):
        stub = _make_stub(voicing_selection="piano")

        changes = SettingsChanges(voicings_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.on_voicing_change.assert_not_called()

    def test_replays_selection_when_active_voicing_is_custom(self):
        """An edited custom voicing definition takes effect immediately."""
        stub = _make_stub(voicing_selection="voicing:MyGuitar")

        changes = SettingsChanges(voicings_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.on_voicing_change.assert_called_once_with()

    def test_font_untouched_when_only_voicings_changed(self):
        stub = _make_stub()

        changes = SettingsChanges(voicings_changed=True)
        MainWindow._on_options_apply(stub, changes)

        stub.viewmodel.set_font_family.assert_not_called()
        stub.viewmodel.set_font_size.assert_not_called()


class TestOnOptionsApplyNewActiveVoicing:
    """new_active_voicing should update the menu selection and re-voice."""

    def test_updates_selection_and_triggers_voicing_change(self):
        stub = _make_stub(voicing_selection="voicing:OldName")

        changes = SettingsChanges(new_active_voicing="voicing:NewName")
        MainWindow._on_options_apply(stub, changes)

        stub.voicing_var.set.assert_called_once_with("voicing:NewName")
        stub.on_voicing_change.assert_called_once_with()

    def test_combined_with_voicings_changed_does_not_double_invoke(self):
        """rebuild + rename in one commit: on_voicing_change fires once."""
        stub = _make_stub(voicing_selection="voicing:OldName")

        changes = SettingsChanges(voicings_changed=True, new_active_voicing="voicing:NewName")
        MainWindow._on_options_apply(stub, changes)

        stub.rebuild_voicing_menu.assert_called_once_with()
        stub.voicing_var.set.assert_called_once_with("voicing:NewName")
        stub.on_voicing_change.assert_called_once_with()

    def test_reset_to_piano_when_active_voicing_deleted(self):
        stub = _make_stub(voicing_selection="voicing:Deleted")

        changes = SettingsChanges(voicings_changed=True, new_active_voicing="piano")
        MainWindow._on_options_apply(stub, changes)

        stub.voicing_var.set.assert_called_once_with("piano")
        stub.on_voicing_change.assert_called_once_with()


class TestRebuildVoicingMenu:
    """rebuild_voicing_menu clears and repopulates the Voicing submenu."""

    def test_clears_existing_entries_first(self):
        stub = _make_stub()

        MainWindow.rebuild_voicing_menu(stub)

        stub.voicing_menu.delete.assert_called_once_with(0, ANY)

    def test_always_adds_piano_entry(self):
        stub = _make_stub()

        MainWindow.rebuild_voicing_menu(stub)

        labels = [call.kwargs.get("label") for call in stub.voicing_menu.add_radiobutton.call_args_list]
        assert "Piano" in labels

    def test_includes_custom_voicings_from_viewmodel(self):
        stub = _make_stub(voicings={"MyGuitar": {"model": "fretboard"}})

        MainWindow.rebuild_voicing_menu(stub)

        labels = [call.kwargs.get("label") for call in stub.voicing_menu.add_radiobutton.call_args_list]
        values = [call.kwargs.get("value") for call in stub.voicing_menu.add_radiobutton.call_args_list]
        assert "MyGuitar" in labels
        assert "voicing:MyGuitar" in values

    def test_omits_custom_voicings_separator_when_registry_empty(self):
        stub = _make_stub(voicings={})

        MainWindow.rebuild_voicing_menu(stub)

        values = [call.kwargs.get("value") for call in stub.voicing_menu.add_radiobutton.call_args_list]
        assert not any(v.startswith("voicing:") for v in values)
