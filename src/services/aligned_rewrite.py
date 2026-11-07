"""Rewrite the chords and directives of a song, keeping chords over their syllables.

Transpose and notation conversion both swap chord names for names of another
length (``C`` to ``Db``, ``Rem`` to ``Dm``). This is the layer that keeps the
song readable while they do, and that makes the change undo itself: moving a
song there and back (transposing up and down by the same amount, converting
to the other notation and back) gives back the text it started from.

The invariant is *chord-above-syllable*: after the rewrite each chord still
sits above the lyric character it did before. A chord line's tokens (chords
and directives) are anchors; the text between two anchors is padding.

* A token that **grows** first eats the spaces after it on the chord line,
  keeping at least one. When that isn't enough, the lyric line below is
  stretched so the rest of it moves right with the chords: spaces are added
  at the last word gap between the token's syllable and the next one's, or,
  with no gap there, a middle dot (:data:`FILL`) and spaces go into the word
  just before the next syllable (``singer`` becomes ``sin·ger``). With no
  lyric under the next token (no lyric line, or one that ends before it)
  the tokens after just move right.
* A token that **shrinks** pads the chord line, so the next tokens keep
  their columns, unless the gap after it is a single space, the shape a
  growth leaves. Then the lyric gives back what a growth would have put in:
  the dot and spaces just before the next syllable, or spaces from the last
  run of two or more under the gap. What it can't give back is padded. With
  no lyric under the next token the tokens after move back left, as long as
  that doesn't bring them over the lyric.

A line that isn't a chord line (``{key: Bb}  {bpm: 90}``) only has its tokens
swapped; its gaps stay as they are.

Each shrink undoes the growth that came before it, so a round trip leaves the
text as it was, with two exceptions, both only in spaces, where the text
can't tell what a growth did:

* a lyric spaced by hand (two or more spaces between words) under a chord
  gap a longer chord narrowed to one space: on the way back a shorter chord
  takes one of those spaces;
* past the end of the lyric, or on a line of chords alone, a gap a longer
  chord narrowed to one space stays one space (the columns of a chord
  chart matter more than that space: a packed line, ``C G Am F``, comes
  back exactly).

The "lyric line" of a chord line is the line right after it, when that is a
non-empty line the detector didn't take for a chord line and that has text
outside directives and comments.
"""

import re
from typing import Callable, List, Optional

from models.line import LineType


#: What goes into a word to move its next syllable right (``sin·ger``): a
#: middle dot, the dictionary's syllable mark, in every font (Latin-1). Not
#: a ``-``: songs write their own hyphens into words (``Hal-le-lu-jah``), and
#: the way back can only take out a fill it can tell from the song's text.
FILL = '\u00b7'


class Anchor:
    """A token on a chord line (chord or directive) and what replaces it.

    ``rs``/``re`` are its columns in the line, ``old_text`` the text there
    and ``new_text`` the replacement.
    """

    __slots__ = ('rs', 're', 'new_text', 'old_text')

    def __init__(self, rs: int, re_: int, new_text: str, old_text: str):
        self.rs = rs
        self.re = re_
        self.new_text = new_text
        self.old_text = old_text


def is_lyric_line(text_lines: List[str], lines_model, idx: int) -> bool:
    """Whether line ``idx`` is a lyric line a chord line above can pair with."""
    if idx < 0 or idx >= len(text_lines):
        return False
    if lines_model[idx].type == LineType.CHORD:
        return False
    s = text_lines[idx]
    if not s.strip():
        return False
    # [^{}]: linear on a line of unclosed braces; * so "{}" alone isn't a lyric.
    stripped = re.sub(r'\{[^{}]*\}', '', s)
    stripped = re.sub(r'//.*$', '', stripped)
    return bool(stripped.strip())


def resize_spaces(segment: str, target_len: int) -> str:
    """Grow/shrink a between-token segment to ``target_len`` by adding or
    removing spaces (from the trailing run first, then the leading run),
    leaving any non-space content intact."""
    cur = len(segment)
    if target_len == cur:
        return segment
    if target_len > cur:
        return segment + ' ' * (target_len - cur)
    remove = cur - target_len
    trailing = len(segment) - len(segment.rstrip(' '))
    take = min(remove, trailing)
    segment = segment[:len(segment) - take]
    remove -= take
    if remove > 0:
        leading = len(segment) - len(segment.lstrip(' '))
        take = min(remove, leading)
        segment = segment[take:]
    return segment


def insert_into_lyric(lyric: List[str], lo: int, hi: int, count: int) -> None:
    """Insert ``count`` characters into the lyric so the syllable at ``hi``
    (the next token's) moves right by ``count`` and the one at ``lo`` stays.

    A space goes in at the last word gap in ``(lo, hi]`` (widening the run);
    with none, a ``-`` and ``count - 1`` spaces go in just before ``hi``.
    The caller makes sure the lyric reaches ``hi``.
    """
    insert_at = None
    for p in range(hi, lo, -1):
        if lyric[p - 1] == ' ' or lyric[p] == ' ':
            insert_at = p
            break
    if insert_at is not None:
        lyric[insert_at:insert_at] = [' '] * count
    else:
        lyric[hi:hi] = [FILL] + [' '] * (count - 1)


