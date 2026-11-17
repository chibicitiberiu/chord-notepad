"""Suggest the capo position that makes a song easiest to play on a fretboard.

This is *advice only*: it never re-voices anything. Given the active
:class:`~models.fretboard_spec.FretboardSpec` and the whole-song chord
sequence, :func:`rank_capos` scores every capo position from 0 up to
``max_capo`` and ranks them, the recommended one first: the one the guitar
picker rates easiest, but only when it beats capo 0 by a meaningful margin
(otherwise capo 0). :func:`suggest_capo` returns just that recommendation,
:func:`ease_of` puts each option in words against capo 0 and
:func:`capo_shapes` names the shapes a capo turns the chords into, for the
Suggest Capo dialog's list.

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
from typing import Callable, List, Optional, Sequence, Tuple

from chordnotepad.audio.guitar_chord_picker import GuitarChordPicker
from chordnotepad.constants import CAPO_MAX_DEFAULT, CAPO_MIN_GAIN, CAPO_MIN_TOTAL_GAIN
from chordnotepad.models.chord_notes import ChordNotes
from chordnotepad.models.fretboard_spec import FretboardSpec

#: :func:`ease_of`'s words.
EASIER = "Easier"
HARDER = "Harder"
ABOUT_THE_SAME = "About the same"
NO_CAPO = "No capo"

#: How many shapes :func:`capo_shapes` names before it stops with "…".
MAX_SHAPES = 8


@dataclasses.dataclass(frozen=True)
class CapoOption:
    """One capo position's whole-song playability.

    Attributes:
        capo: The fret (0 for no capo).
        score: The guitar picker's score for the sequence at this capo
            (higher is easier).
        gain_per_chord: How much better than capo 0 it scores, per chord
            (negative when it is worse; 0.0 for capo 0 itself).
    """

    capo: int
    score: float
    gain_per_chord: float


@dataclasses.dataclass(frozen=True)
class CapoChoice:
    """One row of the Suggest Capo list, before it is put in words.

    Attributes:
        capo: The fret (0 for no capo).
        ease: :func:`ease_of`'s word for it.
        shapes: :func:`capo_shapes` for it.
        recommended: Whether it is :func:`rank_capos`' recommendation
            (the first row).
    """

    capo: int
    ease: str
    shapes: Tuple[str, ...]
    recommended: bool

logger = logging.getLogger(__name__)


def _capo_spec(spec: FretboardSpec, capo: int) -> FretboardSpec:
    """Return ``spec`` with every open-string pitch raised by ``capo`` semitones.

    The tuning is bumped in place via :func:`dataclasses.replace` on the frozen
    spec; all other fields (limits, weights) are preserved unchanged.
    """
    raised = tuple(pitch + capo for pitch in spec.tuning)
    return dataclasses.replace(spec, tuning=raised)


def _gate(chords: int, min_gain: float, min_total_gain: float) -> float:
    """The improvement over capo 0 a capo needs before it is worth suggesting."""
    return max(min_gain * chords, min_total_gain)


def _chord_count(sequence: Sequence[Optional[ChordNotes]]) -> int:
    """The chords with notes (repeats included); rests don't count."""
    return sum(1 for cn in sequence if cn is not None and cn.notes)


def rank_capos(
    spec: FretboardSpec,
    sequence: List[ChordNotes],
    max_capo: int = CAPO_MAX_DEFAULT,
    should_abort: Optional[Callable[[], bool]] = None,
    min_gain: float = CAPO_MIN_GAIN,
    min_total_gain: float = CAPO_MIN_TOTAL_GAIN,
) -> List[CapoOption]:
    """Every capo position ``0..max_capo`` with its score, the recommended one first.

    The recommended option is the top scorer when it beats capo 0 by
    ``max(min_gain * chords, min_total_gain)`` (each chord with notes,
    repeats included), else capo 0. The rest follow by score, best first;
    equal scores go to the lower capo, so the result is deterministic.

    Args:
        spec: The active fretboard spec (its tuning is what a capo raises).
        sequence: The whole song's (or the selection's) resolved chords, in
            playback order.
        max_capo: Highest capo position to consider (inclusive).
        should_abort: Optional cooperative-abort predicate, checked between
            capo positions and threaded into every per-capo score. When it
            fires, :class:`~exceptions.RenderAborted` propagates out of this
            function. ``None`` (default) never aborts.
        min_gain: See :data:`constants.CAPO_MIN_GAIN`.
        min_total_gain: See :data:`constants.CAPO_MIN_TOTAL_GAIN`.

    Returns:
        ``max_capo + 1`` options, or an empty list when the sequence has no
        voiceable chords.
    """
    chords = _chord_count(sequence)
    if not chords:
        return []

    scores = []
    for capo in range(0, max_capo + 1):
        if should_abort is not None and should_abort():
            from chordnotepad.exceptions import RenderAborted
            raise RenderAborted()
        picker = GuitarChordPicker(_capo_spec(spec, capo) if capo else spec)
        scores.append(picker.voice_sequence_score(sequence, should_abort=should_abort))

    base = scores[0]
    options = [CapoOption(capo, score, (score - base) / chords)
               for capo, score in enumerate(scores)]
    # Best first; an equal score keeps the lower capo ahead.
    by_score = sorted(options, key=lambda o: (-o.score, o.capo))
    top = by_score[0]
    recommended = top if top.score - base >= _gate(chords, min_gain, min_total_gain) else options[0]
    if recommended.capo:
        logger.debug("Capo advisor: recommending capo %d (score %.3f vs %.3f at capo 0)",
                     recommended.capo, recommended.score, base)
    return [recommended] + [o for o in by_score if o is not recommended]


