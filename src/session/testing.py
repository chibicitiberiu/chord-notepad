"""Deterministic stand-ins for the session's collaborators, for tests.

:class:`ManualHost` runs nothing on its own: posted callbacks wait for
:meth:`ManualHost.run_pending`, and timers wait for the virtual clock to be
moved with :meth:`ManualHost.advance`. A test drives time explicitly, so a
500 ms debounce takes no real time and can't be flaky.

:class:`InMemoryDocumentStore` keeps documents in a dict, with the same
normalization, recent-list and error behaviour as the file-system store.

:class:`EventRecorder` is a session listener that keeps what it was given, and
:func:`compact` turns that into plain tuples for golden assertions.

:class:`FakePlayer` stands in for the FluidSynth ``NotePlayer`` under the real
``PlaybackService``: it makes no sound and keeps no time, it just turns the
pre-rendered event buffer into the progress pings and the finished callback
the real player would send, through the same ``queue_ui_callback`` path.
"""

import dataclasses
import heapq
import itertools
import threading
from collections import deque
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple, Type, TypeVar, Union

from audio.player_interface import IPlayer
from exceptions import FileOperationError
from models.playback_event import PlaybackEventArgs, PlaybackEventType
from models.playback_event_internal import MidiEventType
from session.documents import DocumentRef
from session.state import Span
from utils.text_normalization import normalize_song_text


class _ManualTimer:
    """A :class:`ManualHost` timer handle."""

    def __init__(self, due: float, cb: Callable[[], None]) -> None:
        self.due = due
        self.cb = cb
        self.cancelled = False

    def cancel(self) -> None:
        """Stop the timer from firing (no-op once it has fired)."""
        self.cancelled = True


class ManualHost:
    """A :class:`session.host.Host` driven by the test, with a virtual clock.

    The thread that creates it is the session thread. ``post`` may be called
    from any thread; everything else belongs to the session thread, and
    ``call_later`` raises if called elsewhere so a threading mistake fails the
    test instead of going unnoticed.

    Callbacks run by :meth:`run_pending` and :meth:`advance` are not guarded:
    an exception propagates to the test.
    """

    def __init__(self, start: float = 0.0) -> None:
        """Create a host whose clock reads ``start`` seconds."""
        self._now = float(start)
        self._lock = threading.Lock()
        self._posted: Deque[Callable[[], None]] = deque()
        self._timers: List[Tuple[float, int, _ManualTimer]] = []
        self._seq = itertools.count()
        self._session_thread = threading.current_thread()

    def post(self, cb: Callable[[], None]) -> None:
        """Queue ``cb`` until the next :meth:`run_pending`."""
        with self._lock:
            self._posted.append(cb)

    def call_later(self, delay_s: float, cb: Callable[[], None]) -> _ManualTimer:
        """Schedule ``cb`` for ``delay_s`` seconds of virtual time from now."""
        if not self.is_session_thread():
            raise RuntimeError("call_later must be called on the session thread")
        timer = _ManualTimer(self._now + max(0.0, delay_s), cb)
        # The sequence number keeps equal deadlines in scheduling order.
        heapq.heappush(self._timers, (timer.due, next(self._seq), timer))
        return timer

    def is_session_thread(self) -> bool:
        """Whether the caller is the thread that created this host."""
        return threading.current_thread() is self._session_thread

    def monotonic(self) -> float:
        """The virtual clock, in seconds."""
        return self._now

    @property
    def pending_posts(self) -> int:
        """How many posted callbacks are waiting."""
        with self._lock:
            return len(self._posted)

    @property
    def pending_timers(self) -> int:
        """How many timers are armed (scheduled and not cancelled)."""
        return sum(1 for _, _, t in self._timers if not t.cancelled)

    def run_pending(self) -> int:
        """Run posted callbacks until none are left, in FIFO order.

        Callbacks posted while this runs are run too, like the Tk drain does.

        Returns:
            How many callbacks ran.
        """
        ran = 0
        while True:
            with self._lock:
                if not self._posted:
                    return ran
                cb = self._posted.popleft()
            cb()
            ran += 1

    def advance(self, seconds: float) -> int:
        """Move the clock forward, firing the timers that come due on the way.

        Posted callbacks run first, and again after each timer, so work a
        timer posts is done before the next timer fires. Timers fire in
        deadline order with the clock set to their deadline.

        Returns:
            How many timers fired.
        """
        target = self._now + max(0.0, seconds)
        fired = 0
        self.run_pending()
        while self._timers and self._timers[0][0] <= target:
            due, _, timer = heapq.heappop(self._timers)
            if timer.cancelled:
                continue
            self._now = max(self._now, due)
            timer.cancelled = True  # fired: a late cancel() is a no-op
            timer.cb()
            fired += 1
            self.run_pending()
        self._now = target
        return fired


