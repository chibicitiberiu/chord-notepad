"""The chord sheet (plan step E4): chord_sheet.py, sheet_paint.py and
ChordSheetPane.qml.

The renderers, the packing and the view model's rules are the core's
(tests/test_chord_sheet_*.py, test_chord_sheet_viewmodel.py); these check
what the Qt window does with them: the buffer fetched through the direct
call and painted (pixels and ops, at 100% and 125%), only the viewport
painted, the dark remap, the tabs, the zoom, scrolling and following
playback, the frozen gutter, clicks, the F9 panel and its saved height.
"""

import json
import math
import re

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QWheelEvent  # noqa: E402
from PySide6.QtQml import qmlEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from chordnotepad.chord_sheet.ops import DrawOps  # noqa: E402
from chordnotepad.chord_sheet.pack import ViewOps, unpack  # noqa: E402
from chordnotepad.chord_sheet.renderer_interface import HAND_COLORS, NOTE_INK, STRIP_BG, SlotBox  # noqa: E402
from chordnotepad_desktop import chord_sheet, sheet_paint  # noqa: E402
from chordnotepad_desktop.main import QML_DIR  # noqa: E402
from chordnotepad_desktop.sheet_paint import (  # noqa: E402
    GlyphCache, PreparedOps, PreparedSheet, SheetPainter, dark_variant, lane_clip_rights,
    parse_tk_color, themed_color,
)
from tests.qt.test_qt_editor import CTRL, NO_MODIFIER, song, start  # noqa: E402
from tests.qt.test_qt_player_bar import Bar  # noqa: E402
from tests.qt.test_qt_value_picker import find, texts_shown  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
SURFACE = QColor("#f6f7f9")         # Theme.panel, light
#: Three sections, eight chords; long enough to scroll in a narrow window.
TEXT = ("{label: verse}\nC   G   Am  F\nC   G   F   C\n"
        "{label: chorus}\nAm  F   C   G\nAm  F   G   C\n{loop: chorus 2}\n")


# -- colours (ChordSheetTheme.kt's remap) ---------------------------------------------------


def hsl(color):
    return color.hslHueF(), color.hslSaturationF(), color.lightnessF()


def test_tk_colour_strings_parse_like_android():
    assert parse_tk_color("#abc") == QColor("#aabbcc")
    assert parse_tk_color("#2a6f8a") == QColor("#2a6f8a")
    assert parse_tk_color("gray") == QColor("#bebebe")
    assert parse_tk_color("") is None and parse_tk_color(None) is None
    assert parse_tk_color("#12345") is None and parse_tk_color("chartreuse") is None


def test_the_light_theme_keeps_the_colours_but_the_paper():
    surface = QColor("#f6f7f9")
    assert themed_color(STRIP_BG, QColor(STRIP_BG), False, surface) == surface
    for spec in (NOTE_INK, HAND_COLORS["rh"], "#c62828"):
        assert themed_color(spec, QColor(spec), False, surface) == QColor(spec)


def test_the_dark_theme_flips_neutrals_and_lifts_hues():
    surface = QColor("#252629")
    # The paper is the panel's surface in both themes.
    assert themed_color(STRIP_BG, QColor(STRIP_BG), True, surface) == surface
    # Ink (a neutral: saturation < 0.3) flips: L 0.18 -> 0.92 - 0.82 * 0.18.
    ink = dark_variant(QColor(NOTE_INK))
    assert ink.lightnessF() == pytest.approx(0.92 - 0.82 * QColor(NOTE_INK).lightnessF(), abs=0.01)
    assert ink.hslSaturationF() == pytest.approx(QColor(NOTE_INK).hslSaturationF() * 0.3, abs=0.01)
    # A white grid line goes dark, a black one light.
    assert dark_variant(QColor("#ffffff")).lightnessF() == pytest.approx(0.10, abs=0.01)
    assert dark_variant(QColor("#000000")).lightnessF() == pytest.approx(0.92, abs=0.01)
    # A hue keeps its hue and saturation and gets at least 66% lightness.
    red = QColor("#c62828")
    lifted = dark_variant(red)
    assert lifted.hslHueF() == pytest.approx(red.hslHueF(), abs=0.01)
    assert lifted.hslSaturationF() == pytest.approx(red.hslSaturationF(), abs=0.01)
    assert lifted.lightnessF() == pytest.approx(0.66, abs=0.01)
    light_hue = QColor("#80c0ff")              # already lighter: unchanged lightness
    assert dark_variant(light_hue).lightnessF() == pytest.approx(light_hue.lightnessF(), abs=0.01)
    # The hands have fixed colours.
    assert themed_color(HAND_COLORS["rh"], QColor(HAND_COLORS["rh"]), True, surface) == QColor("#78a6d8")
    assert themed_color(HAND_COLORS["lh"], QColor(HAND_COLORS["lh"]), True, surface) == QColor("#d09a6c")


def test_a_banded_section_is_a_subtle_step_from_the_surface():
    from chordnotepad.chord_sheet.renderer_interface import SECTION_BAND
    for surface, dark in ((QColor("#f6f7f9"), False), (QColor("#252629"), True)):
        band = themed_color(SECTION_BAND, QColor(SECTION_BAND), dark, surface)
        assert band == sheet_paint.section_band_color(surface, dark)
        step = band.lightnessF() - surface.lightnessF()
        # Darker on the light paper, lighter on the dark one; a few percent.
        assert (0.005 < step < 0.05) if dark else (-0.05 < step < -0.01), (dark, step)
        assert band.hsvHueF() == pytest.approx(surface.hsvHueF(), abs=0.02)
        # The roll's black-key rows over the band stay darker than it.
        row = themed_color(sheet_paint.ROLL_BAND_BLACK_ROW, QColor(sheet_paint.ROLL_BAND_BLACK_ROW),
                           dark, surface)
        assert row.lightnessF() < band.lightnessF() - 0.02


