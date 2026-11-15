"""Painting the chord sheet's draw ops with QPainter (plan step E4).

The core packs the active view into a buffer of draw ops
(``AppSession.chord_sheet_buffer``, ``chord_sheet/pack.py``; the format is
docs/ANDROID.md's "Chord sheet op buffer"). Android decodes it and draws
it with Compose; this module is the same for the Qt window:

* :class:`PreparedSheet`: a decoded buffer (``pack.unpack``) made ready to
  draw, off the GUI thread: rectangles, polylines and paths built once,
  each op's horizontal reach, and the ops bucketed along x so a paint only
  looks at what the viewport shows (Android's ``OpList.intersects``).
* :func:`themed_color` / :func:`dark_variant`: the buffer's colours for
  the theme, ported from Android's ``ChordSheetTheme.kt`` (as the mockup's
  ``sheetpack.py`` did): the strip's paper becomes the panel's surface,
  neutrals flip their lightness in the dark theme, hues get lighter, the
  hands keep their blue and brown. The piano roll in the dark theme takes
  the app's greys: its black-key rows stay the darker ones and its
  keyboard isn't inverted (:func:`roll_dark_colors`, :func:`gutter_palette`).
* :class:`GlyphCache`: the clef, notehead and accidental PNGs from
  ``clef_assets.base_png``, scaled once per device height and tinted.
* :class:`SheetPainter`: replays ops in content coordinates, with fonts,
  metrics, pens and glyphs cached; text and images land on whole device
  pixels (the scaling recipe).

Nothing here is a QObject, so tests paint into a QImage directly.
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)

from chordnotepad.chord_sheet import clef_assets
from chordnotepad.chord_sheet.ops import ImageOp, LineOp, OvalOp, PolygonOp, RectOp, TextOp
from chordnotepad.chord_sheet import piano_roll
from chordnotepad.chord_sheet.pack import ViewOps
from chordnotepad.chord_sheet.renderer_interface import HAND_COLORS, NOTE_INK, STRIP_BG

# -- Colours --------------------------------------------------------------------------

#: The piano roll's gutter keys and their edges (``piano_roll.py``).
GUTTER_WHITE = piano_roll.GUTTER_WHITE
GUTTER_BLACK = piano_roll.GUTTER_BLACK
GUTTER_EDGE = piano_roll.GUTTER_BORDER
GUTTER_LABEL = "#22323a"
#: The piano roll's row shading and C guides (``piano_roll.py``; no other
#: view uses these colours).
ROLL_BLACK_ROW = piano_roll.BLACK_ROW_SHADE
ROLL_GUIDE_C = piano_roll.GUIDE_C
ROLL_GUIDE_C4 = piano_roll.GUIDE_C4
#: The piano roll's note names: white on the light theme's bars, the dark
#: text colour (``Theme.qml``'s light ``text``) on the dark theme's lighter ones.
ROLL_NOTE_LABEL = piano_roll.NOTE_LABEL
_DARK_FIXED = {
    HAND_COLORS["rh"]: QColor("#78a6d8"),
    HAND_COLORS["lh"]: QColor("#d09a6c"),
    ROLL_NOTE_LABEL: QColor("#1d1e22"),
}
#: The keyboard in the dark theme: not inverted (that reads wrong), in the
#: app's own neutral greys (``Theme.qml``: ``icon``, ``muted``, ``input``)
#: instead of Tk's white and slate.
_DARK_KEYS = {
    GUTTER_WHITE: QColor("#c3c6cf"),
    GUTTER_BLACK: QColor("#17181b"),
    GUTTER_EDGE: QColor("#8a8d96"),
    GUTTER_LABEL: QColor("#1d1e22"),
}


def roll_dark_colors(surface: QColor) -> Dict[str, QColor]:
    """The piano roll's rows on a dark ``surface``: black-key rows darker
    than the white-key ones, as in the light theme (a lightness flip would
    make them the lighter ones), and the C guides a step and two lighter,
    all in the surface's own hue."""
    return {
        ROLL_BLACK_ROW: QColor(surface).darker(125),
        ROLL_GUIDE_C: QColor(surface).lighter(155),
        ROLL_GUIDE_C4: QColor(surface).lighter(210),
    }
