"""Request/response flows written as generators.

A flow that has to ask the user something (pick a voicing, fill in a
directive, later: save changes?, pick a file) is a generator. It yields a
request DTO and gets the view's answer back as the value of the ``yield``::

    def suggest_capo(self):
        voicing = yield CapoChoiceRequest(0, options, default)
        if voicing is None:      # cancelled
            return
        ...

:class:`FlowRunner` numbers each request (its ``request_id`` field is
replaced), emits it, and resumes the flow when :meth:`FlowRunner.respond` gets
the answer for that number. Only one flow is pending at a time: starting a
new one closes the pending one (its generator gets ``GeneratorExit``), so a
view that lost a request can't wedge the session. Answers to anything but the
pending request are ignored.

The runner is single-threaded like the rest of the session: it runs the flow
on the caller's thread, inside the caller's command.
"""

import dataclasses
import itertools
import logging
from typing import Any, Callable, Generator, Optional

logger = logging.getLogger(__name__)

Flow = Generator[Any, Any, None]
"""A flow: yields requests (dataclasses with a ``request_id`` field), receives answers."""


class FlowRunner:
    """Runs one request/response flow at a time."""

    def __init__(self, emit: Callable[[object], None]) -> None:
        """Create a runner.

        Args:
            emit: Publishes a request (the session's ``Emitter.emit``).
        """
        self._emit = emit
        self._ids = itertools.count(1)
        self._flow: Optional[Flow] = None
        self._request_id: Optional[int] = None
        self._request: Any = None

    @property
    def pending_request_id(self) -> Optional[int]:
        """The id of the request waiting for an answer, or None."""
        return self._request_id

    @property
    def pending_request(self) -> Any:
        """The request waiting for an answer (with its ``request_id``), or None."""
        return self._request if self._flow is not None else None

    def start(self, flow: Flow) -> None:
        """Run ``flow`` up to its first request (or to its end).

        A flow still waiting for an answer is closed first.

        Raises:
            Whatever the flow raises; the runner is then idle.
        """
        if self._flow is not None:
            logger.warning("Request %s was never answered; closing its flow", self._request_id)
            self.cancel()
        self._step(flow, None)

    def respond(self, request_id: int, value: Any) -> bool:
        """Resume the pending flow with the answer to its request.

        Args:
            request_id: The ``request_id`` of the request being answered.
            value: The answer; by convention None means the user cancelled.

        Returns:
            True if the answer was for the pending request, False if it was
            ignored (stale or unknown id).

        Raises:
            Whatever the flow raises; the runner is then idle.
        """
        if self._flow is None or request_id != self._request_id:
            logger.warning("Ignoring an answer to request %s (pending: %s)",
                           request_id, self._request_id)
            return False
        flow, self._flow, self._request_id = self._flow, None, None
        self._step(flow, value)
        return True

    def cancel(self) -> None:
        """Close the pending flow, if any (its ``finally`` blocks run)."""
        flow, self._flow, self._request_id = self._flow, None, None
        if flow is not None:
            flow.close()

    def _step(self, flow: Flow, value: Any) -> None:
        """Send ``value`` into ``flow`` and publish the request it yields next."""
        try:
            request = flow.send(value)
        except StopIteration:
            return
        request_id = next(self._ids)
        try:
            request = dataclasses.replace(request, request_id=request_id)
        except TypeError:
            flow.close()
            raise TypeError(f"a flow must yield a dataclass with a request_id, not {request!r}")
        self._flow, self._request_id, self._request = flow, request_id, request
        self._emit(request)
