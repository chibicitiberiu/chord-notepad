"""Headless viewmodel for the chord-sheet strip.

Owns the :class:`~models.rendered_song.RenderedSong` displayed by the strip and
the surrounding UI state (which renderer is active, which are available, whether
the panel is shown, and which chord the playhead is on). It is deliberately
Tk-free so it can be unit-tested without a display.

Re-rendering path: when the parsed song changes the viewmodel re-renders it
through the *same* path MIDI export uses -- ``PlaybackService.render_song`` --
so the strip shows exactly the voicing that would play/export, but with a
*private* picker (``private_picker=True``) so a background strip render never
races the shared playback picker's voice-leading state.

Rendering (a whole-song beam-Viterbi voicing search) is expensive, so it is
**debounced** and run **off the UI thread** on a serialized single-worker basis:

- Every ``set_song`` bumps a GENERATION counter.
- When the debounce fires, one job is dispatched through the ``executor`` seam
  (default: a daemon thread; tests: inline). Only one job runs at a time; a
  request arriving while a job runs is remembered and run when the job finishes.
- The job threads a ``should_abort`` predicate -- "my generation is no longer
  current" -- into the render, so a superseded job stops promptly (raising
  :class:`~exceptions.RenderAborted`) instead of running to completion.
- The result is marshaled back to the session thread (``host.post``) and
  APPLIED ONLY IF its generation is still current; stale results are dropped.

Given a :class:`~session.host.Host`, the debounce runs through
``host.call_later`` (:class:`HostScheduler`), so the timer fires on the session
thread, and results are marshaled with ``host.post``. The debounce scheduler,
the executor, the marshal and the render seam are all injectable so tests run
synchronously.
"""

import logging
import threading
from typing import Callable, Dict, List, Optional

from exceptions import RenderAborted

from constants import (
    CHORD_SHEET_RERENDER_DEBOUNCE_MS,
    DEFAULT_CHORD_SHEET_HEIGHT,
    DEFAULT_CHORD_SHEET_VIEW,
)
from models.chord import ChordInfo
from models.line import Line
from models.rendered_song import RenderedSong
from session.host import Host
from session.platform import ANDROID, DESKTOP, check_platform, pick
from chord_sheet.registry import default_renderers
from chord_sheet.renderer_interface import StripRenderer
from utils.observable import Observable

logger = logging.getLogger(__name__)


# Snap band for the auto-scroll rule (fractions of the viewport width).
_SCROLL_SNAP_TO = 0.25   # where the playhead is placed after a snap
_SCROLL_TRIGGER = 0.70   # playhead past this fraction triggers a forward snap
_SCROLL_EPSILON = 0.5    # px; scroll deltas smaller than this are treated as no-op

# Display-zoom step/bounds for zoom-capable renderers (staff, piano roll, ...).
#: Why the fretted views are off for a song without fingerings, per platform.
_PICK_FRETTED_INSTRUMENT = {
    DESKTOP: "Pick a fretted instrument (e.g. Guitar) in Playback \u2192 Voicing to use this view.",
    ANDROID: "Pick a fretted instrument (e.g. Guitar) with the player's Voicing button "
             "to use this view.",
}

_ZOOM_STEP = 1.2   # multiplicative factor per zoom-in/out click
_ZOOM_MIN = 0.5
_ZOOM_MAX = 2.5


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


