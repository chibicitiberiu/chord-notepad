"""Pack one chord-sheet view into a compact, versioned bytes buffer.

The Android UI cannot hold Python draw-op objects, so the session hands Kotlin
one ``bytes`` object per (view, zoom, height): everything the Tk panel draws
for that view, flattened. Kotlin decodes it once, caches it and draws only the
visible part. The buffer holds:

- the content ops (:meth:`StripRenderer.paint`), in content px;
- the marker-lane ops (:func:`~chord_sheet.marker_lane.build_marker_lane`);
- the hit-test / playhead boxes (:class:`SlotBox` per chord, from ``layout``);
- the frozen gutter as a few pre-painted *variants* plus the scroll positions
  where the variant changes. The staff view's gutter shows the key signature
  in effect at the first visible chord, so it gets one variant per distinct
  key signature; static gutters (piano roll) get one variant.

The byte format is specified in ``docs/ANDROID.md`` ("Chord sheet op buffer")
and versioned by :data:`FORMAT_VERSION`; :func:`unpack` is the reference
decoder (used by the tests). Output is deterministic: the same inputs give the
same bytes (strings are numbered in first-use order, floats are float32).
"""

import logging
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from chord_sheet.marker_lane import LANE_HEIGHT, build_marker_lane
from chord_sheet.ops import DrawOps, ImageOp, LineOp, OvalOp, PolygonOp, RectOp, TextOp
from chord_sheet.registry import default_renderers
from chord_sheet.renderer_interface import (
    PLAYHEAD_HIGHLIGHT,
    STRIP_BG,
    SheetContext,
    SlotBox,
    StripRenderer,
)
from models.rendered_song import RenderedSong

logger = logging.getLogger(__name__)

#: First four bytes of every buffer.
MAGIC = b"CNSB"
#: Bumped on any incompatible change to the byte layout.
FORMAT_VERSION = 1
#: String index meaning "no string" (``None``: no fill, no outline, ...).
NO_STRING = 0xFFFF

OP_RECT = 1
OP_OVAL = 2
OP_LINE = 3
OP_POLYGON = 4
OP_TEXT = 5
OP_IMAGE = 6

#: Tk anchor names by their one-byte code.
ANCHORS: Tuple[str, ...] = ("nw", "n", "ne", "w", "center", "e", "sw", "s", "se")
_ANCHOR_CODE: Dict[str, int] = {name: code for code, name in enumerate(ANCHORS)}

_HEADER = struct.Struct("<4sHHHHHHffffffII")
_STR_LEN = struct.Struct("<H")
_SLOT = struct.Struct("<Iff")
_LIST_HEAD = struct.Struct("<II")
_U16 = struct.Struct("<H")
_RUN = struct.Struct("<fH")
_BOX = struct.Struct("<BffffHHf")         # rect / oval
_LINE = struct.Struct("<BHfH")            # + points
_POLYGON = struct.Struct("<BHBH")         # + points
_TEXT = struct.Struct("<BffHBBfH")
_IMAGE = struct.Struct("<BffHB")


@dataclass(frozen=True)
class GutterRun:
    """The gutter variant in effect for every ``scroll_x > start_x``.

    Runs are sorted by ``start_x``; the first starts at ``-inf``. The variant
    for a scroll position is the one of the last run with ``start_x < scroll_x``.
    """

    start_x: float
    variant: int


@dataclass
class ViewOps:
    """Everything one packed view holds (the input of :func:`serialize` and
    the output of :func:`unpack`)."""

    view_id: str
    zoom: float
    height: float
    content_width: float
    content_height: float
    gutter_width: float
    lane_height: float
    background: str
    highlight: str
    slots: Tuple[SlotBox, ...]
    content: List[object]
    lane: List[object]
    gutter_variants: List[List[object]] = field(default_factory=list)
    gutter_runs: List[GutterRun] = field(default_factory=list)

    def gutter_variant_at(self, scroll_x: float) -> Optional[int]:
        """Index of the gutter variant to show at ``scroll_x``, or ``None``
        when the view has no gutter."""
        found = None
        for run in self.gutter_runs:
            if run.start_x < scroll_x:
                found = run.variant
            else:
                break
        return found


