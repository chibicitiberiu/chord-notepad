"""The ▾ value pickers' options (plan step B4), checked against music theory.

The key list is checked against a reference built here from scratch (the
circle of fifths, letters and semitones), not from the app's tables, and
against the approved mockup's chip order. Every value a picker can give
must pass check_directive (what the Tk Insert dialogs used) and parse as a
valid directive.
"""

import itertools

import pytest

from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.session import pickers
from chordnotepad.session.directives import check_directive, directive_fields
from chordnotepad.session.pickers import PickerContext, picker_options

# -- an independent reference ------------------------------------------------------

LETTERS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SYLLABLES = {"Do": "C", "Re": "D", "Mi": "E", "Fa": "F", "Sol": "G", "La": "A", "Si": "B"}


def ref_pitch(name):
    """Pitch class of an American or European root, with any # and b."""
    for syllable, letter in sorted(SYLLABLES.items(), key=lambda kv: -len(kv[0])):
        if name.startswith(syllable):
            name = letter + name[len(syllable):]
            break
    pc = NATURAL[name[0]]
    for c in name[1:]:
        pc += {"#": 1, "b": -1}[c]
    return pc % 12


def spell(letter_index, pitch):
    """The root on ``letter_index`` that sounds ``pitch``."""
    letter = LETTERS[letter_index % 7]
    diff = (pitch - NATURAL[letter] + 6) % 12 - 6
    assert diff in (-1, 0, 1)
    return letter + {-1: "b", 0: "", 1: "#"}[diff]


def circle_of_fifths():
    """The 15 major keys with a signature (0-7 sharps, 1-7 flats) and their
    relative minors, derived step by step: a fifth up is four letters and
    seven semitones; the relative minor is two letters and three semitones
    down."""
    majors = []
    for n in range(8):
        majors.append((4 * n, 7 * n))
    for n in range(1, 8):
        majors.append((-4 * n, -7 * n))
    major_names = [spell(i, p) for i, p in majors]
    minor_names = [spell(i - 2, p - 3) + "m" for i, p in majors]
    return major_names, minor_names


REF_MAJORS, REF_MINORS = circle_of_fifths()

#: The approved mockup's chips (ValuePicker.qml), in its order.
MOCKUP_MAJORS = ["C", "Db", "C#", "D", "Eb", "E", "F", "Gb", "F#", "G", "Ab", "A", "Bb", "B", "Cb"]
MOCKUP_MINORS = ["Cm", "C#m", "Dm", "Ebm", "D#m", "Em", "Fm", "F#m", "Gm", "Abm", "G#m", "Am",
                 "Bbm", "A#m", "Bm"]


def test_the_reference_is_the_circle_of_fifths():
    assert REF_MAJORS[:8] == ["C", "G", "D", "A", "E", "B", "F#", "C#"]
    assert REF_MAJORS[8:] == ["F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"]
    assert REF_MINORS[:8] == ["Am", "Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m"]
    assert REF_MINORS[8:] == ["Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm", "Abm"]


def chips(notation):
    major, minor = picker_options("key", PickerContext(notation=notation)).groups
    assert (major.title, minor.title) == ("Major", "Minor")
    return major.choices, minor.choices


def test_keys_are_every_key_with_a_signature_in_pitch_order_twins_together():
    major, minor = chips("american")
    for group, reference in ((major, REF_MAJORS), (minor, REF_MINORS)):
        values = [c.value for c in group]
        assert sorted(values) == sorted(reference)
        pitches = [ref_pitch(v.rstrip("m")) for v in values]
        assert pitches == sorted(pitches) and pitches[0] == 0      # from C up
        for a, b in zip(group, group[1:]):
            if ref_pitch(a.value.rstrip("m")) == ref_pitch(b.value.rstrip("m")):
                rank = {"": 0, "b": 1, "#": 2}
                assert rank[a.value.rstrip("m")[1:]] < rank[b.value.rstrip("m")[1:]]
    assert [c.value for c in major] == MOCKUP_MAJORS
    assert [c.value for c in minor] == MOCKUP_MINORS


def test_twins_are_the_enharmonic_pairs_both_ways():
    major, minor = chips("american")
    for group in (major, minor):
        by_value = {c.value: c for c in group}
        for c in group:
            same = [o.value for o in group
                    if o.value != c.value and ref_pitch(o.value.rstrip("m")) == ref_pitch(c.value.rstrip("m"))]
            assert c.twin == (same[0] if same else "")
            if c.twin:
                assert by_value[c.twin].twin == c.value
    pairs = {frozenset((c.value, c.twin)) for c in major + minor if c.twin}
    assert pairs == {frozenset(p) for p in [("Db", "C#"), ("Gb", "F#"), ("B", "Cb"),
                                            ("Ebm", "D#m"), ("Abm", "G#m"), ("Bbm", "A#m")]}


def test_labels_show_sharps_and_flats():
    major, minor = chips("american")
    for c in major + minor:
        assert c.label.replace("♯", "#").replace("♭", "b") == c.value
    assert [c.label for c in major[:3]] == ["C", "D♭", "C♯"]


def test_european_keys_are_the_same_pitches_in_solfege():
    am_major, am_minor = chips("american")
    eu_major, eu_minor = chips("european")
    for am, eu in zip(am_major + am_minor, eu_major + eu_minor):
        assert ref_pitch(eu.value.rstrip("m")) == ref_pitch(am.value.rstrip("m"))
        assert eu.value.endswith("m") == am.value.endswith("m")
        assert eu.label.replace("♯", "#").replace("♭", "b") == eu.value
        root = next(s for s in sorted(SYLLABLES, key=len, reverse=True) if eu.value.startswith(s))
        assert SYLLABLES[root] == am.value[0]
    assert [c.value for c in eu_major[:3]] == ["Do", "Reb", "Do#"]
    assert eu_major[1].label == "Re♭" and eu_minor[-1].value == "Sim"
    assert {c.value: c.twin for c in eu_major}["Si"] == "Dob"


