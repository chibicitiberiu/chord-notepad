"""Tk replay of recorded chord-sheet draw ops.

The renderers and their op data model live in :mod:`chord_sheet.ops` (headless,
shared with Android); this is the desktop-only half that turns the recorded ops
into ``tk.Canvas`` items.
"""

from typing import Dict, List, Sequence

from chord_sheet.ops import (
    ImageOp,
    LineOp,
    OvalOp,
    Point,
    PolygonOp,
    RectOp,
    TextOp,
)


def _flatten(points: Sequence[Point]) -> List[float]:
    """Flatten ``[(x0, y0), (x1, y1), ...]`` to ``[x0, y0, x1, y1, ...]``."""
    flat: List[float] = []
    for px, py in points:
        flat.append(px)
        flat.append(py)
    return flat


def replay(ops: Sequence[object], canvas, images: Dict[str, object]) -> None:
    """Replay recorded ops onto a real ``tk.Canvas``.

    Args:
        ops: Recorded ops, in order (typically ``DrawOps.ops``).
        canvas: A ``tk.Canvas`` (or compatible) to draw onto.
        images: Mapping from asset key to a Tk image object for
            :class:`ImageOp`; unknown keys are silently skipped.

    This is intentionally thin: one canvas call per op, no layout or state.
    Text ops resolve to ``TkDefaultFont`` at the requested size/weight.
    """
    import tkinter.font as tkfont

    for op in ops:
        tags = op.tags
        if isinstance(op, RectOp):
            canvas.create_rectangle(
                op.x, op.y, op.x + op.w, op.y + op.h,
                fill=op.fill or "", outline=op.outline or "", width=op.width, tags=tags,
            )
        elif isinstance(op, LineOp):
            canvas.create_line(*_flatten(op.points), fill=op.fill, width=op.width, tags=tags)
        elif isinstance(op, OvalOp):
            canvas.create_oval(
                op.x, op.y, op.x + op.w, op.y + op.h,
                fill=op.fill or "", outline=op.outline or "", width=op.width, tags=tags,
            )
        elif isinstance(op, PolygonOp):
            canvas.create_polygon(
                *_flatten(op.points), fill=op.fill, smooth=op.smooth, tags=tags
            )
        elif isinstance(op, TextOp):
            weight = "bold" if op.bold else "normal"
            font = tkfont.Font(family="TkDefaultFont", size=op.size, weight=weight)
            canvas.create_text(
                op.x, op.y, text=op.s, anchor=op.anchor, fill=op.fill, font=font, tags=tags
            )
        elif isinstance(op, ImageOp):
            image = images.get(op.key)
            if image is not None:
                canvas.create_image(op.x, op.y, image=image, anchor=op.anchor, tags=tags)
