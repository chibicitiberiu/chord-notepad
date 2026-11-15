"""The chord-sheet strip renderer plugin contract.

This module is the frozen seam between the chord-sheet machinery (viewmodel +
panel) and the individual strip renderers. The placeholder
:class:`~chord_sheet.name_card.NameCardRenderer` implements it today; the
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
- ``paint`` draws into a :class:`~chord_sheet.ops.DrawOps` recorder using the
  geometry from the matching :class:`StripLayout` -- it never recomputes x
  positions independently, so hit-testing (which uses the layout) and painting
  stay consistent.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from chordnotepad.models.rendered_song import RenderedChord, RenderedSong
from chordnotepad.chord_sheet.ops import DrawOps


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

    notation: str = "american"
    """The song's notation (``"american"`` or ``"european"``), for renderers
    that draw note names (``models.notation.Notation`` values)."""


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

    def gutter_breakpoints(self, ctx: 'SheetContext', height: float,
                           layout: 'StripLayout') -> List[float]:
        """Scroll positions where :meth:`paint_gutter` may start painting
        something different.

        The gutter painted for any ``scroll_x`` greater than one breakpoint
        and not greater than the next is the same, so a host that cannot call
        :meth:`paint_gutter` on every scroll (Android, through the op buffer)
        paints one gutter per range instead. Breakpoints are content x
        values; the default, ``[]``, means the gutter ignores ``scroll_x``.
        Pure function of (ctx, height, layout).
        """
        return []

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


#: Estimated advance of a bold label's characters, in ems: narrow letters and
#: punctuation, wide M/W/m/w, other capitals, the rest (lower case, digits,
#: accidentals). Measured against Inter Bold (the Qt window's font): within 2%
#: for chord names, rarely over. Regular text is narrower, so it overestimates.
_NARROW_CHARS = frozenset("iljIt()[]/,.:;|' !f")
_WIDE_CHARS = frozenset("MWmw")
_NARROW_EM, _WIDE_EM, _UPPER_EM, _OTHER_EM = 0.36, 0.98, 0.78, 0.64


def label_ems(label: str) -> float:
    """Estimated width of a bold ``label`` in ems (no font metrics in the core)."""
    total = 0.0
    for ch in label:
        if ch in _NARROW_CHARS:
            total += _NARROW_EM
        elif ch in _WIDE_CHARS:
            total += _WIDE_EM
        elif ch.isupper():
            total += _UPPER_EM
        else:
            total += _OTHER_EM
    return total


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

#: Fill the panel draws behind the chord slot under the playhead.
PLAYHEAD_HIGHLIGHT = "#ffe58a"

#: Paper of every second section (the 2nd, 4th, ...), a subtle step darker
#: than :data:`STRIP_BG`, so a section change shows across the whole strip.
#: The front ends map it from their own surface (Qt
#: ``sheet_paint.themed_color``, Android ``themedSheetColor``), as they map
#: ``STRIP_BG``; Tk paints it as written.
SECTION_BAND = "#f1f1ed"

#: Marker kinds that start a section (as the player's timeline counts them,
#: ``session.timeline.song_sections``).
_SECTION_KINDS = ("section", "loop")


def section_band_spans(song: RenderedSong, layout: StripLayout) -> List[Tuple[float, float]]:
    """The ``(x0, x1)`` spans of the sections painted on :data:`SECTION_BAND`.

    Sections start at the song's ``section`` and ``loop`` markers, as on the
    player's timeline: a marker starts its section at the first chord at or
    after its beat, a marker with no chord after it starts none, and two
    markers on the same chord make one start. Whatever comes before the
    first marker is a section too (an intro without a label). A section
    starts at the right edge of the slot before its first chord, so the
    space a renderer leaves ahead of a chord (a repeat sign, a key change)
    goes with the section it opens; the last one runs to the strip's end.
    Every second section, counted from the first, is returned.

    Args:
        song: The rendered song (its markers and chords).
        layout: The view's layout (slots in song order).

    Returns:
        Spans in content x, left to right, possibly empty.
    """
    chords = song.chords
    slots = layout.slots
    if not chords or not slots:
        return []
    order = {slot.chord_index: n for n, slot in enumerate(slots)}
    eps = 1e-9
    starts: List[float] = []
    index = 0
    for marker in song.markers or ():
        if marker.kind not in _SECTION_KINDS:
            continue
        while index < len(chords) and chords[index].start_beat < marker.beat - eps:
            index += 1
        if index == len(chords):
            break
        n = order.get(index)
        if n is None:
            continue
        x = slots[n - 1].x + slots[n - 1].width if n > 0 else 0.0
        if x <= eps:
            continue
        if not starts or x > starts[-1] + eps:
            starts.append(x)
    edges = [0.0] + starts + [layout.width]
    return [(edges[i], edges[i + 1]) for i in range(1, len(edges) - 1, 2)
            if edges[i + 1] > edges[i]]


def paint_section_bands(ops: DrawOps, song: RenderedSong,
                        layout: StripLayout) -> List[Tuple[float, float]]:
    """Paint the banded sections' paper across the content height.

    Every renderer calls this first, so its rows, lines and notes draw over
    the bands. Returns the spans (:func:`section_band_spans`) for renderers
    that draw their own paper-coloured patches (:func:`paper_at`).
    """
    spans = section_band_spans(song, layout)
    for x0, x1 in spans:
        ops.rect(x0, 0.0, x1 - x0, layout.height, fill=SECTION_BAND,
                 tags=("section-band",))
    return spans


def paper_at(x: float, spans: Sequence[Tuple[float, float]]) -> str:
    """The paper colour at content ``x``: :data:`SECTION_BAND` inside a
    banded span, else :data:`STRIP_BG`."""
    for x0, x1 in spans:
        if x0 <= x < x1:
            return SECTION_BAND
    return STRIP_BG


def gutter_paper(scroll_x: float, spans: Sequence[Tuple[float, float]]) -> str:
    """The paper of a frozen gutter scrolled to ``scroll_x``: the paper of
    the content that meets its right edge, so a banded section carries on
    under the gutter with no edge.

    A span counts for ``x0 < scroll_x <= x1``, the way a packed gutter run
    holds for every ``scroll_x`` past its start, so the band edges serve as
    the gutter's breakpoints (:meth:`StripRenderer.gutter_breakpoints`) and
    painting at a breakpoint gives the same gutter as the run before it.
    """
    for x0, x1 in spans:
        if x0 < scroll_x <= x1:
            return SECTION_BAND
    return STRIP_BG


#: Whole rest (Bravura ``restWhole``) proportions, in staff spaces: a block
#: hanging from a line. Shared so every view draws NC with the same symbol.
WHOLE_REST_W = 1.13
WHOLE_REST_H = 0.5
#: Length of the short line a standalone whole rest hangs from (no staff).
WHOLE_REST_LINE_W = 2.0


def paint_whole_rest(ops: DrawOps, cx: float, line_y: float, space: float,
                     fill: str, tag: str, *, own_line: bool = False) -> None:
    """Draw a whole rest centred on ``cx``, hanging below ``line_y``.

    Args:
        ops: Recorder to append draw ops to.
        cx: Horizontal centre.
        line_y: y of the line the rest hangs from.
        space: Size of one staff space (or the view's equivalent) in px.
        fill: Ink colour.
        tag: Slot tag for the ops.
        own_line: Also draw the short line it hangs from, for views with no
            staff line there (fret cards).
    """
    w = WHOLE_REST_W * space
    if own_line:
        half = WHOLE_REST_LINE_W * space / 2.0
        ops.line([(cx - half, line_y), (cx + half, line_y)], fill=fill,
                 width=max(1.0, 0.12 * space), tags=(tag,))
    ops.rect(cx - w / 2.0, line_y, w, WHOLE_REST_H * space, fill=fill, tags=(tag,))


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


def beat_boundaries(song: RenderedSong) -> List[float]:
    """Absolute beat positions of every beat inside a bar (not on a bar
    line) across the song, for a view's beat grid.

    Walks ``song.meter_map`` like :func:`measure_boundaries`, one beat at a
    time from each bar's start, leaving out the bar starts themselves.
    """
    beats: List[float] = []
    meters = list(song.meter_map) or [(0.0, (4, 4))]
    eps = 1e-9
    for i, (seg_start, (per_bar, _unit)) in enumerate(meters):
        seg_end = meters[i + 1][0] if i + 1 < len(meters) else song.total_beats
        if per_bar <= 0:
            continue
        bar = seg_start
        while bar < seg_end - eps:
            for k in range(1, int(per_bar)):
                beat = bar + k
                if beat < seg_end - eps:
                    beats.append(beat)
            bar += per_bar
    return beats


def beat_xs(layout: StripLayout, song: RenderedSong, beats: Sequence[float]) -> List[float]:
    """X positions of beat positions ``beats`` (ascending) within a strip
    layout, interpolated into the slot that holds each (as
    :func:`bar_line_xs` places bar lines); beats past every slot are dropped."""
    xs: List[float] = []
    eps = 1e-9
    slots = layout.slots
    chords = song.chords
    for beat in beats:
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
    return beat_xs(layout, song, measure_boundaries(song))