def take_from_lyric(lyric: List[str], lo: int, hi: int, count: int) -> int:
    """Take up to ``count`` characters out of the lyric between ``lo`` and the
    next token's syllable at ``hi``, as :func:`insert_into_lyric` put them
    in, so the syllable at ``hi`` moves left; returns how many it took.

    Undoes a ``-`` fill first: a ``-`` and spaces just before ``hi`` in a
    word with no other gap in ``(lo, hi)``, spaces first, the ``-`` last.
    Else spaces from the last run touching ``(lo, hi]``, when it has two or
    more, keeping one (all its characters are spaces, so which go is moot).
    """
    # The "-" fill: [lo+1 .. dash) word, dash, spaces up to hi, a letter at hi.
    j = hi
    while j - 1 > lo and lyric[j - 1] == ' ':
        j -= 1
    dash = j - 1
    if (dash - 1 > lo and lyric[dash] == FILL and lyric[hi] != ' '
            and ' ' not in lyric[lo + 1:dash]):
        spaces = hi - j
        take = min(count, spaces + 1)
        if take <= spaces:
            del lyric[j:j + take]
        else:
            del lyric[dash:hi]
        return take
    # Spaces: the last run touching (lo, hi], when it has two or more.
    p = hi
    while p > lo and lyric[p] != ' ':
        p -= 1
    if p <= lo:
        return 0
    start, end = p, p + 1
    while start - 1 >= lo and lyric[start - 1] == ' ':
        start -= 1
    while end <= hi and end < len(lyric) and lyric[end] == ' ':
        end += 1
    run = end - start
    take = min(count, run - 1)
    if take > 0:
        del lyric[start:start + take]
    return max(take, 0)


def substitute_line(raw: str, anchors: List[Anchor]) -> str:
    """``raw`` with each anchor's ``old_text`` replaced by its ``new_text``
    and every gap kept: for a line that isn't a chord line ("{key: Bb}  {bpm:
    90}"), where columns mean nothing."""
    out: List[str] = []
    cursor = 0
    for a in sorted(anchors, key=lambda a: a.rs):
        out.append(raw[cursor:a.rs])
        out.append(a.new_text)
        cursor = a.re
    out.append(raw[cursor:])
    return ''.join(out)


def rewrite_line(raw: str, anchors: List[Anchor], lyric: Optional[List[str]]) -> str:
    """``raw`` with each anchor's ``old_text`` replaced by its ``new_text``,
    kept in line with ``lyric`` (changed in place); see the module doc."""
    anchors = sorted(anchors, key=lambda a: a.rs)
    shift = 0          # how far the lyric has moved under the current token
    out: List[str] = []
    cursor = 0
    for k, a in enumerate(anchors):
        out.append(raw[cursor:a.rs])
        out.append(a.new_text)
        cursor = a.re
        if k == len(anchors) - 1:
            break
        delta = len(a.new_text) - (a.re - a.rs)
        next_rs = anchors[k + 1].rs
        seg = raw[a.re:next_rs]
        seg_len = len(seg)
        lo, hi = a.rs + shift, next_rs + shift
        under = lyric is not None and hi < len(lyric)
        if delta > 0:
            if seg_len - delta >= 1:
                new_seg_len = seg_len - delta
            else:
                new_seg_len = 1
                if under:
                    grow = delta - seg_len + 1
                    insert_into_lyric(lyric, lo, hi, grow)
                    shift += grow
        elif delta < 0 and seg == ' ':
            shrink = -delta
            if under:
                taken = take_from_lyric(lyric, lo, hi, shrink)
                shift -= taken
                new_seg_len = 1 + shrink - taken
            elif lyric is None or hi - shrink >= len(lyric):
                # Nothing below the next token: close up, as a growth into a
                # one-space gap moved the tokens after it right (C G Am F).
                new_seg_len = 1
            else:
                # Closing up would put the next token over the lyric, where
                # the way back would stretch it: keep the columns instead.
                new_seg_len = 1 + shrink
        else:
            new_seg_len = seg_len - delta
        out.append(resize_spaces(seg, new_seg_len))
        cursor = next_rs
    out.append(raw[cursor:])
    return ''.join(out)


def rewrite_aligned(text: str, lines_model,
                    anchors_of: Callable[[int, str, object], List[Anchor]]) -> str:
    """Rewrite ``text`` line by line, keeping chords over their syllables.

    Args:
        text: The song.
        lines_model: The detected lines of ``text`` (one per ``\\n`` line).
        anchors_of: ``(line index, line text, line model)`` -> the line's
            :class:`Anchor` list: every chord and directive on it, those that
            don't change with ``new_text == old_text``, so the gaps between
            tokens stay pure padding.

    Returns:
        The rewritten text (the same line count).
    """
    text_lines = text.split('\n')
    out_lines = list(text_lines)
    for i, model in enumerate(lines_model):
        anchors = anchors_of(i, text_lines[i], model)
        if not anchors or all(a.new_text == a.old_text for a in anchors):
            continue
        if model.type != LineType.CHORD:
            out_lines[i] = substitute_line(text_lines[i], anchors)
            continue
        lyric_idx = None
        if is_lyric_line(text_lines, lines_model, i + 1):
            lyric_idx = i + 1
        lyric = list(out_lines[lyric_idx]) if lyric_idx is not None else None
        out_lines[i] = rewrite_line(text_lines[i], anchors, lyric)
        if lyric is not None:
            out_lines[lyric_idx] = ''.join(lyric)
    return '\n'.join(out_lines)
