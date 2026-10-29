"""The Settings screen through the session: SettingsState and the voicings editor.

The working copy mirrors the desktop dialog (a SettingsViewModel); the
voicing form goes through settings_forms.voicing_form like the Tk page.
"""

import dataclasses
import json

import pytest

from services.appdata_service import AppDataService
from session.bootstrap import build_core_services, create_session
from session.events import UserError
from session.host import HostDispatch
from session.settings import SettingsValues
from session.state import (
    INACTIVE_VOICING_EDITOR, EditorState, SettingsState, VoicingEditorState, VoicingMenuState,
)
from session.testing import EventRecorder, FakePlayer, InMemoryDocumentStore, ManualHost
from settings_forms import voicing_form


def make(tmp_path, voicings=None):
    if voicings is not None:
        config_dir = tmp_path / "config" / "chord-notepad"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps({"voicings": voicings}))
    host = ManualHost()
    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(host),
                                   player=FakePlayer())
    session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False)
    recorder = EventRecorder()
    session.subscribe(recorder)
    session.start()
    return session, services, recorder


def editor(recorder) -> VoicingEditorState:
    return recorder.last(VoicingEditorState)


BASS = {"model": "fretboard", "tuning": [28, 33, 38, 43], "label": "My Bass"}


# -- SettingsState ---------------------------------------------------------------


def test_settings_state_from_the_start_and_after_every_config_write(tmp_path):
    session, services, recorder = make(tmp_path)
    state = recorder.last(SettingsState)
    assert state.values == SettingsValues.read(services.config.config)
    assert state.american_keys[0] == "C" and state.european_keys[0] == "Do"
    assert (state.font_size_min, state.font_size_max) == (6, 72)
    assert (state.bpm_min, state.bpm_max, state.max_recent_files_max) == (20, 400, 50)
    assert state.time_signature_units == (1, 2, 4, 8, 16)
    assert state.values.show_quick_start_on_startup is True

    session.set_show_quick_start_on_startup(False)
    assert recorder.last(SettingsState).values.show_quick_start_on_startup is False
    session.set_bpm(90)
    session.step_font_size(2)
    values = recorder.last(SettingsState).values
    assert values.bpm == 90 and values.font_size == services.config.config.font_size
    # An unchanged config publishes nothing.
    count = len(recorder.of_type(SettingsState))
    session.set_text("C G")
    assert len(recorder.of_type(SettingsState)) == count


def test_apply_settings_publishes_the_new_values(tmp_path):
    session, _, recorder = make(tmp_path)
    values = recorder.last(SettingsState).values
    session.apply_settings(dataclasses.replace(values, max_recent_files=4, key="G"))
    assert recorder.last(SettingsState).values.max_recent_files == 4
    assert recorder.last(SettingsState).values.key == "G"


# -- the voicings editor ---------------------------------------------------------


