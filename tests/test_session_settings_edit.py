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
    default_bpm = services.config.config.bpm
    session.set_bpm(90)          # the document's tempo, not the default
    session.step_font_size(2)
    values = recorder.last(SettingsState).values
    assert values.bpm == default_bpm and values.font_size == services.config.config.font_size
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
    # The spec would only repeat the field's error: no form error while it stands.
    assert state.form_errors == () and state.invalid == ("Bass",)
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
    # The old bottom voice gets a gap to the new one; the new one has none.
    assert [v["gap"] for v in editor(recorder).values["voices"]] == ["19", "12", ""]
    session.move_voicing_record(2, -1)
    assert [v["name"] for v in editor(recorder).values["voices"]] == \
        ["Voice 1", "Voice 3", "Voice 2"]
    assert [v["gap"] for v in editor(recorder).values["voices"]] == ["19", "12", "12"]
    data = session._settings_edit.model.get_voicings()["New voicing"]
    assert data["max_spacing"] == [19, 12]
    session.move_voicing_record(0, -1)                          # already the top: no-op
    assert [v["name"] for v in editor(recorder).values["voices"]] == \
        ["Voice 1", "Voice 3", "Voice 2"]
    session.remove_voicing_record(0)
    assert [v["name"] for v in editor(recorder).values["voices"]] == ["Voice 3", "Voice 2"]
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
    session.step_font_size(2)                                  # after the edit began
    size = services.config.config.font_size
    session.save_settings(None)
    assert services.config.config.font_size == size


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
    assert android["help"]["name"] == "The name of this voicing, shown in the player's Voicing sheet."
    assert android["forms"] == event.schema["forms"]


# -- autosave (Android) ----------------------------------------------------------


def config_writes(services, monkeypatch):
    """Count the config writes from now on."""
    writes = []
    save = services.config.save_config
    monkeypatch.setattr(services.config, "save_config", lambda *a: (writes.append(1), save(*a)))
    return writes


def test_commit_saves_and_applies_and_keeps_the_edit_open(tmp_path, monkeypatch):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.set_voicing("voicing:Bass")
    session.begin_settings_edit()
    writes = config_writes(services, monkeypatch)
    values = recorder.last(SettingsState).values
    session.commit_settings(dataclasses.replace(values, font_size=19))
    config = services.config.config
    assert config.font_size == 19 and len(writes) == 1
    assert recorder.last(EditorState).font_size == 19
    assert recorder.last(SettingsState).values.font_size == 19
    assert editor(recorder).active

    session.select_voicing("Bass")
    session.set_voicing_values({"max_fret": "15"})
    session.commit_settings(None)
    assert config.voicings["Bass"]["max_fret"] == 15 and config.font_size == 19
    saved = json.loads(services.appdata.get_config_file_path().read_text())
    assert saved["voicings"]["Bass"]["max_fret"] == 15
    state = editor(recorder)
    assert state.active and state.selected == "Bass" and state.values["max_fret"] == "15"

    # Nothing new: nothing written.
    session.commit_settings(None)
    session.commit_settings(dataclasses.replace(values, font_size=19))
    assert len(writes) == 2


def test_commit_keeps_the_last_valid_voicings_but_saves_the_other_settings(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"max_fret": "15"})
    session.commit_settings(None)
    session.set_voicing_values({"relaxed_span": "1"})          # below max_span: invalid
    errors = len(recorder.of_type(UserError))
    session.commit_settings(None)
    config = services.config.config
    span = config.voicings["Bass"]["relaxed_span"]
    assert span != 1 and config.voicings["Bass"]["max_fret"] == 15
    assert len(recorder.of_type(UserError)) == errors           # no dialog per keystroke
    state = editor(recorder)
    assert state.active and state.invalid == ("Bass",) and state.form_errors

    values = recorder.last(SettingsState).values
    session.commit_settings(dataclasses.replace(values, bpm=96))
    assert config.bpm == 96 and config.voicings["Bass"]["relaxed_span"] == span

    # Fixed: the voicing goes out with the values the edit has.
    session.set_voicing_values({"relaxed_span": str(span + 1)})
    session.commit_settings(None)
    assert config.voicings["Bass"]["relaxed_span"] == span + 1 and config.bpm == 96

    # Leaving with an invalid voicing drops only that edit.
    session.set_voicing_values({"max_fret": "x"})
    session.commit_settings(None)
    session.cancel_settings_edit()
    assert config.voicings["Bass"]["max_fret"] == 15 and config.bpm == 96


