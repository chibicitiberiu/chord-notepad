"""Tests for the chord-sheet draw-op recorder (``chord_sheet.ops``).

Recording is headless and exercised in full. The Qt painter that replays the
ops (``chordnotepad_desktop/sheet_paint.py``) is tested in
tests/qt/test_qt_chord_sheet.py.
"""

from chordnotepad.chord_sheet.ops import (
    DrawOps,
    RectOp,
    LineOp,
    OvalOp,
    PolygonOp,
    TextOp,
    ImageOp,
)


def test_records_ops_in_call_order():
    ops = DrawOps()
    ops.rect(0, 0, 10, 10)
    ops.text(5, 5, "C", fill="black")
    ops.line([(0, 0), (10, 10)], fill="red")
    types = [type(o) for o in ops.ops]
    assert types == [RectOp, TextOp, LineOp]


def test_rect_field_capture():
    ops = DrawOps()
    ops.rect(1, 2, 3, 4, fill="a", outline="b", width=2.0, tags=("t",))
    (op,) = ops.ops
    assert (op.x, op.y, op.w, op.h) == (1, 2, 3, 4)
    assert op.fill == "a" and op.outline == "b" and op.width == 2.0
    assert op.tags == ("t",)


def test_text_field_capture():
    ops = DrawOps()
    ops.text(4, 6, "Am", anchor="center", size=12, fill="navy", bold=True, tags=("x", "y"))
    (op,) = ops.ops
    assert isinstance(op, TextOp)
    assert (op.x, op.y, op.s) == (4, 6, "Am")
    assert op.anchor == "center" and op.size == 12 and op.fill == "navy"
    assert op.bold is True and op.tags == ("x", "y")


def test_line_and_polygon_capture_points_as_tuples():
    ops = DrawOps()
    ops.line([(0, 0), (1, 1), (2, 0)], fill="k")
    ops.polygon([(0, 0), (5, 0), (5, 5)], fill="g", smooth=True)
    line, poly = ops.ops
    assert isinstance(line, LineOp) and line.points == ((0, 0), (1, 1), (2, 0))
    assert isinstance(poly, PolygonOp) and poly.smooth is True
    assert poly.points == ((0, 0), (5, 0), (5, 5))


def test_oval_and_image_capture():
    ops = DrawOps()
    ops.oval(1, 1, 8, 8, outline="c")
    ops.image(3, 3, "clef_treble", anchor="w", tags=("img",))
    oval, img = ops.ops
    assert isinstance(oval, OvalOp) and oval.outline == "c"
    assert isinstance(img, ImageOp) and img.key == "clef_treble"
    assert img.anchor == "w" and img.tags == ("img",)


def test_tags_default_to_empty_tuple():
    ops = DrawOps()
    ops.rect(0, 0, 1, 1)
    assert ops.ops[0].tags == ()

