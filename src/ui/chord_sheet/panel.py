"""The chord-sheet panel: a horizontal-scrolling strip of voiced-chord cards.

``ChordSheetPanel`` is the thin Tk shell around the headless
:class:`~viewmodels.chord_sheet_viewmodel.ChordSheetViewModel`. It hosts a
horizontally-scrolling ``Canvas`` (plus a view picker), replays the active
renderer's draw ops onto it, highlights the chord under the playhead, follows
playback by auto-scrolling, and turns clicks into auditions. All layout/paint
logic lives in the renderers and all state lives in the viewmodel; this class
only bridges them to Tkinter. The user's commands (zoom, view tabs, clicks to
audition) go through the session, which owns the audio-failure reporting.

Interim (``docs/architecture/session.md``): the panel still reads the strip
directly to paint it (its rendered song, renderers, zoom and playhead, and
change notifications for repaints), because those are live objects until
draw ops cross the Android bridge. It never changes the strip itself.
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Set

from constants import (
    CHORD_SHEET_CONFIGURE_DEBOUNCE_MS,
    UI_BORDER,
    UI_HOVER,
    UI_TAB_IDLE,
    UI_TEXT_DISABLED,
)
from chord_sheet.marker_lane import LANE_HEIGHT, build_marker_lane
from chord_sheet.ops import DrawOps, ImageOp
from chord_sheet.renderer_interface import SheetContext, STRIP_BG, StripLayout
from ui.base.tooltip import TabToolTip
from ui.chord_sheet.clef_images import image_for_clef_key
from ui.chord_sheet.tk_replay import replay

logger = logging.getLogger(__name__)

#: Highlight fill drawn behind the chord slot under the playhead.
_HIGHLIGHT_FILL = "#ffe58a"


class ChordSheetPanel(ttk.Frame):
    """Tk shell hosting the scrolling chord-sheet strip."""

    def __init__(self, parent: tk.Widget, viewmodel=None, *, session, **kwargs) -> None:
        """Build the panel and wire it to the viewmodel.

        Args:
            parent: Parent widget.
            viewmodel: A :class:`ChordSheetViewModel`, whose rendered song
                and display state the panel paints; by default the session's
                (``session.chord_sheet_model``).
            session: Takes the panel's commands: ``chord_sheet_zoom(step)``,
                ``set_chord_sheet_view(view_id)`` and ``audition(index)``
                (an :class:`~session.session.AppSession`).
            **kwargs: Passed through to ``ttk.Frame``.
        """
        super().__init__(parent, **kwargs)
        self._vm = viewmodel if viewmodel is not None else session.chord_sheet_model
        self._session = session
        self._layout: Optional[StripLayout] = None
        # Resolved Tk images by ops image key. These MUST stay referenced or Tk
        # garbage-collects them and the clef glyphs vanish, so the cache is kept
        # on the panel for the panel's lifetime.
        self._images: dict = {}
        self._warned_image_keys: Set[str] = set()

        # Frozen-gutter bookkeeping. ``_gutter_width`` is the currently-shown
        # pane width (0 = collapsed); ``_gutter_state`` is the last painted
        # (renderer, scroll_x, height, zoom, width) key, used to skip identical
        # replays on scroll.
        self._gutter_width: float = 0.0
        self._gutter_state: Optional[tuple] = None

        # Pending trailing-repaint ``after`` id for the <Configure> debounce
        # (see ``_on_canvas_configure``). ``None`` means we are in a quiet
        # period, so the next configure is the "leading" one and repaints live.
        self._configure_after: Optional[str] = None

        self._build_widgets()
        self._wire_viewmodel()

        # Initial paint (a song may already be present when the panel is shown).
        self._relayout_and_paint()

    # -- Construction -------------------------------------------------------

    def _build_widgets(self) -> None:
        """Create the view picker (toggle buttons), canvas, and scrollbar."""
        header = ttk.Frame(self)
        header.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 0))

        # Compact zoom controls pinned to the right end of the header row,
        # enabled only while the active view declares ``supports_zoom``. Packed
        # right-to-left so "+" is rightmost and "-" sits to its left.
        self._zoom_in_btn = ttk.Button(
            header, text="+", width=2, style="Toolbutton",
            command=lambda: self._session.chord_sheet_zoom(1)
        )
        self._zoom_in_btn.pack(side=tk.RIGHT, padx=(0, 0))
        self._zoom_out_btn = ttk.Button(
            header, text="\u2212", width=2, style="Toolbutton",
            command=lambda: self._session.chord_sheet_zoom(-1)
        )
        self._zoom_out_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self._update_zoom_buttons_state()

        # The view picker is a ttk.Notebook used purely as a tab strip: one tab
        # per renderer (in registered order) whose pages are empty zero-height
        # frames, with the real body sitting directly beneath. Renderers gated
        # out for the current song stay visible but disabled, so the row's
        # layout never shifts.
        self._configure_tab_style()
        self._tabs = ttk.Notebook(header, style="ChordSheet.TNotebook", takefocus=False)
        self._tab_ids: list = [renderer.id for renderer in self._vm.renderers]
        for renderer in self._vm.renderers:
            self._tabs.add(ttk.Frame(self._tabs, height=0), text=renderer.label)
        self._tabs.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # True while the panel itself changes tab states/selection, so the
        # resulting <<NotebookTabChanged>> doesn't feed back into the viewmodel.
        self._syncing_tabs = False
        self._tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._tab_tip = TabToolTip(self._tabs, self._tab_tip_text)
        self._update_view_buttons_state()

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        # Column 0: frozen gutter (fixed width, 0 when collapsed). Column 1: the
        # scrolling strip + lane. Row 0: marker lane. Row 1: strip. Row 2: bar.
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=1)
        body.rowconfigure(2, weight=0)

        self._hbar = ttk.Scrollbar(body, orient=tk.HORIZONTAL, command=self._xview_both)
        self._hbar.grid(row=2, column=0, columnspan=2, sticky="ew")

        # Frozen left gutter: a non-scrolling pane pinned at the strip's left
        # edge (piano-roll keyboard, staff clefs). Kept ungridded until a
        # renderer declares a positive ``gutter_width`` (see ``_repaint_gutter``).
        # A small corner above it keeps the top bar visually continuous.
        self._gutter_corner = tk.Canvas(
            # Explicit height: an unset tk.Canvas height defaults to ~260px,
            # which would inflate the marker-lane row it shares (row 0) and
            # shove the strip to the bottom of a tall panel.
            body, width=1, height=int(LANE_HEIGHT), highlightthickness=0,
            bg=STRIP_BG,
        )
        self._gutter_canvas = tk.Canvas(
            body, width=1, highlightthickness=0, bg=STRIP_BG
        )

        # Slim marker lane on top; the main strip fills the rest. Both live in
        # the scrolling column and share one scrollbar so markers stay aligned
        # with the cards below them (and with the strip when a gutter is shown).
        self._lane_canvas = tk.Canvas(
            body,
            height=int(LANE_HEIGHT),
            highlightthickness=0,
            bg=STRIP_BG,
        )
        self._lane_canvas.grid(row=0, column=1, sticky="ew")

        self._canvas = tk.Canvas(
            body,
            height=100,
            highlightthickness=0,
            bg=STRIP_BG,
            xscrollcommand=self._hbar.set,
        )
        self._canvas.grid(row=1, column=1, sticky="nsew")

        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Button-1>", self._on_canvas_click)

    def _xview_both(self, *args) -> None:
        """Scroll the marker lane and the main strip together (scrollbar cmd)."""
        self._canvas.xview(*args)
        self._lane_canvas.xview(*args)
        # A horizontal scroll changes what content sits at the viewport's left
        # edge, so scroll-dependent gutters (staff key signature) must repaint.
        self._repaint_gutter()

    @staticmethod
    def _configure_tab_style() -> None:
        """Style the view picker as tabs attached to the strip below.

        Only configure options (no images) so it degrades across themes. The
        notebook's client area is empty, so its border is trimmed to nothing
        and the selected tab is lifted a little with negative bottom margin.
        """
        style = ttk.Style()
        surface = style.lookup("TFrame", "background")
        # The empty client area blends into the surrounding surface (no stray
        # line under the tabs); the selected tab takes the strip's paper color
        # so it reads as joined to the strip directly below it.
        style.configure("ChordSheet.TNotebook", borderwidth=0, tabmargins=(0, 2, 0, 0),
                        background=surface, bordercolor=surface,
                        lightcolor=surface, darkcolor=surface)
        style.layout("ChordSheet.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        style.configure("ChordSheet.TNotebook.Tab", padding=(10, 3), bordercolor=UI_BORDER)
        style.map(
            "ChordSheet.TNotebook.Tab",
            padding=[("selected", (12, 5))],
            expand=[("selected", (0, 2, 0, 0))],
            background=[("selected", STRIP_BG), ("active", UI_HOVER), ("!selected", UI_TAB_IDLE)],
            lightcolor=[("selected", STRIP_BG), ("!selected", UI_TAB_IDLE)],
            foreground=[("disabled", UI_TEXT_DISABLED)],
        )

    def _wire_viewmodel(self) -> None:
        """Subscribe to the viewmodel's observable state."""
        self._vm.observe("rendered_song", self._on_rendered_song_changed)
        self._vm.observe("current_index", self._on_current_index_changed)
        self._vm.observe("active_view", self._on_active_view_changed)
        self._vm.observe("available_views", self._on_available_views_changed)
        self._vm.observe("zoom", self._on_zoom_changed)

    # -- Viewmodel observers ------------------------------------------------

    def _on_rendered_song_changed(self, _song) -> None:
        """Re-layout and repaint when the displayed song changes."""
        self._relayout_and_paint()

    def _on_current_index_changed(self, _index) -> None:
        """Move the highlight and auto-scroll to follow the playhead."""
        self._draw_highlight()
        self._follow_playhead()

    def _on_active_view_changed(self, view_id: str) -> None:
        """Repaint with the newly selected renderer."""
        self._select_tab(view_id)
        # Zoom support is per-renderer, so the buttons may enable/disable.
        self._update_zoom_buttons_state()
        self._relayout_and_paint()

    def _on_available_views_changed(self, views) -> None:
        """Update the tabs' enabled state when gating changes."""
        self._update_view_buttons_state(views)

    def _on_zoom_changed(self, _zoom) -> None:
        """Re-layout and repaint at the new zoom (display-only, no re-render)."""
        self._relayout_and_paint()

    # -- Tk event handlers --------------------------------------------------

    def _on_tab_changed(self, _event=None) -> None:
        """Forward a user's tab selection to the session.

        <<NotebookTabChanged>> is queued, so it also arrives after our own
        programmatic selects (when ``_syncing_tabs`` is already cleared). Those
        always match the viewmodel's active view; only a real click differs.
        Forwarding them would record the startup fallback as the user's choice.
        """
        if self._syncing_tabs:
            return
        view_id = self._tab_ids[self._tabs.index("current")]
        if view_id == self._vm.active_view:
            return
        self._session.set_chord_sheet_view(view_id)

    def _select_tab(self, view_id: str) -> None:
        """Select the tab for ``view_id`` without notifying the viewmodel."""
        if view_id not in self._tab_ids:
            return
        self._syncing_tabs = True
        try:
            self._tabs.select(self._tab_ids.index(view_id))
        finally:
            self._syncing_tabs = False

    def _tab_tip_text(self, index: int) -> Optional[str]:
        """Tooltip text for tab ``index``: why it is disabled, else ``None``."""
        if self._tabs.tab(index, "state") != "disabled":
            return None
        return self._vm.fretted_views_unavailable_reason

    def _update_view_buttons_state(self, views=None) -> None:
        """Enable tabs for available views, disable the gated-out rest.

        Disabling the selected tab makes Tk auto-select another one, so the
        change handler is suppressed while states update and the selection is
        then re-synced to the viewmodel's own active view.

        Args:
            views: Available renderer ids, or ``None`` to read the
                viewmodel's current ``available_views``.
        """
        available = set(views if views is not None else self._vm.available_views)
        self._syncing_tabs = True
        try:
            for index, view_id in enumerate(self._tab_ids):
                self._tabs.tab(index, state="normal" if view_id in available else "disabled")
            if self._vm.active_view in self._tab_ids:
                self._tabs.select(self._tab_ids.index(self._vm.active_view))
        finally:
            self._syncing_tabs = False
        self._tab_tip.refresh()

    def _update_zoom_buttons_state(self) -> None:
        """Enable the +/- zoom buttons only when the active view supports zoom."""
        state = ["!disabled"] if self._vm.zoom_supported else ["disabled"]
        self._zoom_in_btn.state(state)
        self._zoom_out_btn.state(state)

    def _on_canvas_configure(self, _event) -> None:
        """Re-layout on resize, debounced so a sash-drag storm doesn't stutter.

        A sash drag fires one ``<Configure>`` per pixel, and each full
        re-layout + repaint is expensive. To keep interaction live without
        repainting on every pixel:

        - the FIRST configure after a quiet period repaints immediately (a
          normal window resize still feels responsive), then
        - every configure inside the ensuing burst only (re)arms a single
          trailing repaint ``CHORD_SHEET_CONFIGURE_DEBOUNCE_MS`` after the last
          one, so the burst collapses to one final repaint at the settled size.

        The trailing repaint (via ``_relayout_and_paint``) also repaints the
        frozen gutter, so the gutter follows the same cadence. Height
        persistence is driven separately off the paned window's sash-release
        event, so it is unaffected by this debounce.
        """
        if self._configure_after is None:
            # Leading edge: repaint now for immediate feedback.
            self._relayout_and_paint()
        else:
            # Mid-burst: drop the previously-armed trailing repaint.
            try:
                self.after_cancel(self._configure_after)
            except Exception:
                pass
        self._configure_after = self.after(
            CHORD_SHEET_CONFIGURE_DEBOUNCE_MS, self._on_configure_trailing
        )

    def _on_configure_trailing(self) -> None:
        """Fire the single trailing repaint at the end of a Configure burst."""
        self._configure_after = None
        self._relayout_and_paint()

    def _on_canvas_click(self, event) -> None:
        """Hit-test a click to a chord slot and audition it."""
        if self._layout is None:
            return
        content_x = self._canvas.canvasx(event.x)
        for slot in self._layout.slots:
            if slot.x <= content_x <= slot.x + slot.width:
                self._session.audition(slot.chord_index)
                return

    # -- Painting -----------------------------------------------------------

    def _relayout_and_paint(self) -> None:
        """Recompute the layout for the current song/view and repaint fully."""
        self._canvas.delete("all")
        self._lane_canvas.delete("all")
        self._layout = None
        # A full repaint invalidates any cached gutter replay.
        self._gutter_state = None

        song = self._vm.rendered_song
        renderer = self._vm.active_renderer
        if song is None or renderer is None:
            self._collapse_gutter()
            return

        # The renderer gets the main canvas's height; the marker lane occupies
        # its own fixed-height canvas above it, so the content already excludes
        # the lane (the panel reserves it via the two-canvas split).
        height = max(1, self._canvas.winfo_height())
        ctx = SheetContext(song=song, zoom=self._vm.zoom_for_active_view)
        layout = renderer.layout(ctx, float(height))
        self._layout = layout
        self._canvas.config(scrollregion=(0, 0, layout.width, layout.height))
        self._lane_canvas.config(scrollregion=(0, 0, layout.width, LANE_HEIGHT))

        # Highlight is drawn first so it sits behind the card ops.
        self._draw_highlight()

        ops = DrawOps()
        renderer.paint(ops, ctx, layout)
        self._resolve_images(ops.ops)
        replay(ops.ops, self._canvas, self._images)

        # Marker lane spans the same content width, drawn by the panel so every
        # view gets it for free.
        self._paint_marker_lane(song, layout)
        self._follow_playhead()
        # Paint the frozen gutter last so it reflects the final scroll position.
        self._repaint_gutter()

    def _paint_marker_lane(self, song, layout: StripLayout) -> None:
        """Draw the timeline marker lane over the full content width."""
        lane_ops = build_marker_lane(
            song.markers, song.chords, layout.slots, LANE_HEIGHT, layout.width
        )
        replay(lane_ops.ops, self._lane_canvas, self._images)

    def _repaint_gutter(self) -> None:
        """Size, show, and repaint the frozen left gutter for the active view.

        The gutter is a non-scrolling pane whose width comes from the renderer's
        :meth:`~chord_sheet.renderer_interface.StripRenderer.gutter_width`
        (0 collapses it entirely). Its ops are painted in gutter-local
        coordinates with ``scroll_x`` = the content x currently at the strip
        viewport's left edge, so scroll-dependent gutters can redraw. Identical
        replays (same renderer, scroll_x, height, zoom, width) are skipped.
        """
        song = self._vm.rendered_song
        renderer = self._vm.active_renderer
        if song is None or renderer is None:
            self._collapse_gutter()
            return

        height = max(1, self._canvas.winfo_height())
        ctx = SheetContext(song=song, zoom=self._vm.zoom_for_active_view)
        width = float(renderer.gutter_width(ctx, float(height)))
        if width <= 0:
            self._collapse_gutter()
            return

        # Ensure the pane is shown at the right width.
        if self._gutter_width != width:
            pixels = int(round(width))
            self._gutter_canvas.config(width=pixels)
            self._gutter_corner.config(width=pixels)
            self._gutter_canvas.grid(row=1, column=0, sticky="ns")
            self._gutter_corner.grid(row=0, column=0, sticky="nsew")
            self._gutter_width = width

        scroll_x = float(self._canvas.canvasx(0))
        key = (id(renderer), round(scroll_x, 2), height, round(ctx.zoom, 3),
               round(width, 2))
        if key == self._gutter_state:
            return
        self._gutter_state = key

        self._gutter_canvas.delete("all")
        ops = DrawOps()
        renderer.paint_gutter(ops, ctx, float(height), scroll_x)
        self._resolve_images(ops.ops)
        replay(ops.ops, self._gutter_canvas, self._images)

    def _collapse_gutter(self) -> None:
        """Hide the frozen gutter pane entirely (renderer declares no gutter)."""
        if self._gutter_width != 0.0 or self._gutter_state is not None:
            self._gutter_canvas.grid_remove()
            self._gutter_corner.grid_remove()
            self._gutter_canvas.delete("all")
        self._gutter_width = 0.0
        self._gutter_state = None

    def _resolve_images(self, ops) -> None:
        """Resolve image-op keys to Tk images, caching them on the panel.

        Each :class:`ImageOp` key (e.g. ``'clef_treble:96'``) is resolved through
        :func:`image_for_clef_key` and converted to a ``PhotoImage`` kept in
        :attr:`_images` (so Tk does not garbage-collect it). Unknown keys are
        logged once and left unresolved, so :func:`replay` skips them.
        """
        from PIL import ImageTk

        for op in ops:
            if not isinstance(op, ImageOp) or op.key in self._images:
                continue
            image = image_for_clef_key(op.key)
            if image is None:
                if op.key not in self._warned_image_keys:
                    self._warned_image_keys.add(op.key)
                    logger.warning("Skipping unknown chord-sheet image key: %r", op.key)
                continue
            self._images[op.key] = ImageTk.PhotoImage(image)

    def _draw_highlight(self) -> None:
        """Draw (or move) the highlight rect behind the current slot."""
        self._canvas.delete("playhead-highlight")
        layout = self._layout
        index = self._vm.current_index
        if layout is None or index is None:
            return
        slot = self._slot_for_index(index)
        if slot is None:
            return
        self._canvas.create_rectangle(
            slot.x,
            0,
            slot.x + slot.width,
            layout.height,
            fill=_HIGHLIGHT_FILL,
            outline="",
            tags=("playhead-highlight",),
        )
        self._canvas.tag_lower("playhead-highlight")

    def _follow_playhead(self) -> None:
        """Auto-scroll so the current slot stays in the comfortable band."""
        layout = self._layout
        index = self._vm.current_index
        if layout is None or index is None:
            return
        slot = self._slot_for_index(index)
        if slot is None:
            return

        viewport = self._canvas.winfo_width()
        content_width = layout.width
        current_scroll = self._canvas.canvasx(0)
        playhead_x = slot.x + slot.width / 2.0

        target = self._vm.scroll_target(
            playhead_x, float(viewport), float(current_scroll), float(content_width)
        )
        if target is not None and content_width > 0:
            fraction = target / content_width
            self._canvas.xview_moveto(fraction)
            self._lane_canvas.xview_moveto(fraction)
            # Auto-scroll moved the viewport: refresh the scroll-dependent gutter.
            self._repaint_gutter()

    def _slot_for_index(self, index: int):
        """Return the :class:`SlotBox` for a chord index, or ``None``."""
        if self._layout is None:
            return None
        for slot in self._layout.slots:
            if slot.chord_index == index:
                return slot
        return None
