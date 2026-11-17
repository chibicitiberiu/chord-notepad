"""Chord-tone role taxonomy shared across voicers.

A chord's identity is carried unequally by its tones. This module classifies a
tone (given as a register-preserving interval above the root) into one of six
*roles*, and supplies the default completeness penalties that say how badly a
voicing suffers when a tone of each role is dropped. The piano picker and
the ensemble (SATB) voicer share the taxonomy, so both agree on what a tone
is; the penalties below are the piano's. An ensemble has no left hand to
cover the root, so it keeps its own omission order (fifth first; see
``models.ensemble_spec.ENSEMBLE_OMIT_WEIGHTS``).

The roles:

- ``root`` (interval 0 mod 12): the tonal anchor. Cheap to omit from an upper
  voicing because a bass line normally covers it.
- ``third`` (3 or 4): major/minor quality. Defines the chord; effectively never
  dropped.
- ``fifth`` (7): the perfect fifth. Harmonically weak, the first tone
  sacrificed when a voicing runs out of fingers.
- ``seventh`` (10 or 11): the tone that turns a triad into a seventh chord.
  Defining; effectively never dropped.
- ``color`` (everything else below the octave - notably sus2's 2nd, sus4's 4th,
  the added 6th and a diminished or augmented fifth): the tone that *is* the
  chord's character. A sus4's suspended fourth is not decoration, it replaces
  the third, so it counts as colour and is protected accordingly; likewise the
  b5 of m7b5 or 7b5 and the #5 of aug or 7#5, without which the chord is heard
  as m7, 7 or a major triad. One exception: in a diminished seventh chord
  (minor third, diminished fifth and diminished seventh all present) every
  tone is a minor third from the next and any three of them sound the same
  chord, so its b5 stays a ``fifth``.
- ``extension`` (>= 12, i.e. 9th/11th/13th stacked above the octave): upper
  structure. Adds richness but is expendable when space is tight.
"""

from typing import Dict, Iterable, Mapping, Optional

#: The perfect fifth, the only fifth with the ``fifth`` role (outside a
#: diminished seventh chord).
PERFECT_FIFTH = 7
_DIMINISHED_FIFTH = 6
_DIMINISHED_SEVENTH_TONES = frozenset((3, 6, 9))


def is_diminished_seventh(intervals: Iterable[int]) -> bool:
    """True when the chord holds a minor third, a diminished fifth and a
    diminished seventh (intervals 3, 6 and 9 below the octave)."""
    return _DIMINISHED_SEVENTH_TONES <= {iv for iv in intervals if 0 <= iv < 12}


def classify_role(interval: int, intervals: Optional[Iterable[int]] = None) -> str:
    """Classify a chord tone by its register-preserving interval.

    ``intervals``, the whole chord's intervals, is needed for one case only:
    the diminished fifth of a diminished seventh chord is a ``fifth``, while
    without the chord (or in any other chord) a diminished or augmented
    fifth is ``color``.
    """
    if interval >= 12:
        return 'extension'
    m = interval % 12
    if m == 0:
        return 'root'
    if m in (3, 4):
        return 'third'
    if m in (10, 11):
        return 'seventh'
    if m == PERFECT_FIFTH:
        return 'fifth'
    if m == _DIMINISHED_FIFTH and intervals is not None and is_diminished_seventh(intervals):
        return 'fifth'
    return 'color'  # sus2/sus4/6th, an altered fifth and other defining colour tones


#: Extensions a chord symbol spells as alterations (b9, #9, #11, b13): each is
#: written in the name, so each is a named extension.
ALTERED_EXTENSIONS = frozenset((13, 15, 18, 20))


def is_named_extension(interval: int, intervals: Iterable[int]) -> bool:
    """Whether an extension is one the chord's name spells.

    A chord symbol names its highest natural extension (the 13 of G13, the 11
    of Am11, the 9 of Cmaj9 or Cadd9) and every altered one (the b9 of C7b9,
    the #11 of Cmaj7#11). A natural 9 or 11 under a named 13th, or a 9 under
    a named 11th, is stacked in by the name without being what it says, so it
    is the one to leave out first. False for anything below the octave.
    """
    if interval < 12:
        return False
    if interval in ALTERED_EXTENSIONS:
        return True
    naturals = [iv for iv in intervals if iv >= 12 and iv not in ALTERED_EXTENSIONS]
    return not naturals or interval >= max(naturals)


#: The share of the ``extension`` omission weight an extension the name only
#: stacks in (not :func:`is_named_extension`) costs: G13's 9th goes before its 13th.
STACKED_EXTENSION_SHARE = 0.5


def omission_cost(omit: Mapping[str, float], interval: int, intervals: Iterable[int]) -> float:
    """What leaving out the tone at ``interval`` costs under an ``omit`` map.

    The weight of its role (:func:`classify_role`); an extension the chord's
    name only stacks in costs :data:`STACKED_EXTENSION_SHARE` of it.
    """
    intervals = list(intervals)
    role = classify_role(interval, intervals)
    cost = omit[role]
    if role == 'extension' and not is_named_extension(interval, intervals):
        cost *= STACKED_EXTENSION_SHARE
    return cost


# Completeness (piano): penalty (subtracted) for each chord tone missing from
# the whole voicing, keyed by the tone's harmonic role. The bass covers the root,
# so an omitted root is cheap; the third, seventh and colour tones define the
# chord and are effectively never dropped.
DEFAULT_OMIT_PENALTY: Dict[str, float] = {
    'root': 4.0,
    'third': 40.0,
    'fifth': 8.0,
    'seventh': 40.0,
    'color': 30.0,
    'extension': 7.0,
}
