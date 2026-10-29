"""BackgroundWorker: jobs off the session thread, outcomes posted back to it."""

import threading

import pytest

from session.testing import ManualHost
from session.workers import BackgroundWorker, Outcome


def settle(worker, host):
    assert worker.wait_idle(timeout=10)
    host.run_pending()


def test_a_job_runs_on_the_worker_thread_and_its_value_comes_back_through_the_host():
    host = ManualHost()
    worker = BackgroundWorker(host, name="TestWorker")
    ran_on = []
    outcomes = []

    worker.submit(lambda: ran_on.append(threading.current_thread().name) or 42, outcomes.append)
    assert worker.wait_idle(timeout=10)
    assert outcomes == []  # posted, not delivered until the host runs it

    host.run_pending()
    assert ran_on == ["TestWorker"]
    assert outcomes == [Outcome(value=42)]
    assert outcomes[0].ok


def test_an_exception_comes_back_as_the_outcome():
    host = ManualHost()
    worker = BackgroundWorker(host)
    outcomes = []
    error = ValueError("boom")

    def fail():
        raise error

    worker.submit(fail, outcomes.append)
    settle(worker, host)
    assert len(outcomes) == 1
    assert outcomes[0].error is error and not outcomes[0].ok


def test_jobs_run_one_at_a_time_in_order():
    host = ManualHost()
    worker = BackgroundWorker(host)
    gate = threading.Event()
    order = []
    worker.submit(lambda: gate.wait(5) and order.append(1), lambda o: None)
    worker.submit(lambda: order.append(2), lambda o: None)
    gate.set()
    settle(worker, host)
    assert order == [1, 2]


def test_a_cancelled_job_is_not_delivered():
    host = ManualHost()
    worker = BackgroundWorker(host)
    gate = threading.Event()
    outcomes = []
    running = worker.submit(lambda: gate.wait(5), outcomes.append)
    queued = worker.submit(lambda: outcomes.append("ran"), outcomes.append)
    queued.cancel()     # not started yet: skipped
    running.cancel()    # already running: finishes, outcome dropped
    gate.set()
    settle(worker, host)
    assert outcomes == []
    assert running.cancelled and queued.cancelled


def test_shutdown_drops_outcomes_on_their_way_and_refuses_new_jobs():
    host = ManualHost()
    worker = BackgroundWorker(host)
    outcomes = []
    worker.submit(lambda: 1, outcomes.append)
    assert worker.wait_idle(timeout=10)  # posted
    worker.shutdown()
    host.run_pending()
    assert outcomes == []
    assert worker.is_shut_down
    with pytest.raises(RuntimeError):
        worker.submit(lambda: 2, outcomes.append)
    worker.shutdown()  # twice is fine


def test_the_thread_starts_with_the_first_job():
    worker = BackgroundWorker(ManualHost(), name="LazyWorker")
    assert all(t.name != "LazyWorker" for t in threading.enumerate())
    assert worker.wait_idle(timeout=0)  # idle with nothing submitted
