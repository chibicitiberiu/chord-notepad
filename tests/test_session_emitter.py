"""The session's delivery contract (docs/architecture/session.md).

Output is buffered while a command runs and delivered at the outermost exit;
states coalesce (first position, latest value); events keep their order; a
listener that runs a command gets its output after the current round.
"""

from dataclasses import dataclass

import pytest

from session import errors
from session.emitter import Emitter
from session.testing import EventRecorder


@dataclass(frozen=True)
class StateA:
    value: int


@dataclass(frozen=True)
class StateB:
    value: int


@dataclass(frozen=True)
class Ping:
    n: int


def _subscribed():
    emitter = Emitter()
    recorder = EventRecorder()
    with emitter.batch():
        emitter.subscribe(recorder)
    return emitter, recorder


def test_nothing_is_delivered_until_the_outermost_batch_exits():
    emitter, rec = _subscribed()
    with emitter.batch():
        emitter.set_state(StateA(1))
        with emitter.batch():
            emitter.emit(Ping(1))
        assert rec.items == []
        emitter.emit(Ping(2))
        assert rec.items == []
    assert rec.compact() == [("StateA", 1), ("Ping", 1), ("Ping", 2)]


def test_a_state_set_twice_keeps_its_first_position_and_latest_value():
    emitter, rec = _subscribed()
    with emitter.batch():
        emitter.set_state(StateA(1))
        emitter.emit(Ping(1))
        emitter.set_state(StateB(1))
        emitter.set_state(StateA(2))
        emitter.emit(Ping(2))
        emitter.set_state(StateA(3))
    assert rec.compact() == [("StateA", 3), ("Ping", 1), ("StateB", 1), ("Ping", 2)]


def test_events_are_never_coalesced():
    emitter, rec = _subscribed()
    with emitter.batch():
        emitter.emit(Ping(1))
        emitter.emit(Ping(1))
    assert rec.compact() == [("Ping", 1), ("Ping", 1)]


def test_a_new_listener_gets_the_current_states_first():
    emitter = Emitter()
    with emitter.batch():
        emitter.set_state(StateA(1))
        emitter.set_state(StateB(1))
        emitter.emit(Ping(1))
    with emitter.batch():
        emitter.set_state(StateA(2))

    rec = EventRecorder()
    with emitter.batch():
        emitter.subscribe(rec)
    # Current values in first-set order; past events are not replayed.
    assert rec.compact() == [("StateA", 2), ("StateB", 1)]


def test_replay_goes_only_to_the_new_listener():
    emitter, first = _subscribed()
    with emitter.batch():
        emitter.set_state(StateA(1))
    first.clear()

    second = EventRecorder()
    with emitter.batch():
        emitter.subscribe(second)
    assert first.items == []
    assert second.compact() == [("StateA", 1)]


def test_output_of_a_command_run_by_a_listener_comes_after_the_current_round():
    emitter = Emitter()
    order = []

    def reacting(item):
        order.append(("reacting", item))
        if item == Ping(1):
            with emitter.batch():  # a command run from a listener
                emitter.emit(Ping(99))

    def watching(item):
        order.append(("watching", item))

    with emitter.batch():
        emitter.subscribe(reacting)
        emitter.subscribe(watching)
    with emitter.batch():
        emitter.emit(Ping(1))
        emitter.emit(Ping(2))

    assert order == [
        ("reacting", Ping(1)), ("watching", Ping(1)),
        ("reacting", Ping(2)), ("watching", Ping(2)),
        ("reacting", Ping(99)), ("watching", Ping(99)),
    ]


def test_output_is_flushed_even_when_the_command_raises():
    emitter, rec = _subscribed()
    with pytest.raises(ValueError):
        with emitter.batch():
            emitter.set_state(StateA(1))
            raise ValueError("boom")
    assert rec.compact() == [("StateA", 1)]


def test_a_failing_listener_is_reported_and_the_others_still_get_the_item():
    emitter = Emitter()
    rec = EventRecorder()
    reported = []
    previous = errors.set_handler(lambda exc_info, context: reported.append((exc_info[1], context)))
    try:
        def broken(item):
            raise RuntimeError("listener bug")

        with emitter.batch():
            emitter.subscribe(broken)
            emitter.subscribe(rec)
        with emitter.batch():
            emitter.emit(Ping(1))
    finally:
        errors.set_handler(previous)

    assert rec.compact() == [("Ping", 1)]
    assert len(reported) == 1
    assert str(reported[0][0]) == "listener bug"
    assert "Ping" in reported[0][1]


def test_cancelled_listener_gets_nothing_more():
    emitter = Emitter()
    rec = EventRecorder()
    with emitter.batch():
        subscription = emitter.subscribe(rec)
    subscription.cancel()
    subscription.cancel()  # idempotent
    with emitter.batch():
        emitter.emit(Ping(1))
    assert rec.items == []


def test_output_outside_a_command_is_a_bug():
    emitter = Emitter()
    with pytest.raises(RuntimeError):
        emitter.set_state(StateA(1))
    with pytest.raises(RuntimeError):
        emitter.emit(Ping(1))


def test_state_returns_the_latest_value():
    emitter = Emitter()
    assert emitter.state(StateA) is None
    with emitter.batch():
        emitter.set_state(StateA(1))
        emitter.set_state(StateA(2))
    assert emitter.state(StateA) == StateA(2)


def test_setting_a_state_to_its_current_value_delivers_nothing():
    emitter, rec = _subscribed()
    with emitter.batch():
        emitter.set_state(StateA(1))
    rec.clear()
    with emitter.batch():
        emitter.set_state(StateA(1))
    assert rec.items == []


def test_a_state_changed_and_changed_back_before_a_flush_is_delivered_once():
    emitter, rec = _subscribed()
    with emitter.batch():
        emitter.set_state(StateA(1))
    rec.clear()
    with emitter.batch():
        emitter.set_state(StateA(2))
        emitter.set_state(StateA(1))
    # Already queued, so it still goes out, carrying the latest value.
    assert rec.compact() == [("StateA", 1)]
