"""Key names: which strings name a key, and their American spelling.

A key is a note name and an optional ``m`` for minor: American (``C``,
``F#m``, ``Bb``) or European (``Do``, ``Fa#m``, ``Sib``, accents allowed),
with ``#``/``b`` or ``♯``/``♭``. Roman numerals, MIDI key signatures and
voicing rules all work on the American spelling.
"""

import re
from typing import Optional

from chord.converter import NotationConverter

_AMERICAN_KEY = re.compile(r'^[A-G][#b]?m?$')


def american_key(key: Optional[str]) -> Optional[str]:
    """``key`` spelled in American notation (``"Lam"`` -> ``"Am"``), or None
    when it doesn't name a key (``"Xyz"``, ``"C7"``, empty).

    Args:
        key: A key name in either notation, or None.
    """
    if not key:
        return None
    text = key.strip().replace('♯', '#').replace('♭', 'b')
    if _AMERICAN_KEY.match(text):
        return text
    converted = NotationConverter.chord_european_to_american(text)
    if converted != text and _AMERICAN_KEY.match(converted):
        return converted
    return None


def is_valid_key(key: Optional[str]) -> bool:
    """Whether ``key`` names a key (see :func:`american_key`)."""
    return american_key(key) is not None
