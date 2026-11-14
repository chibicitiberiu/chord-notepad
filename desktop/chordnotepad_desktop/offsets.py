"""Offsets in the session's terms (code points) and in Qt's (UTF-16 units).

The session counts a text in Unicode code points, as Python does. Qt counts
QString positions in UTF-16 units: a character outside the Basic
Multilingual Plane (an emoji, a musical symbol such as U+1D11E) is one code
point but two units. Every position that crosses between the editor and the
session goes through :class:`OffsetMapper`, the only place in the Qt front
end that converts. It is the Android app's ``OffsetMapper.kt`` in Python.

A text without such characters (nearly every song) maps one to one and costs
nothing. Otherwise the mapper keeps the code-point index of each astral
character and converts with a binary search.

A lone surrogate (which a Python str from Qt can hold) counts as one code
point and one unit, as in Java. Offsets outside the text are clamped to it;
a UTF-16 offset between the two halves of a pair maps to the code point the
pair encodes.
"""

import re
from bisect import bisect_left
from typing import List, Tuple

_ASTRAL = re.compile("[\U00010000-\U0010FFFF]")


class OffsetMapper:
    """Converts offsets for one version of a text (make a new one after a change).

    Args:
        text: The text, as Python holds it (code points).
    """

    __slots__ = ("length", "utf16_length", "_astral")

    def __init__(self, text: str) -> None:
        #: Code points before each astral character, ascending.
        self._astral: List[int] = [m.start() for m in _ASTRAL.finditer(text)]
        #: The text's length in code points.
        self.length = len(text)
        #: The text's length in UTF-16 units.
        self.utf16_length = self.length + len(self._astral)

    @property
    def is_identity(self) -> bool:
        """Whether both kinds of offset agree for this text."""
        return not self._astral

    def to_utf16(self, code_point: int) -> int:
        """The UTF-16 offset of code-point offset ``code_point``."""
        cp = min(max(int(code_point), 0), self.length)
        if not self._astral:
            return cp
        # Every astral character before cp adds one unit.
        return cp + bisect_left(self._astral, cp)

    def to_code_point(self, utf16: int) -> int:
        """The code-point offset of UTF-16 offset ``utf16``."""
        u = min(max(int(utf16), 0), self.utf16_length)
        if not self._astral:
            return u
        # Astral character i starts at unit astral[i] + i. Each one that
        # starts before u counts one code point fewer than its units; that
        # also holds when u splits a pair (it maps to the pair's code point).
        lo, hi = 0, len(self._astral)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._astral[mid] + mid < u:
                lo = mid + 1
            else:
                hi = mid
        return u - lo

    def range_to_utf16(self, start: int, end: int) -> Tuple[int, int]:
        """A code-point range ``[start, end)`` in UTF-16 units."""
        return self.to_utf16(start), self.to_utf16(end)


def utf16_length(text: str) -> int:
    """``text``'s length in UTF-16 units."""
    return len(text) + len(_ASTRAL.findall(text))
