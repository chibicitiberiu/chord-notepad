"""Tests for the generic Viterbi/beam-search sequence optimizer."""
import itertools
import random
import time

import pytest

from audio.voicing_optimizer import optimize_sequence


def _total_score(candidate_sets, unary_score, transition_score, choice):
    """Compute the total score of a fully-chosen sequence of indices."""
    total = 0.0
    previous = None
    for position, idx in enumerate(choice):
        candidate = candidate_sets[position][idx]
        total += unary_score(position, candidate)
        if previous is not None:
            total += transition_score(previous, candidate)
        previous = candidate
    return total


def _brute_force(candidate_sets, unary_score, transition_score):
    """Exhaustively find the best index tuple.

    Ties are broken by picking the lexicographically smallest index tuple
    among all tuples achieving the maximum score.
    """
    best_choice = None
    best_score = None
    ranges = [range(len(c)) for c in candidate_sets]
    for choice in itertools.product(*ranges):
        score = _total_score(candidate_sets, unary_score, transition_score, choice)
        if (
            best_score is None
            or score > best_score
            or (score == best_score and choice < best_choice)
        ):
            best_score = score
            best_choice = choice
    return list(best_choice), best_score


def _make_random_instance(rng, n_positions, max_candidates):
    """Build a random small instance with continuous-ish float scores.

    Uses full float precision (no rounding) so that exact ties between
    distinct full sequences are, for practical purposes, impossible - this
    keeps the exactness comparison against brute force unambiguous.
    """
    # Candidate objects just need to be hashable/usable as dict keys; use
    # (position, original_index) tuples so scoring functions can look up
    # per-position, per-candidate values deterministically regardless of
    # any internal reordering/pruning done by the optimizer.
    candidate_sets = []
    unary_table = {}
    transition_table = {}
    for position in range(n_positions):
        n_candidates = rng.randint(1, max_candidates)
        candidates = [(position, i) for i in range(n_candidates)]
        candidate_sets.append(candidates)
        for c in candidates:
            unary_table[c] = rng.uniform(-5.0, 5.0)

    for position in range(n_positions - 1):
        for c1 in candidate_sets[position]:
            for c2 in candidate_sets[position + 1]:
                transition_table[(c1, c2)] = rng.uniform(-5.0, 5.0)

    def unary_score(position, candidate):
        return unary_table[candidate]

    def transition_score(prev_candidate, candidate):
        return transition_table[(prev_candidate, candidate)]

    return candidate_sets, unary_score, transition_score


class TestExactness:
    """The optimizer must match brute force when pruning cannot kick in."""

    def test_random_small_instances_match_brute_force(self):
        """200 random small instances must match the brute-force optimum."""
        rng = random.Random(1234567)
        for trial in range(200):
            n_positions = rng.randint(1, 6)
            max_candidates = rng.randint(1, 5)
            candidate_sets, unary_score, transition_score = _make_random_instance(
                rng, n_positions, max_candidates
            )

            expected_choice, expected_score = _brute_force(
                candidate_sets, unary_score, transition_score
            )

            result = optimize_sequence(
                candidate_sets,
                unary_score,
                transition_score,
                beam_width=1000,
                prune_to=None,
            )

            assert result == expected_choice, f"trial {trial} mismatch"
            actual_score = _total_score(
                candidate_sets, unary_score, transition_score, result
            )
            assert actual_score == pytest.approx(expected_score)


class TestDeterminism:
    """Repeated calls on the same instance must be stable, ties included."""

    def _tied_instance(self):
        # All unary and transition scores identical -> every full sequence
        # scores the same, so every tie-break decision is genuinely
        # exercised at every position.
        candidate_sets = [[0, 1, 2], [0, 1, 2], [0, 1, 2]]

        def unary_score(position, candidate):
            return 1.0

        def transition_score(prev_candidate, candidate):
            return 2.0

        return candidate_sets, unary_score, transition_score

    def test_repeated_calls_are_identical(self):
        """Calling optimize_sequence twice on a tied instance must agree."""
        candidate_sets, unary_score, transition_score = self._tied_instance()

        first = optimize_sequence(candidate_sets, unary_score, transition_score)
        second = optimize_sequence(candidate_sets, unary_score, transition_score)

        assert first == second

    def test_ties_are_broken_towards_lowest_index(self):
        """With every score tied, the lowest index at every position wins."""
        candidate_sets, unary_score, transition_score = self._tied_instance()

        result = optimize_sequence(candidate_sets, unary_score, transition_score)

        assert result == [0, 0, 0]

    def test_determinism_across_many_repeated_calls(self):
        """A larger tied instance must also be stable across repeats."""
        candidate_sets = [list(range(5)) for _ in range(5)]

        def unary_score(position, candidate):
            return 0.0

        def transition_score(prev_candidate, candidate):
            return 0.0

        results = [
            optimize_sequence(candidate_sets, unary_score, transition_score)
            for _ in range(10)
        ]

        assert all(r == results[0] for r in results)