def test_commits_follow_the_voicing_in_use_through_renames_and_removal(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.set_voicing("voicing:Bass")
    session.begin_settings_edit()
    session.select_voicing("Bass")
    config = services.config.config
    for new in ("Bass 4", "Bass 5"):                           # each rename saved
        session.rename_voicing(editor(recorder).selected, new)
        session.commit_settings(None)
        assert set(config.voicings) == {new} and config.voicing == f"voicing:{new}"
        assert recorder.last(VoicingMenuState).selected == f"voicing:{new}"
    session.add_voicing()
    session.commit_settings(None)
    assert set(config.voicings) == {"Bass 5", "New voicing"}
    session.remove_voicing("Bass 5")
    session.commit_settings(None)
    assert set(config.voicings) == {"New voicing"} and config.voicing == "piano"
    assert editor(recorder).active


def test_commit_needs_an_edit_and_values_in_range(tmp_path):
    session, services, recorder = make(tmp_path)
    with pytest.raises(RuntimeError):
        session.commit_settings(None)
    session.begin_settings_edit()
    values = recorder.last(SettingsState).values
    with pytest.raises(ValueError):
        session.commit_settings(dataclasses.replace(values, bpm=5))
    assert services.config.config.bpm == values.bpm


def test_commit_that_cant_write_is_a_user_error_and_the_edit_stays(tmp_path, monkeypatch):
    from exceptions import ConfigurationError

    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()

    def fail(*_):
        raise ConfigurationError("disk full")

    monkeypatch.setattr(services.config, "save_config", fail)
    values = recorder.last(SettingsState).values
    session.commit_settings(dataclasses.replace(values, max_recent_files=3))
    assert recorder.last(UserError).title == "Settings"
    assert editor(recorder).active


# -- field by field, and the staging file (Android) -------------------------------


def staging_file(services):
    config = services.appdata.get_config_file_path()
    return config.with_name(f"{config.stem}-staged.json")


def test_a_wrong_field_keeps_its_saved_value_and_the_others_are_saved(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"tuning": "E1 X9 D2 G2", "max_fret": "15"})
    session.commit_settings(None)
    saved = services.config.config.voicings["Bass"]
    assert saved["tuning"] == BASS["tuning"] and saved["max_fret"] == 15
    state = editor(recorder)
    assert state.invalid == ("Bass",)
    assert state.values["tuning"] == "E1 X9 D2 G2"            # the form keeps the typing
    assert [p.field_id for p in state.problems] == ["tuning"]
    assert state.problems[0].text == (
        "Voicing 'Bass', Strings: E1 X9 D2 G2. X9 isn't a note name. Use note names or "
        "MIDI numbers, e.g. E2 A2 D3 G3 B3 E4, 3 to 12 strings.")
    assert len(recorder.of_type(UserError)) == 0


def test_a_new_voicing_takes_the_default_for_a_wrong_field(tmp_path):
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    session.add_voicing()
    session.set_voicing_values({"max_fret": "abc", "fingers": "3"})
    session.commit_settings(None)
    saved = services.config.config.voicings["New voicing"]
    assert saved["max_fret"] == 12 and saved["fingers"] == 3
    assert editor(recorder).problems[0].text == (
        "Voicing 'New voicing', Max fret: abc. abc isn't a whole number. "
        "Enter a whole number from 5 to 24.")


