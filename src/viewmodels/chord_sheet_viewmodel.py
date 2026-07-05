"""Headless viewmodel for the chord-sheet strip.

Owns the :class:`~models.rendered_song.RenderedSong` displayed by the strip and
the surrounding UI state (which renderer is active, which are available, whether
the panel is shown, and which chord the playhead is on). It is deliberately
Tk-free so it can be unit-tested without a display.

Re-rendering path: when the parsed song changes the viewmodel re-renders it
through the *same* path MIDI export uses -- ``PlaybackService.render_song`` with
the currently-selected note picker -- so the strip shows exactly the voicing
that would play/export. Rendering is expensive, so it is **debounced** and run
**off the UI thread**, with the result marshaled back the way every other
cross-thread result is (``Application.queue_ui_callback``). Both the debounce
timer and the UI-thread marshal are injectable seams so tests run synchronously.
"""

import logging
import threading
from typing import Callable, List, Optional

from constants import (
    CHORD_SHEET_RERENDER_DEBOUNCE_MS,
    DEFAULT_CHORD_SHEET_HEIGHT,
    DEFAULT_CHORD_SHEET_VIEW,
)
from models.chord import ChordInfo
from models.line import Line
from models.rendered_song import RenderedSong
from ui.chord_sheet.fret_card import FretCardRenderer
from ui.chord_sheet.piano_roll import PianoRollRenderer
from ui.chord_sheet.renderer_interface import StripRenderer
from ui.chord_sheet.staff_card import StaffCardRenderer
from ui.chord_sheet.tab_strip import TabStripRenderer
from utils.observable import Observable

logger = logging.getLogger(__name__)


def _default_renderers() -> List[StripRenderer]:
    """Build the standard renderer set, in view-picker order.

    Piano roll, Staff, Chord box, then Tab. The two fretted views declare
    ``requires_fingering`` so the viewmodel gates them out for songs voiced
    without fingering data (e.g. piano/ensemble).
    """
    return [
        PianoRollRenderer(),
        StaffCardRenderer(),
        FretCardRenderer(),
        TabStripRenderer(),
    ]

# Snap band for the auto-scroll rule (fractions of the viewport width).
_SCROLL_SNAP_TO = 0.25   # where the playhead is placed after a snap
_SCROLL_TRIGGER = 0.70   # playhead past this fraction triggers a forward snap
_SCROLL_EPSILON = 0.5    # px; scroll deltas smaller than this are treated as no-op


class _TimerScheduler:
    """Default debounce scheduler backed by ``threading.Timer``.

    ``schedule`` returns the timer as an opaque handle; ``cancel`` cancels it.
    The fired callback runs on the timer's own thread -- i.e. off the UI thread,
    which is exactly where the (expensive) render should happen.
    """

    def schedule(self, delay_seconds: float, fn: Callable[[], None]) -> object:
        """Schedule ``fn`` to run after ``delay_seconds`` on a background thread."""
        timer = threading.Timer(delay_seconds, fn)
        timer.daemon = True
        timer.start()
        return timer

    def cancel(self, handle: object) -> None:
        """Cancel a previously scheduled timer handle (no-op if ``None``)."""
        if handle is not None:
            handle.cancel()


