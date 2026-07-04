"""Sequence optimization harness for chord voicing selection.

When voicing a whole song, each chord (position) has a set of candidate
voicings. Each candidate has an intrinsic quality score (e.g. how idiomatic
a fingering is, or how well a piano voicing fits the chord in isolation),
and each pair of consecutive choices has a transition score capturing
voice-leading smoothness (how easy/pleasant it is to move from one voicing
to the next). Choosing the best voicing for every position independently
can produce a sequence that sounds intrinsically fine chord-by-chord but
jumps around awkwardly; choosing purely by best transitions can drift into
weak individual voicings. The right answer is the sequence that maximizes
the *combined* score, which is a classic Viterbi-style dynamic program:
for every candidate at every position, track the best cumulative score of
any path reaching it, and backtrack once the end is reached.

Songs can have many chords, each with many candidate voicings, so this
module supports two knobs to keep the search tractable:

- ``prune_to`` discards, at each position, all but the best few candidates
  by their own (unary) score before the DP ever runs.
- ``beam_width`` keeps only the best few partial paths (by cumulative
  score so far) as viable predecessors when scoring the next position.

This module is a generic search harness with no music-theory knowledge of
its own. The guitar and piano voicers are expected to supply the candidate
voicings and the two scoring callbacks.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# A beam entry tracks, for one candidate at one position: the best
# cumulative score of any path ending at that candidate, the candidate's
# index in the *original* (unpruned) candidate list for its position, the
# candidate object itself (needed to score the next position's
# transitions), and a back-pointer to the entry in the previous position's
# beam that achieves that best score (None at the first position).
_BeamEntry = Tuple[float, int, Any, Optional[int]]


def optimize_sequence(
    candidate_sets: List[List[Any]],
    unary_score: Callable[[int, Any], float],
    transition_score: Callable[[Any, Any], float],
    beam_width: int = 20,
    prune_to: Optional[int] = 30,
) -> List[int]:
    """Choose the best-scoring candidate at each position of a sequence.

    Uses a beam-pruned Viterbi dynamic program to select, for every
    position, one candidate from ``candidate_sets[position]`` such that the
    sum of unary scores plus the sum of consecutive transition scores is
    maximized (higher score is better).

    Args:
        candidate_sets: One list of candidates per position. Each inner
            list must be non-empty.
        unary_score: Called as ``unary_score(position, candidate)``,
            returning the intrinsic quality of using ``candidate`` at
            ``position``. Receiving the position lets callers weight, for
            example, the first chord of a song differently from the rest.
        transition_score: Called as
            ``transition_score(previous_candidate, candidate)``, returning
            the voice-leading quality of moving from ``previous_candidate``
            to ``candidate`` at consecutive positions.
        beam_width: Maximum number of partial paths kept, by cumulative
            score, as predecessors when scoring the next position. Must be
            >= 1. Smaller values search less of the space (faster, more
            greedy); larger values search more of it (slower, closer to
            exhaustive).
        prune_to: If not ``None``, at each position only the best
            ``prune_to`` candidates (by unary score alone) are kept before
            the DP runs. Must be >= 1 if given. ``None`` keeps every
            candidate.

    Returns:
        A list with one candidate index per position, indexing into the
        corresponding *original* (unpruned) list in ``candidate_sets``.
        Returns ``[]`` if ``candidate_sets`` is empty.

    Raises:
        ValueError: If ``beam_width`` or ``prune_to`` is < 1, or if any
            position's candidate list is empty.

    Notes:
        Deterministic: ties are always broken by preferring the lower
        candidate index (when choosing which candidates survive pruning or
        the beam) or the earlier predecessor (when several predecessors
        yield the same cumulative score). No randomness is used, so the
        same inputs always produce the same output. This function does
        not mutate ``candidate_sets`` or any of its elements.

        Complexity is O(n * prune_to * beam_width), where n is the number
        of positions.
    """
    if beam_width < 1:
        raise ValueError(f"beam_width must be >= 1, got {beam_width}")
    if prune_to is not None and prune_to < 1:
        raise ValueError(f"prune_to must be >= 1 or None, got {prune_to}")

    if not candidate_sets:
        logger.debug("optimize_sequence: empty candidate_sets, returning []")
        return []

    for position, candidates in enumerate(candidate_sets):
        if not candidates:
            raise ValueError(
                f"position {position} has an empty candidate list"
            )

    # Prune each position independently to its best `prune_to` candidates
    # by unary score. Each entry is (original_index, candidate, unary_value).
    # Sorting key (-unary, original_index) keeps the ties-go-to-lower-index
    # rule without relying on sort stability.
    pruned: List[List[Tuple[int, Any, float]]] = []
    for position, candidates in enumerate(candidate_sets):
        scored = [
            (orig_idx, candidate, unary_score(position, candidate))
            for orig_idx, candidate in enumerate(candidates)
        ]
        scored.sort(key=lambda item: (-item[2], item[0]))
        if prune_to is not None and len(scored) > prune_to:
            scored = scored[:prune_to]
        pruned.append(scored)
        logger.debug(
            "position %d: kept %d/%d candidate(s) after pruning",
            position, len(scored), len(candidates),
        )

    # Forward pass: Viterbi with a beam of surviving partial paths.
    beams: List[List[_BeamEntry]] = []

    first_beam: List[_BeamEntry] = [
        (unary_value, orig_idx, candidate, None)
        for orig_idx, candidate, unary_value in pruned[0]
    ]
    first_beam.sort(key=lambda entry: (-entry[0], entry[1]))
    if len(first_beam) > beam_width:
        first_beam = first_beam[:beam_width]
    beams.append(first_beam)

    for position in range(1, len(candidate_sets)):
        prev_beam = beams[position - 1]
        current_beam: List[_BeamEntry] = []
        for orig_idx, candidate, unary_value in pruned[position]:
            best_score: Optional[float] = None
            best_predecessor = 0
            for pred_idx, prev_entry in enumerate(prev_beam):
                score = (
                    prev_entry[0]
                    + transition_score(prev_entry[2], candidate)
                    + unary_value
                )
                if best_score is None or score > best_score:
                    best_score = score
                    best_predecessor = pred_idx
            current_beam.append((best_score, orig_idx, candidate, best_predecessor))
        current_beam.sort(key=lambda entry: (-entry[0], entry[1]))
        if len(current_beam) > beam_width:
            current_beam = current_beam[:beam_width]
        beams.append(current_beam)
        logger.debug(
            "position %d: beam of %d entrie(s), best score %.6f",
            position, len(current_beam), current_beam[0][0],
        )

    # Backward pass: reconstruct the winning path. Each beam is already
    # sorted best-first, so index 0 of the last beam is the overall winner.
    result: List[int] = [0] * len(candidate_sets)
    entry_idx = 0
    for position in range(len(candidate_sets) - 1, -1, -1):
        _score, orig_idx, _candidate, backptr = beams[position][entry_idx]
        result[position] = orig_idx
        if backptr is not None:
            entry_idx = backptr

    logger.debug(
        "optimize_sequence: chose %s with score %.6f",
        result, beams[-1][0][0],
    )
    return result
