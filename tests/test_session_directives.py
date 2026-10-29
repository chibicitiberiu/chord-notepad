"""The Insert menu's directives: building, validation messages, labels."""

import pytest

from services.song_parser_service import SongParserService
from session.directives import (
    DirectiveProblem, InvalidDirective, build_directive, check_directive, existing_labels,
    loop_label_choices,
)


def _message(kind, **values):
    problem = check_directive(kind, values, existing_labels={"verse"})
    return problem.message if problem else None


@pytest.mark.parametrize("value, text", [
    ("110", "{bpm: 110}"), (" +20 ", "{bpm: +20}"), ("-5", "{bpm: -5}"),
    ("20%", "{bpm: 20%}"), ("2x", "{bpm: 2x}"), ("0.5x", "{bpm: 0.5x}"),
    ("reset", "{bpm: reset}"), ("Original", "{bpm: Original}"),
])
def test_valid_bpm(value, text):
    assert build_directive("bpm", {"value": value}) == text


@pytest.mark.parametrize("value, message", [
    ("", "Please enter a BPM value."),
    ("abc%", "Invalid percentage value."),
    ("fastx", "Invalid multiplier value."),
    ("+abc", "Invalid relative BPM value."),
    ("fast", "Invalid BPM value."),
    ("19", "BPM must be between 20 and 300."),
    ("301", "BPM must be between 20 and 300."),
])
def test_invalid_bpm(value, message):
    assert _message("bpm", value=value) == message


def test_time_signature():
    assert build_directive("time", {"beats": "3", "unit": 8}) == "{time: 3/8}"
    assert _message("time", beats="0", unit="4") == "Beats must be between 1 and 16."
    assert _message("time", beats="x", unit="4") == "Beats must be between 1 and 16."
    assert _message("time", beats="4", unit="3") == "Beat unit must be 1, 2, 4, 8, or 16."


def test_key_must_be_one_of_the_notations_options():
    assert build_directive("key", {"key": "Bb"}) == "{key: Bb}"
    assert build_directive("key", {"key": "Sib"}, notation="european") == "{key: Sib}"
    assert _message("key", key="Sib") == "Please select a key."
    assert _message("key", key="") == "Please select a key."


def test_label_rules():
    assert build_directive("label", {"label": "chorus_2"}) == "{label: chorus_2}"
    assert _message("label", label="") == "Please enter a label name."
    assert _message("label", label="my chorus") == (
        "Label name can only contain letters, numbers, and underscores.")
    problem = check_directive("label", {"label": "verse"}, existing_labels=["verse"])
    assert problem == DirectiveProblem(
        "Duplicate Label", "A label named 'verse' already exists. Please use a unique name.",
        "label")


def test_loop_rules():
    assert build_directive("loop", {"label": "@start", "count": "2"}) == "{loop: @start 2}"
    assert build_directive("loop", {"label": "verse", "count": 4}) == "{loop: verse 4}"
    assert _message("loop", label="", count="2") == "Please select a label."
    assert _message("loop", label="verse", count="0") == "Loop count must be at least 1."
    assert _message("loop", label="verse", count="two") == "Loop count must be at least 1."


def test_build_raises_with_the_problem():
    with pytest.raises(InvalidDirective) as info:
        build_directive("bpm", {"value": ""})
    assert info.value.problem.title == "Invalid Input"


def test_unknown_kind():
    with pytest.raises(ValueError):
        check_directive("tempo", {})


def test_existing_labels_and_loop_choices():
    lines = SongParserService().detect_chords_in_text(
        "{label: verse}\nC G\n{label: bridge} // {label: commented}\n{loop: verse 2}",
        "american")
    labels = existing_labels(lines)
    assert labels == ("bridge", "verse")
    assert loop_label_choices(labels) == ("@start", "bridge", "verse")
    assert loop_label_choices(()) == ("@start",)