@pytest.mark.parametrize("notation", ["american", "european"])
def test_every_key_chip_is_a_valid_key_directive(notation):
    parser = SongParserService()
    for c in itertools.chain(*chips(notation)):
        assert check_directive("key", {"key": c.value}, notation=notation) is None, c
        (directive,) = parser.parse_directives(f"{{key: {c.value}}}")
        assert directive.is_valid, c


# -- tempo, time, capo, loop -----------------------------------------------------------


def valid(kind, value, labels=()):
    """check_directive passes and the parser takes it (a loop after its labels)."""
    keyword = {"bpm": "bpm", "time": "time", "capo": "capo", "loop": "loop"}[kind]
    if check_directive(kind, directive_fields(kind, value), existing_labels=labels) is not None:
        return False
    text = "".join(f"{{label: {label}}}\n" for label in labels) + f"{{{keyword}: {value}}}"
    return all(d.is_valid for d in SongParserService().parse_directives(text))


def numbers(field):
    n, out = field.minimum, []
    while n <= field.maximum + 1e-9:
        out.append(round(n, 6))
        n += field.step
    return out


def test_every_tempo_the_picker_can_give_is_valid():
    options = picker_options("tempo")
    assert [c.value for c in options.groups[0].choices] == ["120", "+10", "-10", "50%", "2x", "reset"]
    assert options.groups[0].choices[2].label == "−10"
    for chip in options.groups[0].choices:
        assert valid("bpm", chip.value)
        assert pickers.tempo_form(chip.value)[0] == chip.form
    forms = {f.form: f.number for f in options.forms}
    assert set(forms) == {"abs", "rel", "pct", "mul", "reset"} and forms["reset"] is None
    assert (forms["abs"].minimum, forms["abs"].maximum) == (20, 400)
    assert (forms["mul"].minimum, forms["mul"].maximum, forms["mul"].step) == (0.25, 4, 0.25)
    for form, field in forms.items():
        if field is None:
            continue
        for n in numbers(field):
            value = pickers.tempo_value(form, n)
            assert valid("bpm", value), value
            assert pickers.tempo_form(value) == (form, n)
    assert pickers.tempo_value("mul", 0.25) == "0.25x"
    assert pickers.tempo_value("rel", 10) == "+10" and pickers.tempo_value("rel", -5) == "-5"
    assert pickers.tempo_value("reset") == "reset"
    assert pickers.tempo_form("Original") == ("reset", 0.0)


@pytest.mark.parametrize("form, number", [("abs", 19), ("abs", 401), ("pct", 0), ("mul", 0.3),
                                          ("mul", 4.25), ("rel", 101), ("nope", 1)])
def test_tempo_values_outside_the_ranges_are_refused(form, number):
    with pytest.raises(ValueError):
        pickers.tempo_value(form, number)


def test_every_time_the_picker_can_give_is_valid():
    options = picker_options("time")
    presets = [c.value for c in options.groups[0].choices]
    assert presets == ["2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"]
    assert options.units == (1, 2, 4, 8, 16)
    (beats,) = options.numbers
    assert (beats.minimum, beats.maximum) == (1, 16)
    combos = {pickers.time_value(int(b), u) for b in numbers(beats) for u in options.units}
    assert set(presets) <= combos and len(combos) == 80
    for value in combos:
        assert valid("time", value), value
    for bad in ((0, 4), (17, 4), (4, 3)):
        with pytest.raises(ValueError):
            pickers.time_value(*bad)


def test_every_capo_fret_is_valid():
    (fret,) = picker_options("capo").numbers
    assert (fret.minimum, fret.maximum) == (0, 12)
    for n in numbers(fret):
        assert valid("capo", str(int(n)))
    assert not valid("capo", "13")


def test_the_loop_picker_offers_labels_above_then_start_and_counts():
    options = picker_options("loop", PickerContext(labels=("verse", "my verse", "chorus", "verse")))
    assert [c.value for c in options.groups[0].choices] == ["verse", "chorus", "@start"]
    (count,) = options.numbers
    assert (count.minimum, count.maximum) == (1, 16)
    for label in ("verse", "chorus", "@start"):
        for n in numbers(count):
            value = pickers.loop_value(label, int(n))
            assert valid("loop", value, labels=("verse", "chorus")), value
    assert pickers.loop_value("verse", 1) == "verse 1"     # never dropped: no count means 2
    assert [c.value for c in picker_options("loop").groups[0].choices] == ["@start"]


def test_loop_parts_read_like_the_parser():
    parser = SongParserService()
    for value in ("verse", "verse 3", "my verse 2", "@start 4", "verse x"):
        label, count = pickers.loop_parts(value)
        loop = parser.parse_directives(f"{{label: {label}}}\n{{loop: {value}}}")[-1]
        assert (loop.label, loop.loop_count) == (label, count)
    assert pickers.loop_parts("verse") == ("verse", 2)


def test_options_keep_the_current_value_and_refuse_unknown_kinds():
    assert picker_options("capo", PickerContext(current=" 3 ")).current == "3"
    with pytest.raises(ValueError):
        picker_options("label")
    assert pickers.KIND_OF_KEYWORD["tempo"] == "tempo" == pickers.KIND_OF_KEYWORD["bpm"]