class HostScheduler:
    """Debounce scheduler backed by ``host.call_later``.

    The fired callback runs on the session thread. That only dispatches the
    job; the render itself still runs on the executor's thread.
    """

    def __init__(self, host: Host) -> None:
        """Schedule through ``host``."""
        self._host = host

    def schedule(self, delay_seconds: float, fn: Callable[[], None]) -> object:
        """Schedule ``fn`` to run after ``delay_seconds`` on the session thread."""
        return self._host.call_later(delay_seconds, fn)

    def cancel(self, handle: object) -> None:
        """Cancel a previously scheduled handle (no-op if ``None``)."""
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
        host: Optional[Host] = None,
        renderers: Optional[List[StripRenderer]] = None,
        render_fn: Optional[Callable[..., Optional[RenderedSong]]] = None,
        audition_fn: Optional[Callable[[List[int]], None]] = None,
        scheduler=None,
        executor: Optional[Callable[[Callable[[], None]], None]] = None,
        marshal: Optional[Callable[[Callable[[], None]], None]] = None,
        debounce_ms: int = CHORD_SHEET_RERENDER_DEBOUNCE_MS,
        platform: str = DESKTOP,
    ) -> None:
        """Create the viewmodel.

        Args:
            config_service: ConfigService for persisting/loading strip settings.
            audio_service: PlaybackService; used for the default render and
                audition seams.
            application: Application, for the default UI-thread marshal when
                no ``host`` is given.
            host: Session host. When given, it is the default debounce
                scheduler (:class:`HostScheduler`) and the default marshal
                (``host.post``).
            renderers: Strip renderers to offer; defaults to the standard set
                (:func:`~chord_sheet.registry.default_renderers`: keyboard, staff,
                chord box, tab).
            render_fn: Injectable ``(lines, key, should_abort=None) ->
                RenderedSong | None`` seam; defaults to a private-picker render
                through ``audio_service.render_song`` (so a background strip
                render never shares the shared playback picker's state).
            audition_fn: Injectable ``(midi_notes) -> None`` seam; defaults to
                ``audio_service.play_notes_immediate``.
            scheduler: Injectable debounce scheduler with ``schedule(delay, fn)``
                / ``cancel(handle)``; defaults to :class:`HostScheduler` with a
                host, else a ``threading.Timer`` seam.
            executor: Injectable ``(fn) -> None`` seam that runs a render job.
                Defaults to spawning a daemon thread; tests inject an inline
                ``lambda fn: fn()`` to run jobs synchronously.
            marshal: Injectable UI-thread marshal; defaults to ``host.post``,
                else ``application.queue_ui_callback``, else a direct call.
            debounce_ms: Debounce window in milliseconds.
            platform: ``desktop`` or ``android`` (``session.platform``): the
                wording of :attr:`fretted_views_unavailable_reason`.
        """
        super().__init__()
        self._platform = check_platform(platform)

        self._config = config_service
        self._audio = audio_service
        self._application = application

        self._renderers: List[StripRenderer] = (
            list(renderers) if renderers is not None else default_renderers()
        )
        self._render_fn = render_fn or self._default_render
        self._audition_fn = audition_fn or audio_service.play_notes_immediate
        if scheduler is None:
            scheduler = HostScheduler(host) if host is not None else _TimerScheduler()
        if marshal is None:
            marshal = host.post if host is not None else self._default_marshal
        self._scheduler = scheduler
        self._executor = executor or self._default_executor
        self._marshal = marshal
        self._debounce_seconds = max(0.0, debounce_ms) / 1000.0

        # Debounce/render bookkeeping.
        self._pending_input: Optional[tuple] = None  # (lines, key)
        self._render_handle: object = None
        # True when the pending input has not yet been rendered into
        # ``rendered_song``. While the panel is hidden we hold render work back
        # (no wasted background renders) and flush it when the panel is shown.
        self._dirty: bool = False

        # Background-job serialization. ``_generation`` is bumped on every
        # ``set_song`` and is the freshness token both the cooperative-abort
        # predicate and the apply-guard compare against. ``_job_running`` ensures
        # a single worker; ``_rerun_requested`` remembers a request that arrived
        # while a job was in flight so the newest input is run when the current
        # job finishes. All three are guarded by ``_job_lock``.
        self._job_lock = threading.Lock()
        self._generation: int = 0
        self._job_running: bool = False
        self._rerun_requested: bool = False

        # Observable state (private storage with leading underscore).
        self._rendered_song: Optional[RenderedSong] = None
        self._current_index: Optional[int] = None
        # The last playback ping (chord, index in the played song), kept until
        # playback stops so a song rendered after it can still place it.
        self._last_ping: Optional[tuple] = None
        # The view the user last picked (persisted) vs. the one shown now. They
        # differ while the picked view is gated out, e.g. Fret cards on startup
        # before any chords render; the strip returns to it once available.
        self._preferred_view: str = self._config.get("chord_sheet_view", DEFAULT_CHORD_SHEET_VIEW)
        self._active_view: str = self._preferred_view
        self._available_views: List[str] = self._compute_available_views(None)
        self._visible: bool = bool(self._config.get("chord_sheet_visible", False))
        self._height: int = int(self._config.get("chord_sheet_height", DEFAULT_CHORD_SHEET_HEIGHT))

        # Snap the initial active view into the available set (e.g. a persisted
        # fingering-requiring view with no song loaded yet falls back to default).
        if self._active_view not in self._available_views:
            self._active_view = self._fallback_view(self._available_views)

        # Per-view display zoom factors (renderer id -> factor). ``zoom`` mirrors
        # the factor for the *active* view so the panel can observe it directly.
        self._zoom_by_view: Dict[str, float] = self._load_zoom_factors()
        self._zoom: float = self._zoom_by_view.get(self._active_view, 1.0)

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
    def fretted_views_unavailable_reason(self) -> Optional[str]:
        """Why the fingering-requiring views are disabled, or ``None`` if available."""
        song = self._rendered_song
        if self._song_has_fingering(song):
            return None
        if song is None or not song.chords:
            return "Add some chords to see this view."
        return pick(_PICK_FRETTED_INSTRUMENT, self._platform)

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

    # -- Display zoom -------------------------------------------------------

    @property
    def zoom(self) -> float:
        """Display zoom factor for the active view (observable). 1.0 = default."""
        return self._zoom

    @property
    def zoom_for_active_view(self) -> float:
        """The active view's zoom factor (the value the panel threads into
        :class:`~chord_sheet.renderer_interface.SheetContext`)."""
        return self._zoom

    @property
    def zoom_supported(self) -> bool:
        """Whether the active renderer honors zoom (``supports_zoom``).

        The panel enables its +/- zoom buttons only when this is ``True``.
        """
        renderer = self.active_renderer
        return bool(renderer is not None and renderer.supports_zoom)

    def zoom_in(self) -> None:
        """Zoom the active view in one multiplicative step (no-op if unsupported)."""
        self._set_zoom(self._zoom * _ZOOM_STEP)

    def zoom_out(self) -> None:
        """Zoom the active view out one multiplicative step (no-op if unsupported)."""
        self._set_zoom(self._zoom / _ZOOM_STEP)

    def zoom_steps(self, steps: int) -> None:
        """Zoom ``steps`` steps at once (positive in, negative out): the same
        factor as that many :meth:`zoom_in`/:meth:`zoom_out` calls, applied
        (and repainted) once. No-op if unsupported or ``steps`` is 0."""
        if not steps or not self.zoom_supported:
            return
        value = self._zoom
        factor = _ZOOM_STEP if steps > 0 else 1 / _ZOOM_STEP
        for _ in range(abs(int(steps))):
            value = round(min(_ZOOM_MAX, max(_ZOOM_MIN, value * factor)), 3)
        self._set_zoom(value)

    def _set_zoom(self, value: float) -> None:
        """Clamp/round and apply a zoom factor to the active view, then notify.

        Ignored when the active renderer does not support zoom. Persists the
        per-view factors and notifies ``zoom`` observers so the panel repaints
        (display-only: no song re-render).
        """
        if not self.zoom_supported:
            return
        value = round(min(_ZOOM_MAX, max(_ZOOM_MIN, value)), 3)
        self._zoom_by_view[self._active_view] = value
        self._persist_zoom_factors()
        self.set_and_notify("zoom", value)

    def _load_zoom_factors(self) -> Dict[str, float]:
        """Load and sanitize persisted per-view zoom factors from config."""
        raw = self._config.get("chord_sheet_zoom", {})
        if not isinstance(raw, dict):
            return {}
        factors: Dict[str, float] = {}
        for key, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            factors[str(key)] = round(min(_ZOOM_MAX, max(_ZOOM_MIN, float(value))), 3)
        return factors

    def _persist_zoom_factors(self) -> None:
        """Persist only the non-default (non-1.0) per-view zoom factors."""
        stored = {
            view: factor
            for view, factor in self._zoom_by_view.items()
            if abs(factor - 1.0) > 1e-9
        }
        self._config.set("chord_sheet_zoom", stored)

    # -- Song input / debounced re-render -----------------------------------

    def set_song(self, lines: List[Line], key: Optional[str]) -> None:
        """Feed a freshly parsed song; schedule a debounced off-thread re-render.

        Rapid calls collapse to a single render: each call bumps the generation
        (invalidating any in-flight render), cancels the prior pending timer, and
        re-arms it with the latest input.

        Args:
            lines: Parsed lines (chords + directives), as from
                ``SongParserService.detect_chords_in_text``.
            key: Current key signature (for roman-numeral resolution).
        """
        self._pending_input = (list(lines), key)
        self._dirty = True
        with self._job_lock:
            self._generation += 1
        # Skip the (expensive) render while the panel is hidden; ``set_visible``
        # flushes the held input when the panel is shown again.
        self._scheduler.cancel(self._render_handle)
        self._render_handle = None
        if not self._visible:
            return
        self._render_handle = self._scheduler.schedule(
            self._debounce_seconds, self._dispatch
        )

    # -- Background render job (serialized single worker) --------------------

    def _dispatch(self) -> None:
        """Start a render job, or remember a rerun if one is already running.

        Called by the debounce scheduler. Serializes so at most one job runs at a
        time: if a job is in flight, the newest request is remembered
        (``_rerun_requested``) and picked up when that job finishes.
        """
        with self._job_lock:
            if self._job_running:
                self._rerun_requested = True
                return
            self._job_running = True
        self._executor(self._run_job)

    def _run_job(self) -> None:
        """Run the pending work off the UI thread, marshaling the result back.

        Loops so a rerun requested during the job (newest input) runs without
        re-entering the executor. Each iteration snapshots the current
        generation and threads a "still current?" abort predicate into the
        (expensive) render; a superseded iteration raises
        :class:`~exceptions.RenderAborted` and simply falls through to the rerun
        check. Results are marshaled back and applied only if still current.
        """
        while True:
            with self._job_lock:
                gen = self._generation
                pending = self._pending_input
                self._rerun_requested = False
                # Snapshotting the pending work means it is now being handled;
                # a fresh ``set_song`` re-dirties.
                self._dirty = False
            should_abort = self._make_abort(gen)
            try:
                if pending is not None:
                    lines, key = pending
                    rendered = self._render_fn(lines, key, should_abort=should_abort)
                    self._marshal(self._apply_cb(gen, rendered))
            except RenderAborted:
                logger.debug(
                    "Chord-sheet render aborted (generation %d superseded)", gen)
            except Exception as e:  # pragma: no cover - defensive
                logger.error(f"Chord-sheet render failed: {e}", exc_info=True)
            with self._job_lock:
                if not self._rerun_requested:
                    self._job_running = False
                    return
                # else: loop again to run the newest requested work.

    def _make_abort(self, gen: int) -> Callable[[], bool]:
        """Build the cooperative-abort predicate for job generation ``gen``.

        Returns ``True`` once a newer ``set_song`` has bumped the generation past
        ``gen``, so the in-flight render bails.
        """
        return lambda: gen != self._generation

    def _apply_cb(
        self,
        gen: int,
        rendered: Optional[RenderedSong],
    ) -> Callable[[], None]:
        """Build the UI-thread apply callback, guarded by generation ``gen``.

        A stale result (a newer generation has since been requested) is dropped
        silently (debug log) so it can never clobber fresher UI state.
        """
        def _apply() -> None:
            if gen != self._generation:
                logger.debug(
                    "Dropping stale chord-sheet result (generation %d, current %d)",
                    gen, self._generation)
                return
            self._apply_rendered(rendered)
        return _apply

    def _apply_rendered(self, rendered: Optional[RenderedSong]) -> None:
        """Adopt a freshly rendered song and refresh gated view availability.

        Runs on the UI thread (via the marshal seam).
        """
        self.set_and_notify("rendered_song", rendered)
        # A new song moves the playhead: onto the chord sounding now when it
        # has one (a render that lands after playback started, which is usual
        # for a whole-song render racing a mid-song one), else off.
        index = self._resolve_index(*self._last_ping) if self._last_ping is not None else None
        if index != self._current_index:
            self.set_and_notify("current_index", index)
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
            self._last_ping = None
            self.set_and_notify("current_index", None)
            return
        self._last_ping = (chord_info, chord_index)
        self.set_and_notify("current_index", self._resolve_index(chord_info, chord_index))

    def _resolve_index(
        self, chord_info: ChordInfo, chord_index: Optional[int]
    ) -> Optional[int]:
        """Resolve the played chord to an index in the displayed song.

        Prefers the carried ``chord_index`` (loop-accurate) when the displayed
        song has the played chord there; falls back to a char-span match (the
        first occurrence) when it is missing, out of range or points at another
        chord (the strip rendered other text than the run played).
        """
        song = self._rendered_song
        if song is None:
            return None
        if chord_index is not None and 0 <= chord_index < len(song.chords):
            source = song.chords[chord_index].chord_info
            if source is None or _same_span(source, chord_info):
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
            if source is not None and _same_span(source, chord_info):
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
        self._preferred_view = view_id
        self._config.set("chord_sheet_view", view_id)
        self._show_view(view_id)

    def _show_view(self, view_id: str) -> None:
        """Make ``view_id`` the displayed view without touching the user's choice."""
        self.set_and_notify("active_view", view_id)
        # Surface the newly-active view's own zoom factor (per-view isolation).
        self.set_and_notify("zoom", self._zoom_by_view.get(view_id, 1.0))

    def _refresh_available_views(self) -> None:
        """Recompute gated availability and pick the view to show.

        Shows the user's preferred view whenever it is available; otherwise
        keeps the current view if still available, else falls back. Fallbacks
        are not persisted, so a temporarily gated choice isn't forgotten.
        """
        views = self._compute_available_views(self._rendered_song)
        self.set_and_notify("available_views", views)
        if self._preferred_view in views:
            target = self._preferred_view
        elif self._active_view in views:
            target = self._active_view
        else:
            target = self._fallback_view(views)
        if target != self._active_view:
            self._show_view(target)

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

        No background render ever runs while the panel is hidden, because nobody
        is looking. Concretely:

        - Hiding aborts any in-flight job by bumping the generation (so its
          result is dropped) and, if that job had work in flight, re-marks the
          pending state dirty so showing re-runs it. It also cancels any armed
          debounce timer.
        - Showing flushes exactly ONE render for the pending input via the
          debounce scheduler.
        """
        visible = bool(visible)
        self._config.set("chord_sheet_visible", visible)
        self.set_and_notify("visible", visible)

        if not visible:
            # Abort an in-flight job (hidden means nobody's looking); if it had
            # uncommitted work, re-dirty so showing re-runs it.
            with self._job_lock:
                aborting = self._job_running
                if aborting:
                    self._generation += 1
            if aborting:
                self._dirty = True
            self._scheduler.cancel(self._render_handle)
            self._render_handle = None
            return

        if self._dirty:
            self._scheduler.cancel(self._render_handle)
            self._render_handle = self._scheduler.schedule(
                self._debounce_seconds, self._dispatch
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

    def _default_executor(self, fn: Callable[[], None]) -> None:
        """Default executor: run a render job on a short-lived daemon thread."""
        thread = threading.Thread(target=fn, daemon=True, name="ChordSheetRenderJob")
        thread.start()

    def _default_render(
        self,
        lines: List[Line],
        key: Optional[str],
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> Optional[RenderedSong]:
        """Default render seam: render through the audio service with a private picker.

        Uses ``private_picker=True`` so this (possibly background) strip render
        never shares the shared playback picker's mutable voice-leading state and
        caches, and threads the cooperative-abort predicate through.
        """
        return self._audio.render_song(
            lines, key, should_abort=should_abort, private_picker=True)


def _same_span(a: ChordInfo, b: ChordInfo) -> bool:
    """Whether two parses' chords are the same chord of the text (same span)."""
    return a.start == b.start and a.end == b.end