class ChordSheetViewModel(Observable):
    """Presentation logic for the chord-sheet strip (headless, Observable).

    Observable properties (via :meth:`Observable.set_and_notify`):

    - ``rendered_song`` (``RenderedSong | None``): the song currently displayed.
    - ``current_index`` (``int | None``): index into ``rendered_song.chords`` the
      playhead is on, driven by the playback ping; ``None`` when nothing plays.
    - ``active_view`` (``str``): the active renderer id.
    - ``available_views`` (``List[str]``): renderer ids selectable for the current
      song (fingering-requiring renderers are gated out unless the song carries
      fingering data).
    - ``visible`` (``bool``): whether the panel is shown.
    """

    def __init__(
        self,
        config_service,
        audio_service,
        application=None,
        *,
        renderers: Optional[List[StripRenderer]] = None,
        render_fn: Optional[Callable[[List[Line], Optional[str]], Optional[RenderedSong]]] = None,
        audition_fn: Optional[Callable[[List[int]], None]] = None,
        scheduler=None,
        marshal: Optional[Callable[[Callable[[], None]], None]] = None,
        debounce_ms: int = CHORD_SHEET_RERENDER_DEBOUNCE_MS,
    ) -> None:
        """Create the viewmodel.

        Args:
            config_service: ConfigService for persisting/loading strip settings.
            audio_service: PlaybackService; used for the default render and
                audition seams.
            application: Application, for the default UI-thread marshal.
            renderers: Strip renderers to offer; defaults to the standard set
                (:func:`_default_renderers`: keyboard, staff, chord box, tab).
            render_fn: Injectable ``(lines, key) -> RenderedSong | None`` seam;
                defaults to ``audio_service.render_song``.
            audition_fn: Injectable ``(midi_notes) -> None`` seam; defaults to
                ``audio_service.play_notes_immediate``.
            scheduler: Injectable debounce scheduler with ``schedule(delay, fn)``
                / ``cancel(handle)``; defaults to a ``threading.Timer`` seam.
            marshal: Injectable UI-thread marshal; defaults to
                ``application.queue_ui_callback`` (or a direct call if no
                application is supplied).
            debounce_ms: Debounce window in milliseconds.
        """
        super().__init__()

        self._config = config_service
        self._audio = audio_service
        self._application = application

        self._renderers: List[StripRenderer] = (
            list(renderers) if renderers is not None else _default_renderers()
        )
        self._render_fn = render_fn or audio_service.render_song
        self._audition_fn = audition_fn or audio_service.play_notes_immediate
        self._scheduler = scheduler or _TimerScheduler()
        self._marshal = marshal or self._default_marshal
        self._debounce_seconds = max(0.0, debounce_ms) / 1000.0

        # Debounce/render bookkeeping.
        self._pending_input: Optional[tuple] = None  # (lines, key)
        self._render_handle: object = None
        # True when the pending input has not yet been rendered into
        # ``rendered_song``. While the panel is hidden we hold render work back
        # (no wasted background renders) and flush it when the panel is shown.
        self._dirty: bool = False

        # Observable state (private storage with leading underscore).
        self._rendered_song: Optional[RenderedSong] = None
        self._current_index: Optional[int] = None
        self._active_view: str = self._config.get("chord_sheet_view", DEFAULT_CHORD_SHEET_VIEW)
        self._available_views: List[str] = self._compute_available_views(None)
        self._visible: bool = bool(self._config.get("chord_sheet_visible", False))
        self._height: int = int(self._config.get("chord_sheet_height", DEFAULT_CHORD_SHEET_HEIGHT))

        # Snap the initial active view into the available set (e.g. a persisted
        # fingering-requiring view with no song loaded yet falls back to default).
        if self._active_view not in self._available_views:
            self._active_view = self._fallback_view(self._available_views)

    # -- Properties ---------------------------------------------------------

    @property
    def rendered_song(self) -> Optional[RenderedSong]:
        """The song currently displayed by the strip (``None`` before first render)."""
        return self._rendered_song

    @property
    def current_index(self) -> Optional[int]:
        """Index into ``rendered_song.chords`` the playhead is on, or ``None``."""
        return self._current_index

    @property
    def active_view(self) -> str:
        """The active renderer id."""
        return self._active_view

    @property
    def available_views(self) -> List[str]:
        """Renderer ids selectable for the current song."""
        return self._available_views

    @property
    def visible(self) -> bool:
        """Whether the chord-sheet panel is shown."""
        return self._visible

    @property
    def height(self) -> int:
        """Persisted panel height in pixels."""
        return self._height

    @property
    def renderers(self) -> List[StripRenderer]:
        """All registered renderers (regardless of current availability)."""
        return list(self._renderers)

    def get_renderer(self, view_id: str) -> Optional[StripRenderer]:
        """Return the renderer with ``view_id``, or ``None`` if unknown."""
        for renderer in self._renderers:
            if renderer.id == view_id:
                return renderer
        return None

    @property
    def active_renderer(self) -> Optional[StripRenderer]:
        """The renderer matching :attr:`active_view`, or ``None``."""
        return self.get_renderer(self._active_view)

    # -- Song input / debounced re-render -----------------------------------

    def set_song(self, lines: List[Line], key: Optional[str]) -> None:
        """Feed a freshly parsed song; schedule a debounced off-thread re-render.

        Rapid calls collapse to a single render: each call cancels the prior
        pending timer and re-arms it with the latest input.

        Args:
            lines: Parsed lines (chords + directives), as from
                ``SongParserService.detect_chords_in_text``.
            key: Current key signature (for roman-numeral resolution).
        """
        self._pending_input = (list(lines), key)
        self._dirty = True
        # Skip the (expensive) render while the panel is hidden; ``set_visible``
        # flushes the held input when the panel is shown again.
        if not self._visible:
            self._scheduler.cancel(self._render_handle)
            self._render_handle = None
            return
        self._scheduler.cancel(self._render_handle)
        self._render_handle = self._scheduler.schedule(
            self._debounce_seconds, self._run_render
        )

    def _run_render(self) -> None:
        """Render the pending input (off the UI thread), then marshal the result."""
        self._render_handle = None
        pending = self._pending_input
        if pending is None:
            return
        lines, key = pending
        try:
            rendered = self._render_fn(lines, key)
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Chord-sheet render failed: {e}", exc_info=True)
            return
        self._dirty = False
        self._marshal(lambda: self._apply_rendered(rendered))

    def _apply_rendered(self, rendered: Optional[RenderedSong]) -> None:
        """Adopt a freshly rendered song and refresh gated view availability.

        Runs on the UI thread (via the marshal seam).
        """
        self.set_and_notify("rendered_song", rendered)
        # A new song can invalidate the current playhead index.
        if self._current_index is not None:
            self.set_and_notify("current_index", None)
        self._refresh_available_views()

    # -- Playback ping ------------------------------------------------------

    def on_playback_chord(
        self, chord_info: Optional[ChordInfo], chord_index: Optional[int] = None
    ) -> None:
        """Move the playhead in response to a playback ping.

        This is the same signal that drives ``TAG_CHORD_PLAYING`` in the editor:
        the main window forwards each ``PlaybackEventArgs`` here.

        The playhead is driven by ``chord_index`` -- the index of the chord in
        the (unrolled) ``RenderedSong`` the playback engine compiled, carried
        through the event stream. It maps directly onto this viewmodel's own
        ``rendered_song.chords`` because both are the deterministic unroll of the
        same parsed song, so loop passes 2+ (which share their char spans with
        pass 1) advance the highlight forward instead of jumping backward. When
        no index is supplied (or it is out of range for the current song) we
        fall back to matching the chord's char span.

        Args:
            chord_info: The chord that just started, or ``None`` on stop/finish.
            chord_index: Index of the chord in the played song's unrolled chord
                list, or ``None`` if unavailable.
        """
        if chord_info is None:
            self.set_and_notify("current_index", None)
            return
        self.set_and_notify("current_index", self._resolve_index(chord_info, chord_index))

    def _resolve_index(
        self, chord_info: ChordInfo, chord_index: Optional[int]
    ) -> Optional[int]:
        """Resolve the played chord to an index in the displayed song.

        Prefers the carried ``chord_index`` (loop-accurate); falls back to a
        char-span match when it is missing or out of range.
        """
        song = self._rendered_song
        if song is None:
            return None
        if chord_index is not None and 0 <= chord_index < len(song.chords):
            return chord_index
        return self._index_for_chord(chord_info)

    def _index_for_chord(self, chord_info: ChordInfo) -> Optional[int]:
        """Map a played chord to its index in the displayed song by char span.

        Matches on ``(start, end)`` offsets, which are stable across independent
        parses of the same text (the strip renders its own ``RenderedSong``,
        distinct from the playback engine's). Used as the fallback when no
        loop-accurate ``chord_index`` is carried on the ping.
        """
        song = self._rendered_song
        if song is None:
            return None
        for index, rendered in enumerate(song.chords):
            source = rendered.chord_info
            if source is not None and source.start == chord_info.start \
                    and source.end == chord_info.end:
                return index
        return None

    # -- Audition -----------------------------------------------------------

    def audition(self, chord_index: int) -> None:
        """Play a chord's exact voiced notes once (click-to-hear).

        Uses the rendered chord's ``midi_notes`` through the same note-level
        immediate-play path a chord click in the editor uses. Rests, skipped
        chords, and out-of-range indices are ignored.

        Args:
            chord_index: Index into ``rendered_song.chords``.
        """
        song = self._rendered_song
        if song is None or not (0 <= chord_index < len(song.chords)):
            return
        notes = song.chords[chord_index].midi_notes
        if notes:
            self._audition_fn(list(notes))

    # -- View selection / gating --------------------------------------------

    def set_active_view(self, view_id: str) -> None:
        """Select a renderer by id and persist it.

        Ignores unknown ids and ids not currently available.

        Args:
            view_id: The renderer id to activate.
        """
        if view_id not in self._available_views:
            logger.debug(f"Ignoring unavailable chord-sheet view: {view_id!r}")
            return
        self._config.set("chord_sheet_view", view_id)
        self.set_and_notify("active_view", view_id)

    def _refresh_available_views(self) -> None:
        """Recompute gated availability and fall back if the active view vanished."""
        views = self._compute_available_views(self._rendered_song)
        self.set_and_notify("available_views", views)
        if self._active_view not in views:
            self.set_active_view(self._fallback_view(views))

    def _compute_available_views(self, song: Optional[RenderedSong]) -> List[str]:
        """Renderer ids selectable for ``song`` (fingering-requiring ones gated)."""
        has_fingering = self._song_has_fingering(song)
        return [
            renderer.id
            for renderer in self._renderers
            if not renderer.requires_fingering or has_fingering
        ]

    @staticmethod
    def _song_has_fingering(song: Optional[RenderedSong]) -> bool:
        """True if any rendered chord carries fretboard fingering data."""
        if song is None:
            return False
        return any(getattr(chord, "fingering", None) for chord in song.chords)

    @staticmethod
    def _fallback_view(views: List[str]) -> str:
        """Pick a fallback view: the default ('keyboard') if present, else first.

        Keeps the strip on a stable, always-available view. A persisted view id
        that no longer exists (e.g. the retired ``'name'`` placeholder) or one
        gated out for the current song therefore resolves to ``'keyboard'``.
        """
        if DEFAULT_CHORD_SHEET_VIEW in views:
            return DEFAULT_CHORD_SHEET_VIEW
        return views[0] if views else DEFAULT_CHORD_SHEET_VIEW

    # -- Visibility / height persistence ------------------------------------

    def set_visible(self, visible: bool) -> None:
        """Show or hide the panel and persist the choice.

        Showing the panel flushes any song input that arrived while it was
        hidden (rendering is held back while hidden to avoid wasted work).
        """
        visible = bool(visible)
        self._config.set("chord_sheet_visible", visible)
        self.set_and_notify("visible", visible)
        if visible and self._dirty and self._pending_input is not None:
            self._scheduler.cancel(self._render_handle)
            self._render_handle = self._scheduler.schedule(
                self._debounce_seconds, self._run_render
            )

    def toggle_visible(self) -> None:
        """Toggle panel visibility."""
        self.set_visible(not self._visible)

    def set_height(self, height: int) -> None:
        """Persist the panel height (from a sash drag); no observers fire.

        Height is a layout detail the panel drives directly; it is stored so it
        survives restart but does not need to notify observers.
        """
        height = max(1, int(height))
        self._height = height
        self._config.set("chord_sheet_height", height)

    # -- Scroll math --------------------------------------------------------

    @staticmethod
    def scroll_target(
        playhead_x: float,
        viewport_width: float,
        current_scroll_x: float,
        content_width: float,
    ) -> Optional[float]:
        """Compute a new horizontal scroll offset for the playhead, or ``None``.

        Snap rule: keep the playhead in a comfortable band. While it sits between
        25% and 70% of the viewport, do not scroll (return ``None``). When it
        moves past 70% (normal forward playback) or behind 25% (a backward jump
        from a loop restart or play-from-cursor), snap so it lands at 25% of the
        viewport. The result is clamped to ``[0, content_width - viewport_width]``
        and returned as ``None`` when it would not move the view meaningfully.

        Args:
            playhead_x: Playhead position in content-space px.
            viewport_width: Visible width in px.
            current_scroll_x: Current scroll offset (left edge) in content px.
            content_width: Total content width in px.

        Returns:
            The new scroll offset, or ``None`` for no change.
        """
        if viewport_width <= 0:
            return None

        relative = playhead_x - current_scroll_x
        low = _SCROLL_SNAP_TO * viewport_width
        high = _SCROLL_TRIGGER * viewport_width

        # Inside the comfortable band -> leave the view alone.
        if low <= relative <= high:
            return None

        target = playhead_x - low
        max_scroll = max(0.0, content_width - viewport_width)
        target = min(max(target, 0.0), max_scroll)

        if abs(target - current_scroll_x) < _SCROLL_EPSILON:
            return None
        return target

    # -- Internals ----------------------------------------------------------

    def _default_marshal(self, fn: Callable[[], None]) -> None:
        """Default UI-thread marshal: hand off to the application queue if present."""
        if self._application is not None:
            self._application.queue_ui_callback(fn)
        else:
            fn()
