"""Tap tempo (the {bpm} picker's Tap button): the tempo from the taps' times.

The maths is the core's (toolbar.tap_tempo); the desktop picker only keeps
the times from a monotonic clock. Tibi, 2026-11-15: "add a tap here to find
the bpm by tapping".
"""

import random

import pytest

from chordnotepad.session.toolbar import (
    MAX_BPM, MIN_BPM, TAP_INTERVALS, TAP_RESET_S, tap_count, tap_tempo)


def taps(bpm, n, start=100.0):
    return [start + i * 60.0 / bpm for i in range(n)]


def test_one_tap_or_none_is_no_tempo_yet():
    assert tap_tempo([]) is None and tap_count([]) == 0
    assert tap_tempo([5.0]) is None and tap_count([5.0]) == 1


@pytest.mark.parametrize("bpm", [20, 60, 100, 120, 137, 240, 400])
def test_steady_taps_give_their_tempo(bpm):
    assert tap_tempo(taps(bpm, 2)) == bpm
    assert tap_tempo(taps(bpm, 12)) == bpm
    assert tap_count(taps(bpm, 12)) == 12


def test_no_magnet_to_tens_a_tapped_119_stays_119():
    assert tap_tempo(taps(119, 6)) == 119
    assert tap_tempo(taps(121, 6)) == 121


def test_jitter_averages_out():
    # Each tap up to 30 ms off a 120 bpm grid: eight intervals span 4 s, so
    # the average is off by at most 60 ms / 8 (under 2 bpm).
    rng = random.Random(7)
    for _ in range(50):
        times = [i * 0.5 + rng.uniform(-0.03, 0.03) for i in range(9)]
        assert abs(tap_tempo(times) - 120) <= 2
    # Alternating early and late taps cancel exactly.
    times = [0.02, 0.48, 1.02, 1.48, 2.02]
    assert tap_tempo(times) == 120


def test_only_the_last_intervals_count():
    # Eight intervals at 100 after a slower start: only the 100s are averaged.
    slow = taps(90, 5)
    fast = taps(100, TAP_INTERVALS + 1, start=slow[-1] + 60.0 / 100)
    assert tap_tempo(slow + fast) == 100
    # Speeding up: the count follows within a few taps.
    assert tap_tempo(slow + fast[:3]) not in (90, 100)


def test_a_pause_starts_a_new_count():
    first = taps(60, 6)
    second = taps(150, 4, start=first[-1] + TAP_RESET_S + 0.5)
    assert tap_tempo(first + second) == 150
    assert tap_count(first + second) == 4
    # The tap after the pause is the new count's first: no tempo yet.
    assert tap_tempo(first + second[:1]) is None
    assert tap_count(first + second[:1]) == 1


def test_a_gap_over_twice_the_average_starts_a_new_count():
    # 120 bpm (0.5 s), then a 1.2 s gap: a fresh count, not 50 bpm mixed in.
    times = taps(120, 5)
    times.append(times[-1] + 1.2)
    assert tap_count(times) == 1 and tap_tempo(times) is None
    times += [times[-1] + 0.6, times[-1] + 1.2]
    assert tap_tempo(times) == 100
    # A little slower than the average is still the same count.
    times = taps(120, 5)
    times.append(times[-1] + 0.9)
    assert tap_count(times) == 6


def test_clamped_to_the_toolbar_range():
    # Faster than 400 bpm (a flam of taps) shows 400; the slowest is 20.
    assert tap_tempo([0.0, 0.05, 0.1]) == MAX_BPM
    assert tap_tempo([0.0, TAP_RESET_S]) == MIN_BPM


def test_the_same_instant_twice_is_one_tap():
    assert tap_tempo([1.0, 1.0]) is None
    assert tap_tempo([1.0, 1.0, 1.5]) == 120
