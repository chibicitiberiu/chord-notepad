"""The Directives palette and the ▾ pickers' commands (plan step B4).

insert_snippet puts a palette snippet in as one undo step with its value
selected; replace_directive_value changes a directive's value as one undo
step. Both validate like the Tk Insert dialogs (check_directive) and refuse
what wouldn't parse as valid where it goes.
"""

import pytest

from chordnotepad.session import snippets
from chordnotepad.session.events import TextEdited, UndoPolicy, UserError
from chordnotepad.session.platform import DESKTOP_QT
from chordnotepad.session.state import PlaybackStatus
from tests.test_session_player import Env


def env(text, **kw):
    return Env(platform=DESKTOP_QT, text=text, **kw)


def edit(e):
    (edited,) = e.recorder.of_type(TextEdited)
    return edited


def selected(e):
    edited = edit(e)
    lo, hi = sorted((edited.anchor, edited.cursor))
    return e.session.text[lo:hi]


# -- the palette ----------------------------------------------------------------------


def test_the_palette_groups_and_tiles():
    assert [g.title for g in snippets.PALETTE] == ["Tempo", "Time · key · capo", "Sections", "Text"]
    ids = [s.id for g in snippets.PALETTE for s in g.snippets]
    assert len(ids) == len(set(ids)) == 16
    assert snippets.snippet("loop-start").text == "{loop: @start 2}"
    with pytest.raises(KeyError):
        snippets.snippet("duration")


@pytest.mark.parametrize("text, selection", [
    ("{bpm: 120}", "120"), ("{loop: verse 3}", "verse 3"), ("{key: Am}", "Am"),
    ("// comment", "comment"), ("NC", None), ("Am7", None), ("{bpm}", None), ("//", None),
])
def test_what_gets_selected(text, selection):
    span = snippets.select_range(text)
    assert (text[span[0]:span[1]] if span else None) == selection


def test_fill_makes_the_template_valid_where_it_goes():
    fill = snippets.fill_snippet
    assert fill("{key: G}", notation="european") == "{key: Sol}"
    assert fill("{key: Am}", notation="european") == "{key: Lam}"
    assert fill("{key: Sol}", notation="american") == "{key: G}"
    assert fill("{label: verse}", labels=("verse", "verse2")) == "{label: verse3}"
    assert fill("{label: verse}", labels=("chorus",)) == "{label: verse}"
    assert fill("{loop: verse}", labels_above=("intro", "verse")) == "{loop: verse}"
    assert fill("{loop: verse 3}", labels_above=("intro", "chorus")) == "{loop: chorus 3}"
    assert fill("{loop: verse}", labels_above=()) == "{loop: @start}"
    assert fill("{loop: @start 2}", labels_above=()) == "{loop: @start 2}"
    assert fill("NC") == "NC" and fill("{bpm: 120}") == "{bpm: 120}"


@pytest.mark.parametrize("tile", [s for g in snippets.PALETTE for s in g.snippets],
                         ids=lambda s: s.id)
def test_every_tile_goes_into_a_song_as_a_valid_directive(tile):
    e = env("{label: verse}\nC G\n\n")
    e.session.insert_snippet(len(e.session.text), tile.text)
    assert not e.recorder.of_type(UserError)
    edited = edit(e)
    assert edited.undo is UndoPolicy.GROUP
    assert all(d.is_valid for d in e.session._parsed_directives(e.session.text))


# -- insert_snippet -----------------------------------------------------------------------


def test_a_directive_goes_in_with_its_value_selected():
    e = env("C G\n")
    e.session.insert_snippet(4, "{bpm: 120}")
    edited = edit(e)
    assert e.session.text == "C G\n{bpm: 120}"
    assert (edited.start, edited.end, edited.replacement) == (4, 4, "{bpm: 120}")
    assert (edited.anchor, edited.cursor) == (10, 13) and selected(e) == "120"
    assert e.status() == "Inserted: {bpm: 120}"


def test_spaces_keep_it_off_the_words_around_it():
    e = env("C G")
    e.session.insert_snippet(1, "{capo: 3}")
    assert e.session.text == "C {capo: 3} G"
    assert selected(e) == "3"


def test_snap_moves_a_drop_off_the_middle_of_a_word():
    e = env("Am7 G")
    e.session.insert_snippet(1, "NC", snap=True)        # A|m7: nearer the left edge
    assert e.session.text == "NC Am7 G"
    edited = edit(e)
    assert edited.anchor is None and edited.cursor == 2
    e = env("Am7 G")
    e.session.insert_snippet(2, "NC", snap=True)        # Am|7: nearer the right edge
    assert e.session.text == "Am7 NC G"
    e = env("Am7 G")
    e.session.insert_snippet(1, "NC")                   # no snap: in the middle, spaced
    assert e.session.text == "A NC m7 G"