# -- Collect ------------------------------------------------------------------

def _gutter(renderer: StripRenderer, ctx: SheetContext, height: float,
            layout, width: float) -> Tuple[List[List[object]], List[GutterRun]]:
    """Paint each distinct gutter once and map scroll ranges onto them."""
    if width <= 0:
        return [], []
    thresholds = sorted(renderer.gutter_breakpoints(ctx, height, layout))
    starts = [-math.inf] + thresholds
    variants: List[List[object]] = []
    runs: List[GutterRun] = []
    for i, start in enumerate(starts):
        # A scroll position inside the run: just past its start, short of the next.
        if i == 0:
            probe = min(0.0, thresholds[0] - 1.0) if thresholds else 0.0
        else:
            nxt = starts[i + 1] if i + 1 < len(starts) else start + 2.0
            probe = start + min(1.0, (nxt - start) / 2.0)
        ops = DrawOps()
        renderer.paint_gutter(ops, ctx, height, probe)
        try:
            index = variants.index(ops.ops)
        except ValueError:
            index = len(variants)
            variants.append(ops.ops)
        if runs and runs[-1].variant == index:
            continue
        runs.append(GutterRun(start, index))
    return variants, runs


def collect_view(song: RenderedSong, renderer: StripRenderer, zoom: float,
                 height: float) -> ViewOps:
    """Lay out and paint one view headlessly, as the Tk panel would.

    Args:
        song: The rendered song to draw.
        renderer: The view's renderer.
        zoom: Display zoom (ignored by renderers without ``supports_zoom``).
        height: Content height in px (the strip canvas, lane excluded).

    Returns:
        The view's ops, slots and gutter variants (see :class:`ViewOps`).
    """
    ctx = SheetContext(song=song, zoom=zoom)
    layout = renderer.layout(ctx, height)
    content = DrawOps()
    renderer.paint(content, ctx, layout)
    lane = build_marker_lane(song.markers, song.chords, layout.slots,
                             LANE_HEIGHT, layout.width)
    gutter_width = float(renderer.gutter_width(ctx, height))
    variants, runs = _gutter(renderer, ctx, height, layout, gutter_width)
    return ViewOps(
        view_id=renderer.id, zoom=zoom, height=height,
        content_width=layout.width, content_height=layout.height,
        gutter_width=max(0.0, gutter_width), lane_height=LANE_HEIGHT,
        background=STRIP_BG, highlight=PLAYHEAD_HIGHLIGHT,
        slots=tuple(layout.slots), content=content.ops, lane=lane.ops,
        gutter_variants=variants, gutter_runs=runs,
    )


# -- Serialize ----------------------------------------------------------------

