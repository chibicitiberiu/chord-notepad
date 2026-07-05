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

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._hbar = ttk.Scrollbar(body, orient=tk.HORIZONTAL)
        self._hbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Slim marker lane on top; the main strip fills the rest. Both scroll
        # horizontally together (one scrollbar drives both) so markers stay
        # aligned with the cards below them.
        self._lane_canvas = tk.Canvas(
            body,
            height=int(LANE_HEIGHT),
            highlightthickness=0,
            bg=STRIP_BG,
        )
        self._lane_canvas.pack(side=tk.TOP, fill=tk.X)

        self._canvas = tk.Canvas(
            body,
            height=100,
            highlightthickness=0,
            bg=STRIP_BG,
            xscrollcommand=self._hbar.set,
        )
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._hbar.config(command=self._xview_both)

        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Button-1>", self._on_canvas_click)

    def _xview_both(self, *args) -> None:
        """Scroll the marker lane and the main strip together (scrollbar cmd)."""
        self._canvas.xview(*args)
        self._lane_canvas.xview(*args)

    def _wire_viewmodel(self) -> None:
        """Subscribe to the viewmodel's observable state."""
        self._vm.observe("rendered_song", self._on_rendered_song_changed)
        self._vm.observe("current_index", self._on_current_index_changed)
        self._vm.observe("active_view", self._on_active_view_changed)
        self._vm.observe("available_views", self._on_available_views_changed)
        self._vm.observe("capo_suggestion", self._on_capo_suggestion_changed)

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
        self._relayout_and_paint()

    def _on_available_views_changed(self, views) -> None:
        """Update the toggle buttons' enabled state when gating changes."""
        self._update_view_buttons_state(views)

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

    def _on_canvas_configure(self, _event) -> None:
        """Re-layout on resize (height feeds the renderer)."""
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

        song = self._vm.rendered_song
        renderer = self._vm.active_renderer
        if song is None or renderer is None:
            return

        # The renderer gets the main canvas's height; the marker lane occupies
        # its own fixed-height canvas above it, so the content already excludes
        # the lane (the panel reserves it via the two-canvas split).
        height = max(1, self._canvas.winfo_height())
        ctx = SheetContext(song=song)
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

    def _paint_marker_lane(self, song, layout: StripLayout) -> None:
        """Draw the timeline marker lane over the full content width."""
        lane_ops = build_marker_lane(
            song.markers, song.chords, layout.slots, LANE_HEIGHT, layout.width
        )
        replay(lane_ops.ops, self._lane_canvas, self._images)

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

    def _slot_for_index(self, index: int):
        """Return the :class:`SlotBox` for a chord index, or ``None``."""
        if self._layout is None:
            return None
        for slot in self._layout.slots:
            if slot.chord_index == index:
                return slot
        return None
