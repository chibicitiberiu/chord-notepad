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
from typing import Tuple

from models.rendered_song import RenderedSong
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
