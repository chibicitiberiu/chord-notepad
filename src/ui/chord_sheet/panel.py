"""The chord-sheet panel: a horizontal-scrolling strip of voiced-chord cards.

``ChordSheetPanel`` is the thin Tk shell around the headless
:class:`~viewmodels.chord_sheet_viewmodel.ChordSheetViewModel`. It hosts a
horizontally-scrolling ``Canvas`` (plus a view picker), replays the active
renderer's draw ops onto it, highlights the chord under the playhead, follows
playback by auto-scrolling, and turns clicks into auditions. All layout/paint
logic lives in the renderers and all state lives in the viewmodel; this class
only bridges them to Tkinter.
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Set

from constants import CHORD_SHEET_CONFIGURE_DEBOUNCE_MS
from ui.chord_sheet.clef_assets import image_for_clef_key
from ui.chord_sheet.marker_lane import LANE_HEIGHT, build_marker_lane
from ui.chord_sheet.ops import DrawOps, ImageOp, replay
from ui.chord_sheet.renderer_interface import SheetContext, STRIP_BG, StripLayout

logger = logging.getLogger(__name__)

#: Highlight fill drawn behind the chord slot under the playhead.
_HIGHLIGHT_FILL = "#ffe58a"

#: Muted foreground for the capo-suggestion label in the header row.
_MUTED_FG = "#666666"

#: Views for which the capo suggestion is relevant (fretboard renderers).
_FRETBOARD_VIEWS = ("fret", "tab")


class ChordSheetPanel(ttk.Frame):
    """Tk shell hosting the scrolling chord-sheet strip."""

    def __init__(self, parent: tk.Widget, viewmodel, **kwargs) -> None:
        """Build the panel and wire it to the viewmodel.

        Args:
            parent: Parent widget.
            viewmodel: A :class:`ChordSheetViewModel`.
            **kwargs: Passed through to ``ttk.Frame``.
        """
        super().__init__(parent, **kwargs)
        self._vm = viewmodel
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

        ttk.Label(header, text="View:").pack(side=tk.LEFT)

        # One Toolbutton-style radiobutton per renderer the viewmodel knows
        # (in its registered order), sharing a single StringVar so selecting
        # one deselects the rest. Renderers gated out for the current song
        # (e.g. fretted views for a piano-voiced song) stay visible but
        # disabled, so the row's layout never shifts.
        self._view_var = tk.StringVar(value=self._vm.active_view)
        self._view_buttons: dict = {}
        for renderer in self._vm.renderers:
            button = ttk.Radiobutton(
                header,
                text=renderer.label,
                value=renderer.id,
                variable=self._view_var,
                style="Toolbutton",
                command=self._on_view_picked,
            )
            button.pack(side=tk.LEFT, padx=(4, 0))
            self._view_buttons[renderer.id] = button
        self._update_view_buttons_state()

        # Capo suggestion (advice only), shown next to the toggles while a
        # fret/tab view is active and the viewmodel has a suggestion.
        self._capo_label = ttk.Label(header, text="", foreground=_MUTED_FG)
        self._capo_label.pack(side=tk.LEFT, padx=(12, 0))
        self._update_capo_label()

        # Compact zoom controls pinned to the right end of the header row,
        # enabled only while the active view declares ``supports_zoom``. Packed
        # right-to-left so "+" is rightmost and "-" sits to its left.
        self._zoom_in_btn = ttk.Button(
            header, text="+", width=2, style="Toolbutton", command=self._vm.zoom_in
        )
        self._zoom_in_btn.pack(side=tk.RIGHT, padx=(0, 0))
        self._zoom_out_btn = ttk.Button(
            header, text="−", width=2, style="Toolbutton", command=self._vm.zoom_out
        )
        self._zoom_out_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self._update_zoom_buttons_state()

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
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

    def _wire_viewmodel(self) -> None:
        """Subscribe to the viewmodel's observable state."""
        self._vm.observe("rendered_song", self._on_rendered_song_changed)
        self._vm.observe("current_index", self._on_current_index_changed)
        self._vm.observe("active_view", self._on_active_view_changed)
        self._vm.observe("available_views", self._on_available_views_changed)
        self._vm.observe("capo_suggestion", self._on_capo_suggestion_changed)
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
        if self._view_var.get() != view_id:
            self._view_var.set(view_id)
        # The suggestion is only shown for fret/tab, so its visibility can
        # change purely from a view switch.
        self._update_capo_label()
        # Zoom support is per-renderer, so the buttons may enable/disable.
        self._update_zoom_buttons_state()
        self._relayout_and_paint()

    def _on_available_views_changed(self, views) -> None:
        """Update the toggle buttons' enabled state when gating changes."""
        self._update_view_buttons_state(views)

    def _on_zoom_changed(self, _zoom) -> None:
        """Re-layout and repaint at the new zoom (display-only, no re-render)."""
        self._relayout_and_paint()

    def _on_capo_suggestion_changed(self, _suggestion) -> None:
        """Show/hide/update the capo suggestion label."""
        self._update_capo_label()

    def _update_capo_label(self) -> None:
        """Refresh the capo-suggestion label from the viewmodel state.

        Text is shown only when a suggestion exists AND a fretboard view
        (fret/tab) is active; it is blank otherwise.
        """
        suggestion = self._vm.capo_suggestion
        if suggestion is not None and self._vm.active_view in _FRETBOARD_VIEWS:
            self._capo_label.config(text=f"Suggested: capo {suggestion}")
        else:
            self._capo_label.config(text="")

    # -- Tk event handlers --------------------------------------------------

    def _on_view_picked(self) -> None:
        """Forward a toggle-button selection to the viewmodel."""
        self._vm.set_active_view(self._view_var.get())

    def _update_view_buttons_state(self, views=None) -> None:
        """Enable buttons for available views, disable the gated-out rest.

        Args:
            views: Available renderer ids, or ``None`` to read the
                viewmodel's current ``available_views``.
        """
        available = set(views if views is not None else self._vm.available_views)
        for view_id, button in self._view_buttons.items():
            if view_id in available:
                button.state(["!disabled"])
            else:
                button.state(["disabled"])

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
                self._vm.audition(slot.chord_index)
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
        :meth:`~ui.chord_sheet.renderer_interface.StripRenderer.gutter_width`
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