def ease_of(
    option: CapoOption,
    base: CapoOption,
    chords: int,
    min_gain: float = CAPO_MIN_GAIN,
    min_total_gain: float = CAPO_MIN_TOTAL_GAIN,
) -> str:
    """``option`` against capo 0 (``base``), in words.

    "Easier" when it beats capo 0 by the margin a suggestion needs
    (``max(min_gain * chords, min_total_gain)``), "Harder" when capo 0
    beats it by that margin, otherwise "About the same". Capo 0 itself is
    "No capo".
    """
    if option.capo == 0:
        return NO_CAPO
    gate = _gate(chords, min_gain, min_total_gain)
    gain = option.score - base.score
    if gain >= gate:
        return EASIER
    if -gain >= gate:
        return HARDER
    return ABOUT_THE_SAME


def capo_shapes(
    chords: Sequence[Tuple[str, Optional[str]]],
    capo: int,
    notation: str,
    limit: int = MAX_SHAPES,
) -> Tuple[str, ...]:
    """The shapes ``chords`` are played with under a capo on fret ``capo``.

    Each chord moves down ``capo`` semitones
    (:func:`services.transpose_service.transpose_chord_token`), spelled in
    the key it is in, moved the same way, as Transpose would write it.

    Args:
        chords: ``(chord, key)`` in playback order: the chord in American
            spelling (a roman numeral already resolved), the key in effect
            as the song writes it (in ``notation``), or None. Repeats are
            dropped: each chord is named once, where it first appears.
        capo: The fret.
        notation: The song's notation (``american`` or ``european``): the
            keys are read in it and the shapes are written in it.
        limit: How many shapes to name; when there are more, the last
            entry is "…".

    Returns:
        The distinct shapes, in the order their chords first appear.
    """
    from chordnotepad.chord.converter import NotationConverter
    from chordnotepad.services.transpose_service import keys_for_move, transpose_chord_token

    distinct = list(dict.fromkeys(chords))
    shapes: List[str] = []
    for i, (chord, key) in enumerate(distinct):
        keys = keys_for_move(key, -capo, notation) if key else None
        source, target = keys if keys is not None else (None, None)
        next_chord = distinct[i + 1][0] if i + 1 < len(distinct) else None
        shape = transpose_chord_token(chord, -capo, "american", key=target,
                                      next_chord=next_chord, source_key=source)
        if notation == "european":
            shape = NotationConverter.chord_american_to_european(shape)
        if shape not in shapes:
            shapes.append(shape)
    if len(shapes) > limit:
        return tuple(shapes[:limit]) + ("\u2026",)
    return tuple(shapes)


def suggest_capo(
    spec: FretboardSpec,
    sequence: List[ChordNotes],
    max_capo: int = CAPO_MAX_DEFAULT,
    min_gain: float = CAPO_MIN_GAIN,
    min_total_gain: float = CAPO_MIN_TOTAL_GAIN,
    should_abort: Optional[Callable[[], bool]] = None,
) -> Optional[int]:
    """Suggest the easiest-to-play capo position for a song, or ``None``.

    The recommended option of :func:`rank_capos`: the best-scoring position,
    but only when it is nonzero *and* beats capo 0 by at least ``min_gain``
    per chord (each chord with notes, repeats included) and
    ``min_total_gain`` in all. Deterministic; ties go to the lower capo.

    Args:
        spec: The active fretboard spec (its tuning is what a capo raises).
        sequence: The whole song's resolved chords, in playback order.
            Entries with no notes (rests) are ignored for the empty-guard.
        max_capo: Highest capo position to consider (inclusive).
        min_gain: Minimum score improvement per chord over capo 0 required to
            suggest a capo. See :data:`constants.CAPO_MIN_GAIN`.
        min_total_gain: Minimum improvement over the whole sequence, so two
            or three chords can't get a capo on a small gain. See
            :data:`constants.CAPO_MIN_TOTAL_GAIN`.
        should_abort: Optional cooperative-abort predicate (see
            :func:`rank_capos`); :class:`~exceptions.RenderAborted`
            propagates out of this function when it fires.

    Returns:
        The suggested capo fret (``1..max_capo``), or ``None`` when capo 0 is
        best, the improvement is below the margin, or the sequence has no
        voiceable chords.
    """
    options = rank_capos(spec, sequence, max_capo, should_abort=should_abort,
                         min_gain=min_gain, min_total_gain=min_total_gain)
    if not options or options[0].capo == 0:
        return None
    return options[0].capo