def test_the_piano_roll_in_the_dark_theme_takes_the_apps_greys():
    surface = QColor("#252629")
    rows = sheet_paint.roll_dark_colors(surface)
    # Black-key rows stay the darker ones (a lightness flip made them lighter).
    black_row = themed_color(sheet_paint.ROLL_BLACK_ROW, QColor(sheet_paint.ROLL_BLACK_ROW), True, surface)
    assert black_row == rows[sheet_paint.ROLL_BLACK_ROW]
    assert black_row.lightnessF() < surface.lightnessF()
    assert themed_color(sheet_paint.ROLL_BLACK_ROW, QColor(sheet_paint.ROLL_BLACK_ROW), False,
                        surface) == QColor(sheet_paint.ROLL_BLACK_ROW)
    # The C guides are lighter than the paper, C4's more; all in its hue (no green tint).
    c, c4 = rows[sheet_paint.ROLL_GUIDE_C], rows[sheet_paint.ROLL_GUIDE_C4]
    assert surface.lightnessF() < c.lightnessF() < c4.lightnessF()
    for color in (black_row, c, c4):
        assert color.hsvHueF() == pytest.approx(surface.hsvHueF(), abs=0.02)
    # The keyboard isn't inverted and uses neutral greys, not Tk's white and slate.
    strings = [sheet_paint.GUTTER_WHITE, sheet_paint.GUTTER_BLACK, sheet_paint.GUTTER_EDGE]
    dark_keys = sheet_paint.gutter_palette(strings, True, surface)
    white, black = dark_keys[sheet_paint.GUTTER_WHITE], dark_keys[sheet_paint.GUTTER_BLACK]
    assert white.lightnessF() > 0.6 and black.lightnessF() < surface.lightnessF()
    assert white.hslSaturationF() < 0.15 and black.hslSaturationF() < 0.15
    light_keys = sheet_paint.gutter_palette(strings, False, surface)
    assert light_keys[sheet_paint.GUTTER_WHITE] == QColor("#ffffff")
    assert light_keys[sheet_paint.GUTTER_BLACK] == QColor("#31424a")


def test_the_rolls_note_names_are_white_on_light_bars_and_dark_on_dark_ones():
    from chordnotepad.chord_sheet import piano_roll
    label, fill = piano_roll.NOTE_LABEL, piano_roll.NOTE_FILL
    surface = QColor("#252629")
    assert themed_color(label, QColor(label), False, SURFACE).lightnessF() > 0.98
    dark_label = themed_color(label, QColor(label), True, surface)
    assert dark_label == QColor("#1d1e22")                 # not dark_variant's grey
    assert label.lower() != sheet_paint.GUTTER_WHITE        # Android maps that one otherwise
    # Readable on every bar colour in both themes (WCAG contrast >= 3).
    def contrast(a, b):
        def lum(c):
            def ch(v):
                return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            return 0.2126 * ch(c.redF()) + 0.7152 * ch(c.greenF()) + 0.0722 * ch(c.blueF())
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    bars = [fill, HAND_COLORS["lh"], HAND_COLORS["rh"], *renderer_interface_voice_colors()]
    for bar in bars:
        assert contrast(QColor(label), QColor(bar)) >= 3, bar
        assert contrast(dark_label, themed_color(bar, QColor(bar), True, surface)) >= 3, bar


def renderer_interface_voice_colors():
    from chordnotepad.chord_sheet.renderer_interface import VOICE_COLORS
    return VOICE_COLORS


def test_the_dark_remap_matches_the_kotlin_formula_on_the_sheets_colours():
    """Every colour the renderers use, against an independent HSL computation
    of ChordSheetTheme.kt's rule (colorsys)."""
    import colorsys
    from chordnotepad.chord_sheet import marker_lane, piano_roll, renderer_interface

    specs = {v for v in vars(renderer_interface).values() if isinstance(v, str) and v.startswith("#")}
    specs |= {v for v in vars(marker_lane).values() if isinstance(v, str) and v.startswith("#")}
    specs |= set(renderer_interface.VOICE_COLORS) | set(marker_lane._KIND_COLOR.values())
    specs.add(piano_roll.NOTE_FILL)
    assert len(specs) > 8
    for spec in specs:
        c = QColor(spec)
        h, l, s = colorsys.rgb_to_hls(c.redF(), c.greenF(), c.blueF())
        if s < 0.3:
            l2, s2 = 0.92 - 0.82 * l, s * 0.3
        else:
            l2, s2 = max(l, 0.66), s
        r, g, b = colorsys.hls_to_rgb(h, min(max(l2, 0), 1), min(max(s2, 0), 1))
        got = dark_variant(c)
        assert max(abs(got.redF() - r), abs(got.greenF() - g), abs(got.blueF() - b)) < 0.01, spec


# -- prepared ops ----------------------------------------------------------------------


def view_of(content, lane=(), slots=(), width=2000.0, gutter=()):
    return ViewOps(view_id="staff", zoom=1.0, height=100.0, content_width=width, content_height=100.0,
                   gutter_width=40.0 if gutter else 0.0, lane_height=20.0, background=STRIP_BG,
                   highlight="#ffe58a", slots=tuple(slots), content=list(content), lane=list(lane),
                   gutter_variants=[list(gutter)] if gutter else [],
                   gutter_runs=[sheet_paint_run()] if gutter else [])


def sheet_paint_run():
    from chordnotepad.chord_sheet.pack import GutterRun
    return GutterRun(-math.inf, 0)


def test_only_the_ops_in_the_viewport_are_drawn_in_their_order():
    ops = DrawOps()
    for i in range(40):                        # a card every 50 px
        ops.rect(i * 50, 10, 40, 40, fill="#123456")
    ops.line([(0, 5), (2000, 5)], fill="#000000")      # a staff line across everything
    ops.text(1000, 60, "C", fill="#000000")
    prepared = PreparedOps(ops.ops)
    shown = prepared.visible(500, 700)
    rects = [item[1].x() for item in shown if item[0] == sheet_paint.K_RECT]
    assert rects == [500, 550, 600, 650, 700]        # the one at 450 ends at 490.5
    assert any(item[0] == sheet_paint.K_SEGMENT for item in shown)
    assert not any(item[0] == sheet_paint.K_TEXT for item in shown)
    # Paint order is kept across buckets.
    everything = prepared.visible(0, 2000)
    assert [item[0] for item in everything][-2:] == [sheet_paint.K_SEGMENT, sheet_paint.K_TEXT]
    assert len(everything) == 42