#: Below this HSL saturation a colour counts as neutral (ink, grid, shading).
NEUTRAL_SATURATION = 0.3
_NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "gray": "#bebebe",
          "grey": "#bebebe"}


def parse_tk_color(spec: Optional[str]) -> Optional[QColor]:
    """A Tk colour string as a QColor, or None ("" or a name Tk renderers
    don't use): ``#rgb``, ``#rrggbb`` and a few names (Android's
    ``parseTkColor``)."""
    if not spec:
        return None
    if spec[0] == "#":
        digits = spec[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        if len(digits) != 6 or any(c not in "0123456789abcdefABCDEF" for c in digits):
            return None
        return QColor("#" + digits)
    named = _NAMED.get(spec.lower())
    return QColor(named) if named else None


def dark_variant(color: QColor) -> QColor:
    """``color`` for a dark background: neutrals flip their lightness and
    lose most of their tint (a warm off-white must not turn olive), hues get
    lighter (at least 66% lightness). ``ChordSheetTheme.kt:darkVariant``."""
    r, g, b = color.redF(), color.greenF(), color.blueF()
    hi, lo = max(r, g, b), min(r, g, b)
    lightness = (hi + lo) / 2
    d = hi - lo
    saturation = 0.0 if d == 0 else d / (1 - abs(2 * lightness - 1))
    if d == 0:
        hue = 0.0
    elif hi == r:
        hue = 60 * (((g - b) / d) % 6)
    elif hi == g:
        hue = 60 * ((b - r) / d + 2)
    else:
        hue = 60 * ((r - g) / d + 4)
    if hue < 0:
        hue += 360
    neutral = saturation < NEUTRAL_SATURATION
    new_l = 0.92 - 0.82 * lightness if neutral else max(lightness, 0.66)
    new_s = saturation * 0.3 if neutral else saturation
    return QColor.fromHslF(hue / 360.0, min(max(new_s, 0.0), 1.0), min(max(new_l, 0.0), 1.0),
                           color.alphaF())


def themed_color(spec: str, parsed: QColor, dark: bool, surface: QColor) -> QColor:
    """A buffer colour as the sheet paints it: the strip's paper is the
    panel's ``surface`` in both themes; in the dark one the hands' bars and
    the piano roll's note names get fixed colours, and the piano roll's rows
    follow the surface (:func:`roll_dark_colors`); everything else goes
    through :func:`dark_variant`. (The roll's keyboard has its own palette,
    :func:`gutter_palette`.)"""
    low = spec.lower()
    if low == STRIP_BG:
        return QColor(surface)
    if not dark:
        return parsed
    if low in _DARK_FIXED:
        return QColor(_DARK_FIXED[low])
    roll = roll_dark_colors(surface).get(low)
    if roll is not None:
        return roll
    return dark_variant(parsed)


def palette_for(strings: Sequence[str], dark: bool, surface: QColor) -> Dict[str, QColor]:
    """Every colour among a buffer's strings, themed (strings that aren't
    colours are left out)."""
    palette: Dict[str, QColor] = {}
    for spec in strings:
        parsed = parse_tk_color(spec)
        if parsed is not None:
            palette[spec] = themed_color(spec, parsed, dark, surface)
    return palette


def gutter_palette(strings: Sequence[str], dark: bool, surface: QColor) -> Dict[str, QColor]:
    """The piano roll keyboard's palette: its light colours, and in the dark
    theme the app's greys for the keys, their edges and the octave labels."""
    palette = palette_for(strings, False, surface)
    if dark:
        for spec in list(palette):
            key = _DARK_KEYS.get(spec.lower())
            if key is not None:
                palette[spec] = QColor(key)
    return palette


def key_bed(items: Sequence[tuple]) -> Optional[QRectF]:
    """The box the keyboard's keys cover (the union of the gutter's
    rectangles, square or rounded), or None: painted in the white keys'
    colour first, so the space beside each black key isn't a hole in the
    keyboard."""
    bed: Optional[QRectF] = None
    for item in items:
        if item[0] == K_RECT or item[0] == K_RRECT:
            bed = QRectF(item[1]) if bed is None else bed.united(item[1])
    return bed


# -- Prepared ops -----------------------------------------------------------------------

K_RECT, K_OVAL, K_LINE, K_SEGMENT, K_POLY, K_TEXT, K_IMAGE, K_RRECT = range(8)
#: Text sizes are points at 96 dpi, as Tk drew them (Android's ``PT_TO_SP``).
PT_TO_PX = 4.0 / 3.0
#: Anchor fractions (Tk's compass anchors): (x, y) of the anchor in the box.
ANCHOR_FRACTIONS = {"nw": (0, 0), "n": (.5, 0), "ne": (1, 0), "w": (0, .5), "center": (.5, .5),
                    "e": (1, .5), "sw": (0, 1), "s": (.5, 1), "se": (1, 1)}
#: The width of a culling bucket, in content px.
BUCKET = 256.0


def _smooth_path(points: Sequence[Tuple[float, float]], smooth: bool) -> QPainterPath:
    """A polygon; smooth is Tk's quadratic B-spline through the edge
    midpoints (``ChordSheetPainter.kt:polygonPath``)."""
    path = QPainterPath()
    n = len(points)
    if n < 2:
        return path
    if not smooth or n < 3:
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        path.closeSubpath()
        return path

    def mid(i):
        a, b = points[i % n], points[(i + 1) % n]
        return QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    path.moveTo(mid(n - 1))
    for i in range(n):
        path.quadTo(QPointF(*points[i]), mid(i))
    path.closeSubpath()
    return path


def _image_height(key: str) -> int:
    parsed = clef_assets.parse_image_key(key)
    return parsed.height if parsed is not None else 256


def lane_clip_rights(ops: Sequence[object]) -> List[float]:
    """The right edge each marker-lane text may paint up to: the next lane
    text's x minus 2 px, or +inf. Inter measures wider than the font the lane
    estimated label widths for (Android's ``laneClipRights``)."""
    xs = sorted(op.x for op in ops if isinstance(op, TextOp))
    rights = []
    for op in ops:
        right = math.inf
        if isinstance(op, TextOp):
            right = next((x - 2.0 for x in xs if x > op.x + 0.5), math.inf)
        rights.append(right)
    return rights


class PreparedOps:
    """One op list ready to paint: each op as a tuple (kind first), its
    horizontal reach, and the ops bucketed by :data:`BUCKET` px of x."""

    __slots__ = ("items", "x0", "x1", "_buckets", "_bed")

    def __init__(self, ops: Sequence[object], clip_rights: Optional[Sequence[float]] = None) -> None:
        self.items: List[tuple] = []
        self.x0: List[float] = []
        self.x1: List[float] = []
        for i, op in enumerate(ops):
            item, lo, hi = self._prepare(op, clip_rights[i] if clip_rights else math.inf)
            self.items.append(item)
            self.x0.append(lo)
            self.x1.append(hi)
        self._bed: Optional[Tuple[Optional[QRectF]]] = None
        self._buckets: Dict[int, List[int]] = {}
        for i, (lo, hi) in enumerate(zip(self.x0, self.x1)):
            if hi < lo:
                continue
            for b in range(int(math.floor(lo / BUCKET)), int(math.floor(hi / BUCKET)) + 1):
                self._buckets.setdefault(b, []).append(i)

    def key_bed(self) -> Optional[QRectF]:
        """:func:`key_bed` of these ops, worked out once."""
        if self._bed is None:
            self._bed = (key_bed(self.items),)
        return self._bed[0]

    @staticmethod
    def _prepare(op: object, clip_right: float) -> Tuple[tuple, float, float]:
        kind = type(op)
        if kind is RectOp or kind is OvalOp:
            pad = op.width / 2
            rect = QRectF(op.x, op.y, op.w, op.h)
            if kind is RectOp and op.radius > 0:
                item = (K_RRECT, rect, op.fill, op.outline, op.width, op.radius)
            else:
                item = (K_RECT if kind is RectOp else K_OVAL, rect, op.fill, op.outline, op.width)
            return item, op.x - pad, op.x + op.w + pad
        if kind is LineOp:
            xs = [p[0] for p in op.points]
            lo, hi = (min(xs), max(xs)) if xs else (0.0, -1.0)
            pad = op.width / 2 + 1
            if len(op.points) == 2:
                (ax, ay), (bx, by) = op.points
                item = (K_SEGMENT, QLineF(ax, ay, bx, by), op.fill, op.width)
            else:
                item = (K_LINE, QPolygonF([QPointF(x, y) for x, y in op.points]), op.fill, op.width)
            return item, lo - pad, hi + pad
        if kind is PolygonOp:
            xs = [p[0] for p in op.points]
            lo, hi = (min(xs), max(xs)) if xs else (0.0, -1.0)
            return (K_POLY, _smooth_path(op.points, op.smooth), op.fill), lo - 1, hi + 1
        if kind is TextOp:
            # Wider than any sans serif at this size: up to one em per character.
            reach = len(op.s) * op.size * PT_TO_PX + 4
            fx, fy = ANCHOR_FRACTIONS.get(op.anchor, (0, 0))
            item = (K_TEXT, op.x, op.y, op.s, fx, fy, float(op.size), bool(op.bold), op.fill,
                    clip_right)
            return item, op.x - reach, op.x + reach
        if kind is ImageOp:
            # Images are at most ~1.7 x their height wide (the whole notehead).
            reach = 2 * _image_height(op.key) + 4
            fx, fy = ANCHOR_FRACTIONS.get(op.anchor, (0, 0))
            return (K_IMAGE, op.x, op.y, op.key, fx, fy), op.x - reach, op.x + reach
        raise TypeError(f"unknown chord sheet op {kind.__name__}")

    def __len__(self) -> int:
        return len(self.items)

    def visible(self, left: float, right: float) -> List[tuple]:
        """The ops that may paint between content x ``left`` and ``right``,
        in paint order."""
        first, last = int(math.floor(left / BUCKET)), int(math.floor(right / BUCKET))
        if first == last:
            indices = self._buckets.get(first, ())
        else:
            found = set()
            for b in range(first, last + 1):
                found.update(self._buckets.get(b, ()))
            indices = sorted(found)
        x0, x1, items = self.x0, self.x1, self.items
        return [items[i] for i in indices if x1[i] >= left and x0[i] <= right]


class PreparedSheet:
    """A decoded buffer (:class:`~chordnotepad.chord_sheet.pack.ViewOps`)
    ready to paint; built off the GUI thread (no QObject, no font work)."""

    def __init__(self, view: ViewOps, strings: Sequence[str] = ()) -> None:
        self.view_id = view.view_id
        self.zoom = view.zoom
        self.height = view.height
        self.content_width = float(view.content_width)
        self.content_height = float(view.content_height)
        self.gutter_width = float(view.gutter_width)
        self.lane_height = float(view.lane_height)
        self.slots = sorted(((s.x, s.width, s.chord_index) for s in view.slots))
        self._slot_by_index = {index: (x, w) for x, w, index in self.slots}
        self.content = PreparedOps(view.content)
        self.lane = PreparedOps(view.lane, lane_clip_rights(view.lane))
        self.gutters = [PreparedOps(ops) for ops in view.gutter_variants]
        self._view = view
        self.strings = tuple(strings) or tuple(self._collect_strings(view))

    @staticmethod
    def _collect_strings(view: ViewOps):
        seen = set()
        for ops in [view.content, view.lane] + list(view.gutter_variants):
            for op in ops:
                for attr in ("fill", "outline"):
                    value = getattr(op, attr, None)
                    if value and value not in seen:
                        seen.add(value)
                        yield value

    def slot(self, chord_index: Optional[int]) -> Optional[Tuple[float, float]]:
        """``(x, width)`` of a chord's slot, or None."""
        if chord_index is None or chord_index < 0:
            return None
        return self._slot_by_index.get(chord_index)

    def chord_at(self, content_x: float) -> int:
        """The chord whose slot holds content x, or -1."""
        for x, w, index in self.slots:
            if x <= content_x <= x + w:
                return index
            if x > content_x:
                break
        return -1

    def gutter_at(self, scroll_x: float) -> Optional[PreparedOps]:
        """The gutter variant for the content x at the viewport's left edge."""
        index = self._view.gutter_variant_at(scroll_x)
        return None if index is None or self.gutter_width <= 0 else self.gutters[index]


# -- Glyphs ----------------------------------------------------------------------------

class GlyphCache:
    """The base clef and glyph images, scaled to whole device pixels once per
    (key, device pixel ratio, colour) and tinted (black ink and alpha: the
    tint keeps the alpha as a mask, like Tk's ``clef_images``)."""

    def __init__(self) -> None:
        self._bases: Dict[str, Optional[QImage]] = {}
        self._scaled: Dict[tuple, Optional[QImage]] = {}

    def _base(self, asset: str) -> Optional[QImage]:
        if asset not in self._bases:
            image = QImage.fromData(clef_assets.base_png(asset), "PNG")
            self._bases[asset] = None if image.isNull() else image.convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied)
        return self._bases[asset]

    def image(self, key: str, dpr: float, color: Optional[QColor]) -> Optional[Tuple[QImage, float, float]]:
        """The glyph for ``key`` and its size in logical px, or None for a
        key the core doesn't know (skipped, as Tk and Android do)."""
        parsed = clef_assets.parse_image_key(key)
        if parsed is None:
            return None
        width = float(clef_assets.scaled_width(parsed.asset, parsed.height))
        cache_key = (key, round(dpr * 1000), color.rgba() if color is not None else None)
        if cache_key not in self._scaled:
            if len(self._scaled) > 2048:
                self._scaled.clear()
            base = self._base(parsed.asset)
            if base is None:
                self._scaled[cache_key] = None
            else:
                h = max(1, round(parsed.height * dpr))
                w = max(1, round(base.width() * h / base.height()))
                image = base.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                if color is not None:
                    tint = QPainter(image)
                    tint.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    tint.fillRect(image.rect(), color)
                    tint.end()
                image.setDevicePixelRatio(dpr)
                self._scaled[cache_key] = image
        image = self._scaled[cache_key]
        return None if image is None else (image, width, float(parsed.height))


