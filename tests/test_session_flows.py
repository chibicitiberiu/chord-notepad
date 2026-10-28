"""FlowRunner: generator flows that ask the view and resume on the answer."""

from dataclasses import dataclass

import pytest

from session.flows import FlowRunner


@dataclass(frozen=True)
class Ask:
    request_id: int
    question: str


class Runner:
    def __init__(self):
        self.emitted = []
        self.runner = FlowRunner(self.emitted.append)


def test_a_flow_runs_to_its_first_request_and_resumes_with_the_answer():
    r = Runner()
    log = []

    def flow():
        name = yield Ask(0, "name?")
        log.append(name)
        colour = yield Ask(0, "colour?")
        log.append(colour)

    r.runner.start(flow())
    assert r.emitted == [Ask(1, "name?")]
    assert r.runner.pending_request_id == 1

    assert r.runner.respond(1, "Arthur") is True
    assert r.emitted[-1] == Ask(2, "colour?")
    assert r.runner.respond(2, "blue") is True
    assert log == ["Arthur", "blue"]
    assert r.runner.pending_request_id is None


def test_a_flow_without_requests_just_runs():
    r = Runner()
    ran = []

    def flow():
        ran.append(True)
        return
        yield  # a generator nonetheless

    r.runner.start(flow())
    assert ran == [True]
    assert r.emitted == []
    assert r.runner.pending_request_id is None


def test_wrong_or_stale_ids_are_ignored():
    r = Runner()
    answers = []

    def flow():
        answers.append((yield Ask(0, "?")))

    r.runner.start(flow())
    assert r.runner.respond(99, "x") is False
    assert r.runner.respond(1, "ok") is True
    assert r.runner.respond(1, "again") is False
    assert answers == ["ok"]


def test_starting_a_flow_closes_the_pending_one():
    r = Runner()
    closed = []

    def first():
        try:
            yield Ask(0, "first")
        finally:
            closed.append("first")

    def second():
        yield Ask(0, "second")

    r.runner.start(first())
    r.runner.start(second())
    assert closed == ["first"]
    assert r.emitted == [Ask(1, "first"), Ask(2, "second")]
    assert r.runner.respond(1, "late") is False
    assert r.runner.pending_request_id == 2


def test_cancel_closes_the_pending_flow():
    r = Runner()
    closed = []

    def flow():
        try:
            yield Ask(0, "?")
        finally:
            closed.append(True)

    r.runner.start(flow())
    r.runner.cancel()
    assert closed == [True]
    assert r.runner.pending_request_id is None
    r.runner.cancel()  # nothing pending: no-op


def test_an_exception_in_a_flow_propagates_and_leaves_the_runner_idle():
    r = Runner()

    def flow():
        yield Ask(0, "?")
        raise RuntimeError("boom")

    r.runner.start(flow())
    with pytest.raises(RuntimeError, match="boom"):
        r.runner.respond(1, "x")
    assert r.runner.pending_request_id is None


def test_yielding_something_without_a_request_id_is_a_bug():
    r = Runner()

    def flow():
        yield "not a request"

    with pytest.raises(TypeError):
        r.runner.start(flow())
    assert r.runner.pending_request_id is None