class _Writer:
    """Accumulates the body and the string table in first-use order."""

    def __init__(self) -> None:
        self.body = bytearray()
        self.strings: List[str] = []
        self._index: Dict[str, int] = {}

    def s(self, value: Optional[str]) -> int:
        """Intern ``value`` and return its index (``NO_STRING`` for ``None``)."""
        if value is None:
            return NO_STRING
        index = self._index.get(value)
        if index is None:
            index = len(self.strings)
            if index >= NO_STRING:
                raise ValueError("chord sheet op buffer: more than 65535 strings")
            self.strings.append(value)
            self._index[value] = index
        return index

    def tags(self, out: bytearray, tags: Sequence[str]) -> None:
        if len(tags) > 255:
            raise ValueError("chord sheet op buffer: more than 255 tags on one op")
        out.append(len(tags))
        for tag in tags:
            out += _U16.pack(self.s(tag))

    def points(self, out: bytearray, points) -> None:
        flat = [c for point in points for c in point]
        out += struct.pack(f"<{len(flat)}f", *flat)

    def op_list(self, ops: Sequence[object]) -> None:
        """Append ``u32 count, u32 nbytes`` and the encoded ops."""
        out = bytearray()
        for op in ops:
            kind = type(op)
            if kind is RectOp or kind is OvalOp:
                out += _BOX.pack(OP_RECT if kind is RectOp else OP_OVAL,
                                 op.x, op.y, op.w, op.h,
                                 self.s(op.fill), self.s(op.outline), op.width)
            elif kind is LineOp:
                out += _LINE.pack(OP_LINE, self.s(op.fill), op.width, len(op.points))
                self.points(out, op.points)
            elif kind is PolygonOp:
                out += _POLYGON.pack(OP_POLYGON, self.s(op.fill), 1 if op.smooth else 0,
                                     len(op.points))
                self.points(out, op.points)
            elif kind is TextOp:
                out += _TEXT.pack(OP_TEXT, op.x, op.y, self.s(op.s),
                                  _ANCHOR_CODE[op.anchor], 1 if op.bold else 0,
                                  op.size, self.s(op.fill))
            elif kind is ImageOp:
                out += _IMAGE.pack(OP_IMAGE, op.x, op.y, self.s(op.key),
                                   _ANCHOR_CODE[op.anchor])
            else:
                raise TypeError(f"chord sheet op buffer: unknown op {kind.__name__}")
            self.tags(out, op.tags)
        self.body += _LIST_HEAD.pack(len(ops), len(out))
        self.body += out


def serialize(view: ViewOps) -> bytes:
    """Encode a :class:`ViewOps` in the documented byte format."""
    w = _Writer()
    view_id = w.s(view.view_id)
    background = w.s(view.background)
    highlight = w.s(view.highlight)

    for slot in view.slots:
        w.body += _SLOT.pack(slot.chord_index, slot.x, slot.width)
    w.op_list(view.content)
    w.op_list(view.lane)
    w.body += _U16.pack(len(view.gutter_variants))
    for variant in view.gutter_variants:
        w.op_list(variant)
    w.body += _U16.pack(len(view.gutter_runs))
    for run in view.gutter_runs:
        w.body += _RUN.pack(run.start_x, run.variant)

    table = bytearray()
    for text in w.strings:
        raw = text.encode("utf-8")
        if len(raw) > 0xFFFF:
            raise ValueError("chord sheet op buffer: string longer than 65535 bytes")
        table += _STR_LEN.pack(len(raw))
        table += raw

    header = _HEADER.pack(
        MAGIC, FORMAT_VERSION, _HEADER.size, view_id, background, highlight, 0,
        view.zoom, view.height, view.content_width, view.content_height,
        view.gutter_width, view.lane_height, len(w.strings), len(view.slots),
    )
    return bytes(header + table + w.body)


def pack_view(song: RenderedSong, view_id: str, zoom: float, height: float,
              renderers: Optional[Sequence[StripRenderer]] = None) -> bytes:
    """Render one chord-sheet view and pack it for Android.

    Args:
        song: The rendered song (the chord sheet's ``rendered_song``).
        view_id: Renderer id: ``'keyboard'``, ``'staff'``, ``'fret'`` or ``'tab'``.
        zoom: Display zoom factor (1.0 = default).
        height: Content height in px (the strip, marker lane excluded).
        renderers: Renderers to pick ``view_id`` from (default: the standard
            set, :func:`~chord_sheet.registry.default_renderers`).

    Returns:
        The packed buffer (format: ``docs/ANDROID.md``, "Chord sheet op buffer").

    Raises:
        ValueError: if no renderer has id ``view_id``, or the view overflows
            the format's limits (65535 strings, 255 tags per op).
    """
    for renderer in (renderers if renderers is not None else default_renderers()):
        if renderer.id == view_id:
            return serialize(collect_view(song, renderer, zoom, height))
    raise ValueError(f"unknown chord sheet view: {view_id!r}")


# -- Unpack (reference decoder) -------------------------------------------------