def test_lane_labels_are_clipped_short_of_the_next_one():
    ops = DrawOps()
    ops.rect(0, 0, 3, 8, fill="#000000")
    ops.text(5, 2, "verse", fill="#000000")
    ops.text(60, 2, "chorus", fill="#000000")
    assert lane_clip_rights(ops.ops) == [math.inf, 58.0, math.inf]


def test_slots_hit_test_and_look_up():
    sheet = PreparedSheet(view_of([], slots=[SlotBox(0, 10, 50), SlotBox(1, 60, 50), SlotBox(3, 110, 40)]))
    assert sheet.chord_at(5) == -1 and sheet.chord_at(10) == 0 and sheet.chord_at(75) == 1
    assert sheet.chord_at(149) == 3 and sheet.chord_at(151) == -1
    assert sheet.slot(1) == (60, 50) and sheet.slot(2) is None and sheet.slot(None) is None


def test_glyphs_are_scaled_to_device_pixels_and_tinted():
    glyphs = GlyphCache()
    image, width, height = glyphs.image("clef_treble:96", 1.25, None)
    assert height == 96 and image.height() == 120 and image.devicePixelRatio() == 1.25
    red, _, _ = glyphs.image("glyph_notehead_whole:20:ff0000", 1.0, QColor("#ff0000"))
    opaque = [red.pixelColor(x, y) for x in range(red.width()) for y in range(red.height())
              if red.pixelColor(x, y).alpha() == 255]
    assert opaque and all(c.red() == 255 and c.green() == 0 and c.blue() == 0 for c in opaque)
    assert glyphs.image("clef_nonsense:20", 1.0, None) is None
    # Cached per (key, ratio, colour).
    assert glyphs.image("clef_treble:96", 1.25, None)[0] is image