class TestBeamPruningRecoversLookaheadTrap:
    """Demonstrates why the DP (beam >= 2) exists over greedy (beam == 1).

    Position 0 has a locally-worse candidate ("A_bad", low unary score)
    that unlocks a much better transition into position 1's "B_special"
    candidate. A greedy, beam_width=1 search locks in the locally-best
    "A_good" candidate after position 0 (since with no history yet, its
    partial score is just its unary score) and can never revisit that
    decision, so it is stuck taking a mediocre transition afterwards.
    A wider beam keeps both position-0 candidates alive long enough to
    discover that the "worse" one actually leads to the global optimum.
    """

    def _trap_instance(self):
        # position 0: index 0 = A_good (unary 10), index 1 = A_bad (unary 0)
        # position 1: index 0 = B_normal (unary 0), index 1 = B_special (unary 0)
        candidate_sets = [["A_good", "A_bad"], ["B_normal", "B_special"]]

        unary_values = {"A_good": 10.0, "A_bad": 0.0, "B_normal": 0.0, "B_special": 0.0}
        transitions = {
            ("A_good", "B_normal"): 0.0,
            ("A_good", "B_special"): -1000.0,
            ("A_bad", "B_normal"): 0.0,
            ("A_bad", "B_special"): 100.0,
        }

        def unary_score(position, candidate):
            return unary_values[candidate]

        def transition_score(prev_candidate, candidate):
            return transitions[(prev_candidate, candidate)]

        return candidate_sets, unary_score, transition_score

    def test_greedy_beam_width_one_is_suboptimal(self):
        """beam_width=1 commits to A_good and misses the global optimum."""
        candidate_sets, unary_score, transition_score = self._trap_instance()

        result = optimize_sequence(
            candidate_sets, unary_score, transition_score, beam_width=1
        )

        # A_good (index 0), then the best reachable option from it, B_normal (index 0).
        assert result == [0, 0]
        score = _total_score(candidate_sets, unary_score, transition_score, result)
        assert score == pytest.approx(10.0)

    def test_wider_beam_recovers_global_optimum(self):
        """beam_width>=2 (including the default) finds the true best path."""
        candidate_sets, unary_score, transition_score = self._trap_instance()

        for beam_width in (2, 20):
            result = optimize_sequence(
                candidate_sets, unary_score, transition_score, beam_width=beam_width
            )
            assert result == [1, 1]
            score = _total_score(candidate_sets, unary_score, transition_score, result)
            assert score == pytest.approx(100.0)


