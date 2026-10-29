"""Background work for the session: one job at a time, results on the session thread.

The session thread never renders (``docs/architecture/session.md``, threading
contract). Work that renders a song for the user (MIDI export, Suggest Capo)
is handed to a :class:`BackgroundWorker`::

    job = make_job()                       # on the session thread: snapshot inputs
    handle = worker.submit(job, on_done)   # job() runs on the worker thread
    ...
    on_done(outcome)                       # later, on the session thread

A job must only read what it captured when it was made (never live session or
viewmodel state) and must not touch the session. Its return value or the
exception it raised comes back as an :class:`Outcome`, through ``host.post``,
so ``on_done`` runs on the session thread like any other posted callback.

Jobs run in submission order on one daemon thread, started on the first
submit. :meth:`Job.cancel` (or :meth:`BackgroundWorker.shutdown`) drops a
result that hasn't been delivered yet; a job that already started still runs
to its end, its outcome is just not delivered.
"""

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from session.host import Host

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class Outcome(Generic[T]):
    """What a job produced: its value, or the exception it raised."""

    value: Optional[T] = None
    error: Optional[BaseException] = None

    @property
    def ok(self) -> bool:
        """Whether the job returned (rather than raised)."""
        return self.error is None


class Job:
    """A submitted job; ``cancel()`` keeps its outcome from being delivered."""

    def __init__(self, fn: Callable[[], Any], on_done: Callable[[Outcome], None]) -> None:
        self._fn = fn
        self._on_done = on_done
        self._cancelled = threading.Event()

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` was called."""
        return self._cancelled.is_set()

    def cancel(self) -> None:
        """Drop the outcome (and skip the job if it hasn't started)."""
        self._cancelled.set()


# Put on the queue to end the worker thread.
_STOP = object()


class BackgroundWorker:
    """A single background thread whose results are posted to the session thread."""

    def __init__(self, host: Host, name: str = "SessionWorker") -> None:
        """Create the worker; its thread starts with the first :meth:`submit`.

        Args:
            host: Where outcomes are delivered (``host.post``).
            name: The thread's name, for logs and debuggers.
        """
        self._host = host
        self._name = name
        self._queue: "queue.Queue[Any]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._shut_down = False
        # Jobs submitted and not yet finished running, for wait_idle().
        self._unfinished = 0
        self._idle = threading.Condition(self._lock)

    def submit(self, fn: Callable[[], T], on_done: Callable[[Outcome[T]], None]) -> Job:
        """Run ``fn()`` on the worker thread; ``on_done(outcome)`` on the session thread.

        Args:
            fn: The job. Runs after every job submitted before it.
            on_done: Gets the :class:`Outcome`, unless the job was cancelled
                or the worker shut down first.

        Returns:
            The job's handle.

        Raises:
            RuntimeError: After :meth:`shutdown`.
        """
        job = Job(fn, on_done)
        with self._lock:
            if self._shut_down:
                raise RuntimeError("the background worker has been shut down")
            self._unfinished += 1
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
                self._thread.start()
        self._queue.put(job)
        return job

    def shutdown(self) -> None:
        """Stop taking jobs and drop every outcome not delivered yet.

        Doesn't wait: a job already running finishes on its (daemon) thread
        and its outcome is thrown away.
        """
        with self._lock:
            if self._shut_down:
                return
            self._shut_down = True
        self._queue.put(_STOP)

    @property
    def is_shut_down(self) -> bool:
        """Whether :meth:`shutdown` was called."""
        return self._shut_down

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """Block until every submitted job has run (tests; never on the session thread
        of a live app). Outcomes are posted by then, not necessarily delivered.

        Returns:
            True if the worker went idle, False on timeout.
        """
        with self._idle:
            return self._idle.wait_for(lambda: self._unfinished == 0, timeout)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is _STOP:
                return
            try:
                if not job.cancelled and not self._shut_down:
                    outcome = self._execute(job)
                    self._host.post(lambda job=job, outcome=outcome: self._deliver(job, outcome))
            finally:
                with self._idle:
                    self._unfinished -= 1
                    self._idle.notify_all()

    @staticmethod
    def _execute(job: Job) -> Outcome:
        try:
            return Outcome(value=job._fn())
        except Exception as e:
            logger.debug("Background job failed: %s", e, exc_info=True)
            return Outcome(error=e)

    def _deliver(self, job: Job, outcome: Outcome) -> None:
        """On the session thread: hand the outcome over unless it was called off."""
        if job.cancelled or self._shut_down:
            logger.debug("Dropping the outcome of a cancelled background job")
            return
        job._on_done(outcome)