def paint(view, width=400, height=140, dpr=1.0, dark=False, surface=SURFACE):
    sheet = PreparedSheet(view)
    painter = SheetPainter()
    painter.dpr = dpr
    painter.set_theme(sheet.strings, dark, surface)
    image = QImage(round(width * dpr), round(height * dpr), QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(surface)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.draw(p, sheet.content.visible(0, width))
    p.end()
    return image, painter


def test_the_painter_draws_rects_lines_text_and_glyphs():
    ops = DrawOps()
    ops.rect(10, 10, 40, 30, fill="#2a6f8a")
    ops.line([(0, 60), (400, 60)], fill="#000000", width=2)
    ops.text(200, 100, "Am", anchor="center", size=14, fill="#c62828", bold=True)
    ops.image(300, 20, "clef_bass:40")
    image, painter = paint(view_of(ops.ops))
    assert image.pixelColor(30, 25) == QColor("#2a6f8a")
    assert image.pixelColor(100, 60) == QColor("#000000")
    reds = [image.pixelColor(x, y) for x in range(170, 230) for y in range(85, 115)]
    assert any(c.red() > 150 and c.green() < 90 for c in reds)          # the text's ink
    inks = [image.pixelColor(x, y) for x in range(300, 340) for y in range(20, 60)]
    assert any(c.lightness() < 80 for c in inks)                         # the clef
    assert painter.drawn == 4


def test_a_rounded_rect_paints_rounded_and_counts_in_the_key_bed():
    ops = DrawOps()
    ops.rect(10, 10, 40, 30, fill="#2a6f8a", radius=6)
    ops.rect(60, 10, 40, 30, fill="#2a6f8a")
    prepared = PreparedOps(ops.ops)
    assert [item[0] for item in prepared.items] == [sheet_paint.K_RRECT, sheet_paint.K_RECT]
    image, painter = paint(view_of(ops.ops))
    assert image.pixelColor(30, 25) == QColor("#2a6f8a")
    assert image.pixelColor(10, 10) == SURFACE             # the corner is cut
    assert image.pixelColor(60, 10) == QColor("#2a6f8a")   # the square one isn't
    assert painter.drawn == 2
    assert prepared.key_bed() == QRectF(10, 10, 90, 30)


def test_dark_paints_the_remapped_colours():
    ops = DrawOps()
    ops.rect(10, 10, 40, 30, fill=NOTE_INK)
    ops.rect(60, 10, 40, 30, fill=STRIP_BG)
    dark_surface = QColor("#252629")
    image, _ = paint(view_of(ops.ops), dark=True, surface=dark_surface)
    assert image.pixelColor(30, 25).name() == dark_variant(QColor(NOTE_INK)).name()
    assert image.pixelColor(80, 25).name() == dark_surface.name()


@pytest.mark.parametrize("dark", [False, True])
def test_the_piano_roll_names_its_notes_in_its_rounded_bars_on_a_tall_strip(dark):
    from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
    from chordnotepad.chord_sheet import piano_roll
    from chordnotepad.chord_sheet.ops import RectOp, TextOp
    from chordnotepad.chord_sheet.pack import collect_view
    from chordnotepad.services.song_parser_service import SongParserService
    from chordnotepad.services.song_renderer import SongRenderer

    rendered = SongRenderer().render(
        lines=SongParserService().detect_chords_in_text("{key: Eb}\nEb*4  Ab*4\n"),
        initial_key="C", initial_bpm=100, initial_time_sig=(4, 4),
        note_picker=GuitarChordPicker("standard"))
    view = collect_view(rendered, piano_roll.PianoRollRenderer(), 1.0, 400.0)
    labels = [op for op in view.content if isinstance(op, TextOp) and "note-label" in op.tags]
    assert labels and any(op.s.startswith("Eb") for op in labels)
    surface = QColor("#252629") if dark else SURFACE
    image, _ = paint(view, width=260, height=400, dpr=1.25, dark=dark, surface=surface)
    ink = themed_color(piano_roll.NOTE_LABEL, QColor(piano_roll.NOTE_LABEL), dark, surface)
    fill = themed_color(piano_roll.NOTE_FILL, QColor(piano_roll.NOTE_FILL), dark, surface)
    for label in labels:
        bar = next(op for op in view.content if isinstance(op, RectOp)
                   and label.tags[-1] in op.tags and label.tags[0] in op.tags)
        assert bar.radius > 0
        # The bar's middle holds its fill, and its name's ink inside it.
        box = [image.pixelColor(round(x * 1.25), round(y * 1.25))
               for x in range(int(bar.x) + 2, int(bar.x + 24)) for y in range(int(bar.y) + 2, int(bar.y + bar.h) - 1)]
        assert any(abs(c.lightness() - ink.lightness()) < 30 for c in box), label.s
        assert any(c.name() == fill.name() for c in box)
        # The corners are cut.
        assert image.pixelColor(round(bar.x * 1.25), round(bar.y * 1.25)).name() != fill.name()


def test_text_and_glyphs_land_on_device_pixels_at_125():
    painter = SheetPainter()
    painter.dpr = 1.25
    for x in (0.1, 3.3, 10.7, 99.99):
        assert (painter.snap(x) * 1.25) == pytest.approx(round(painter.snap(x) * 1.25), abs=1e-9)


def test_every_sheet_font_is_inter_unhinted():
    from PySide6.QtGui import QFont
    painter = SheetPainter()
    font, _ = painter.font(10, True)
    assert font.family() == "Inter" and font.bold() and font.pixelSize() == 13
    assert font.hintingPreference() == QFont.HintingPreference.PreferNoHinting


@pytest.mark.parametrize("height", [130.0, 160.0, 450.0, 600.0])
def test_staff_chord_names_as_inter_draws_them_stay_in_their_slots(height):
    # The core estimates the names' widths; Inter Bold (the Qt sheet's font)
    # must agree: no name past its slot, so neighbours never run together
    # ("Gmaj7Am7" on the tall Play strip).
    from tests.test_chord_sheet_staff_card import example_song, paint as paint_staff, symbol_boxes
    painter = SheetPainter()
    layout, ops = paint_staff(example_song(), height=height)

    def measured(text):
        size = next(op.size for op in ops.ops if getattr(op, "s", None) == text and op.bold)
        return painter.font(size, True)[1].horizontalAdvance(text) / (size * sheet_paint.PT_TO_PX)

    boxes = symbol_boxes(layout, ops, ems=measured)
    assert len(boxes) > 20
    for left, right, slot_left, slot_right in boxes:
        assert slot_left <= left and right <= slot_right


# -- the QML type ----------------------------------------------------------------------


def qmltypes(cls, module, name, file):
    """The .qmltypes text describing ``cls`` (what qml/CNSheet holds)."""
    m = cls.staticMetaObject
    lines = ["import QtQuick.tooling 1.2", "",
             "// For qmllint: " + module + "." + name + " is registered from Python",
             "// (" + file + ", register_types). tests/qt/test_qt_chord_sheet.py checks this against the class.",
             "Module {", "    Component {",
             f'        file: "{file}"', f'        name: "{name}"',
             '        accessSemantics: "reference"', '        prototype: "QQuickPaintedItem"',
             f'        exports: ["{module}/{name} 1.0"]', "        exportMetaObjectRevisions: [256]"]
    for i in range(m.propertyOffset(), m.propertyCount()):
        p = m.property(i)
        t = p.typeName()
        parts = [f'name: "{p.name()}"']
        parts += [f'type: "{t[:-1]}"', "isPointer: true"] if t.endswith("*") else [f'type: "{t}"']
        if not p.isWritable():
            parts.append("isReadonly: true")
        if p.isConstant():
            parts.append("isConstant: true")
        if p.hasNotifySignal():
            parts.append(f'notify: "{p.notifySignal().name().data().decode()}"')
        parts.append(f"index: {i - m.propertyOffset()}")
        lines.append("        Property { " + "; ".join(parts) + " }")
    for i in range(m.methodOffset(), m.methodCount()):
        me = m.method(i)
        if me.name().data().decode().startswith("_"):
            continue                   # Python's own slots (connections), not for QML
        kind = "Signal" if me.methodType() == me.MethodType.Signal else "Method"
        params = [bytes(t).decode() for t in me.parameterTypes()]
        head = f'        {kind} {{ name: "{me.name().data().decode()}"'
        if me.typeName() and me.typeName() != "void":
            head += f'; type: "{me.typeName()}"'
        if not params:
            lines.append(head + " }")
            continue
        lines.append(head)
        lines += [f'            Parameter {{ name: "p{n}"; type: "{t}" }}' for n, t in enumerate(params)]
        lines.append("        }")
    lines += ["    }", "}", ""]
    return "\n".join(lines)


def test_the_qmltypes_describe_the_sheet_view():
    expected = qmltypes(chord_sheet.SheetView, chord_sheet.QML_MODULE, chord_sheet.QML_TYPE, "chord_sheet.py")
    path = QML_DIR / "CNSheet" / "sheet.qmltypes"
    assert path.read_text(encoding="utf-8") == expected, \
        "regenerate qml/CNSheet/sheet.qmltypes with this test's qmltypes():\n" + expected


# -- the window ------------------------------------------------------------------------


class Sheet(Bar):
    """The editor and player bar harness plus the chord sheet's items."""

    @property
    def view(self):
        return self.it("sheetView")

    @property
    def model(self):
        return self.harness.app.sheet

    def sheet_state(self, key):
        return self.store.state("ChordSheetState").value(key)

    def theme(self):
        return qmlEngine(self.window).singletonInstance("CNTheme", "Theme")

    def wait_sheet(self, view=None):
        """Until the sheet shows the current state's buffer (``view`` when given)."""
        self.qtbot.waitUntil(lambda: self.sheet_state("song_revision") and self.view.property("hasSheet")
                             and not self.model.property("loading")
                             and (view is None or self.model.sheet.view_id == view), timeout=5000)
        self.run(50)

    def grab(self):
        return self.window.grabWindow()

    def at(self, x, y):
        """Window point of view-item point (x, y)."""
        return self.view.mapToScene(QPointF(x, y)).toPoint()

    def slot_point(self, index, dy=None):
        sheet = self.model.sheet
        x, w = sheet.slot(index)
        return self.at(sheet.gutter_width + x + w / 2 - self.view.property("scrollX"),
                       dy if dy is not None else sheet.lane_height + sheet.content_height / 2)

    def wheel_at(self, point, dy=0, dx=0, modifiers=NO_MODIFIER):
        pos = QPointF(point)
        event = QWheelEvent(pos, QPointF(self.window.mapToGlobal(point)), QPoint(0, 0),
                            QPoint(dx, dy), Qt.MouseButton.NoButton, modifiers,
                            Qt.ScrollPhase.NoScrollPhase, False)
        self.qapp.sendEvent(self.window, event)
        self.run()

    def config(self, key):
        return self.harness.app.core.config.get(key)


def make_sheet(qapp, qtbot, tmp_path, text=TEXT, **config):
    harness = start(qapp, qtbot, tmp_path, **config)
    sh = Sheet(harness, qtbot)
    qtbot.waitUntil(lambda: sh.area.hasActiveFocus(), timeout=1000)
    harness.player.auto_play = False
    song(sh, text)
    return sh


@pytest.fixture
def sh(qapp, qtbot, tmp_path):
    sh = make_sheet(qapp, qtbot, tmp_path)
    yield sh
    finish(sh)


def finish(sh):
    warnings, unexpected = list(sh.harness.app.warnings), list(sh.harness.unexpected)
    sh.harness.shutdown()
    sh.qtbot.wait(1)
    assert warnings == [] and unexpected == []


def test_play_shows_the_sheet_and_paints_the_known_song(sh):
    sh.to_play(1200)
    sh.wait_sheet("keyboard")
    sheet = sh.model.sheet
    # The buffer is the session's own, for the strip's height without the lane.
    data = sh.harness.app._session.chord_sheet_buffer(float(sh.model._height))
    packed = unpack(data)
    assert packed.view_id == "keyboard" and len(sheet.content) == len(packed.content)
    assert [s[2] for s in sheet.slots] == [s.chord_index for s in packed.slots]
    assert sh.model._height == math.floor(sh.view.height() - sheet.lane_height)
    # Pixels: the lane's label, the piano roll's notes (the hands' colours), the gutter's keys.
    image = sh.grab()
    top_left = sh.view.mapToScene(QPointF(0, 0)).toPoint()
    colors = {image.pixelColor(top_left.x() + x, top_left.y() + y).name()
              for x in range(0, int(sh.view.width()), 3) for y in range(0, int(sh.view.height()), 3)}
    assert HAND_COLORS["rh"] in colors and HAND_COLORS["lh"] in colors
    assert "#ffffff" in colors                                  # the gutter's white keys
    assert sh.view.last_paint_ops > 0


def test_only_the_viewport_is_painted(qapp, qtbot, tmp_path):
    long_song = "{label: verse}\n" + "C   G   Am  F\n" * 30
    sh = make_sheet(qapp, qtbot, tmp_path, text=long_song)
    try:
        sh.to_play(1000)
        sh.wait_sheet()
        sheet = sh.model.sheet
        total = len(sheet.content) + len(sheet.lane)
        assert sheet.content_width > 4 * sh.view.width()
        sh.view.update()
        sh.run(100)
        assert 0 < sh.view.last_paint_ops < total / 3
    finally:
        finish(sh)


def test_the_view_tabs_send_the_view_and_a_fallback_isnt_kept(qapp, qtbot, tmp_path):
    # Fret cards saved, but the piano voicing has no fingerings: the core
    # falls back to the piano roll and the saved choice stays.
    sh = make_sheet(qapp, qtbot, tmp_path, chord_sheet_view="fret")
    try:
        sh.to_play(1200)
        sh.wait_sheet("keyboard")
        tabs = {name: sh.it("sheetTab:" + name) for name in ("keyboard", "staff", "fret", "tab")}
        assert sh.sheet_state("active_view") == "keyboard" and sh.config("chord_sheet_view") == "fret"
        assert [v["label"] for v in sh.sheet_state("views")] == ["Piano roll", "Staff", "Fret cards", "Tab"]
        # The disabled tab says why (the core's Qt text), after 400 ms.
        reason = sh.sheet_state("disabled_reason")
        assert reason and "Voicing button" in reason
        sh.hover(tabs["fret"])
        sh.qtbot.waitUntil(lambda: reason in texts_shown(sh.window.contentItem()), timeout=2000)
        # A click on a disabled tab sends nothing; on Staff it switches and is kept.
        sh.click_on(tabs["fret"])
        sh.run()
        assert sh.sent("set_chord_sheet_view") == []
        sh.click_on(tabs["staff"])
        sh.wait_sheet("staff")
        assert sh.sent("set_chord_sheet_view") == [{"view_id": "staff"}]
        assert sh.config("chord_sheet_view") == "staff"
    finally:
        finish(sh)


def test_alt_digits_switch_the_view(sh):
    sh.to_play(1200)
    sh.wait_sheet("keyboard")
    QTest.keyClick(sh.window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)
    sh.wait_sheet("staff")
    QTest.keyClick(sh.window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)   # off: piano voicing
    sh.run()
    assert sh.sheet_state("active_view") == "staff"
    QTest.keyClick(sh.window, Qt.Key.Key_1, Qt.KeyboardModifier.AltModifier)
    sh.wait_sheet("keyboard")


def test_zoom_buttons_and_ctrl_wheel_follow_the_cores_rules(sh):
    sh.to_play(1200)
    sh.wait_sheet("keyboard")
    # The piano roll zooms too (time only: its rows fill the strip at any zoom).
    roll_width = sh.model.sheet.content_width
    roll_height = sh.model.sheet.content_height
    assert sh.it("sheetZoomIn").isVisible() and sh.it("sheetZoomLabel").isVisible()
    sh.click_on(sh.it("sheetZoomIn"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.2), timeout=2000)
    sh.wait_sheet("keyboard")
    sh.qtbot.waitUntil(lambda: sh.model.sheet.zoom == pytest.approx(1.2), timeout=2000)
    assert sh.model.sheet.content_width > roll_width * 1.1
    assert sh.model.sheet.content_height == roll_height
    sh.store.submit("set_chord_sheet_view", {"view_id": "staff"})
    sh.wait_sheet("staff")
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == 1.0, timeout=2000)
    width = sh.model.sheet.content_width
    assert sh.it("sheetZoomIn").isVisible()
    sh.click_on(sh.it("sheetZoomIn"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.2), timeout=2000)
    sh.wait_sheet("staff")
    assert sh.it("sheetZoomLabel").property("text") == "120%"
    assert sh.model.sheet.content_width > width * 1.1
    # Ctrl+wheel: a step per notch, about the pointer.
    sh.wheel_at(sh.slot_point(1), dy=240, modifiers=CTRL)
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.728), timeout=2000)
    assert sh.sent("chord_sheet_zoom") == [{"step": 1}, {"step": 1}, {"step": 2}]
    # Up to 250%, where + turns off; persisted per view (only values that aren't 1).
    sh.store.submit("chord_sheet_zoom", {"step": 10})
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(2.5), timeout=2000)
    sh.run()
    assert not sh.it("sheetZoomIn").isEnabled() and sh.it("sheetZoomOut").isEnabled()
    assert sh.config("chord_sheet_zoom") == {"keyboard": 1.2, "staff": 2.5}
    # The piano roll keeps its own.
    sh.store.submit("set_chord_sheet_view", {"view_id": "keyboard"})
    sh.qtbot.waitUntil(lambda: sh.sheet_state("zoom") == pytest.approx(1.2), timeout=2000)


