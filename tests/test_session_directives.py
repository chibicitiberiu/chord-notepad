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
    ("19", "BPM must be between 20 and 400."),
    ("401", "BPM must be between 20 and 400."),
])
def test_invalid_bpm(value, message):
    assert _message("bpm", value=value) == message


@pytest.mark.parametrize("value", ["20", "300", "301", "400"])
def test_bpm_range_is_the_apps_tempo_range(value):
    assert _message("bpm", value=value) is None


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


# -- the Insert Key list (C5) ------------------------------------------------------------

_LETTERS = "CDEFGAB"
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR, _MINOR = (0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10)


def _signature(key):
    """The key's scale accidentals, one per letter, worked out from the
    tonic (an oracle independent of the app's tables); None if a degree
    would need a double accidental or the signature mixes sharps and flats."""
    minor = key.endswith("m")
    tonic = key[:-1] if minor else key
    letter = _LETTERS.index(tonic[0])
    pc = _NATURAL[tonic[0]] + tonic.count("#") - tonic.count("b")
    shifts = []
    for degree, step in enumerate(_MINOR if minor else _MAJOR):
        name = _LETTERS[(letter + degree) % 7]
        shift = (pc + step - _NATURAL[name] + 6) % 12 - 6
        shifts.append(shift)
    if any(abs(x) > 1 for x in shifts) or (1 in shifts and -1 in shifts):
        return None
    return shifts


def test_the_insert_key_list_is_every_key_with_a_signature():
    from session.toolbar import insert_key_options

    keys = insert_key_options("american")
    roots = [r + a for r in _LETTERS for a in ("", "#", "b")]
    expected = {root + m for root in roots for m in ("", "m") if _signature(root + m)}
    assert len(keys) == len(set(keys)) == 30
    assert set(keys) == expected
    assert keys[:15] == tuple(k for k in keys if not k.endswith("m"))   # majors first
    for absent in ("D#", "G#", "A#", "Dbm", "Gbm", "Fb", "E#m"):
        assert absent not in keys


def test_the_european_insert_key_list_is_the_american_one_respelled():
    from chord.converter import NotationConverter
    from session.toolbar import insert_key_options

    converter = NotationConverter()
    american, european = insert_key_options("american"), insert_key_options("european")
    assert tuple(converter.chord_american_to_european(k) for k in american) == european


@pytest.mark.parametrize("notation", ["american", "european"])
def test_every_insert_key_makes_a_valid_key_directive(notation):
    from session.toolbar import insert_key_options

    parser = SongParserService()
    for key in insert_key_options(notation):
        text = build_directive("key", {"key": key}, notation=notation)
        [line] = parser.detect_chords_in_text(text, notation)
        assert [d.is_valid for d in line.directives] == [True], key


def test_minor_keys_can_be_inserted_but_not_keys_without_a_signature():
    assert build_directive("key", {"key": "F#m"}) == "{key: F#m}"
    assert build_directive("key", {"key": "Cb"}) == "{key: Cb}"
    assert build_directive("key", {"key": "Sol#m"}, notation="european") == "{key: Sol#m}"
    assert _message("key", key="D#") == "Please select a key."
    assert _message("key", key="Gbm") == "Please select a key."


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