def test_editor_is_inactive_until_begun_and_after_cancel(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    assert editor(recorder) == INACTIVE_VOICING_EDITOR
    with pytest.raises(RuntimeError):
        session.add_voicing()
    session.begin_settings_edit()
    state = editor(recorder)
    assert state.active and state.selected is None and state.values == {}
    assert [(g.model, g.names) for g in state.groups] == [
        ("fretboard", ("Bass",)), ("piano", ()), ("ensemble", ())]
    assert state.presets[0].group == "fretboard"
    assert state.presets[-1].label == "Bass" and state.presets[-1].group == "custom"
    session.add_voicing()
    session.cancel_settings_edit()
    assert editor(recorder) == INACTIVE_VOICING_EDITOR
    assert set(services.config.config.voicings) == {"Bass"}


def test_select_edit_and_validate_like_the_desktop_page(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    state = editor(recorder)
    assert state.model == "fretboard" and not state.dirty
    assert state.values == voicing_form.values_from_voicing("fretboard", BASS)
    assert state.field_errors == {} and state.form_errors == ()
    assert state.hints["tuning"].startswith("(note names")

    # A partial edit: only the changed field; the rest stays.
    session.set_voicing_values({"max_fret": "abc", "tuning": "E1 A1 D2 G2"})
    state = editor(recorder)
    assert state.dirty and state.values["tuning"] == "E1 A1 D2 G2"
    assert state.field_errors == {"max_fret": "Must be a whole number"}
    assert state.form_errors and state.invalid == ("Bass",)
    session.set_voicing_values({"max_fret": "15"})
    state = editor(recorder)
    assert state.field_errors == {} and state.form_errors == () and state.invalid == ()
    # The working copy holds the parsed voicing, the label carried over.
    data = session._settings_edit.model.get_voicings()["Bass"]
    assert data["max_fret"] == 15 and data["tuning"] == [28, 33, 38, 43]
    assert data["label"] == "My Bass"
    assert services.config.config.voicings["Bass"] == BASS        # not saved yet

    with pytest.raises(ValueError):
        session.select_voicing("Nope")


def test_add_rename_remove_and_the_rename_error(tmp_path):
    session, _, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.add_voicing()
    assert editor(recorder).selected == "New voicing"
    session.add_voicing()
    assert editor(recorder).selected == "New voicing 2"
    session.rename_voicing("New voicing 2", "  Uke ")
    state = editor(recorder)
    assert state.selected == "Uke" and "Uke" in state.groups[0].names
    revision = state.revision
    session.rename_voicing("Uke", "Bass")
    error = recorder.last(UserError)
    assert error.title == "Rename Voicing" and "already exists" in error.message
    assert editor(recorder).selected == "Uke" and editor(recorder).revision == revision + 1
    session.remove_voicing("Uke")
    state = editor(recorder)
    assert state.selected is None and state.groups[0].names == ("Bass", "New voicing")


def test_model_switch_records_and_presets(tmp_path):
    session, _, recorder = make(tmp_path)
    session.begin_settings_edit()
    session.add_voicing()
    session.set_voicing_model("ensemble")
    state = editor(recorder)
    assert state.model == "ensemble" and len(state.values["voices"]) == 2
    assert state.values == voicing_form.default_values("ensemble")
    assert state.groups[2].names == ("New voicing",)
    session.add_voicing_record()
    assert len(editor(recorder).values["voices"]) == 3
    assert editor(recorder).hints["max_spacing"] == "(comma-separated, 2 values expected)"
    session.remove_voicing_record(0)
    assert [v["name"] for v in editor(recorder).values["voices"]] == ["Voice 2", "Voice 3"]
    with pytest.raises(ValueError):
        session.set_voicing_model("harp")

    satb = next(p for p in editor(recorder).presets if p.group == "ensemble")
    session.load_voicing_preset(satb.group, satb.label)
    state = editor(recorder)
    assert len(state.values["voices"]) == 4 and state.form_errors == ()
    data = session._settings_edit.model.get_voicings()["New voicing"]
    assert data.get("label") == satb.label
    with pytest.raises(ValueError):
        session.load_voicing_preset("ensemble", "Nope")


def test_save_is_gated_by_every_voicing_then_commits_and_applies(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.set_voicing("voicing:Bass")
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"relaxed_span": "1"})          # below max_span: invalid
    session.add_voicing()                                      # select another one
    values = recorder.last(SettingsState).values
    session.save_settings(dataclasses.replace(values, font_size=19))
    error = recorder.last(UserError)
    assert error.title == "Invalid Voicing" and error.message.startswith("Bass: ")
    assert editor(recorder).selected == "Bass" and editor(recorder).active
    assert services.config.config.font_size != 19             # nothing written

    session.set_voicing_values({"relaxed_span": "5"})
    session.rename_voicing("Bass", "Bass 4")
    session.save_settings(dataclasses.replace(values, font_size=19))
    assert editor(recorder) == INACTIVE_VOICING_EDITOR
    config = services.config.config
    assert config.font_size == 19 and set(config.voicings) == {"Bass 4", "New voicing"}
    assert config.voicings["Bass 4"]["relaxed_span"] == 5
    # Applied like the dialog's Save: the menu, the voicing in use, the font.
    assert config.voicing == "voicing:Bass 4"
    assert recorder.last(VoicingMenuState).selected == "voicing:Bass 4"
    assert recorder.last(EditorState).font_size == 19
    assert recorder.last(SettingsState).values.font_size == 19
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert "Bass 4" in saved["voicings"]
    with pytest.raises(RuntimeError):
        session.save_settings(None)


def test_save_without_values_keeps_the_current_config_values(tmp_path):
    session, services, _ = make(tmp_path)
    session.begin_settings_edit()
    session.set_bpm(150)                                       # after the edit began
    session.save_settings(None)
    assert services.config.config.bpm == 150


def test_save_rejects_out_of_range_values(tmp_path):
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    values = recorder.last(SettingsState).values
    with pytest.raises(ValueError):
        session.save_settings(dataclasses.replace(values, bpm=5))
    assert editor(recorder).active


def test_editor_schema_event_per_platform(tmp_path):
    from session.events import VoicingEditorSchema

    session, _, recorder = make(tmp_path)
    session.request_voicing_editor_schema()
    event = recorder.last(VoicingEditorSchema)
    assert event.version == voicing_form.SCHEMA_VERSION
    assert event.schema == voicing_form.editor_schema()
    assert event.schema["help"]["name"] == (
        "The name of this voicing, shown in the Playback → Voicing menu.")
    android = voicing_form.editor_schema("android")
    assert android["help"]["name"] == "The name of this voicing, shown in ⋮ → Playback → Voicing."
    assert android["forms"] == event.schema["forms"]