def test_the_wheel_scrolls_and_stops_at_the_ends(sh):
    sh.to_play(700)
    sh.wait_sheet()
    view = sh.view
    centre = sh.at(view.width() / 2, view.height() / 2)
    assert view.property("scrollX") == 0
    sh.wheel_at(centre, dy=-120)
    assert view.property("scrollX") == 120
    sh.wheel_at(centre, dx=-120)                         # sideways too
    assert view.property("scrollX") == 240
    sh.wheel_at(centre, dy=120 * 100)
    assert view.property("scrollX") == 0
    sh.wheel_at(centre, dy=-120 * 100)
    end = sh.model.sheet.content_width - (view.width() - sh.model.sheet.gutter_width)
    assert view.property("scrollX") == pytest.approx(end)
    assert sh.sent("chord_sheet_zoom") == []


def test_the_gutter_stays_while_the_content_scrolls(sh):
    sh.to_play(700)
    sh.wait_sheet("keyboard")
    gutter = sh.model.sheet.gutter_width
    assert gutter > 0

    def strip(x0, x1):
        image = sh.grab()
        o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
        return [image.pixel(o.x() + x, o.y() + y) for x in range(int(x0), int(x1))
                for y in range(30, int(sh.view.height()) - 10, 4)]

    before_gutter, before_content = strip(0, gutter - 1), strip(gutter + 5, gutter + 300)
    sh.view.setProperty("scrollX", 200)
    sh.run(50)
    assert strip(0, gutter - 1) == before_gutter
    assert strip(gutter + 5, gutter + 300) != before_content


