"""The chord-sheet strip renderer plugin contract.

This module is the frozen seam between the chord-sheet machinery (viewmodel +
panel) and the individual strip renderers. The placeholder
:class:`~ui.chord_sheet.name_card.NameCardRenderer` implements it today; the
four real renderers (keyboard diagram, grand staff, guitar fret box, and tab
view) plug in later **without changing this interface**.

Design rules for renderers:

- A renderer is a *pure function of* ``(ctx, height)``. :meth:`StripRenderer.layout`
  and :meth:`StripRenderer.paint` must not mutate the context, read Tk, or hold
  per-paint state: given the same ``SheetContext`` and ``height`` they must
  produce the same :class:`StripLayout` and the same ops. This lets the panel
  re-layout and re-paint freely (on resize, scroll, or highlight change) and
  lets tests exercise renderers headlessly.
- ``layout`` returns one :class:`SlotBox` per rendered chord, **in song order**,
  including rests. Rests (``RenderedChord.is_rest``) get slim slots.
- ``paint`` draws into a :class:`~ui.chord_sheet.ops.DrawOps` recorder using the
  geometry from the matching :class:`StripLayout` -- it never recomputes x
  positions independently, so hit-testing (which uses the layout) and painting
  stay consistent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

from models.rendered_song import RenderedChord, RenderedSong
from ui.chord_sheet.ops import DrawOps


@dataclass(frozen=True)
class SlotBox:
    """Hit-test and playhead geometry for one rendered chord.

    Only the horizontal extent is tracked: the strip is a single horizontal row,
    so a click maps to a slot by x alone, and the playhead is a vertical rule at
    the slot's x. ``chord_index`` indexes into ``RenderedSong.chords``.
    """

    chord_index: int
    x: float
    width: float


@dataclass(frozen=True)
class StripLayout:
    """The laid-out strip: total content size plus one slot per chord.

    ``slots`` is one :class:`SlotBox` per rendered chord in song order (rests
    included). ``width``/``height`` are the content-space extent the panel uses
    to size the canvas scroll region.
    """

    width: float
    height: float
    slots: Tuple[SlotBox, ...]


@dataclass
class SheetContext:
    """Song-wide precomputed info shared by renderers for one render.

    Holds the :class:`RenderedSong` being displayed. Deliberately a mutable
    dataclass with room to grow: later renderers will attach precomputed,
    song-wide helpers here (keyboard window bounds, fretboard spec, a staff
    pitch->line resolver, ...) so per-chord painting stays cheap. Renderers
    must treat it as read-only during ``layout``/``paint``.
    """

    song: RenderedSong

    zoom: float = 1.0
    """User zoom factor for renderers that declare ``supports_zoom``. 1.0 =
    default size. Zoom scales the renderer's intrinsic geometry (staff
    space, string gap, fret-box size), not the panel height."""


class StripRenderer(ABC):
    """A pluggable chord-sheet strip view.

    Subclasses declare an ``id`` (stable key persisted in config and used by the
    view picker) and a human ``label``, then implement :meth:`layout` and
    :meth:`paint` as pure functions of ``(ctx, height)``.
    """

    id: str = ""
    """Stable renderer key: ``'keyboard' | 'staff' | 'fret' | 'tab' | 'name'``."""

    label: str = ""
    """Human-readable name shown in the view picker."""

    supports_zoom: bool = False
    """Whether this renderer honors ``SheetContext.zoom`` (the panel enables
    its +/- zoom buttons only for such renderers)."""

    def gutter_width(self, ctx: 'SheetContext', height: float) -> float:
        """Width in px of this renderer's frozen left gutter, or 0 for none.

        The gutter is drawn on a separate, non-scrolling canvas pinned to the
        strip's left edge (e.g. the piano roll's keyboard, the staff view's
        clefs and key signature), so it stays visible while the content
        scrolls. Pure function of (ctx, height).
        """
        return 0.0

    def paint_gutter(self, ops: DrawOps, ctx: 'SheetContext', height: float,
                     scroll_x: float) -> None:
        """Emit draw ops for the frozen gutter.

        Called on every render AND whenever the strip scrolls, with
        ``scroll_x`` = the content x currently at the viewport's left edge,
        so scroll-dependent gutters (the staff view's key signature must show
        the key in effect at the first visible chord) can redraw. Renderers
        with a static gutter simply ignore ``scroll_x``. Coordinates are
        gutter-local (x=0 is the gutter's left edge). Default: nothing.
        """
        return None

    requires_fingering: bool = False
    """When ``True`` the renderer only makes sense for songs that carry
    fretboard fingering data (``RenderedChord.fingering``); the viewmodel hides
    it from ``available_views`` for songs voiced without fingerings (e.g. piano).
    """

    @abstractmethod
    def layout(self, ctx: SheetContext, height: float) -> StripLayout:
        """Compute the strip layout for the given content ``height``.

        Args:
            ctx: Song-wide context (read-only).
            height: Available content height in pixels.

        Returns:
            A :class:`StripLayout` with one :class:`SlotBox` per chord, in song
            order, rests included (as slim slots).
        """
        raise NotImplementedError

    @abstractmethod
    def paint(self, ops: DrawOps, ctx: SheetContext, layout: StripLayout) -> None:
        """Emit draw ops for the strip.

        Args:
            ops: Recorder to append primitive draw ops to.
            ctx: Song-wide context (read-only).
            layout: The layout previously returned by :meth:`layout` for the
                same ``ctx``/``height``; painting reuses its slot geometry.
        """
        raise NotImplementedError


def chord_symbol_label(chord: RenderedChord) -> str:
    """Display label for a chord's symbol on the strip.

    Roman-numeral (relative) chords append the absolute chord they resolved
    to in the current key, e.g. ``"V7 (G7)"``; absolute chords are shown
    as written.

    Args:
        chord: The rendered chord whose label to build.

    Returns:
        The label text.
    """
    label = chord.chord_info.chord
    notes = chord.chord_notes
    if notes is not None and notes.resolved_symbol:
        return f"{label} ({notes.resolved_symbol})"
    return label


#: Shared note-color palette, used by every renderer that color-codes notes so
#: the strip reads consistently across views. Ensemble voicings color by voice
#: (indexed low voice first, matching ``RenderedChord.voice_notes`` /
#: ``RenderedSong.voice_labels`` order, wrapping if there are more voices than
#: colors); muted, distinguishable hues on the light strip background.
VOICE_COLORS: Tuple[str, ...] = (
    "#3a5a8a",  # low voice (e.g. Bass) - blue
    "#4a7a4a",  # e.g. Tenor - green
    "#a07a3a",  # e.g. Alto - amber
    "#a04848",  # top voice (e.g. Soprano) - red
    "#7a4a8a",  # 5th voice - purple
    "#3a8a7a",  # 6th voice - teal
    "#8a8a3a",  # 7th voice - olive
    "#8a4a3a",  # 8th voice - rust
)

#: Piano-model hand colors (two tones of the same family so hands read as
#: related but separable).
HAND_COLORS = {"lh": "#8a5a3a", "rh": "#2a6f8a"}

#: Default note ink when there is no voice/hand structure (e.g. guitar).
NOTE_INK = "#22323a"

#: Background color of the whole strip (panel canvases and any cutout rects a
#: renderer draws behind glyphs/numbers must use this so they blend in).
STRIP_BG = "#fbfbf8"


def measure_boundaries(song: RenderedSong) -> List[float]:
    """Absolute beat positions of measure boundaries across the song.

    Walks ``song.meter_map`` (each entry starts a fresh bar) stepping by that
    meter's beats-per-bar until the next meter change or ``total_beats``.
    Beat 0 is not included; a meter-change point itself is a boundary.

    Returns:
        Strictly increasing beat positions, possibly empty for tiny songs.
    """
    boundaries: List[float] = []
    meters = list(song.meter_map) or [(0.0, (4, 4))]
    eps = 1e-9
    for i, (seg_start, (beats, _unit)) in enumerate(meters):
        seg_end = meters[i + 1][0] if i + 1 < len(meters) else song.total_beats
        if beats <= 0:
            continue
        if seg_start > eps and (not boundaries or seg_start > boundaries[-1] + eps):
            boundaries.append(seg_start)
        b = seg_start + beats
        while b < seg_end - eps:
            boundaries.append(b)
            b += beats
    if boundaries and abs(boundaries[-1] - song.total_beats) < eps:
        boundaries.pop()
    return boundaries


def bar_line_xs(layout: StripLayout, song: RenderedSong) -> List[float]:
    """X positions of measure-boundary bar lines within a strip layout.

    Boundaries that fall INSIDE a chord's slot are interpolated beat-
    proportionally into it, so a chord held across a measure boundary (e.g.
    ``A*8`` in 4/4) still shows the bar line mid-chord. A boundary exactly at
    a chord's start lands on that slot's left edge. Boundaries outside every
    slot (past the last chord) are dropped.

    Args:
        layout: The layout whose slots to map into (slot order matches
            ``song.chords``).
        song: The rendered song providing ``start_beat``/``duration_beats``.

    Returns:
        X positions in content coordinates, in ascending order.
    """
    xs: List[float] = []
    eps = 1e-9
    slots = layout.slots
    chords = song.chords
    for beat in measure_boundaries(song):
        for slot in slots:
            chord = chords[slot.chord_index]
            start = chord.start_beat
            dur = chord.duration_beats
            if beat < start - eps:
                xs.append(slot.x)
                break
            if beat < start + dur - eps:
                if dur > eps and beat > start + eps:
                    xs.append(slot.x + slot.width * (beat - start) / dur)
                else:
                    xs.append(slot.x)
                break
    return xs