class _Reader:
    def __init__(self, data: bytes, offset: int, strings: List[str]) -> None:
        self.data = data
        self.pos = offset
        self.strings = strings

    def read(self, st: struct.Struct) -> tuple:
        values = st.unpack_from(self.data, self.pos)
        self.pos += st.size
        return values

    def s(self, index: int) -> Optional[str]:
        return None if index == NO_STRING else self.strings[index]

    def points(self, n: int) -> Tuple[Tuple[float, float], ...]:
        flat = struct.unpack_from(f"<{2 * n}f", self.data, self.pos)
        self.pos += 8 * n
        return tuple(zip(flat[0::2], flat[1::2]))

    def tags(self) -> Tuple[str, ...]:
        count = self.data[self.pos]
        self.pos += 1
        return tuple(self.s(self.read(_U16)[0]) for _ in range(count))

    def op_list(self) -> List[object]:
        count, nbytes = self.read(_LIST_HEAD)
        end = self.pos + nbytes
        ops: List[object] = []
        for _ in range(count):
            code = self.data[self.pos]
            if code in (OP_RECT, OP_OVAL):
                _, x, y, w, h, fill, outline, width = self.read(_BOX)
                cls = RectOp if code == OP_RECT else OvalOp
                ops.append(cls(x, y, w, h, fill=self.s(fill), outline=self.s(outline),
                               width=width, tags=self.tags()))
            elif code == OP_LINE:
                _, fill, width, n = self.read(_LINE)
                points = self.points(n)
                ops.append(LineOp(points, fill=self.s(fill), width=width, tags=self.tags()))
            elif code == OP_POLYGON:
                _, fill, smooth, n = self.read(_POLYGON)
                points = self.points(n)
                ops.append(PolygonOp(points, fill=self.s(fill), smooth=bool(smooth),
                                     tags=self.tags()))
            elif code == OP_TEXT:
                _, x, y, text, anchor, bold, size, fill = self.read(_TEXT)
                if size.is_integer():
                    size = int(size)
                ops.append(TextOp(x, y, self.s(text), anchor=ANCHORS[anchor], size=size,
                                  fill=self.s(fill), bold=bool(bold), tags=self.tags()))
            elif code == OP_IMAGE:
                _, x, y, key, anchor = self.read(_IMAGE)
                ops.append(ImageOp(x, y, self.s(key), anchor=ANCHORS[anchor],
                                   tags=self.tags()))
            else:
                raise ValueError(f"chord sheet op buffer: unknown opcode {code}")
        if self.pos != end:
            raise ValueError("chord sheet op buffer: op list length mismatch")
        return ops


def unpack(data: bytes) -> ViewOps:
    """Decode a buffer from :func:`pack_view` back into a :class:`ViewOps`.

    Floats come back as their float32 values. Raises ``ValueError`` on a bad
    magic, an unsupported version or a malformed buffer.
    """
    (magic, version, header_size, view_id, background, highlight, _flags,
     zoom, height, content_width, content_height, gutter_width, lane_height,
     string_count, slot_count) = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError("not a chord sheet op buffer")
    if version != FORMAT_VERSION:
        raise ValueError(f"unsupported chord sheet op buffer version {version}")

    pos = header_size
    strings: List[str] = []
    for _ in range(string_count):
        (length,) = _STR_LEN.unpack_from(data, pos)
        pos += _STR_LEN.size
        strings.append(bytes(data[pos:pos + length]).decode("utf-8"))
        pos += length

    r = _Reader(data, pos, strings)
    slots = tuple(SlotBox(*r.read(_SLOT)) for _ in range(slot_count))
    content = r.op_list()
    lane = r.op_list()
    variants = [r.op_list() for _ in range(r.read(_U16)[0])]
    runs = [GutterRun(*r.read(_RUN)) for _ in range(r.read(_U16)[0])]
    if r.pos != len(data):
        raise ValueError("chord sheet op buffer: trailing bytes")
    return ViewOps(
        view_id=r.s(view_id), zoom=zoom, height=height,
        content_width=content_width, content_height=content_height,
        gutter_width=gutter_width, lane_height=lane_height,
        background=r.s(background), highlight=r.s(highlight),
        slots=slots, content=content, lane=lane,
        gutter_variants=variants, gutter_runs=runs,
    )
