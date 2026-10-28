"""The session's outbound stream: buffered, coalesced, delivered at flush points.

Everything the session tells its views goes through one :class:`Emitter`.
Output produced while a command runs is buffered and delivered when the
outermost command returns, never in the middle of one, so a view never sees a
half-updated session. The rules (``docs/architecture/session.md``, "Delivery
contract"):

- *States* (:meth:`Emitter.set_state`) are coalesced per type: a state set more
  than once before a flush keeps its first position and carries its latest
  value. Setting a state to the value it already has delivers nothing.
- *Events* (:meth:`Emitter.emit`) are delivered in order, every one of them.
- A listener that runs a command while output is being delivered gets that
  command's output after the output already being delivered.
- A new listener first gets the current value of every state.

The emitter is single-threaded: only the session thread may touch it.
"""

import logging
import sys
from contextlib import contextmanager
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Type, TypeVar

from session import errors

logger = logging.getLogger(__name__)

Listener = Callable[[object], None]
T = TypeVar("T")


class _Subscription:
    """A listener's registration; cancelling it stops delivery to it."""

    def __init__(self, emitter: "Emitter", listener: Listener) -> None:
        self._emitter = emitter
        self.listener = listener
        self.active = True

    def cancel(self) -> None:
        """Stop delivering to this listener (no-op if already cancelled)."""
        if self.active:
            self.active = False
            self._emitter._remove(self)


# A buffered item and who gets it: None means every listener, a subscription
# means only that one (the replay of current states to a new listener).
_Entry = Tuple[Optional[_Subscription], object]


class Emitter:
    """Buffers output during commands and delivers it at the outermost exit."""

    def __init__(self) -> None:
        """Create an emitter with no listeners and no states."""
        self._subscriptions: List[_Subscription] = []
        # Latest value per state type; dict order is first-set order, which
        # is the order a new listener gets them in.
        self._current: Dict[type, object] = {}
        self._pending: List[_Entry] = []
        # Where each state type sits in _pending, so a repeat replaces it.
        self._pending_state_at: Dict[type, int] = {}
        self._depth = 0
        self._delivering = False

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Run a command: buffer its output and flush on the outermost exit.

        The flush happens even if the command raises, so states already
        changed still reach the views.
        """
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            if self._depth == 0:
                self._flush()

    @property
    def in_batch(self) -> bool:
        """Whether a command is running (output is being buffered)."""
        return self._depth > 0

    def set_state(self, state: object) -> None:
        """Publish a new value of a state (coalesced per type).

        A value equal to the current one is dropped, unless a different value
        is waiting to be delivered (then it replaces that one).

        Raises:
            RuntimeError: If called outside :meth:`batch`.
        """
        self._require_batch()
        key = type(state)
        index = self._pending_state_at.get(key)
        if index is None and self._current.get(key) == state:
            return
        self._current[key] = state
        if index is None:
            self._pending_state_at[key] = len(self._pending)
            self._pending.append((None, state))
        else:
            self._pending[index] = (None, state)

    def emit(self, event: object) -> None:
        """Publish a one-off event (delivered in order, never coalesced).

        Raises:
            RuntimeError: If called outside :meth:`batch`.
        """
        self._require_batch()
        self._pending.append((None, event))

    def state(self, state_type: Type[T]) -> Optional[T]:
        """The latest value of a state type, or None if never set."""
        return self._current.get(state_type)  # type: ignore[return-value]

    def subscribe(self, listener: Listener) -> _Subscription:
        """Add a listener; it gets the current states at the next flush.

        Raises:
            RuntimeError: If called outside :meth:`batch`.
        """
        self._require_batch()
        subscription = _Subscription(self, listener)
        self._subscriptions.append(subscription)
        for state in self._current.values():
            self._pending.append((subscription, state))
        return subscription

    def close(self) -> None:
        """Drop every listener and anything still buffered."""
        for subscription in list(self._subscriptions):
            subscription.cancel()
        self._pending.clear()
        self._pending_state_at.clear()

    def _remove(self, subscription: _Subscription) -> None:
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def _require_batch(self) -> None:
        if self._depth == 0:
            raise RuntimeError("session output outside a command; wrap the entry point")

    def _flush(self) -> None:
        """Deliver everything buffered, including what delivery itself adds.

        Re-entrant calls (a listener ran a command) return at once: the loop
        already running picks their output up after the current round.
        """
        if self._delivering:
            return
        self._delivering = True
        try:
            while self._pending:
                entries, self._pending = self._pending, []
                self._pending_state_at.clear()
                for target, item in entries:
                    receivers = [target] if target is not None else list(self._subscriptions)
                    for subscription in receivers:
                        if subscription.active:
                            self._deliver(subscription, item)
        finally:
            self._delivering = False

    @staticmethod
    def _deliver(subscription: _Subscription, item: object) -> None:
        """Hand one item to one listener; a failing listener doesn't stop the rest."""
        try:
            subscription.listener(item)
        except Exception:
            errors.report_from_any_thread(
                sys.exc_info(), f"session listener ({type(item).__name__})")