@pytest.mark.parametrize("text, offset, expected", [
    ("Am7 G", 1, 0),            # A|m7: the left edge is nearer
    ("Am7 G", 2, 3),            # Am|7: the right edge
    ("Am G", 1, 0),             # A|m: a tie goes left
    ("Am7 G", 3, 3),            # next to a space: kept
    ("Am7 G", 4, 4),
    ("Am7", 0, 0),              # the ends of the text
    ("Am7", 3, 3),
    ("one\ntwo", 3, 3),         # before the newline
    ("C {bpm: 90} G", 4, 2),    # {b|pm: 90}: out of the directive, left
    ("C {bpm: 90} G", 9, 11),   # {bpm: 9|0}: right, past the brace
    ("C {bpm: 90} G", 7, 11),   # {bpm:| 90}: next to its space, still inside
    ("{a: 1}{b: 2}", 6, 6),     # between two directives
    ("Am7{bpm: 90}", 2, 3),     # Am|7{: a word stops at the brace
    ("{bpm: 90}Am7", 10, 9),    # }A|m7
    ("C {bpm: 90", 4, 2),       # no closing brace: a word like any other
    ("x}\n{y", 5, 5),           # braces on other lines don't count
])
def test_a_drop_lands_on_the_nearer_edge_of_a_word_or_directive(text, offset, expected):
    assert snippets.drop_offset(text, offset) == expected


def test_a_snapped_drop_never_lands_inside_a_directive():
    e = env("C {bpm: 90} G")
    e.session.insert_snippet(9, "{key: G}", snap=True)
    assert e.session.text == "C {bpm: 90} {key: G} G"


def test_a_dropped_chord_goes_in_spaced_as_one_undo_step():
    e = env("C G\n")
    e.session.insert_snippet(2, "Am7", snap=True)       # the identifier's drop
    assert e.session.text == "C Am7 G\n"
    edited = edit(e)
    assert edited.undo is UndoPolicy.GROUP and edited.anchor is None and edited.cursor == 5


def test_a_comment_selects_its_words():
    e = env("C G\n")
    e.session.insert_snippet(4, "// comment")
    assert selected(e) == "comment"


def test_a_label_taken_gets_a_number_and_a_loop_finds_a_label_above():
    e = env("{label: verse}\nC G\n{label: chorus}\nAm F\n")
    e.session.insert_snippet(len(e.session.text), "{label: verse}")
    assert e.session.text.endswith("{label: verse2}")
    e = env("{label: verse}\nC G\n{label: chorus}\nAm F\n")
    e.session.insert_snippet(len(e.session.text), "{loop: verse 3}")
    assert e.session.text.endswith("{loop: verse 3}")
    e = env("C G\n{label: verse}\nAm F\n")
    e.session.insert_snippet(0, "{loop: verse}")          # the label is below
    assert e.session.text.startswith("{loop: @start} C G")


def test_a_key_follows_the_songs_notation():
    e = env("Do Sol Lam Fa\n")
    e.session.set_notation("european")
    e.recorder.clear()
    e.session.insert_snippet(0, "{key: Am}")
    assert e.session.text.startswith("{key: Lam}")


@pytest.mark.parametrize("text, message", [
    ("{bpm: 9000}", "BPM must be between 20 and 400."),
    ("{time: 3/5}", "Beat unit must be 1, 2, 4, 8, or 16."),
    ("{capo: 13}", "The capo must be on a fret from 0 to 12 (0 means no capo)."),
    ("{key: H}", "Please select a key."),
    ("{bpm: 0%}", "A percentage must be above 0"),
])
def test_an_invalid_directive_is_refused_and_nothing_goes_in(text, message):
    e = env("C G\n")
    e.session.insert_snippet(4, text)
    assert e.session.text == "C G\n"
    assert not e.recorder.of_type(TextEdited)
    (error,) = e.recorder.of_type(UserError)
    assert error.message.startswith(message)


def test_refused_while_playing_and_bad_arguments():
    e = env("C G\n", auto_play=False)
    e.session.play_pause()
    e.rendered()
    assert e.playback().status is PlaybackStatus.PLAYING
    e.session.insert_snippet(0, "{bpm: 120}")
    assert e.session.text == "C G\n"
    e = env("C G\n")
    for offset, text in ((-1, "NC"), (99, "NC"), (0, "")):
        with pytest.raises(ValueError):
            e.session.insert_snippet(offset, text)


def test_one_undo_step_even_with_the_spaces():
    e = env("C G")
    e.session.insert_snippet(1, "{bpm: +10}")
    assert len(e.recorder.of_type(TextEdited)) == 1


# -- replace_directive_value ---------------------------------------------------------------


def span_of(text, directive):
    start = text.index(directive)
    return (start, start + len(directive))


def test_a_value_is_replaced_in_place_as_one_step():
    e = env("{bpm: 120}\nC G\n")
    e.session.replace_directive_value((0, 10), "90")
    edited = edit(e)
    assert e.session.text == "{bpm: 90}\nC G\n"
    assert (edited.start, edited.end, edited.replacement) == (6, 9, "90")
    assert edited.undo is UndoPolicy.GROUP and edited.cursor == 9 and edited.anchor is None