def test_a_click_auditions_and_moves_the_playhead(sh):
    sh.to_play(1200)
    sh.wait_sheet()
    index = 2                                   # "Am" in the first line
    QTest.mouseClick(sh.window, LEFT, NO_MODIFIER, sh.slot_point(index))
    sh.qtbot.waitUntil(lambda: sh.sent("audition") == [{"index": index}], timeout=2000)
    sh.qtbot.waitUntil(lambda: sh.playback("playhead_offset") == TEXT.index("Am"), timeout=2000)
    sh.qtbot.waitUntil(lambda: sh.view.property("cursorIndex") == index, timeout=2000)
    # The lane and the gutter don't audition.
    QTest.mouseClick(sh.window, LEFT, NO_MODIFIER, sh.slot_point(index, dy=5))
    QTest.mouseClick(sh.window, LEFT, NO_MODIFIER, sh.at(3, 80))
    sh.run()
    assert sh.sent("audition") == [{"index": index}]


def test_the_playing_column_is_highlighted_and_followed(sh):
    sh.to_play(700)
    sh.wait_sheet()
    view, sheet = sh.view, sh.model.sheet
    viewport = view.width() - sheet.gutter_width
    sh.store.submit("play_pause")
    sh.wait_status("playing")
    sh.ping(1)
    assert view.property("playingIndex") == 0
    # The column: the playing colour over the paper, in a gap of the first slot.
    x, w = sheet.slot(0)
    image = sh.grab()
    o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
    column = {image.pixelColor(o.x() + int(sheet.gutter_width + x + 2), o.y() + y).name()
              for y in range(int(sheet.lane_height) + 4, int(view.height()) - 4)}
    assert SURFACE.name() not in column
    # Following: chords inside 25-70% don't scroll; past 70% it snaps to 25%.
    scrolled_at = None
    for _ in range(12):
        sh.ping(1)
        index = view.property("playingIndex")
        if view.property("scrollX") > 0:
            scrolled_at = index
            break
    assert scrolled_at is not None
    x, w = sheet.slot(scrolled_at)
    assert x + w / 2 - view.property("scrollX") == pytest.approx(0.25 * viewport, abs=1)
    # Stop clears the column.
    sh.store.submit("stop")
    sh.qtbot.waitUntil(lambda: view.property("playingIndex") == -1, timeout=2000)


