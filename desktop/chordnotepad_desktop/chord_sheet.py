"""The chord sheet (plan step E4): the buffer source and the painted item.

The session renders the chord sheet's song (``ChordSheetViewModel``,
debounced 500 ms, off its thread, never while off screen) and packs the
view it shows, at its zoom, for a strip of a given height:
``AppSession.chord_sheet_buffer(height)`` (a direct call, the one Android
makes through Chaquopy). ``ChordSheetState`` says when to fetch again
(``song_revision``, ``active_view``, ``zoom``) and what plays
(``current_index``) or where the playhead is (``cursor_index``).

* :class:`ChordSheetModel` (``sheet`` in Main.qml): fetches and decodes the
  buffer off the GUI thread (``pack.unpack`` then
  :class:`~chordnotepad_desktop.sheet_paint.PreparedSheet`) whenever the
  request changes, waits 60 ms for a split drag to settle (Android's
  ``ChordSheetController``), keeps a few recent sheets (Edit and Play have
  different heights), and keeps the Edit panel's height in logical pixels
  (``logical_chord_sheet_height`` / ``set_logical_chord_sheet_height``,
  B3).
* :class:`SheetView` (``CNSheet.SheetView`` in QML): a viewport-sized
  QQuickPaintedItem. It paints only what the viewport shows: the marker
  lane on top, the playing column, the content, the playhead's edge mark,
  and the frozen gutter on the left with its own variant for the scroll
  position. Scrolling is a property (the wheel and the scroll bar set it);
  following playback uses the core's rule
  (``ChordSheetViewModel.scroll_target``: keep the chord between 25% and
  70% of the width, else put it at 25%). A new playing chord repaints only
  the two columns when nothing scrolls.

QML can't see a Python type unless it is registered; ``qml/CNSheet`` is a
module with a hand-written ``sheet.qmltypes`` so qmllint knows
SheetView's properties (``tests/qt/test_qt_chord_sheet.py`` checks it
against the class).
"""

import logging
import math
import threading
import time
from collections import OrderedDict
from typing import Any, Optional, Tuple

from PySide6.QtCore import Property, QObject, QRect, QRectF, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPainter
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem

from chordnotepad.chord_sheet.marker_lane import LANE_HEIGHT
from chordnotepad.chord_sheet.pack import unpack
from chordnotepad.viewmodels.chord_sheet_viewmodel import ChordSheetViewModel
from chordnotepad_desktop.sheet_paint import GUTTER_WHITE, PreparedSheet, SheetPainter

logger = logging.getLogger(__name__)

#: A height change (a split drag) waits this long before a new buffer is
#: fetched (Android's ``SETTLE_MS``); the other changes too, so a burst of
#: states collapses.
SETTLE_MS = 60
#: Sheets kept for requests seen lately (the Edit panel and the Play strip
#: differ in height; a zoom back and forth).
CACHE_SIZE = 6
#: The QML module and type name.
QML_MODULE = "CNSheet"
QML_TYPE = "SheetView"

#: (song revision, view id, zoom, content height in logical px).
Request = Tuple[int, str, float, int]