# -- Painting --------------------------------------------------------------------------

class SheetPainter:
    """Replays prepared ops onto a QPainter whose transform maps content px
    to the item (the caller translates and clips). Fonts, metrics, pens and
    the themed palette are cached; :meth:`set_theme` changes the palette."""

    def __init__(self, glyphs: Optional[GlyphCache] = None) -> None:
        self.glyphs = glyphs or GlyphCache()
        self.family = "Inter"
        self.dpr = 1.0
        self.dark = False
        self.surface = QColor(STRIP_BG)
        self.palette: Dict[str, QColor] = {}
        self.light_palette: Dict[str, QColor] = {}
        self._fonts: Dict[tuple, Tuple[QFont, QFontMetricsF]] = {}
        self._widths: Dict[tuple, float] = {}
        self._pens: Dict[tuple, QPen] = {}
        self._ink_tint: Optional[QColor] = None
        #: Ops drawn since the counter was last reset (perf numbers, tests).
        self.drawn = 0

    def set_theme(self, strings: Sequence[str], dark: bool, surface: QColor) -> None:
        """The palette for a sheet's colour strings in this theme."""
        self.dark = dark
        self.surface = QColor(surface)
        self.palette = palette_for(strings, dark, surface)
        #: The piano roll keyboard's palette (:func:`gutter_palette`).
        self.light_palette = gutter_palette(strings, dark, surface)
        self._pens.clear()
        ink = QColor(NOTE_INK)
        self._ink_tint = themed_color(NOTE_INK, ink, True, surface) if dark else None

    def set_family(self, family: str) -> None:
        if family != self.family:
            self.family = family
            self._fonts.clear()
            self._widths.clear()

    def font(self, size: float, bold: bool) -> Tuple[QFont, QFontMetricsF]:
        """The sheet's font at a Tk point size (Inter, unhinted: pitfall 11)."""
        key = (size, bold)
        found = self._fonts.get(key)
        if found is None:
            font = QFont(self.family)
            font.setPixelSize(max(1, round(size * PT_TO_PX)))
            font.setBold(bold)
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            found = (font, QFontMetricsF(font))
            self._fonts[key] = found
        return found

    def _pen(self, colors: Dict[str, QColor], spec: Optional[str], width: float,
             join: Qt.PenJoinStyle) -> QPen:
        key = (id(colors), spec, width, join)
        pen = self._pens.get(key)
        if pen is None:
            color = colors.get(spec) if spec else None
            if color is None:
                color = QColor("black")
            pen = QPen(color, width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setJoinStyle(join)
            self._pens[key] = pen
        return pen

    def snap(self, value: float) -> float:
        """``value`` on the device pixel grid (the transform must be snapped)."""
        return round(value * self.dpr) / self.dpr

    def draw(self, p: QPainter, items: Sequence[tuple],
             palette: Optional[Dict[str, QColor]] = None) -> None:
        """Draw prepared op tuples in order (``palette``: another palette for
        these ops, e.g. the piano roll's gutter in its light colours)."""
        colors = self.palette if palette is None else palette
        no_pen, no_brush = Qt.PenStyle.NoPen, Qt.BrushStyle.NoBrush
        black = QColor("black")
        for item in items:
            kind = item[0]
            self.drawn += 1
            if kind == K_RECT or kind == K_OVAL or kind == K_RRECT:
                rect, fill, outline, width = item[1:5]
                fc = colors.get(fill) if fill else None
                oc = colors.get(outline) if outline and width > 0 else None
                if fc is None and oc is None:
                    continue
                if oc is not None:
                    join = Qt.PenJoinStyle.MiterJoin if kind == K_RECT else Qt.PenJoinStyle.RoundJoin
                    p.setPen(self._pen(colors, outline, width, join))
                else:
                    p.setPen(no_pen)
                p.setBrush(QBrush(fc) if fc is not None else no_brush)
                if kind == K_RECT:
                    p.drawRect(rect)
                elif kind == K_RRECT:
                    p.drawRoundedRect(rect, item[5], item[5])
                else:
                    p.drawEllipse(rect)
            elif kind == K_SEGMENT or kind == K_LINE:
                _, shape, fill, width = item
                p.setPen(self._pen(colors, fill, width, Qt.PenJoinStyle.RoundJoin))
                p.setBrush(no_brush)
                if kind == K_SEGMENT:
                    p.drawLine(shape)
                else:
                    p.drawPolyline(shape)
            elif kind == K_POLY:
                _, path, fill = item
                p.setPen(no_pen)
                p.setBrush(colors.get(fill, black) if fill else black)
                p.drawPath(path)
            elif kind == K_TEXT:
                self._text(p, item, colors)
            elif kind == K_IMAGE:
                self._image(p, item, colors)

    def _text(self, p: QPainter, item: tuple, colors: Dict[str, QColor]) -> None:
        _, x, y, s, fx, fy, size, bold, fill, clip_right = item
        font, metrics = self.font(size, bold)
        wkey = (s, size, bold)
        width = self._widths.get(wkey)
        if width is None:
            if len(self._widths) > 8192:
                self._widths.clear()
            width = metrics.horizontalAdvance(s)
            self._widths[wkey] = width
        height = metrics.height()
        left = self.snap(x - fx * width)
        baseline = self.snap(y - fy * height + metrics.ascent())
        p.setFont(font)
        p.setPen(colors.get(fill, QColor("black")) if fill else QColor("black"))
        if left + width > clip_right:
            p.save()
            p.setClipRect(QRectF(left - 1, baseline - metrics.ascent() - 1,
                                 max(0.0, clip_right - left + 1), height + 2),
                          Qt.ClipOperation.IntersectClip)
            p.drawText(QPointF(left, baseline), s)
            p.restore()
        else:
            p.drawText(QPointF(left, baseline), s)

    def _image(self, p: QPainter, item: tuple, colors: Dict[str, QColor]) -> None:
        _, x, y, key, fx, fy = item
        parsed = clef_assets.parse_image_key(key)
        if parsed is None:
            return
        if parsed.color is not None:
            spec = "#" + parsed.color
            raw = QColor(spec)
            color = themed_color(spec, raw, self.dark, self.surface)
        else:
            color = self._ink_tint
        found = self.glyphs.image(key, self.dpr, color)
        if found is None:
            return
        image, width, height = found
        p.drawImage(QPointF(self.snap(x - fx * width), self.snap(y - fy * height)), image)