def test_the_playing_column_repaint_is_partial(sh):
    sh.to_play(1400)
    sh.wait_sheet()
    view = sh.view
    rects = []
    original = view.update

    def spy(*args):
        rects.append(args[0] if args else None)
        return original(*args)

    view.update = spy
    view.setProperty("playingIndex", 1)
    view.setProperty("playingIndex", 2)
    sh.run(50)
    assert rects and all(r is not None and r.width() < view.width() / 4 for r in rects)


def test_a_follow_scroll_then_a_cursor_move_repaints_everything(sh):
    # Tibi, 2026-11-15: bits of the old frame stayed around the playing
    # column. Qt keeps only update(rect) when it follows a plain update() in
    # the same frame: the follow-scroll's whole repaint was lost to the
    # cursor's two columns.
    sh.to_play(700)
    sh.wait_sheet()
    view, sheet = sh.view, sh.model.sheet
    count = 0
    while sheet.slot(count) is not None:
        count += 1
    view.setProperty("playingIndex", 0)
    view.setProperty("cursorIndex", 0)
    sh.run(50)
    o = view.mapToScene(QPointF(0, 0)).toPoint()
    area = QRect(o.x(), o.y(), int(view.width()), int(view.height()))
    # One frame: the playing chord jumps past the band (the strip scrolls),
    # then the cursor moves (a partial repaint of its columns).
    view.setProperty("playingIndex", count - 1)
    view.setProperty("cursorIndex", count - 1)
    assert view.property("scrollX") > 0
    sh.run(50)
    after = sh.grab().copy(area)
    view.update()
    sh.run(50)
    assert after == sh.grab().copy(area)


def test_edit_shows_the_panel_with_f9_and_play_always(sh):
    pane, host = sh.it("chordSheetPane"), sh.it("editSheetHost")
    assert sh.window.property("mode") == "edit" and sh.sheet_state("visible") is False
    assert not host.isVisible() and sh.view.property("active") is False
    QTest.keyClick(sh.window, Qt.Key.Key_F9)
    sh.qtbot.waitUntil(lambda: sh.sheet_state("visible") is True, timeout=2000)
    sh.run()
    assert host.isVisible() and pane.parentItem() is host and sh.view.property("active") is True
    sh.wait_sheet()
    assert sh.config("chord_sheet_visible") is True
    # Edit's header: the Voicing selector and ×.
    assert sh.it("sheetVoicing").isVisible() and sh.it("sheetClose").isVisible()
    # Play: the strip, without them; F9 does nothing there.
    sh.to_play(1200)
    assert pane.parentItem() is sh.it("playSheetHost")
    assert not sh.it("sheetVoicing").isVisible() and not sh.it("sheetClose").isVisible()
    sent = len(sh.sent("set_chord_sheet_visible"))
    QTest.keyClick(sh.window, Qt.Key.Key_F9)
    sh.run()
    assert len(sh.sent("set_chord_sheet_visible")) == sent
    # Back in Edit, × hides it.
    sh.window.setProperty("mode", "edit")
    sh.run()
    sh.click_on(sh.it("sheetClose"))
    sh.qtbot.waitUntil(lambda: sh.sheet_state("visible") is False, timeout=2000)
    assert sh.sent("set_chord_sheet_on_screen")[-1] == {"on_screen": None}


def test_a_minimized_window_takes_the_sheet_off_screen(sh):
    sh.to_play(1200)
    sh.window.showMinimized()
    sh.qtbot.waitUntil(lambda: bool(sh.sent("set_chord_sheet_on_screen"))
                       and sh.sent("set_chord_sheet_on_screen")[-1] == {"on_screen": False}, timeout=2000)
    sh.window.showNormal()
    sh.qtbot.waitUntil(lambda: sh.sent("set_chord_sheet_on_screen")[-1] == {"on_screen": True}, timeout=2000)


def test_the_voicing_selector_is_locked_while_playing(sh):
    sh.store.submit("set_chord_sheet_visible", {"visible": True})
    sh.qtbot.waitUntil(lambda: sh.it("sheetVoicing").isVisible(), timeout=2000)
    button = sh.it("sheetVoicing")
    assert button.isEnabled() and "Piano" in button.property("text")
    sh.store.submit("play_pause")
    sh.wait_status("playing")
    sh.qtbot.waitUntil(lambda: not button.isEnabled(), timeout=2000)
    reason = sh.store.state("VoicingMenuState").value("locked_reason")
    sh.hover(sh.it("sheetVoicingTip"))
    sh.qtbot.waitUntil(lambda: any(reason in t for t in texts_shown(sh.window.contentItem())),
                       timeout=2500)


def test_the_voicing_label_collapses_below_150_units(sh):
    sh.store.submit("set_chord_sheet_visible", {"visible": True})
    sh.qtbot.waitUntil(lambda: sh.it("sheetVoicing").isVisible(), timeout=2000)
    button, pane = sh.it("sheetVoicing"), sh.it("chordSheetPane")
    u = qmlEngine(sh.window).singletonInstance("CNTheme", "Theme").property("u")
    sh.window.setWidth(1400)
    sh.qtbot.waitUntil(lambda: pane.width() > 150 * u, timeout=2000)
    sh.qtbot.waitUntil(lambda: button.property("showText") is True, timeout=1000)
    sh.window.setWidth(round(pane.mapToScene(QPointF(0, 0)).x() + 140 * u))
    sh.qtbot.waitUntil(lambda: pane.width() <= 150 * u, timeout=2000)
    sh.qtbot.waitUntil(lambda: button.property("showText") is False, timeout=1000)


