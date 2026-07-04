"""A draw-op recorder decoupling chord-sheet renderers from Tkinter.

Renderers describe what to draw by appending primitive ops to a
:class:`DrawOps` recorder; they never call a real ``tk.Canvas``. This keeps
renderers pure and headless-testable -- a test can inspect the recorded ops
directly, without a display. :func:`replay` walks the recorded ops onto a real
canvas at paint time.

Coordinates are content-space pixels (the strip's own left-to-right layout);
the panel applies scrolling via the canvas ``xview``. Every op carries a
``tags`` tuple so the panel can hit-test and restyle groups of items (e.g. all
items belonging to one chord slot).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

# A point is an (x, y) pair; a poly-line/polygon is a sequence of points.
Point = Tuple[float, float]


@dataclass
class RectOp:
    """A rectangle from its top-left ``(x, y)`` spanning ``w`` x ``h`` px."""

    x: float
    y: float
    w: float
    h: float
    fill: str = None
    outline: str = None
    width: float = 1.0
    tags: Tuple[str, ...] = ()


@dataclass
class LineOp:
    """A poly-line through ``points`` (two or more ``(x, y)`` pairs)."""

    points: Tuple[Point, ...]
    fill: str = None
    width: float = 1.0
    tags: Tuple[str, ...] = ()


@dataclass
class OvalOp:
    """An oval inscribed in the box from ``(x, y)`` spanning ``w`` x ``h`` px."""

    x: float
    y: float
    w: float
    h: float
    fill: str = None
    outline: str = None
    width: float = 1.0
    tags: Tuple[str, ...] = ()


@dataclass
class PolygonOp:
    """A filled polygon through ``points`` (three or more ``(x, y)`` pairs)."""

    points: Tuple[Point, ...]
    fill: str = None
    smooth: bool = False
    tags: Tuple[str, ...] = ()


@dataclass
class TextOp:
    """A run of text anchored at ``(x, y)``.

    ``anchor`` follows Tk's compass convention (``'nw'``, ``'center'``, ...).
    ``size`` is a point size; ``bold`` selects a bold weight. The concrete font
    family is chosen by :func:`replay` so renderers stay font-agnostic.
    """

    x: float
    y: float
    s: str
    anchor: str = "nw"
    size: int = 10
    fill: str = None
    bold: bool = False
    tags: Tuple[str, ...] = ()


@dataclass
class ImageOp:
    """A named embedded asset (e.g. ``'clef_treble'``) placed at ``(x, y)``.

    ``key`` is resolved against the ``images`` mapping passed to :func:`replay`;
    unknown keys are skipped so a missing asset never crashes a paint.
    """

    x: float
    y: float
    key: str
    anchor: str = "nw"
    tags: Tuple[str, ...] = ()


class DrawOps:
    """Ordered recorder of primitive draw ops.

    Each ``rect``/``line``/``oval``/``polygon``/``text``/``image`` call appends
    one inspectable record to :attr:`ops`, preserving call order. Renderers
    receive a fresh recorder per paint and only append; they never read Tk.
    """

    def __init__(self) -> None:
        """Create an empty recorder."""
        self.ops: List[object] = []

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = None,
        outline: str = None,
        width: float = 1.0,
        tags: Sequence[str] = (),
    ) -> None:
        """Record a rectangle. See :class:`RectOp`."""
        self.ops.append(
            RectOp(x, y, w, h, fill=fill, outline=outline, width=width, tags=tuple(tags))
        )

    def line(
        self,
        points: Sequence[Point],
        *,
        fill: str,
        width: float = 1.0,
        tags: Sequence[str] = (),
    ) -> None:
        """Record a poly-line through ``points``. See :class:`LineOp`."""
        self.ops.append(
            LineOp(tuple(points), fill=fill, width=width, tags=tuple(tags))
        )

    def oval(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = None,
        outline: str = None,
        width: float = 1.0,
        tags: Sequence[str] = (),
    ) -> None:
        """Record an oval. See :class:`OvalOp`."""
        self.ops.append(
            OvalOp(x, y, w, h, fill=fill, outline=outline, width=width, tags=tuple(tags))
        )

    def polygon(
        self,
        points: Sequence[Point],
        *,
        fill: str,
        smooth: bool = False,
        tags: Sequence[str] = (),
    ) -> None:
        """Record a filled polygon through ``points``. See :class:`PolygonOp`."""
        self.ops.append(
            PolygonOp(tuple(points), fill=fill, smooth=smooth, tags=tuple(tags))
        )

    def text(
        self,
        x: float,
        y: float,
        s: str,
        *,
        anchor: str = "nw",
        size: int = 10,
        fill: str,
        bold: bool = False,
        tags: Sequence[str] = (),
    ) -> None:
        """Record a text run anchored at ``(x, y)``. See :class:`TextOp`."""
        self.ops.append(
            TextOp(x, y, s, anchor=anchor, size=size, fill=fill, bold=bold, tags=tuple(tags))
        )

    def image(
        self,
        x: float,
        y: float,
        key: str,
        *,
        anchor: str = "nw",
        tags: Sequence[str] = (),
    ) -> None:
        """Record a named embedded asset at ``(x, y)``. See :class:`ImageOp`."""
        self.ops.append(ImageOp(x, y, key, anchor=anchor, tags=tuple(tags)))


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
