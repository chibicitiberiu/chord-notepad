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
