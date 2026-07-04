"""Chord-tone role taxonomy shared across voicers.

A chord's identity is carried unequally by its tones. This module classifies a
tone (given as a register-preserving interval above the root) into one of six
*roles*, and supplies the default completeness penalties that say how badly a
voicing suffers when a tone of each role is dropped. The piano picker uses it
today; the upcoming ensemble (SATB) voicer reuses the same taxonomy so both
agree on what a chord "needs".

The roles:

- ``root`` (interval 0 mod 12): the tonal anchor. Cheap to omit from an upper
  voicing because a bass line normally covers it.
- ``third`` (3 or 4): major/minor quality. Defines the chord; effectively never
  dropped.
- ``fifth`` (6, 7 or 8): perfect/altered fifth. Harmonically weak, the first
  tone sacrificed when a voicing runs out of fingers.
- ``seventh`` (10 or 11): the tone that turns a triad into a seventh chord.
  Defining; effectively never dropped.
- ``color`` (everything else below the octave - notably sus2's 2nd, sus4's 4th
  and the added 6th): the tone that *is* the chord's character. A sus4's
  suspended fourth is not decoration, it replaces the third, so it counts as
  colour and is protected accordingly.
- ``extension`` (>= 12, i.e. 9th/11th/13th stacked above the octave): upper
  structure. Adds richness but is expendable when space is tight.
"""

from typing import Dict


def classify_role(interval: int) -> str:
    """Classify a chord tone by its register-preserving interval."""
    if interval >= 12:
        return 'extension'
    m = interval % 12
    if m == 0:
        return 'root'
    if m in (3, 4):
        return 'third'
    if m in (10, 11):
        return 'seventh'
    if m in (6, 7, 8):
        return 'fifth'
    return 'color'  # sus2/sus4/6th and other defining colour tones


# Completeness: penalty (subtracted) for each chord tone missing from the
# whole voicing, keyed by the tone's harmonic role. The bass covers the root,
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
