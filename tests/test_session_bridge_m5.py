"""The M5 screens over the bridge's strings: chord identifier, chord-sheet zoom.

Runs like Android runs (see ``test_session_bridge``): a ThreadedHost session
thread, only ``submit(command, args_json)`` in and ``(type_name, json)`` out.
"""

import pytest

from tests.test_session_bridge import BridgeEnv


@pytest.fixture
def env(tmp_path):
    e = BridgeEnv(tmp_path)
    yield e
    e.close()


def test_identifier_over_the_bridge(env):
    first = env.expect("IdentifierState")
    assert first == {"notes": [], "notes_text": "", "typed_text_error": None,
                     "candidates": [], "message": "Select notes to identify chords..."}
    env.send("identifier_toggle_note", note="A", octave=4)
    env.send("identifier_toggle_note", note="C", octave=5)
    env.send("identifier_toggle_note", note="E", octave=5)
    state = env.expect("IdentifierState", lambda d: len(d["notes"]) == 3)
    assert state["notes"][0] == {"name": "A", "octave": 4, "midi": 69}
    assert state["notes_text"] == "C E A" and "Am" in state["candidates"]
    assert env.player.immediate == [[69], [72], [76]]

    env.send("play_identified_chord", chord="Am")
    env.send("play_note", note="G", octave=3)
    env.settle()
    assert env.player.immediate[-1] == [55]

    env.send("identifier_set_notes_text", text="D F# A, Zz")
    state = env.expect("IdentifierState", lambda d: d["typed_text_error"] is not None)
    assert state["typed_text_error"] == "Not a note: Zz" and "D" in state["candidates"]

    env.send("insert_chord", at=0, chord="D")
    env.expect("TextEdited", lambda d: d["replacement"] == "D ")
    env.send("identifier_clear")
    env.expect("IdentifierState", lambda d: d["notes"] == [])

    env.send("identifier_toggle_note", note="H", octave=4)
    error = env.expect("UnexpectedError")
    assert error["context"] == "identifier_toggle_note"


def test_identifier_audio_failure_is_reported_once(tmp_path):
    env = BridgeEnv(tmp_path, audio_works=False)
    try:
        env.send("identifier_toggle_note", note="C", octave=4)
        failure = env.expect("AudioUnavailable")
        assert failure["from_click"] is True
        assert failure["message"].endswith("Clicked chords won't play until this is fixed.")
        env.send("play_identified_chord", chord="C")
        env.send("play_note", note="C", octave=4)
        env.settle()
        assert [name for name, _ in env.out].count("AudioUnavailable") == 1
    finally:
        env.close()


def test_one_pinch_zooms_several_steps_in_one_command(tmp_path):
    env = BridgeEnv(tmp_path, chord_sheet=True)
    try:
        env.send("set_chord_sheet_visible", visible=True)
        env.send("set_chord_sheet_view", view_id="staff")
        env.expect("ChordSheetState", lambda d: d["active_view"] == "staff"
                   and d["zoom_supported"])
        env.send("chord_sheet_zoom", step=2)
        state = env.expect("ChordSheetState", lambda d: d["zoom"] != 1.0)
        assert state["zoom"] == 1.44
        env.send("chord_sheet_zoom", step=-3)
        state = env.expect("ChordSheetState", lambda d: d["zoom"] != 1.44)
        assert state["zoom"] == round(1.44 / 1.2 / 1.2 / 1.2, 3)
    finally:
        env.close()


def test_settings_screen_over_the_bridge(env):
    settings = env.expect("SettingsState")
    assert settings["values"]["show_quick_start_on_startup"] is True
    assert env.latest("VoicingEditorState")["active"] is False

    env.send("request_voicing_editor_schema")
    schema = env.expect("VoicingEditorSchema")
    assert set(schema["schema"]["forms"]) == {"fretboard", "ensemble", "piano"}

    env.send("begin_settings_edit")
    env.send("add_voicing")
    state = env.expect("VoicingEditorState", lambda d: d["selected"] == "New voicing")
    assert state["model"] == "fretboard" and state["values"]["max_fret"] == "12"
    env.send("set_voicing_values", values={"max_fret": "x"})
    state = env.expect("VoicingEditorState", lambda d: d["field_errors"])
    assert state["field_errors"] == {"max_fret": "Must be a whole number"}
    env.send("set_voicing_model", model="ensemble")
    env.send("add_voicing_record", field_id="voices")
    state = env.expect("VoicingEditorState", lambda d: len(d["values"].get("voices", [])) == 3)
    env.send("remove_voicing_record", index=2)                 # field_id has a default
    env.expect("VoicingEditorState", lambda d: len(d["values"].get("voices", [])) == 2)
    env.send("set_voicing_values", values={"voices": [
        {"name": "Hi", "low": "C4", "high": "C5", "staff": "treble"},
        {"name": "Lo", "low": "C3", "high": "C4", "staff": None}]})
    env.send("rename_voicing", old="New voicing", new="Duo")
    env.expect("VoicingEditorState", lambda d: d["selected"] == "Duo")

    values = dict(settings["values"], bpm=111)
    env.send("save_settings", values=values)
    env.expect("VoicingEditorState", lambda d: d["active"] is False)
    env.expect("SettingsState", lambda d: d["values"]["bpm"] == 111)
    env.settle()
    config = env.services.config.config
    assert config.voicings["Duo"]["voices"][0]["staff"] == "treble"
    menu = env.latest("VoicingMenuState")
    assert ["Duo"] == [item["label"] for item in menu["groups"][-1]]

    env.send("set_voicing_values", values={})                  # no edit open
    assert env.expect("UnexpectedError")["context"] == "set_voicing_values"


def test_quick_start_over_the_bridge(env):
    env.send("set_show_quick_start_on_startup", show=False)
    env.expect("SettingsState", lambda d: d["values"]["show_quick_start_on_startup"] is False)
    env.send("request_quick_start")
    content = env.expect("QuickStartContent")
    assert content["show_on_startup"] is False
    block = content["pages"][0]["blocks"][1]
    assert block["kind"] == "snippet" and block["spans"][0]["kind"] in ("chord", "comment")
