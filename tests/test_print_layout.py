"""Export PDF's layout: the song's lines as they print, and the pages."""

import pytest

from chordnotepad.session import print_layout
from chordnotepad.session.print_layout import (
    ADVANCE_EM, ASCENT_EM, HEADER_GAP, LINE_HEIGHT_EM, MARGIN, MAX_FONT_SIZE, MIN_FONT_SIZE,
    PAGE_SIZES, SMALL_FONT_SIZE, PrintLine, layout_song, page_for_territory, paginate,
    printable_lines,
)


def texts(song, notation="american"):
    return [line.text for line in printable_lines(song, notation)]


def dim_parts(line):
    return [(column, text) for column, text, dim in line.runs() if dim]


# -- printable_lines ----------------------------------------------------------------


def test_neighbouring_directives_join_into_one_dim_run_padded_to_their_width():
    song = "{key: A} {time: 4/4} {bpm: 200}"
    [line] = printable_lines(song)
    assert line.text == "Key: A | Time: 4/4 | BPM: 200" + "  "
    assert len(line.text) == len(song)
    assert line.runs() == [(0, "Key: A | Time: 4/4 | BPM: 200", True), (29, "  ", False)]


def test_a_shorter_label_keeps_the_chords_after_it_in_their_columns():
    song = "{capo: 3}  A    D\n           Hello world"
    chords, lyric = printable_lines(song)
    assert chords.text == "Capo: 3    A    D"
    assert chords.text.index("A") == song.index("A") == 11
    assert chords.chord and not lyric.chord
    assert dim_parts(chords) == [(0, "Capo: 3")]


def test_a_longer_label_pushes_the_rest_of_its_line_right():
    song = "{label: v}\nC\n{loop: v} G"
    assert texts(song)[2] == "Repeat v ×2 G"


def test_directives_apart_from_each_other_are_separate_runs():
    [line] = printable_lines("{key: G} text {bpm: 90}")
    assert line.text == "Key: G   text BPM: 90  "
    assert dim_parts(line) == [(0, "Key: G"), (14, "BPM: 90")]


def test_labels():
    song = ("{label: Chorus}\n{tempo: 120}\n{bpm: +10}\n{bpm: 50%}\n{bpm: reset}\n"
            "{time: 6/8}\n{capo: 3}\n{loop: Chorus 3}\n{loop: @start}\n{key: F#m}")
    assert [t.rstrip() for t in texts(song)] == [
        "Chorus", "BPM: 120", "BPM: +10", "BPM: 50%", "BPM: reset", "Time: 6/8", "Capo: 3",
        "Repeat Chorus ×3", "Repeat from the start ×2", "Key: F#m"]


def test_invalid_and_unknown_directives_print_the_text_inside_their_braces():
    song = "{bpm: 999} {foo: bar}\n{key: H}\n{loop: nowhere}\n{ capo }"
    assert [t.rstrip() for t in texts(song)] == [
        "bpm: 999 | foo: bar", "key: H", "loop: nowhere", "capo"]


def test_comments_and_text_lines_print_as_written():
    song = "C G // {key: A} here\n// {bpm: 90}\n.la la {bpm: 90}\n  .text {x}\n{} and { }"
    assert texts(song) == ["C G // {key: A} here", "// {bpm: 90}", ".la la {bpm: 90}",
                           "  .text {x}", "{} and { }"]
    assert all(not any(line.dim) for line in printable_lines(song))


def test_tabs_expand_to_columns_of_eight():
    assert texts("\tC\tG\nab\tc") == ["        C       G", "ab      c"]
    # After a directive the tab counts from the directive's columns.
    assert texts("{key: A}\tC") == ["Key: A          C"]
    assert texts("{key: A}\tC")[0].index("C") == 16


def test_european_keys_print_as_written_and_european_chord_lines_count():
    song = "{key: Sol}\nSol Re Mim Do\nAmazing grace"
    lines = printable_lines(song, "european")
    assert lines[0].text.rstrip() == "Key: Sol"
    assert [line.chord for line in lines] == [False, True, False]
    assert not printable_lines(song, "american")[1].chord


def test_roman_numeral_lines_are_chord_lines():
    assert [line.chord for line in printable_lines("{key: G}\nI IV V I\nla la")] == [
        False, True, False]


def test_a_loop_before_its_label_is_invalid_as_in_the_editor():
    # Parsed once over the whole text: the loop sees the label is below it.
    assert texts("{loop: v}\n{label: v}") == ["loop: v  ", "v         "]