class ChordSheetModel(QObject):
    """The chord sheet's buffers and its saved height, for QML and SheetView.

    Args:
        store: The SessionStore (``ChordSheetState``, the direct calls).
    """

    sheetChanged = Signal()
    loadingChanged = Signal()
    #: A buffer is ready (emitted from the worker; queued to the GUI thread).
    _loaded = Signal(object, object, float)

    def __init__(self, store: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._height = 0
        self._wanted: Optional[Request] = None
        self._fetching: Optional[Request] = None
        self._loaded_for: Optional[Request] = None
        self.sheet: Optional[PreparedSheet] = None
        self._cache: "OrderedDict[Request, Optional[PreparedSheet]]" = OrderedDict()
        self._closed = False
        #: How long the last fetches took (ms: pack in the core, then unpack
        #: and prepare), for the perf numbers in the logs.
        self.last_fetch_ms = 0.0
        self._settle = QTimer(self, singleShot=True, interval=SETTLE_MS)
        self._settle.timeout.connect(self._fetch)
        self._loaded.connect(self._on_loaded, Qt.ConnectionType.QueuedConnection)
        store.stateChanged.connect(self._on_state)

    # -- what to fetch --------------------------------------------------------------

    def _state(self, key: str) -> Any:
        return self._store.state("ChordSheetState").value(key)

    def _request(self) -> Optional[Request]:
        view = self._state("active_view")
        if self._height <= 0 or not view:
            return None
        return (int(self._state("song_revision") or 0), str(view),
                float(self._state("zoom") or 1.0), self._height)

    @Slot(str)
    def _on_state(self, type_name: str) -> None:
        if type_name == "ChordSheetState":
            self._want(self._request())

    @Slot(int)
    def setContentHeight(self, height: int) -> None:  # noqa: N802 (Qt)
        """The strip's content height in logical px (the item's, the marker
        lane excluded); 0 while the sheet is off screen (nothing is fetched)."""
        height = max(0, int(height))
        if height != self._height:
            self._height = height
            self._want(self._request())

    def _want(self, request: Optional[Request]) -> None:
        if request == self._wanted:
            return
        self._wanted = request
        if request is None:
            self._settle.stop()
            return
        if request in self._cache:
            self._cache.move_to_end(request)
            self._settle.stop()
            self._show(request, self._cache[request])
            return
        self.loadingChanged.emit()
        self._settle.start()

    def _get_loading(self) -> bool:
        return self._wanted is not None and self._wanted != self._loaded_for

    loading = Property(bool, _get_loading, notify=loadingChanged)

    # -- fetching (one at a time, off the GUI thread) -----------------------------------

    def _fetch(self) -> None:
        request = self._wanted
        if request is None or self._fetching is not None or self._closed:
            return
        self._fetching = request
        threading.Thread(target=self._work, args=(request,), daemon=True,
                         name="ChordSheetBuffer").start()

    def _work(self, request: Request) -> None:
        start = time.perf_counter()
        prepared = None
        try:
            data = self._store.direct("chord_sheet_buffer", float(request[3]))
            if data is not None:
                prepared = PreparedSheet(unpack(data))
        finally:
            # Even when it raised (the error goes to threading.excepthook,
            # the error presenter's): the next request can run.
            if not self._closed:
                self._loaded.emit(request, prepared, (time.perf_counter() - start) * 1000)

    @Slot(object, object, float)
    def _on_loaded(self, request: Request, prepared: Optional[PreparedSheet], ms: float) -> None:
        self._fetching = None
        if self._closed:
            return
        self.last_fetch_ms = ms
        if prepared is not None:
            logger.debug("Chord sheet %s z=%s h=%s: %d+%d ops in %.1f ms", request[1], request[2],
                         request[3], len(prepared.content), len(prepared.lane), ms)
        self._cache[request] = prepared
        self._cache.move_to_end(request)
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        if request == self._wanted:
            self._show(request, prepared)
        elif self._wanted is not None and self._wanted not in self._cache:
            self._settle.start()

    def _show(self, request: Request, prepared: Optional[PreparedSheet]) -> None:
        self._loaded_for = request
        if prepared is not self.sheet:
            self.sheet = prepared
            self.sheetChanged.emit()
        self.loadingChanged.emit()

    # -- the Edit panel's height (B3; logical px, Tk's kept in step) ---------------------

    @Slot(float, result=int)
    def savedHeight(self, scale: float) -> int:  # noqa: N802 (Qt)
        """The Edit panel's saved height in logical px (migrated from Tk's
        pixels with ``scale``, the window's device pixel ratio)."""
        return int(self._store.direct("logical_chord_sheet_height", float(scale) or 1.0))

    @Slot(int, float)
    def saveHeight(self, height: int, scale: float) -> None:  # noqa: N802 (Qt)
        """Keep the Edit panel's height (after a drag)."""
        self._store.submit("set_logical_chord_sheet_height",
                           {"height": max(1, int(height)), "scale": float(scale) or 1.0})

    def close(self) -> None:
        """Stop fetching (shutdown); a fetch still running is dropped."""
        self._closed = True
        self._settle.stop()


class SheetView(QQuickPaintedItem):
    """One chord-sheet view, viewport-sized (see the module docstring).

    Driven from QML: ``model`` (a :class:`ChordSheetModel`), ``active`` (on
    screen: fetch buffers), ``playingIndex`` / ``cursorIndex`` (the
    ``ChordSheetState`` indices, -1 for none), ``scrollX``, the theme
    (``dark``, ``surface``, ``playingColor``, ``edgeColor``,
    ``fontFamily``, ``dpr``).
    """

    changed = Signal()
    scrollXChanged = Signal()
    contentChanged = Signal()

    def __init__(self, parent: Optional[QQuickPaintedItem] = None) -> None:
        super().__init__(parent)
        self._model: Optional[ChordSheetModel] = None
        self._sheet: Optional[PreparedSheet] = None
        self._painter = SheetPainter()
        self._active = False
        self._dark = False
        self._surface = QColor("#f6f7f9")
        self._playing_color = QColor(255, 235, 59, 0x73)
        self._edge_color = QColor("#3f51b5")
        self._dpr = 1.0
        self._playing = -1
        self._cursor = -1
        self._scroll = 0.0
        self._zoom_anchor = -1.0
        self._theme_dirty = True
        #: The last paint's duration in ms and the ops it drew (perf numbers).
        self.last_paint_ms = 0.0
        self.last_paint_ops = 0
        self.paints = 0
        self.setAntialiasing(True)
        self.setOpaquePainting(True)
        # Slots, not plain methods: a QML instance that declares a property
        # gets QML's own metaobject, and PySide's dynamic slots on it are
        # never called (signals connected to plain methods went dead).
        self.heightChanged.connect(self._report_height)
        self.widthChanged.connect(self._on_width)

    # -- the model ------------------------------------------------------------------

    def _get_model(self) -> Optional[QObject]:
        return self._model

    def _set_model(self, model: Optional[QObject]) -> None:
        if model is self._model:
            return
        if self._model is not None:
            self._model.sheetChanged.disconnect(self._take_sheet)
        self._model = model
        if model is not None:
            model.sheetChanged.connect(self._take_sheet)
        self._report_height()
        self._take_sheet()
        self.changed.emit()

    model = Property(QObject, _get_model, _set_model, notify=changed)

    def _get_active(self) -> bool:
        return self._active

    def _set_active(self, active: bool) -> None:
        if bool(active) != self._active:
            self._active = bool(active)
            self._report_height()
            self.changed.emit()

    active = Property(bool, _get_active, _set_active, notify=changed)

    @Slot()
    def _report_height(self) -> None:
        if self._model is not None:
            height = self.height() - LANE_HEIGHT if self._active else 0
            self._model.setContentHeight(int(math.floor(max(0.0, height))))

    @Slot()
    def _take_sheet(self) -> None:
        old = self._sheet
        new = self._model.sheet if self._model is not None else None
        if new is old:
            return
        self._sheet = new
        self._theme_dirty = True
        if new is not None and old is not None:
            viewport = self._viewport_width()
            if old.view_id == new.view_id and old.zoom != new.zoom:
                # The same music stays under the pointer (Ctrl+wheel) or the
                # middle of the strip (the buttons).
                anchor = self._zoom_anchor - new.gutter_width
                if not 0 <= anchor <= viewport:
                    anchor = viewport / 2
                self._scroll = _rescale_scroll(self._scroll, anchor, old.content_width,
                                               new.content_width, viewport)
                self._zoom_anchor = -1.0
            elif old.view_id != new.view_id and old.content_width > 0:
                self._scroll = self._scroll / old.content_width * new.content_width
        self._scroll = self._clamped(self._scroll)
        self.contentChanged.emit()
        self.scrollXChanged.emit()
        self._follow(self._playing)
        self.update()

    # -- theme ----------------------------------------------------------------------

    def _theme_prop(attr: str, conv):
        def get(self):
            return getattr(self, attr)

        def set_(self, value):
            value = conv(value)
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                self._theme_dirty = True
                self.changed.emit()
                self.update()
        return get, set_

    dark = Property(bool, *_theme_prop("_dark", bool), notify=changed)
    surface = Property(QColor, *_theme_prop("_surface", QColor), notify=changed)
    playingColor = Property(QColor, *_theme_prop("_playing_color", QColor), notify=changed)
    edgeColor = Property(QColor, *_theme_prop("_edge_color", QColor), notify=changed)
    dpr = Property(float, *_theme_prop("_dpr", float), notify=changed)

    def _get_family(self) -> str:
        return self._painter.family

    def _set_family(self, family: str) -> None:
        if family != self._painter.family:
            self._painter.set_family(family)
            self.changed.emit()
            self.update()

    fontFamily = Property(str, _get_family, _set_family, notify=changed)

    # -- what plays -----------------------------------------------------------------

    def _get_playing(self) -> int:
        return self._playing

    def _set_playing(self, index: int) -> None:
        index = int(index)
        if index == self._playing:
            return
        old = self._playing
        self._playing = index
        self.changed.emit()
        if not self._follow(index):
            # Only the two columns change (the edge mark goes with them).
            self._update_slot(old)
            self._update_slot(index)
            if self._cursor >= 0:
                self._update_slot(self._cursor)

    playingIndex = Property(int, _get_playing, _set_playing, notify=changed)

    def _get_cursor(self) -> int:
        return self._cursor

    def _set_cursor(self, index: int) -> None:
        index = int(index)
        if index == self._cursor:
            return
        old = self._cursor
        self._cursor = index
        self.changed.emit()
        # The playhead's chord while nothing plays, when it moves (a click,
        # ⏮, a seek): only on the move, so a zoom or a scroll by hand stays.
        if self._playing >= 0 or not self._follow(index):
            self._update_slot(old)
            self._update_slot(index)

    cursorIndex = Property(int, _get_cursor, _set_cursor, notify=changed)

    # -- scrolling ------------------------------------------------------------------

    def _viewport_width(self) -> float:
        gutter = self._sheet.gutter_width if self._sheet is not None else 0.0
        return max(0.0, self.width() - gutter)

    def _max_scroll(self) -> float:
        if self._sheet is None:
            return 0.0
        return max(0.0, self._sheet.content_width - self._viewport_width())

    def _clamped(self, value: float) -> float:
        return min(max(0.0, float(value)), self._max_scroll())

    def _get_scroll(self) -> float:
        return self._scroll

    def _set_scroll(self, value: float) -> None:
        value = self._clamped(value)
        if abs(value - self._scroll) > 1e-6:
            self._scroll = value
            self.scrollXChanged.emit()
            self.update()

    scrollX = Property(float, _get_scroll, _set_scroll, notify=scrollXChanged)

    def _get_content_width(self) -> float:
        return self._sheet.content_width if self._sheet is not None else 0.0

    contentWidth = Property(float, _get_content_width, notify=contentChanged)

    def _get_gutter_width(self) -> float:
        return self._sheet.gutter_width if self._sheet is not None else 0.0

    gutterWidth = Property(float, _get_gutter_width, notify=contentChanged)

    def _get_has_sheet(self) -> bool:
        return self._sheet is not None

    hasSheet = Property(bool, _get_has_sheet, notify=contentChanged)

    def _get_lane_height(self) -> float:
        return LANE_HEIGHT

    laneHeight = Property(float, _get_lane_height, constant=True)

    @Slot()
    def _on_width(self) -> None:
        self._scroll = self._clamped(self._scroll)
        self.scrollXChanged.emit()
        self._follow(self._playing)
        self.update()

    def _get_zoom_anchor(self) -> float:
        return self._zoom_anchor

    def _set_zoom_anchor(self, x: float) -> None:
        self._zoom_anchor = float(x)

    #: Item x to zoom about when the next sheet comes at another zoom
    #: (Ctrl+wheel sets the pointer's); -1: the middle.
    zoomAnchor = Property(float, _get_zoom_anchor, _set_zoom_anchor, notify=changed)

    @Slot(float)
    def scrollBy(self, dx: float) -> None:  # noqa: N802 (Qt)
        self._set_scroll(self._scroll + dx)

    def _follow(self, index: int) -> bool:
        """Scroll so chord ``index`` sits in the 25-70% band; True if it scrolled."""
        sheet = self._sheet
        slot = sheet.slot(index) if sheet is not None else None
        if slot is None:
            return False
        x, w = slot
        target = ChordSheetViewModel.scroll_target(x + w / 2, self._viewport_width(), self._scroll,
                                                   sheet.content_width)
        if target is None:
            return False
        before = self._scroll
        self._set_scroll(target)
        return self._scroll != before

    # -- hit test -------------------------------------------------------------------

    @Slot(float, float, result=int)
    def chordAt(self, x: float, y: float) -> int:  # noqa: N802 (Qt)
        """The chord under item point (x, y), or -1 (the lane and the gutter
        have none)."""
        sheet = self._sheet
        if sheet is None or y < sheet.lane_height or x < sheet.gutter_width:
            return -1
        return sheet.chord_at(x - sheet.gutter_width + self._scroll)

    @Slot(int, result=float)
    def slotCenter(self, index: int) -> float:  # noqa: N802 (Qt)
        """Item x of a chord's slot centre, or -1 when it has none."""
        sheet = self._sheet
        slot = sheet.slot(index) if sheet is not None else None
        if slot is None:
            return -1.0
        return sheet.gutter_width + slot[0] + slot[1] / 2 - self._scroll

    # -- painting -------------------------------------------------------------------

    def _origin(self) -> float:
        """Item x of content x 0, on the device pixel grid."""
        sheet = self._sheet
        return round((sheet.gutter_width - self._scroll) * self._dpr) / self._dpr

    def _update_slot(self, index: int) -> None:
        sheet = self._sheet
        slot = sheet.slot(index) if sheet is not None else None
        if slot is None:
            return
        left = self._origin() + slot[0]
        rect = QRectF(left - 2, 0, slot[1] + 4, self.height()).toAlignedRect()
        clip = QRect(int(math.ceil(sheet.gutter_width)), 0, int(self.width()) + 1,
                     int(self.height()) + 1)
        rect = rect.intersected(clip)
        if not rect.isEmpty():
            self.update(rect)

    def _apply_theme(self) -> None:
        painter = self._painter
        painter.dpr = self._dpr or 1.0
        if self._sheet is not None:
            painter.set_theme(self._sheet.strings, self._dark, self._surface)
        self._theme_dirty = False

    def paint(self, p: QPainter) -> None:
        start = time.perf_counter()
        sheet = self._sheet
        clip = p.clipBoundingRect() if p.hasClipping() else QRectF()
        if clip.isEmpty():
            clip = QRectF(0, 0, self.width(), self.height())
        p.fillRect(clip, self._surface)
        if sheet is None:
            return
        if self._theme_dirty:
            self._apply_theme()
        painter = self._painter
        painter.drawn = 0
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        gutter = sheet.gutter_width
        origin = self._origin()
        lane = sheet.lane_height
        left = clip.left() - origin
        right = clip.right() - origin

        if clip.right() > gutter:
            p.save()
            p.setClipRect(QRectF(gutter, 0, self.width() - gutter, self.height()),
                          Qt.ClipOperation.IntersectClip)
            p.translate(origin, 0)
            painter.draw(p, sheet.lane.visible(left, right))
            p.translate(0, lane)
            playing = sheet.slot(self._playing)
            if playing is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._playing_color)
                p.drawRoundedRect(QRectF(playing[0], 2, playing[1], sheet.content_height - 4), 6, 6)
            painter.draw(p, sheet.content.visible(left, right))
            edge = sheet.slot(self._cursor) if playing is None else None
            if edge is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self._edge_color)
                p.drawRoundedRect(QRectF(edge[0], 2, 3, sheet.content_height - 4), 1.5, 1.5)
            p.restore()

        variant = sheet.gutter_at(self._scroll)
        if variant is not None and clip.left() < gutter:
            p.save()
            p.setClipRect(QRectF(0, 0, gutter, self.height()), Qt.ClipOperation.IntersectClip)
            p.translate(0, lane)
            # The piano roll's keyboard: its own palette (not inverted in the
            # dark theme; its labels sit on white keys), on a bed of the white
            # keys' colour so the space beside each black key is filled.
            palette = None
            if sheet.view_id == "keyboard":
                palette = painter.light_palette
                bed = variant.key_bed()
                white = palette.get(GUTTER_WHITE)
                if bed is not None and white is not None:
                    p.fillRect(bed, white)
            painter.draw(p, variant.items, palette)
            p.restore()
        self.last_paint_ops = painter.drawn
        self.last_paint_ms = (time.perf_counter() - start) * 1000
        self.paints += 1


def _rescale_scroll(scroll: float, anchor: float, old_width: float, new_width: float,
                    viewport: float) -> float:
    """The scroll that keeps the content under viewport x ``anchor`` in place
    when the content's width changes (Android's ``rescaleScroll``)."""
    max_scroll = max(0.0, new_width - viewport)
    if old_width <= 0:
        return min(max(scroll, 0.0), max_scroll)
    return min(max((scroll + anchor) * (new_width / old_width) - anchor, 0.0), max_scroll)


_registered = False


def register_types() -> None:
    """Make ``CNSheet.SheetView`` known to QML (once per process)."""
    global _registered
    if not _registered:
        qmlRegisterType(SheetView, QML_MODULE, 1, 0, QML_TYPE)
        _registered = True