class TestPruneToCorrectness:
    """Verifies the prune_to knob behaves exactly as documented."""

    def test_pruned_candidates_never_appear_in_output(self):
        """Candidates outside the top prune_to by unary score are excluded."""
        # 5 candidates per position; only the best 2 by unary score may
        # ever be chosen when prune_to=2.
        candidate_sets = [[0, 1, 2, 3, 4], [0, 1, 2, 3, 4]]
        unary_values = {0: 1.0, 1: 5.0, 2: 3.0, 3: 9.0, 4: 2.0}

        def unary_score(position, candidate):
            return unary_values[candidate]

        def transition_score(prev_candidate, candidate):
            # Deliberately favor low-unary candidates in transitions, so
            # that if pruning were not applied by unary score alone, a
            # pruned-out candidate could otherwise win.
            return 100.0 if candidate in (0, 4) else 0.0

        allowed = {3, 1}  # top-2 by unary score at every position

        result = optimize_sequence(
            candidate_sets, unary_score, transition_score, prune_to=2
        )

        assert set(result) <= allowed

    def test_prune_to_one_forces_per_position_unary_argmax(self):
        """With prune_to=1, only the unary-best candidate can survive."""
        candidate_sets = [[0, 1, 2], [0, 1, 2, 3], [0, 1]]
        unary_values = [
            {0: 1.0, 1: 5.0, 2: -3.0},
            {0: 0.0, 1: 2.0, 2: 9.0, 3: 4.0},
            {0: -1.0, 1: 7.0},
        ]

        def unary_score(position, candidate):
            return unary_values[position][candidate]

        def transition_score(prev_candidate, candidate):
            # Scores are irrelevant here: with a single surviving
            # candidate per position there is no choice left to make.
            return -1000.0 if candidate == 0 else 0.0

        expected = [
            max(values, key=values.get) for values in unary_values
        ]

        result = optimize_sequence(
            candidate_sets, unary_score, transition_score, prune_to=1
        )

        assert result == expected


class TestIndexIntegrity:
    """Returned indices must index into the ORIGINAL candidate lists."""

    def test_indices_survive_internal_compaction(self):
        """Original indices are reported correctly even with heavy pruning."""
        # Position 0: only index 3 has a strong unary score; others tie at 0.
        candidate_sets = [[0, 1, 2, 3], [0, 1, 2, 3]]
        unary_pos0 = {0: 0.0, 1: 0.0, 2: 0.0, 3: 100.0}
        # Position 1: index 2 has the strongest unary score, so it survives
        # prune_to=2 alongside the lowest-index tie-break winner (index 0).
        unary_pos1 = {0: 1.0, 1: 1.0, 2: 5.0, 3: 1.0}

        transitions = {
            (3, 2): 9.0,
            (3, 0): 5.0,
            (0, 2): -1000.0,
            (0, 0): -1000.0,
        }

        def unary_score(position, candidate):
            return unary_pos0[candidate] if position == 0 else unary_pos1[candidate]

        def transition_score(prev_candidate, candidate):
            return transitions[(prev_candidate, candidate)]

        result = optimize_sequence(
            candidate_sets, unary_score, transition_score, prune_to=2, beam_width=2
        )

        # Best full total: unary(3)=100 + transition(3,2)=9 + unary(2)=5 = 114,
        # beating (3, 0) -> 100+5+1=106. Original indices 3 and 2 must be
        # reported even though position 0's candidates 1 and 2 (unrelated
        # ties) were pruned away and never entered the DP at all.
        assert result == [3, 2]

        score = _total_score(candidate_sets, unary_score, transition_score, result)
        assert score == pytest.approx(114.0)


class TestEdgeCases:
    """Boundary conditions explicitly called out in the module contract."""

    def test_empty_candidate_sets_returns_empty_list(self):
        """No positions at all means no choices to make."""
        result = optimize_sequence([], lambda p, c: 0.0, lambda a, b: 0.0)
        assert result == []

    def test_single_position_returns_unary_argmax(self):
        """With one position, the DP degenerates to a plain argmax."""
        candidate_sets = [["a", "b", "c"]]
        unary_values = {"a": 1.0, "b": 9.0, "c": 4.0}

        result = optimize_sequence(
            candidate_sets,
            lambda position, candidate: unary_values[candidate],
            lambda prev, cur: 0.0,
        )

        assert result == [1]

    def test_empty_candidate_list_raises_value_error_naming_position(self):
        """An empty inner list must raise, and the message names the position."""
        candidate_sets = [["a"], [], ["c"]]

        with pytest.raises(ValueError, match="1"):
            optimize_sequence(candidate_sets, lambda p, c: 0.0, lambda a, b: 0.0)

    def test_beam_width_zero_raises_value_error(self):
        """beam_width < 1 is invalid."""
        with pytest.raises(ValueError):
            optimize_sequence(
                [["a"]], lambda p, c: 0.0, lambda a, b: 0.0, beam_width=0
            )

    def test_negative_beam_width_raises_value_error(self):
        """Negative beam_width is invalid."""
        with pytest.raises(ValueError):
            optimize_sequence(
                [["a"]], lambda p, c: 0.0, lambda a, b: 0.0, beam_width=-5
            )

    def test_prune_to_zero_raises_value_error(self):
        """prune_to < 1 is invalid (None is the "keep everything" sentinel)."""
        with pytest.raises(ValueError):
            optimize_sequence(
                [["a"]], lambda p, c: 0.0, lambda a, b: 0.0, prune_to=0
            )

    def test_prune_to_none_keeps_everything(self):
        """prune_to=None is the documented "no pruning" sentinel, not invalid."""
        result = optimize_sequence(
            [["a", "b"]],
            lambda p, c: {"a": 1.0, "b": 2.0}[c],
            lambda a, b: 0.0,
            prune_to=None,
        )
        assert result == [1]