def test_the_panel_height_is_restored_and_kept_after_a_drag(qapp, qtbot, tmp_path):
    sh = make_sheet(qapp, qtbot, tmp_path, chord_sheet_visible=True, chord_sheet_logical_height=180)
    try:
        host = sh.it("editSheetHost")
        sh.qtbot.waitUntil(lambda: abs(host.height() - 180) <= 1, timeout=2000)
        # Drag the handle up by 60 px.
        top = host.mapToScene(QPointF(host.width() / 2, 0)).toPoint() - QPoint(0, 2)
        QTest.mousePress(sh.window, LEFT, NO_MODIFIER, top)
        for dy in range(10, 70, 10):
            QTest.mouseMove(sh.window, top - QPoint(0, dy))
            sh.run(10)
        QTest.mouseRelease(sh.window, LEFT, NO_MODIFIER, top - QPoint(0, 60))
        sh.qtbot.waitUntil(lambda: bool(sh.sent("set_logical_chord_sheet_height")), timeout=2000)
        saved = sh.sent("set_logical_chord_sheet_height")[-1]
        assert saved["height"] == round(host.height()) and abs(saved["height"] - 240) <= 3
        assert saved["scale"] == 1.0
        sh.qtbot.waitUntil(lambda: sh.config("chord_sheet_logical_height") == saved["height"], timeout=2000)
    finally:
        finish(sh)


def test_dark_paints_the_sheet_on_the_dark_panel(sh):
    sh.to_play(1200)
    sh.wait_sheet()
    theme = sh.theme()
    theme.setProperty("dark", True)
    sh.run(100)
    image = sh.grab()
    o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
    sheet = sh.model.sheet
    # The lane's paper (top right, past every label) is the dark panel.
    assert image.pixelColor(o.x() + int(sh.view.width()) - 3, o.y() + 3) == QColor("#252629")
    colors = {image.pixelColor(o.x() + x, o.y() + y).name()
              for x in range(int(sheet.gutter_width), int(sh.view.width()), 3)
              for y in range(0, int(sh.view.height()), 3)}
    assert "#78a6d8" in colors and "#d09a6c" in colors        # the hands' dark colours
    theme.setProperty("dark", False)


def test_the_piano_roll_keyboard_has_no_holes_and_its_rows_follow_the_keys(sh):
    sh.to_play(1200)
    sh.wait_sheet("keyboard")
    theme = sh.theme()
    sheet = sh.model.sheet
    bottom = sh.view.height() - sheet.lane_height - 4
    keys = [item[1] for item in sheet.gutters[0].items
            if item[0] in (sheet_paint.K_RECT, sheet_paint.K_RRECT)
            and item[2] == sheet_paint.GUTTER_BLACK
            and item[1].bottom() + item[1].height() < bottom]
    assert keys
    o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
    try:
        for dark in (False, True):
            theme.setProperty("dark", dark)
            sh.run(100)
            image = sh.grab()
            surface = QColor("#252629") if dark else QColor(theme.property("panel"))
            white_key = sheet_paint.gutter_palette([sheet_paint.GUTTER_WHITE], dark, surface)[
                sheet_paint.GUTTER_WHITE]
            black_row = themed_color(sheet_paint.ROLL_BLACK_ROW, QColor(sheet_paint.ROLL_BLACK_ROW),
                                     dark, surface)
            for key in keys:
                y = o.y() + int(sheet.lane_height + key.center().y())
                # Beside a black key: the white keys' colour, not the panel.
                assert image.pixelColor(o.x() + int(key.right()) + 3, y) == white_key, (dark, key)
                # Its row across the content is shaded wherever no note covers
                # it (never the bare paper); the white-key row under it isn't.
                row = [image.pixelColor(o.x() + x, y).name()
                       for x in range(int(sheet.gutter_width) + 2, int(sh.view.width()) - 2)]
                below = [image.pixelColor(o.x() + x, y + int(key.height())).name()
                         for x in range(int(sheet.gutter_width) + 2, int(sh.view.width()) - 2)]
                assert black_row.name() in row and surface.name() not in row, (dark, key)
                assert black_row.name() not in below, (dark, key)
    finally:
        theme.setProperty("dark", False)


def test_the_sheet_at_125_percent_is_painted_on_device_pixels(sh):
    sh.to_play(1200)
    sh.wait_sheet()
    sh.view.setProperty("dpr", 1.25)
    sh.view.setProperty("scrollX", 33.3)
    sh.run(50)
    assert (sh.view._origin() * 1.25) == pytest.approx(round(sh.view._origin() * 1.25))
    assert sh.view.last_paint_ops > 0


def test_the_staff_gutter_follows_the_key_and_the_lane_names_the_sections(qapp, qtbot, tmp_path):
    text = "{label: verse}\nC   G   Am  F\n" * 4 + "{key: D}\n{label: bridge}\nD   A   Bm  G\n" * 4
    sh = make_sheet(qapp, qtbot, tmp_path, text=text, chord_sheet_view="staff")
    try:
        sh.to_play(700)
        sh.wait_sheet("staff")
        sheet = sh.model.sheet
        lane = [item[3] for item in sheet.lane.items if item[0] == sheet_paint.K_TEXT]
        assert lane == ["verse", "Key D · bridge"]               # the directives too
        first = sheet.gutter_at(0)
        assert first is not None and sheet.gutter_width > 0
        # Scrolled to the D major part, the gutter shows its key signature
        # (another variant), painted at the item's left.
        sh.view.setProperty("scrollX", sheet.content_width)
        sh.run(50)
        assert sheet.gutter_at(sh.view.property("scrollX")) is not first
        image = sh.grab()
        o = sh.view.mapToScene(QPointF(0, 0)).toPoint()
        inks = [image.pixelColor(o.x() + x, o.y() + y) for x in range(int(sheet.gutter_width))
                for y in range(int(sheet.lane_height), int(sh.view.height()))]
        assert any(c.lightness() < 100 for c in inks)          # the clefs and the sharps
    finally:
        finish(sh)