def test_a_rule_across_fields_blames_the_field_just_edited(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"max_fret": "15"})
    session.set_voicing_values({"relaxed_span": "1"})          # below max span (4)
    session.commit_settings(None)
    saved = services.config.config.voicings["Bass"]
    assert saved["max_fret"] == 15 and saved.get("relaxed_span", 5) == 5
    state = editor(recorder)
    assert state.field_errors["relaxed_span"].startswith("Relaxed span (1) must be >= Max span (4)")
    assert [p.field_id for p in state.problems] == ["relaxed_span"]

    # Too few strings: the strings are blamed, not the fret just saved.
    session.set_voicing_values({"relaxed_span": "5"})
    session.set_voicing_values({"tuning": "E1 A1"})
    session.commit_settings(None)
    assert services.config.config.voicings["Bass"]["tuning"] == BASS["tuning"]
    text = editor(recorder).problems[0].text
    assert text.startswith("Voicing 'Bass', Strings: E1 A1. Must have between 3 and 12 strings")


def test_an_ensemble_cell_falls_back_cell_by_cell(tmp_path):
    session, services, recorder = make(tmp_path)
    session.begin_settings_edit()
    session.add_voicing()
    session.set_voicing_model("ensemble")
    session.commit_settings(None)
    voices = [{"name": "Top", "low": "H9", "high": "C5", "staff": None},
              {"name": "Low", "low": "C3", "high": "C4", "staff": None}]
    session.set_voicing_values({"voices": voices})
    session.commit_settings(None)
    saved = services.config.config.voicings["New voicing"]["voices"]
    assert [v["name"] for v in saved] == ["Top", "Low"]       # the names are saved
    assert saved[0]["range"][0] == 60                         # the bad low stays C4
    problem = editor(recorder).problems[0]
    assert problem.field_id == "voice:0:low"
    assert problem.text.startswith("Voicing 'New voicing', Voice 1, Low: H9. H9 isn't a note name.")


def test_wrong_values_are_staged_and_come_back_next_time(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"tuning": "E1 X9 D2 G2"})
    session.commit_settings(None, invalid_numbers={"font_size": "999"})
    staged = json.loads(staging_file(services).read_text())
    assert staged["numbers"] == {"font_size": "999"}
    assert staged["voicings"]["Bass"]["tuning"] == "E1 X9 D2 G2"
    assert services.config.config.voicings["Bass"]["tuning"] == BASS["tuning"]
    assert editor(recorder).staged_numbers == {"font_size": "999"}
    assert not editor(recorder).restored

    # The app goes away without leaving Settings: a new session finds them.
    session2, services2, recorder2 = make(tmp_path)
    assert services2.config.config.voicings["Bass"]["tuning"] == BASS["tuning"]
    session2.begin_settings_edit()
    state = editor(recorder2)
    assert state.restored and state.invalid == ("Bass",)
    assert state.staged_numbers == {"font_size": "999"}
    session2.select_voicing("Bass")
    assert editor(recorder2).values["tuning"] == "E1 X9 D2 G2"
    assert editor(recorder2).field_errors["tuning"]

    # Fixed: saved, nothing staged any more.
    session2.set_voicing_values({"tuning": "E1 A1 D2 G2 C3"})
    session2.commit_settings(None, invalid_numbers={})
    assert services2.config.config.voicings["Bass"]["tuning"] == [28, 33, 38, 43, 48]
    assert not staging_file(services2).exists()
    assert not editor(recorder2).restored and editor(recorder2).problems == ()


def test_a_staged_voicing_that_is_gone_is_dropped(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    staging_file(services).write_text(json.dumps({
        "version": 1,
        "voicings": {"Gone": {"model": "fretboard", "tuning": "X1"},
                     "Bass": dict(BASS, max_fret="abc")},
        "numbers": {"bpm": "5", "nope": "1"}}))
    session.begin_settings_edit()
    state = editor(recorder)
    assert state.restored and "Gone" not in [n for g in state.groups for n in g.names]
    assert [(p.voicing, p.field_id) for p in state.problems] == [("Bass", "max_fret")]
    assert state.staged_numbers == {"bpm": "5"}
    staged = json.loads(staging_file(services).read_text())
    assert set(staged["voicings"]) == {"Bass"} and staged["numbers"] == {"bpm": "5"}


def test_a_damaged_staging_file_is_ignored(tmp_path):
    session, services, recorder = make(tmp_path)
    staging_file(services).write_text("{not json")
    session.begin_settings_edit()
    assert editor(recorder).active and not editor(recorder).restored


def test_discard_drops_the_wrong_values_and_the_staging_file(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"max_fret": "15"})
    session.set_voicing_values({"tuning": "E1 X9"})
    session.commit_settings(None, invalid_numbers={"bpm": "1000"})
    assert staging_file(services).exists()
    session.discard_settings_problems()
    state = editor(recorder)
    assert state.active and state.problems == () and state.staged_numbers == {}
    assert state.values["tuning"] == "E1 A1 D2 G2" and state.values["max_fret"] == "15"
    assert not staging_file(services).exists()
    assert services.config.config.voicings["Bass"]["max_fret"] == 15

    # Leaving drops them too.
    session.set_voicing_values({"tuning": "E1 X9"})
    session.commit_settings(None)
    assert staging_file(services).exists()
    session.cancel_settings_edit()
    assert not staging_file(services).exists()


