"""Redundant directives: a value directive that another of the same kind
replaces before any chord plays has no effect. It stays valid (playback is
unchanged: the later one wins anyway) but is shown faded, with a reason."""
import pytest

from services.song_parser_service import SongParserService
from session.highlighting import compute_spans, directive_hint
from session.state import SpanKind


def _directives(text, notation="american"):
    lines = SongParserService().detect_chords_in_text(text, notation)
    return [d for line in lines for d in line.directives]


def _redundant(text):
    return [text[d.start:d.end] for d in _directives(text) if d.redundant]


@pytest.mark.parametrize("text, redundant", [
    ("{capo: 2}\n{capo: 3}\nC", ["{capo: 2}"]),
    ("{capo: 2} {capo: 3} C", ["{capo: 2}"]),
    ("{key: G}\n{key: D}\nI IV", ["{key: G}"]),
    ("{time: 3/4}\n{time: 4/4}\nC", ["{time: 3/4}"]),
    ("{bpm: 100}\n{bpm: 120}\nC", ["{bpm: 100}"]),
    ("{bpm: 100}\n{bpm: 110}\n{bpm: 120}\nC", ["{bpm: 100}", "{bpm: 110}"]),
    ("C\n{key: G}\n{key: D}\nG", ["{key: G}"]),
    # The end of the song: neither plays anything; the first is replaced.
    ("C\n{capo: 1}\n{capo: 2}", ["{capo: 1}"]),
])
def test_replaced_before_any_chord(text, redundant):
    assert _redundant(text) == redundant


@pytest.mark.parametrize("text", [
    "{capo: 2}\nC\n{capo: 3}\nG",                 # a chord plays in between
    "{key: G}\nNC\n{key: D}\nI",                   # a rest counts as a chord
    "{bpm: 100}\n{bpm: +10}\nC",                  # relative stacks on it
    "{bpm: 100}\n{bpm: +10}\n{bpm: 120}\nC",      # a relative change in between
    "{bpm: +10}\n{bpm: 120}\nC",                  # only absolute ones are marked
    "{bpm: 100}\n{bpm: reset}\nC",                # reset depends on the start tempo
    "{bpm: 100}\n{bpm: 50%}\nC",
    "{key: G}\n{label: a}\n{key: D}\nC\n{loop: a 2}",  # a label in between
    "{label: a}\nC\n{capo: 1}\n{loop: a 2}\n{capo: 2}\nG",  # a loop in between
    "{capo: 2}\n{key: D}\nC",                     # different kinds
    "{capo: 2}\n{capo: 30}\nC",                   # an invalid one replaces nothing
])
def test_not_redundant(text):
    assert _redundant(text) == []


def test_redundant_directives_stay_valid_and_say_why():
    text = "{capo: 2}\n\n\n{capo: 3}\nC"
    first, second = _directives(text)
    assert first.is_valid and first.redundant
    assert first.message == "Has no effect: replaced by {capo: 3} on line 4 before any chord plays"
    assert not second.redundant and second.message is None


def test_redundant_span_kind_and_message():
    text = "{key: G}\n{key: D}\nI"
    lines = SongParserService().detect_chords_in_text(text)
    spans = {s.start: s for s in compute_spans(lines, text)}
    assert spans[0].kind == SpanKind.DIRECTIVE_REDUNDANT
    assert spans[0].message == "Has no effect: replaced by {key: D} on line 2 before any chord plays"
    assert spans[text.index("{key: D}")].kind == SpanKind.DIRECTIVE


def test_hint_includes_the_redundant_reason():
    text = "{key: Sol}\n{key: Re}\nDo"
    hint = directive_hint(text, 2, notation="european")
    assert hint.message.startswith("Has no effect: replaced by {key: Re} on line 2")


def test_european_songs_too():
    assert _redundant_eu("{key: Sol}\n{key: Re}\nDo Fa") == ["{key: Sol}"]


def _redundant_eu(text):
    return [text[d.start:d.end] for d in _directives(text, "european") if d.redundant]


def test_playback_is_unchanged():
    from audio.chord_picker import ChordNotePicker
    from services.song_renderer import SongRenderer
    lines = SongParserService().detect_chords_in_text("{capo: 2}\n{capo: 3}\n{key: G}\n{key: D}\nI")
    song = SongRenderer().render(lines=lines, initial_key="C", initial_bpm=120,
                                 initial_time_sig=(4, 4), note_picker=ChordNotePicker())
    [chord] = song.chords
    assert (chord.capo, chord.key, chord.chord_notes.root) == (3, "D", "D")


def test_blend_is_the_directive_colour_faded_into_the_background():
    from ui.text_editor import blend_rgb
    purple = (0x8B * 257, 0x47 * 257, 0x89 * 257)
    white = (65535, 65535, 65535)
    assert blend_rgb(purple, white, 1.0) == "#8b4789"
    assert blend_rgb(purple, white, 0.0) == "#ffffff"
    assert blend_rgb(purple, white, 0.45) == "#cbacca"


def test_tk_paints_redundant_directives_with_their_own_faded_tag():
    import os
    import tkinter as tk
    from constants import COLOR_DIRECTIVE_VALID, TAG_DIRECTIVE_REDUNDANT, TAG_DIRECTIVE_VALID
    from session.state import HighlightState, Span
    from ui.text_editor import ChordTextEditor

    if not (os.environ.get("DISPLAY") or os.name == "nt"):
        pytest.skip("No display available for tkinter tests")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")
    try:
        editor = ChordTextEditor(root, background="white")
        editor.insert("1.0", "{key: G}\n{key: D}\nI")
        editor.apply_highlight(HighlightState(1, 0, (
            Span(0, 8, SpanKind.DIRECTIVE_REDUNDANT, "Has no effect"),
            Span(9, 17, SpanKind.DIRECTIVE))))
        assert editor.tag_ranges(TAG_DIRECTIVE_REDUNDANT)
        faded = editor.tag_cget(TAG_DIRECTIVE_REDUNDANT, "foreground")
        assert faded not in ("", COLOR_DIRECTIVE_VALID)
        # The existing directive tag is untouched.
        assert editor.tag_cget(TAG_DIRECTIVE_VALID, "foreground") == COLOR_DIRECTIVE_VALID
    finally:
        root.destroy()