def test_territories():
    assert page_for_territory("US") == "letter"
    assert page_for_territory("ca") == "letter"
    assert page_for_territory("RO") == "a4"
    assert page_for_territory("GB") == "a4"
    assert page_for_territory("") == page_for_territory(None) == "a4"


# -- paginate ----------------------------------------------------------------------


def body_top(size=MAX_FONT_SIZE):
    return MARGIN + LINE_HEIGHT_EM * SMALL_FONT_SIZE + HEADER_GAP


def page_texts(page):
    return ["".join(run.text for run in line.runs) for line in page.lines]


def test_a_short_song_on_one_a4_page_at_full_size():
    layout = layout_song("{key: A} {time: 4/4} {bpm: 200}\nC  G\nHello", "american", "Song", "a4")
    assert (layout.page_width, layout.page_height) == (595.28, 841.89)
    assert layout.font_size == MAX_FONT_SIZE
    assert layout.line_height == round(LINE_HEIGHT_EM * MAX_FONT_SIZE, 2)
    assert layout.page_count == 1 and len(layout.pages) == 1
    assert layout.title == "Song" and layout.title_x == round(MARGIN, 2)
    assert layout.title_y == round(MARGIN + ASCENT_EM * SMALL_FONT_SIZE, 2)
    [page] = layout.pages
    assert page.footer == "1 / 1"
    assert page.footer_x == round((595.276 - 5 * ADVANCE_EM * SMALL_FONT_SIZE) / 2, 2)
    first, chords, lyric = page.lines
    assert first.y == round(body_top() + ASCENT_EM * MAX_FONT_SIZE, 2)
    assert chords.y == round(first.y + layout.line_height, 2)
    assert [(r.x, r.text, r.dim) for r in first.runs] == [
        (round(MARGIN, 2), "Key: A | Time: 4/4 | BPM: 200", True)]
    # Runs start where their first character is: G three columns in.
    assert [(r.x, r.text) for r in chords.runs] == [
        (round(MARGIN, 2), "C  G")]


def test_runs_after_padding_start_at_their_column():
    layout = layout_song("{capo: 3}  A", "american", "Song", "a4")
    [line] = layout.pages[0].lines
    advance = ADVANCE_EM * MAX_FONT_SIZE
    assert [(r.x, r.text, r.dim) for r in line.runs] == [
        (round(MARGIN, 2), "Capo: 3", True), (round(MARGIN + 11 * advance, 2), "A", False)]


def test_letter():
    layout = layout_song("C", "american", "Song", "letter")
    assert (layout.page_width, layout.page_height) == (612.0, 792.0)
    assert layout.footer_y == round(792.0 - MARGIN - print_layout.DESCENT_EM * SMALL_FONT_SIZE, 2)


def test_an_unknown_page_size_is_refused():
    with pytest.raises(ValueError):
        layout_song("C", "american", "Song", "a5")


def test_the_font_shrinks_until_the_longest_chord_line_fits():
    width = PAGE_SIZES["a4"][0] - 2 * MARGIN
    chords = " ".join(["Am"] * 34)          # 101 columns: 85 fit at 10 pt
    layout = layout_song(chords + "\n" + "la " * 60, "american", "Song", "a4")
    assert MIN_FONT_SIZE < layout.font_size < MAX_FONT_SIZE
    assert len(chords) * ADVANCE_EM * layout.font_size <= width
    assert len(chords) * ADVANCE_EM * (layout.font_size + 0.1) > width
    # The chord line is one line; the longer lyric line wraps instead.
    texts_ = page_texts(layout.pages[0])
    assert texts_[0] == chords
    assert len(texts_) == 3 and texts_[2].startswith("la")
    indent = 2 * ADVANCE_EM * layout.font_size
    assert layout.pages[0].lines[2].runs[0].x == round(MARGIN + indent, 2)


def test_long_lyric_lines_alone_do_not_shrink_the_font():
    layout = layout_song("C G\n" + "word " * 50, "american", "Song", "a4")
    assert layout.font_size == MAX_FONT_SIZE


def test_the_font_stops_shrinking_at_the_minimum_and_the_chord_line_wraps():
    chords = " ".join(["C"] * 150)
    layout = layout_song(chords, "american", "Song", "a4")
    assert layout.font_size == MIN_FONT_SIZE
    rows = page_texts(layout.pages[0])
    assert len(rows) == 3 and "".join(rows).replace(" ", "") == "C" * 150
    xs = [line.runs[0].x for line in layout.pages[0].lines]
    assert xs[1] == xs[2] == round(MARGIN + 2 * ADVANCE_EM * MIN_FONT_SIZE, 2) > xs[0]