def test_commit_rejects_unknown_number_settings(tmp_path):
    session, _, _ = make(tmp_path)
    session.begin_settings_edit()
    with pytest.raises(ValueError):
        session.commit_settings(None, invalid_numbers={"volume": "11"})


def test_problem_texts_give_the_syntax_or_range():
    from settings_forms.voicing_autosave import plan_voicing, problem_text

    values = voicing_form.default_values("piano")
    values.update({"range:lh_range:low": "C9", "rh_center": "x"})
    plan = plan_voicing("P", "piano", values, None, None, ["range:lh_range:low"])
    texts = [problem_text("P", "piano", p, values) for p in plan.problems]
    assert texts == [
        "Voicing 'P', Left hand low: C9. Left hand must have low < high, got 120 >= 48. "
        "Use a note name or a MIDI number, e.g. C4 or 60.",
        "Voicing 'P', RH center: x. x isn't a number. Enter a number from 0 to 127.",
    ]
    assert plan.data["lh_range"] == [24, 48] and plan.data["rh_center"] == 63.0

    spacing = voicing_form.default_values("ensemble")
    spacing["voices"][0]["gap"] = "y"
    plan = plan_voicing("E", "ensemble", spacing, None, None)
    assert problem_text("E", "ensemble", plan.problems[0], spacing) == (
        "Voicing 'E', Voice 1, Max gap to next voice: y. y isn't a whole number. "
        "Enter a whole number from 1 to 127.")
    assert plan.data["max_spacing"] == [19]                     # the default kept
    spacing["voices"][0]["gap"] = "0"
    plan = plan_voicing("E", "ensemble", spacing, None, None)
    assert problem_text("E", "ensemble", plan.problems[0], spacing) == (
        "Voicing 'E', Voice 1, Max gap to next voice: 0. 0 is out of range. "
        "Enter a whole number from 1 to 127.")


