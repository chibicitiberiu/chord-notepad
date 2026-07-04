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
from typing import Optional

from ui.chord_sheet.ops import DrawOps, replay
from ui.chord_sheet.renderer_interface import SheetContext, StripLayout

logger = logging.getLogger(__name__)

#: Highlight fill drawn behind the chord slot under the playhead.
_HIGHLIGHT_FILL = "#ffe58a"


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
        self._images: dict = {}  # asset key -> Tk image (none needed by NameCard yet)

        self._build_widgets()
        self._wire_viewmodel()

        # Initial paint (a song may already be present when the panel is shown).
        self._relayout_and_paint()

    # -- Construction -------------------------------------------------------

    def _build_widgets(self) -> None:
        """Create the view picker, canvas, and horizontal scrollbar."""
        header = ttk.Frame(self)
        header.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 0))

        ttk.Label(header, text="View:").pack(side=tk.LEFT)
        self._view_var = tk.StringVar(value=self._vm.active_view)
        self._view_picker = ttk.Combobox(
            header,
            textvariable=self._view_var,
            state="readonly",
            width=16,
            values=list(self._vm.available_views),
        )
        self._view_picker.pack(side=tk.LEFT, padx=(4, 0))
        self._view_picker.bind("<<ComboboxSelected>>", self._on_view_picked)

        body = ttk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)

        self._hbar = ttk.Scrollbar(body, orient=tk.HORIZONTAL)
        self._hbar.pack(side=tk.BOTTOM, fill=tk.X)

        self._canvas = tk.Canvas(
            body,
            height=100,
            highlightthickness=0,
            xscrollcommand=self._hbar.set,
        )
        self._canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self._hbar.config(command=self._canvas.xview)

        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Button-1>", self._on_canvas_click)

    def _wire_viewmodel(self) -> None:
        """Subscribe to the viewmodel's observable state."""
        self._vm.observe("rendered_song", self._on_rendered_song_changed)
        self._vm.observe("current_index", self._on_current_index_changed)
        self._vm.observe("active_view", self._on_active_view_changed)
        self._vm.observe("available_views", self._on_available_views_changed)

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
        self._relayout_and_paint()

    def _on_available_views_changed(self, views) -> None:
        """Update the picker's options when gating changes."""
        self._view_picker.config(values=list(views))

    # -- Tk event handlers --------------------------------------------------

    def _on_view_picked(self, _event) -> None:
        """Forward a picker selection to the viewmodel."""
        self._vm.set_active_view(self._view_var.get())

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
        self._layout = None

        song = self._vm.rendered_song
        renderer = self._vm.active_renderer
        if song is None or renderer is None:
            return

        height = max(1, self._canvas.winfo_height())
        ctx = SheetContext(song=song)
        layout = renderer.layout(ctx, float(height))
        self._layout = layout
        self._canvas.config(scrollregion=(0, 0, layout.width, layout.height))

        # Highlight is drawn first so it sits behind the card ops.
        self._draw_highlight()

        ops = DrawOps()
        renderer.paint(ops, ctx, layout)
        replay(ops.ops, self._canvas, self._images)
        self._follow_playhead()

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
            self._canvas.xview_moveto(target / content_width)

    def _slot_for_index(self, index: int):
        """Return the :class:`SlotBox` for a chord index, or ``None``."""
        if self._layout is None:
            return None
        for slot in self._layout.slots:
            if slot.chord_index == index:
                return slot
        return None