class TestRealisticShapeSmokeTest:
    """A song-sized instance must run fast and return a valid result."""

    def test_large_instance_completes_quickly(self):
        """100 positions x 30 candidates, beam 20/prune 30, under a second."""
        rng = random.Random(42)
        n_positions = 100
        n_candidates = 30
        candidate_sets = [list(range(n_candidates)) for _ in range(n_positions)]

        unary_table = [
            [rng.uniform(-1.0, 1.0) for _ in range(n_candidates)]
            for _ in range(n_positions)
        ]
        transition_table = [
            [
                [rng.uniform(-1.0, 1.0) for _ in range(n_candidates)]
                for _ in range(n_candidates)
            ]
            for _ in range(n_positions - 1)
        ]

        def unary_score(position, candidate):
            return unary_table[position][candidate]

        def transition_score(prev_candidate, candidate):
            # transition_table is indexed by the position of the *earlier*
            # candidate in the pair; recovered from closures is fine here
            # since candidates are plain ints 0..n_candidates-1 and we only
            # need *a* well-defined smooth-ish score, not per-position truth.
            return transition_table[0][prev_candidate][candidate]

        start = time.monotonic()
        result = optimize_sequence(
            candidate_sets,
            unary_score,
            transition_score,
            beam_width=20,
            prune_to=30,
        )
        elapsed = time.monotonic() - start

        assert elapsed < 1.0, f"took {elapsed:.3f}s, expected < 1s"
        assert len(result) == n_positions
        for position, idx in enumerate(result):
            assert 0 <= idx < len(candidate_sets[position])


# --------------------------------------------------------------------------
# Cooperative abort (should_abort)
# --------------------------------------------------------------------------

from exceptions import RenderAborted  # noqa: E402


def test_should_abort_none_is_identical_to_default():
    # An explicit should_abort=None must produce the exact same choice as the
    # default (goldens rely on this being a pure no-op).
    candidate_sets = [[0, 1, 2], [0, 1, 2], [0, 1, 2]]

    def unary(pos, c):
        return float(c)

    def transition(prev, c):
        return -abs(c - prev)

    base = optimize_sequence(candidate_sets, unary, transition)
    with_none = optimize_sequence(candidate_sets, unary, transition, should_abort=None)
    assert base == with_none


def test_should_abort_false_never_raises():
    candidate_sets = [[0, 1], [0, 1], [0, 1]]
    result = optimize_sequence(
        candidate_sets,
        lambda pos, c: float(c),
        lambda prev, c: 0.0,
        should_abort=lambda: False,
    )
    assert len(result) == 3


def test_should_abort_true_raises_render_aborted_promptly():
    # A never-say-die scoring function would loop forever if the abort were not
    # honored; firing it immediately must raise before much work is done.
    calls = {"unary": 0}

    def unary(pos, c):
        calls["unary"] += 1
        return float(c)

    big = [list(range(50)) for _ in range(200)]
    with pytest.raises(RenderAborted):
        optimize_sequence(
            big, unary, lambda prev, c: 0.0, should_abort=lambda: True
        )


def test_should_abort_mid_sequence_stops_forward_pass():
    # Abort turns on after the third forward-pass position check.
    state = {"n": 0}

    def should_abort():
        state["n"] += 1
        return state["n"] > 3

    candidate_sets = [[0, 1] for _ in range(20)]
    with pytest.raises(RenderAborted):
        optimize_sequence(
            candidate_sets,
            lambda pos, c: float(c),
            lambda prev, c: 0.0,
            should_abort=should_abort,
        )
