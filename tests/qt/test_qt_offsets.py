"""Code points and UTF-16 (offsets.py), the editor's span shifting and the
editor font's family and zoom steps (editor_bridge.py, editor_font.py)."""

import random

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from pathlib import Path  # noqa: E402

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF  # noqa: E402

from chordnotepad_desktop import editor_font  # noqa: E402
from chordnotepad_desktop.editor_bridge import TextChange, diff_texts, shift_spans  # noqa: E402
from chordnotepad_desktop.offsets import OffsetMapper, utf16_length  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CLEF = "\U0001D11E"      # MUSICAL SYMBOL G CLEF, outside the BMP
GRIN = "\U0001F600"


def utf16_of(text, cp):
    """The reference: UTF-16 units before code point ``cp``."""
    return len(text[:cp].encode("utf-16-le", "surrogatepass")) // 2


# -- OffsetMapper -----------------------------------------------------------------------------


def test_a_bmp_text_maps_one_to_one():
    mapper = OffsetMapper("C   G   Am\nSol la si\n")
    assert mapper.is_identity
    assert [mapper.to_utf16(i) for i in range(5)] == list(range(5))
    assert [mapper.to_code_point(i) for i in range(5)] == list(range(5))


def test_astral_characters_take_two_units():
    text = f"a{CLEF}b{GRIN}{GRIN}c"
    mapper = OffsetMapper(text)
    assert not mapper.is_identity
    assert mapper.length == 6 and mapper.utf16_length == 9
    assert [mapper.to_utf16(cp) for cp in range(7)] == [0, 1, 3, 4, 6, 8, 9]
    assert [mapper.to_code_point(u) for u in [0, 1, 3, 4, 6, 8, 9]] == list(range(7))


def test_a_utf16_offset_inside_a_pair_maps_to_its_character():
    mapper = OffsetMapper(f"a{CLEF}b")
    assert mapper.to_code_point(2) == 1


def test_offsets_outside_the_text_are_clamped():
    mapper = OffsetMapper(f"{GRIN}x")
    assert mapper.to_utf16(-3) == 0 and mapper.to_utf16(99) == 3
    assert mapper.to_code_point(-1) == 0 and mapper.to_code_point(99) == 2


def test_a_lone_surrogate_counts_once():
    text = "a\ud83db"
    mapper = OffsetMapper(text)
    assert mapper.utf16_length == 3 and mapper.to_utf16(2) == 2


def test_round_trips_match_the_utf16_encoding():
    rng = random.Random(7)
    alphabet = ["a", " ", "\n", "C", "é", "♯", CLEF, GRIN, "\U00010348"]
    for _ in range(200):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        mapper = OffsetMapper(text)
        assert mapper.utf16_length == utf16_length(text) == utf16_of(text, len(text))
        for cp in range(len(text) + 1):
            assert mapper.to_utf16(cp) == utf16_of(text, cp)
            assert mapper.to_code_point(mapper.to_utf16(cp)) == cp


# -- span shifting -----------------------------------------------------------------------------


def test_diff_finds_the_changed_middle_in_utf16():
    assert diff_texts("abc", "abc") is None
    assert diff_texts("C G", "C Am G") == TextChange(2, 2, 5)
    assert diff_texts(f"{GRIN} C", f"{GRIN} Cm") == TextChange(4, 4, 5)
    assert diff_texts("abcdef", "abef") == TextChange(2, 4, 2)


def test_spans_move_like_tk_tags():
    spans = [(0, 1, "chord"), (4, 6, "chord"), (8, 10, "directive")]
    # Typed in front: everything after moves.
    assert shift_spans(spans, TextChange(0, 0, 2)) == [
        (2, 3, "chord"), (6, 8, "chord"), (10, 12, "directive")]
    # Typed at a span's end: outside it; inside it: joins it.
    assert shift_spans(spans, TextChange(6, 6, 7))[1] == (4, 6, "chord")
    assert shift_spans(spans, TextChange(5, 5, 6))[1] == (4, 7, "chord")
    # A span whose text was removed is gone.
    assert shift_spans(spans, TextChange(3, 7, 3)) == [(0, 1, "chord"), (4, 6, "directive")]


# -- the editor font ---------------------------------------------------------------------------


def test_the_bundled_noto_sans_mono_is_loaded(qapp):
    folder = REPO / "resources" / "fonts"
    assert sorted(p.name for p in folder.glob(editor_font.MONO_FONT_GLOB)) == ["NotoSansMono-Regular.ttf"]
    font_id = QFontDatabase.addApplicationFont(str(folder / "NotoSansMono-Regular.ttf"))
    assert QFontDatabase.applicationFontFamilies(font_id) == ["Noto Sans Mono"]
    assert editor_font.load_mono_font(folder)
    metrics = QFontMetricsF(QFont("Noto Sans Mono", 11))
    assert metrics.horizontalAdvance("i") == metrics.horizontalAdvance("W")   # chords align


def test_a_missing_mono_font_is_logged(qapp, caplog, tmp_path, monkeypatch):
    monkeypatch.setattr(editor_font, "MONO_FAMILY", "Not Bundled Mono")
    assert editor_font.load_mono_font(tmp_path) is False
    assert "bundled Not Bundled Mono font was not found" in caplog.text


def test_tk_fixed_font_and_missing_families_give_the_editor_monospace(qapp):
    for name in ("TkFixedFont", "", None, "TkTextFont", "No Such Font 123"):
        assert editor_font.resolve_family(name) == "Noto Sans Mono"
    assert editor_font.resolve_family("Inter") == "Inter"


def test_the_platform_monospace_is_the_fallback(qapp, monkeypatch):
    monkeypatch.setattr(editor_font, "MONO_FAMILY", "Not Bundled Mono")
    assert editor_font.resolve_family("TkFixedFont") == editor_font.platform_monospace()


def test_zoom_shows_percent_of_11pt_in_10_percent_steps():
    assert editor_font.zoom_percent(11) == 100
    ladder = [11]
    while editor_font.zoomed_size(ladder[-1], 1) != ladder[-1]:
        ladder.append(editor_font.zoomed_size(ladder[-1], 1))
    assert ladder[:8] == [11, 12, 13, 14, 15, 17, 18, 19]
    assert ladder[-1] == 72
    assert [editor_font.zoom_percent(s) for s in ladder] == list(range(100, 100 + 10 * len(ladder), 10))
    down = [11]
    while editor_font.zoomed_size(down[-1], -1) != down[-1]:
        down.append(editor_font.zoomed_size(down[-1], -1))
    assert down == [11, 10, 9, 8, 7, 6]
    assert [editor_font.zoom_percent(s) for s in down] == [100, 90, 80, 70, 60, 50]


def test_a_size_between_rungs_shows_its_nearest_and_steps_from_there():
    assert editor_font.zoom_percent(16) == 150       # 16 pt is 145%
    assert editor_font.zoomed_size(16, 1) == 18
    assert editor_font.zoomed_size(16, -1) == 15
    assert editor_font.zoomed_size(99, 0) == 72 and editor_font.zoomed_size(3, 0) == 6
