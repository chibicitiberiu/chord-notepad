"""Suggest the capo position that makes a song easiest to play on a fretboard.

This is *advice only*: it never re-voices anything. Given the active
:class:`~models.fretboard_spec.FretboardSpec` and the whole-song chord
sequence, :func:`suggest_capo` scores every capo position from 0 up to
``max_capo`` and returns the one the guitar picker rates easiest -- but only
when it beats capo 0 by a meaningful margin.

How a capo is modeled
---------------------
A capo at fret *N* raises every open string by *N* semitones. That is exactly
:func:`dataclasses.replace` on the (frozen) spec with each tuning entry bumped
by *N* (see :func:`_capo_spec`). A fresh :class:`GuitarChordPicker` built on the
raised spec then voices the same chords from the capo's new "nut", and its
:meth:`~audio.guitar_chord_picker.GuitarChordPicker.voice_sequence_score`
reports the total playability of the winning whole-song fingering path.

What drives the suggestion
--------------------------
The score is the picker's own weighted heuristic, dominated for this purpose by
three fretboard weights: ``open_string_bonus`` (a capo turns barre shapes back
into open ones), ``position_penalty`` (open shapes sit lower on the neck), and
``barre_penalty`` (barres disappear). A song full of barre chords in an awkward
key -- F#/B/C#/D#m, say -- scores much better a couple of frets up; a cowboy
progression already in open position (C/G/Am/F) only gets harder with a capo, so
no capo is suggested.

Very high capos raise the tuning so far that fewer chord shapes fit under
``max_fret``; the picker's normal relaxation ladder and fallbacks absorb that,
and the score simply reflects the worse playability, so no special guarding is
needed here -- the score speaks for itself.
"""

import dataclasses
import logging
from typing import Callable, List, Optional

from audio.guitar_chord_picker import GuitarChordPicker
from constants import CAPO_MAX_DEFAULT, CAPO_MIN_GAIN
from models.chord_notes import ChordNotes
from models.fretboard_spec import FretboardSpec

logger = logging.getLogger(__name__)


def _capo_spec(spec: FretboardSpec, capo: int) -> FretboardSpec:
    """Return ``spec`` with every open-string pitch raised by ``capo`` semitones.

    The tuning is bumped in place via :func:`dataclasses.replace` on the frozen
    spec; all other fields (limits, weights) are preserved unchanged.
    """
    raised = tuple(pitch + capo for pitch in spec.tuning)
    return dataclasses.replace(spec, tuning=raised)


def suggest_capo(
    spec: FretboardSpec,
    sequence: List[ChordNotes],
    max_capo: int = CAPO_MAX_DEFAULT,
    min_gain: float = CAPO_MIN_GAIN,
    should_abort: Optional[Callable[[], bool]] = None,
) -> Optional[int]:
    """Suggest the easiest-to-play capo position for a song, or ``None``.

    Scores capo positions ``0..max_capo`` with the guitar picker's whole-song
    playability score and returns the best-scoring position, but only when it is
    nonzero *and* beats capo 0 by at least ``min_gain``. Deterministic; ties go
    to the lower capo (a higher capo must strictly beat the running best to
    replace it, and capo 0 is the running best to start).

    Args:
        spec: The active fretboard spec (its tuning is what a capo raises).
        sequence: The whole song's resolved chords, in playback order. Entries
            with no notes (rests) are ignored for the empty-guard.
        max_capo: Highest capo position to consider (inclusive).
        min_gain: Minimum score improvement over capo 0 required to suggest a
            capo. See :data:`constants.CAPO_MIN_GAIN`.
        should_abort: Optional cooperative-abort predicate checked between capo
            positions and threaded into every per-capo whole-song score. When it
            fires, the underlying search raises
            :class:`~exceptions.RenderAborted`, which propagates out of this
            function. ``None`` (default) never aborts.

    Returns:
        The suggested capo fret (``1..max_capo``), or ``None`` when capo 0 is
        best, the improvement is below ``min_gain``, or the sequence has no
        voiceable chords.
    """
    if not any(cn is not None and cn.notes for cn in sequence):
        return None

    base_score = GuitarChordPicker(spec).voice_sequence_score(
        sequence, should_abort=should_abort)

    best_capo = 0
    best_score = base_score
    for capo in range(1, max_capo + 1):
        if should_abort is not None and should_abort():
            from exceptions import RenderAborted
            raise RenderAborted()
        picker = GuitarChordPicker(_capo_spec(spec, capo))
        score = picker.voice_sequence_score(sequence, should_abort=should_abort)
        # Strictly-greater keeps the tie-goes-to-lower-capo rule: an equal score
        # never displaces the lower capo already held in best_capo.
        if score > best_score:
            best_score = score
            best_capo = capo

    if best_capo == 0:
        return None
    if best_score - base_score < min_gain:
        return None
    logger.debug(
        "Capo advisor: suggesting capo %d (score %.3f vs %.3f at capo 0)",
        best_capo, best_score, base_score,
    )
    return best_capo