def test_prose_wraps_at_a_space_with_a_two_space_indent():
    columns = int((PAGE_SIZES["a4"][0] - 2 * MARGIN) / (ADVANCE_EM * MAX_FONT_SIZE))
    words = ["lorem"] * 20
    layout = layout_song(" ".join(words), "american", "Song", "a4")
    rows = page_texts(layout.pages[0])
    assert len(rows) == 2
    assert len(rows[0]) <= columns and rows[0].endswith("lorem")
    assert rows[1].startswith("lorem")      # the run starts after the indent ...
    advance = ADVANCE_EM * MAX_FONT_SIZE
    assert layout.pages[0].lines[1].runs[0].x == round(MARGIN + 2 * advance, 2)  # ... of 2
    assert " ".join(rows).split() == words


def test_a_word_longer_than_the_line_is_cut():
    word = "x" * 200
    rows = page_texts(layout_song(word, "american", "Song", "a4").pages[0])
    assert "".join(rows) == word and len(rows) == 3


def test_a_dim_label_keeps_its_colour_when_it_wraps():
    lines = [PrintLine("ab cd", (True, True, False, True, True), False)]
    layout = paginate(lines, "Song", "a4")
    assert [(r.text, r.dim) for r in layout.pages[0].lines[0].runs] == [
        ("ab", True), ("cd", True)]


def test_pages_fill_with_lines_and_number_themselves():
    layout = layout_song("\n".join(f"line {i}" for i in range(120)), "american", "My song", "a4")
    per_page = len(layout.pages[0].lines)
    assert per_page == int((PAGE_SIZES["a4"][1] - 2 * body_top())
                           / (LINE_HEIGHT_EM * MAX_FONT_SIZE)) == 52
    assert layout.page_count == len(layout.pages) == 3
    assert [p.footer for p in layout.pages] == ["1 / 3", "2 / 3", "3 / 3"]
    assert page_texts(layout.pages[1])[0] == f"line {per_page}"
    assert layout.pages[1].lines[0].y == layout.pages[0].lines[0].y
    assert layout.title == "My song"


def test_a_chord_line_moves_to_the_next_page_with_its_lyric():
    per_page = 52
    assert len(layout_song("\n".join(["x"] * 60), "american", "S", "a4").pages[0].lines) == per_page
    song = "\n".join(["words"] * (per_page - 1) + ["C G Am F", "Lyrics under them", "more"])
    layout = layout_song(song, "american", "Song", "a4")
    first, second = (page_texts(p) for p in layout.pages)
    assert len(first) == per_page - 1 and first[-1] == "words"
    assert second[:2] == ["C G Am F", "Lyrics under them"]


def test_a_chord_line_without_a_lyric_under_it_may_end_a_page():
    per_page = 52
    song = "\n".join(["words"] * (per_page - 1) + ["C G Am F", "", "more"])
    first = page_texts(layout_song(song, "american", "Song", "a4").pages[0])
    assert first[-1] == "C G Am F"


def test_blank_lines_keep_their_space_and_trailing_ones_go():
    layout = layout_song("a\n\nb\n\n\n", "american", "Song", "a4")
    a, b = layout.pages[0].lines
    assert round(b.y - a.y, 2) == round(2 * LINE_HEIGHT_EM * MAX_FONT_SIZE, 2)
    assert layout.page_count == 1


def test_empty_text_is_one_page_with_the_header_only():
    for text in ("", "\n\n  \n"):
        layout = layout_song(text, "american", "Untitled", "a4")
        assert layout.page_count == 1
        assert layout.pages[0].lines == ()
        assert layout.pages[0].footer == "1 / 1"
        assert layout.title == "Untitled"


def test_a_long_title_is_shortened_to_fit():
    layout = layout_song("C", "american", "A" * 300, "a4")
    columns = int((PAGE_SIZES["a4"][0] - 2 * MARGIN) / (ADVANCE_EM * SMALL_FONT_SIZE))
    assert len(layout.title) == columns and layout.title.endswith("…")


def test_android_uses_the_same_letter_territories():
    from pathlib import Path
    import re
    kotlin = (Path(__file__).parent.parent / "android" / "app" / "src" / "main" / "kotlin" / "com"
              / "tibich" / "chordnotepad" / "files" / "PdfExporter.kt").read_text(encoding="utf-8")
    listed = re.search(r"val LETTER_COUNTRIES = setOf\(([^)]*)\)", kotlin)
    assert listed is not None
    assert set(re.findall(r'"([A-Z]{2})"', listed.group(1))) == print_layout.LETTER_TERRITORIES