def test_renaming_a_voicing_with_a_wrong_field_keeps_its_saved_values(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    session.set_voicing("voicing:Bass")
    session.begin_settings_edit()
    session.select_voicing("Bass")
    session.set_voicing_values({"tuning": "E1 X9"})
    session.commit_settings(None)
    session.rename_voicing("Bass", "Bass 4")
    session.commit_settings(None)
    config = services.config.config
    assert set(config.voicings) == {"Bass 4"} and config.voicing == "voicing:Bass 4"
    assert config.voicings["Bass 4"]["tuning"] == BASS["tuning"]
    assert [p.voicing for p in editor(recorder).problems] == ["Bass 4"]
    staged = json.loads(staging_file(services).read_text())
    assert set(staged["voicings"]) == {"Bass 4"}


def test_each_blamed_field_gets_the_rule_it_breaks():
    from settings_forms.voicing_autosave import plan_voicing

    values = voicing_form.values_from_voicing("fretboard", BASS)
    values.update({"max_fret": "30", "relaxed_span": "1"})        # two rules
    plan = plan_voicing("Bass", "fretboard", values, None, BASS, ["max_fret", "relaxed_span"])
    assert {p.field_id: p.message.split(" must")[0] for p in plan.problems} == {
        "max_fret": "Max fret", "relaxed_span": "Relaxed span (1)"}

    voices = voicing_form.default_values("ensemble")
    voices["voices"][0].update(low="C5", high="C4")                # low and high swapped
    plan = plan_voicing("E", "ensemble", voices, None, None, ["voices"])
    assert [p.field_id for p in plan.problems] == ["voice:0:low", "voice:0:high"]
    assert all(p.message.endswith("got 72 >= 60.") for p in plan.problems)
    assert plan.data["voices"][0]["range"] == [60, 72]


# -- note names in the Settings notation ---------------------------------------------------


def test_note_names_parse_in_either_notation_and_show_in_the_one_asked():
    assert voicing_form.parse_pitch_token("Do4") == 60
    assert voicing_form.parse_pitch_token("sol#3") == 56
    assert voicing_form.parse_pitch_token("Sib2") == 46
    assert voicing_form.parse_pitch_token("E2") == 40
    assert voicing_form.parse_pitch_token("Re") is None
    assert voicing_form.pitch_to_text(61, "european") == "Do#4"
    assert voicing_form.pitch_to_text("C4", "european") == "Do4"     # a stored name
    assert voicing_form.pitch_to_text("H9", "european") == "H9"      # being typed
    guitar = {"model": "fretboard", "tuning": [40, 45, 50, 55, 59, 64]}
    assert voicing_form.values_from_voicing("fretboard", guitar, "european")["tuning"] == (
        "Mi2 La2 Re3 Sol3 Si3 Mi4")
    assert voicing_form.voicing_from_values(
        "fretboard", {"tuning": "Mi2 La2 Re3 Sol3 Si3 Mi4"})["tuning"] == guitar["tuning"]
    tuning = voicing_form.iter_fields(voicing_form.form_schema("fretboard"))[0]
    assert voicing_form.field_hint(tuning, {}, "european") == (
        "(note names or MIDI numbers, e.g. Mi2 La2 Re3 Sol3 Si3 Mi4)")


def test_the_voicing_form_follows_the_settings_notation(tmp_path):
    session, services, recorder = make(tmp_path, voicings={"Bass": BASS})
    services.config.config.notation = "european"
    session.set_notation("american")                       # the song's: Settings ignores it
    session.begin_settings_edit()
    session.select_voicing("Bass")
    state = editor(recorder)
    assert state.values["tuning"] == "Mi1 La1 Re2 Sol2"
    assert "Mi2 La2 Re3" in state.hints["tuning"]

    # Typed in either spelling, stored as MIDI.
    session.set_voicing_values({"tuning": "Mi1 La1 D2 Sol2 Do3"})
    session.commit_settings(None)
    assert services.config.config.voicings["Bass"]["tuning"] == [28, 33, 38, 43, 48]

    # A wrong value is worded in the Settings notation.
    session.set_voicing_values({"tuning": "Mi1 X9"})
    session.commit_settings(None)
    assert editor(recorder).problems[0].text.endswith(
        "Use note names or MIDI numbers, e.g. Mi2 La2 Re3 Sol3 Si3 Mi4, 3 to 12 strings.")

    # Switching the Settings notation respells the form at once (the typing stays).
    session.set_voicing_values({"tuning": "Mi1 La1 Re2 Sol2 Do3"})
    values = dataclasses.replace(session.settings_values(), notation="american")
    session.commit_settings(values)
    state = editor(recorder)
    assert state.values["tuning"] == "E1 A1 D2 G2 C3"
    assert "E2 A2 D3" in state.hints["tuning"]
    assert services.config.config.notation == "american"


def test_an_ensemble_cell_and_a_piano_range_in_european(tmp_path):
    session, services, recorder = make(tmp_path)
    services.config.config.notation = "european"
    session.begin_settings_edit()
    session.add_voicing()
    session.set_voicing_model("ensemble")
    voices = editor(recorder).values["voices"]
    assert (voices[0]["low"], voices[0]["high"]) == ("Do4", "Do5")
    session.add_voicing_record()
    assert editor(recorder).values["voices"][2]["low"] == "Do3"
    session.set_voicing_values({"voices": [dict(voices[0], low="H9"), voices[1]]})
    session.commit_settings(None)
    assert "e.g. Do4 or 60." in editor(recorder).problems[0].text

    session.set_voicing_model("piano")
    assert editor(recorder).values["range:lh_range:low"] == "Do1"