class InMemoryDocumentStore:
    """A :class:`session.documents.DocumentStore` backed by a dict.

    Documents are keyed by ``ref.id``; :meth:`ref` makes a reference for a
    name. Text documents are stored as ``str``, exports as ``bytes``.
    """

    def __init__(self, documents: Optional[Dict[str, Union[str, bytes]]] = None,
                 max_recent: int = 10) -> None:
        """Create the store.

        Args:
            documents: Initial contents, keyed by display name.
            max_recent: Length cap of the recent list.
        """
        self.contents: Dict[str, Union[str, bytes]] = {}
        self._recent: List[DocumentRef] = []
        self._max_recent = max_recent
        for name, data in (documents or {}).items():
            self.contents[self.ref(name).id] = data

    @staticmethod
    def ref(name: str) -> DocumentRef:
        """A reference to the document called ``name``."""
        return DocumentRef(id=f"memory:{name}", display_name=name, location=name)

    def read_text(self, ref: DocumentRef) -> str:
        """Return the normalized text, like reading a file does."""
        if ref.id not in self.contents:
            raise FileOperationError(f"File not found: {ref.location}")
        data = self.contents[ref.id]
        if isinstance(data, bytes):
            raise FileOperationError(f"Cannot read file (encoding issue): {ref.location}")
        self.add_recent(ref)
        return normalize_song_text(data)

    def write_text(self, ref: DocumentRef, text: str) -> None:
        """Store ``text`` and remember the document as recent."""
        self.contents[ref.id] = text
        self.add_recent(ref)

    def write_bytes(self, ref: DocumentRef, data: bytes) -> None:
        """Store an export (not added to the recent list)."""
        self.contents[ref.id] = bytes(data)

    def is_available(self, ref: DocumentRef) -> bool:
        """Whether the document exists."""
        return ref.id in self.contents

    def recent(self) -> List[DocumentRef]:
        """Recent documents that still exist, newest first (prunes the rest)."""
        self._recent = [r for r in self._recent if self.is_available(r)]
        return list(self._recent)

    def add_recent(self, ref: DocumentRef) -> None:
        """Move ``ref`` to the front of the recent list."""
        self._recent = [ref] + [r for r in self.recent() if r.id != ref.id]
        del self._recent[self._max_recent:]


T = TypeVar("T")


def compact(item: Any) -> Any:
    """A session DTO as nested plain tuples, for golden assertions.

    A dataclass becomes ``(ClassName, field, ...)``, a :class:`Span` the
    shorter ``(kind, start, end)``, an enum its value; tuples and lists are
    compacted element-wise. Anything else is returned as is.
    """
    if isinstance(item, Span):
        return (item.kind.value, item.start, item.end)
    if isinstance(item, Enum):
        return item.value
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return (type(item).__name__,) + tuple(
            compact(getattr(item, f.name)) for f in dataclasses.fields(item))
    if isinstance(item, (tuple, list)):
        return tuple(compact(x) for x in item)
    return item


class EventRecorder:
    """A session listener that records everything delivered to it.

    Pass the recorder itself to ``session.subscribe``.
    """

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.items: List[Any] = []

    def __call__(self, item: Any) -> None:
        """Record one delivered item."""
        self.items.append(item)

    def clear(self) -> None:
        """Forget what was recorded so far."""
        self.items.clear()

    def compact(self) -> List[Any]:
        """Everything recorded, through :func:`compact`."""
        return [compact(item) for item in self.items]

    def of_type(self, item_type: Type[T]) -> List[T]:
        """The recorded items of one type, in delivery order."""
        return [item for item in self.items if isinstance(item, item_type)]

    def last(self, item_type: Type[T]) -> Optional[T]:
        """The last recorded item of one type, or None."""
        found = self.of_type(item_type)
        return found[-1] if found else None