def test_the_keyword_and_spacing_stay_as_typed():
    text = "{ Tempo :120 }\nC G\n"
    e = env(text)
    e.session.replace_directive_value(span_of(text, "{ Tempo :120 }"), "2x")
    assert e.session.text == "{ Tempo :2x }\nC G\n"


@pytest.mark.parametrize("before, value, after", [
    ("{time: 4/4}", "6/8", "{time: 6/8}"),
    ("{key: C}", "Db", "{key: Db}"),
    ("{key: H}", "C#m", "{key: C#m}"),          # an invalid directive is fixed by a pick
    ("{capo: 2}", "0", "{capo: 0}"),
    ("{loop: verse}", "verse 3", "{loop: verse 3}"),
    ("{loop: verse}", "@start 1", "{loop: @start 1}"),
    ("{bpm: 120}", "reset", "{bpm: reset}"),
])
def test_picker_values(before, value, after):
    text = "{label: verse}\nC G\n" + before + "\n"
    e = env(text)
    e.session.replace_directive_value(span_of(text, before), value)
    assert e.session.text == "{label: verse}\nC G\n" + after + "\n"


@pytest.mark.parametrize("before, value, message", [
    ("{time: 4/4}", "3/5", "Beat unit must be"),
    ("{key: C}", "D#", "Please select a key."),          # D# major has no signature
    ("{capo: 2}", "13", "The capo must be"),
    ("{loop: verse}", "chorus 2", "Label 'chorus' comes after the loop"),
    ("{loop: verse}", "nowhere 2", "No label 'nowhere' in the song"),
    ("{label: verse}", "chorus", "A label named 'chorus' already exists"),
])
def test_a_wrong_value_changes_nothing(before, value, message):
    text = "{label: verse}\nC G\n" + before + "\n{label: chorus}\nAm\n"
    start = text.index(before, 1) if before == "{label: verse}" else text.index(before)
    e = env(text)
    e.session.replace_directive_value((start, start + len(before)), value)
    assert e.session.text == text
    (error,) = e.recorder.of_type(UserError)
    assert message in error.message


def test_a_label_can_keep_its_own_name():
    text = "{label: verse}\nC G\n{loop: verse}\n"
    e = env(text)
    e.session.replace_directive_value((0, 14), "verse")
    assert not e.recorder.of_type(UserError)


@pytest.mark.parametrize("span, value", [
    ((0, 3), "90"), ((4, 7), "90"), ((-1, 10), "90"), ((0, 99), "90"),
    ((0, 10), ""), ((0, 10), "9}0"), ((0, 10), "9\n0"),
])
def test_a_span_that_isnt_a_directive_or_a_bad_value_raises(span, value):
    e = env("{bpm: 120}\nC G\n")
    with pytest.raises(ValueError):
        e.session.replace_directive_value(span, value)


def test_an_unknown_keyword_raises():
    e = env("{tempi: 120}\nC G\n")
    with pytest.raises(ValueError):
        e.session.replace_directive_value((0, 12), "90")


# -- picker_at ------------------------------------------------------------------------------


def test_the_picker_for_the_directive_at_the_caret():
    text = "{label: verse}\nC G\n{loop: verse 2} {key: Am}\n// {bpm: 90}\n"
    e = env(text)
    loop = text.index("{loop")
    picker = e.session.picker_at(loop + 3)
    assert (picker.kind, picker.start, picker.end) == ("loop", loop, loop + 15)
    assert text[picker.value_start:picker.value_end] == "verse 2"
    assert picker.options.current == "verse 2"
    assert [c.value for c in picker.options.groups[0].choices] == ["verse", "@start"]
    key = text.index("{key")
    assert e.session.picker_at(key + 9).kind == "key"      # just after the }
    assert e.session.picker_at(key + 9).options.current == "Am"
    assert e.session.picker_at(3) is None                   # {label}: typed, no picker
    assert e.session.picker_at(text.index("C G")) is None
    assert e.session.picker_at(text.index("{bpm")) is None  # in a comment


def test_a_loop_picker_only_offers_labels_above_it():
    text = "{loop: @start}\n{label: verse}\nC\n"
    e = env(text)
    assert [c.value for c in e.session.picker_at(1).options.groups[0].choices] == ["@start"]


def test_the_key_picker_in_a_european_song():
    text = "{key: Lam}\nDo Sol Lam Fa\n"
    e = env(text)
    e.session.set_notation("european")
    options = e.session.picker_at(1).options
    assert options.groups[0].choices[1].value == "Reb" and options.current == "Lam"


def test_the_capo_tile_says_only_the_fretted_views_change():
    tile = snippets.snippet("capo")
    assert tile.hint.startswith("Where the capo sits on a fretted instrument.")
    assert "The sound and the chord names stay as written." in tile.hint