class FakePlayer(IPlayer):
    """A silent :class:`audio.player_interface.IPlayer` for session tests.

    ``PlaybackService`` hands it the event buffer and callbacks on its render
    thread and then calls :meth:`start_playback`. By default that consumes
    the whole buffer at once, still on the render thread: every chord (and
    ``NC`` rest) posts a ``CHORD_START`` ping through ``queue_ui_callback``
    like ``NotePlayer`` does, then the end of the song calls the finished
    callback. A test joins ``PlaybackService._render_thread`` and runs the
    host's pending callbacks to see the result.

    With ``auto_play=False`` nothing is consumed until the test calls
    :meth:`play`, so it can pause or stop in the middle of a song.

    Attributes:
        calls: Transport calls in order (``start``, ``pause``, ``resume``,
            ``stop``).
        immediate: The note lists played by click-to-hear, in order.
        played: The buffer events consumed so far.
    """

    def __init__(self, auto_play: bool = True) -> None:
        """Create the player.

        Args:
            auto_play: Consume the whole song as soon as playback starts.
        """
        self.auto_play = auto_play
        self.event_buffer: Any = None
        self.on_event_callback: Optional[Callable[[PlaybackEventArgs], None]] = None
        self.application: Any = None
        self.on_playback_finished_callback: Optional[Callable[[], None]] = None
        self.is_playing = False
        self.is_paused = False
        self.calls: List[str] = []
        self.immediate: List[List[int]] = []
        self.played: List[Any] = []
        self.bpm: Optional[int] = None
        self.bpm_multiplier = 1.0
        self.instrument = 0
        self.metronome_enabled = False

    # -- what PlaybackService wires up -------------------------------------

    def set_event_buffer(self, event_buffer: Any) -> None:
        """Take the pre-rendered events to play."""
        self.event_buffer = event_buffer

    def set_event_callback(self, callback: Optional[Callable[[PlaybackEventArgs], None]],
                           application: Any) -> None:
        """Take the progress callback and what to marshal it through."""
        self.on_event_callback = callback
        self.application = application

    def set_playback_finished_callback(self, callback: Callable[[], None]) -> None:
        """Take the callback for a song that played to its end."""
        self.on_playback_finished_callback = callback

    # -- transport -----------------------------------------------------------

    def start_playback(self) -> None:
        """Start the song; with ``auto_play`` play all of it right away."""
        self.calls.append("start")
        self.is_playing = True
        self.is_paused = False
        if self.auto_play:
            self.play()

    def play(self, chords: Optional[int] = None) -> int:
        """Consume buffered events, posting a ping per chord.

        Args:
            chords: Stop after this many chord pings; None plays to the end
                of the song, which calls the finished callback.

        Returns:
            How many chord pings were posted.
        """
        posted = 0
        while self.event_buffer is not None and (chords is None or posted < chords):
            event = self.event_buffer.pop_event(timeout=0)
            if event is None:
                break
            self.played.append(event)
            if event.event_type == MidiEventType.END_OF_SONG:
                self.is_playing = False
                if self.on_playback_finished_callback is not None:
                    self.on_playback_finished_callback()
                break
            if (event.event_type in (MidiEventType.NOTE_ON, MidiEventType.REST)
                    and event.metadata.get("has_callback")):
                self._post_ping(event.metadata)
                posted += 1
        return posted

    def _post_ping(self, meta: Dict[str, Any]) -> None:
        if self.on_event_callback is None or self.application is None:
            return
        args = PlaybackEventArgs(
            event_type=PlaybackEventType.CHORD_START,
            chord_info=meta.get("chord_info"),
            chord_index=meta.get("chord_index"),
            bpm=meta.get("bpm"),
            time_signature_beats=meta.get("time_signature_beats"),
            time_signature_unit=meta.get("time_signature_unit"),
            key=meta.get("key"),
            current_line=meta.get("line_index"),
            current_bar=meta.get("bar"),
            total_bars=meta.get("total_bars"),
        )
        callback = self.on_event_callback
        self.application.queue_ui_callback(lambda: callback(args))

    def pause_playback(self) -> None:
        """Pause (nothing is consumed meanwhile unless the test plays)."""
        self.calls.append("pause")
        self.is_paused = True

    def resume_playback(self) -> None:
        """Resume after a pause."""
        self.calls.append("resume")
        self.is_paused = False

    def stop_playback(self) -> None:
        """Stop; a stopped song never calls the finished callback."""
        self.calls.append("stop")
        self.is_playing = False
        self.is_paused = False

    # -- everything else -----------------------------------------------------

    def play_notes_immediate(self, midi_notes: List[int]) -> None:
        """Record a click-to-hear chord."""
        self.immediate.append(list(midi_notes))

    def stop_all_notes(self) -> None:
        """Nothing rings, so nothing to silence."""

    def set_bpm(self, bpm: int) -> None:
        """Record the tempo."""
        self.bpm = bpm

    def set_bpm_multiplier(self, multiplier: float) -> None:
        """Record the speed multiplier."""
        self.bpm_multiplier = multiplier

    def set_instrument(self, program: int) -> None:
        """Record the MIDI program."""
        self.instrument = program

    def get_available_instruments(self) -> List[Tuple[int, str]]:
        """No soundfont, no instruments."""
        return []

    def set_metronome_enabled(self, enabled: bool) -> None:
        """Record whether the click track is on."""
        self.metronome_enabled = enabled

    def cleanup(self) -> None:
        """Nothing to release."""
