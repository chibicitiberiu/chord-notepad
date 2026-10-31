"""Headless chord transposition.

Transposes every absolute chord (and ``{key: ...}`` directive) in a document
by a number of semitones, reusing the existing detection machinery
(:class:`services.song_parser_service.SongParserService` /
:class:`chord.detector.ChordDetector`) to locate chords rather than inventing
new regexes. It mirrors the notation-conversion command path
(``convert_to_*``) but adds region support, key-directive shifting, and a
chord-line / lyric-line alignment layer.

What transposes
---------------
* Absolute chords, American and European, whose ``[start, end)`` span
  intersects the target region. Both the root and any slash-bass note shift.
  Quality/extensions/parentheses and any ``*duration`` suffix are preserved
  verbatim.
* ``{key: X}`` directives whose span intersects the region ('C' and 'Am'
  forms both shift; the major/minor form is preserved).

What does NOT transpose
-----------------------
* Roman-numeral chords (they are key-relative by definition), ``NC`` rests,
  invalid chords, comments and lyric lines.

Enharmonic policy
-----------------
Each moved root and slash bass is spelled by its scale degree in the key the
chord lands in (:mod:`services.key_spelling`), so a song moved into B gets
``F# C# G#m``, not ``Gb Db Abm``. The key at a chord is:

* the last valid ``{key: ...}`` before it, moved with the song (as
  :func:`transpose_key` rewrites it), whether or not the directive is in the
  transposed region;
* before the first one, the key detected from the chords before it, when the
  detection is sure (:func:`services.key_spelling.detected_target`);
* otherwise none. The toolbar / Settings key is never used.

Major keys use the key's letters, lowered 2, 3, 6, 7 and raised 4; minor keys
lowered 2 and raised 3, 4, 6, 7. A diminished chord whose next chord's root or
bass is a semitone above it takes a sharp (``D#dim7 Em7`` in D, not
``Ebdim7``). A degree spelling of E#/B#/Cb/Fb or a double accidental is
refused and the plain table below spells that note instead.

Without a key (and for callers of :func:`transpose_chord_token` that pass
none) the plain table applies. The default spelling for each pitch class (used
when the source root had no accidental) is::

    0=C  1=C#  2=D  3=Eb  4=E  5=F  6=F#  7=G  8=Ab  9=A  10=Bb  11=B

When the source root carried an accidental, that accidental *style* is kept
for the (black-key) result: a sharp source prefers the sharp spelling
(C# D# F# G# A#), a flat source the flat spelling (Db Eb Gb Ab Bb). Natural
(white-key) results have a single spelling regardless of style. The table
never emits double accidentals nor E#/Cb/Fb/B#.

Examples: ``C#`` +2 -> ``D#`` (style kept), ``Db`` +2 -> ``Eb``, ``Bb`` +1 ->
``B``, ``F#`` +1 -> ``G``, ``C`` +1 -> ``C#`` (default).

*Keys* (``{key}`` directives and the toolbar key) are named by
:func:`services.key_spelling.key_tonic`: the signature with fewer accidentals
(``C`` +1 -> ``Db``, ``Am`` -1 -> ``G#m``), the source's style breaking a tie
(``F#``/``Gb``, ``D#m``/``Ebm``). A key with no real signature (D#/G#/A# major,
Dbm/Gbm minor) is never written; a D# chord is unremarkable, D# major as a
key is not.

Chord-line / lyric-line alignment
---------------------------------
The invariant is *chord-above-syllable*: after transposing, each chord must
still sit above the same lyric character it did before.

* A chord that **shrinks** is padded with trailing spaces so following chords
  keep their columns; the paired lyric is untouched.
* A chord that **grows** first tries to absorb the growth by eating following
  spaces on the chord line (keeping >= 1 space between chords). When it cannot
  absorb, the *lyric line below* is stretched instead: characters are inserted
  so the rest of the lyric shifts right together with the chords above it
  (a space is added at an existing word gap when possible, otherwise a "-" is
  inserted mid-word). Growths are processed left to right, accumulating the
  offset.
* The "lyric line below" is the immediately following line the detector
  classified as a lyric line (non-empty, not a chord/directive/comment line).
  A chord line with no paired lyric line simply accepts the drift.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Union

from models.notation import Notation
from models.line import LineType
from models.directive import DirectiveType
from services.key_spelling import (
    Key, detected_target, key_tonic, leads_up, plain_spelling, spell_in_key)
from services.song_parser_service import SongParserService


# --- pitch-class tables -----------------------------------------------------

_NATURAL_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

_AMERICAN_TO_EUROPEAN = {'C': 'Do', 'D': 'Re', 'E': 'Mi', 'F': 'Fa',
                         'G': 'Sol', 'A': 'La', 'B': 'Si'}
# European roots to try, longest first so "Sol" wins over any 2-char prefix.
_EUROPEAN_ROOTS = ['sol', 'do', 're', 'mi', 'fa', 'la', 'si']
_EUROPEAN_PC = {'do': 0, 're': 2, 'mi': 4, 'fa': 5, 'sol': 7, 'la': 9, 'si': 11}

_ACC_OFFSET = {'#': 1, '♯': 1, 'b': -1, '♭': -1, '': 0}
_SHARPS = ('#', '♯')
_FLATS = ('b', '♭')


def _normalize_ascii(text: str) -> str:
    """Strip combining accents (Dó -> Do) without changing string length."""
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _acc_style(acc: str) -> Optional[str]:
    if acc in _SHARPS:
        return 'sharp'
    if acc in _FLATS:
        return 'flat'
    return None


def _notation_str(notation: Union[Notation, str]) -> str:
    return notation.value if isinstance(notation, Notation) else notation


def _parse_root(token: str, notation: str) -> Optional[Tuple[int, Optional[str], bool, int]]:
    """Parse the leading root note of a chord/note token.

    Returns ``(pitch_class, accidental_style, is_lowercase, consumed_chars)``
    or ``None`` if the token does not start with a recognizable root.
    """
    if not token:
        return None

    if notation == 'european':
        ascii_t = _normalize_ascii(token)
        low = ascii_t.lower()
        for root in _EUROPEAN_ROOTS:
            if low.startswith(root):
                consumed = len(root)
                acc = ''
                if consumed < len(ascii_t) and ascii_t[consumed] in ('#', 'b', '♯', '♭'):
                    acc = ascii_t[consumed]
                    consumed += 1
                is_lower = token[0].islower()
                pc = (_EUROPEAN_PC[root] + _ACC_OFFSET[acc]) % 12
                return (pc, _acc_style(acc), is_lower, consumed)
        return None

    # American
    letter = token[0]
    upper = letter.upper()
    if upper not in _NATURAL_PC:
        return None
    is_lower = letter.islower()
    consumed = 1
    acc = ''
    if consumed < len(token) and token[consumed] in ('#', 'b', '♯', '♭'):
        acc = token[consumed]
        consumed += 1
    pc = (_NATURAL_PC[upper] + _ACC_OFFSET[acc]) % 12
    return (pc, _acc_style(acc), is_lower, consumed)


def _spell(pc: int, style: Optional[str], notation: str, is_lower: bool,
           key: Optional[Key] = None, leading: bool = False) -> str:
    """Spell a pitch class back into a root note in the given notation.

    With a ``key`` the note is spelled by its degree in that key
    (:func:`services.key_spelling.spell_in_key`; ``leading`` raises a flat
    for a diminished chord leading up); without one, or when the degree
    spelling is refused, by the plain table and the source's ``style``
    (:func:`services.key_spelling.plain_spelling`).
    """
    american = spell_in_key(pc, key, leading) if key is not None else None
    if american is None:
        american = plain_spelling(pc, style)
    return _in_notation(american, notation, is_lower)


def _in_notation(american: str, notation: str, is_lower: bool) -> str:
    """An American note name (``F#``) in ``notation`` and case."""
    letter, acc = american[0], american[1:]
    if notation == 'european':
        spelled = _AMERICAN_TO_EUROPEAN[letter] + acc
    else:
        spelled = letter + acc
    return spelled.lower() if is_lower else spelled


def _transpose_note(token: str, semitones: int, notation: str, key: Optional[Key] = None) -> str:
    """Transpose a bare note token (root + accidental, e.g. a slash bass)."""
    parsed = _parse_root(token, notation)
    if parsed is None:
        return token
    pc, style, is_lower, consumed = parsed
    new_root = _spell((pc + semitones) % 12, style, notation, is_lower, key)
    return new_root + token[consumed:]


def transpose_chord_token(chord_part: str, semitones: int, notation: Union[Notation, str],
                          key: Optional[Key] = None, next_chord: Optional[str] = None) -> str:
    """Transpose a single chord string (root + optional slash bass).

    Quality/extensions/parentheses are preserved verbatim; the root and any
    slash-bass note shift. This is the per-token transform that could feed
    :py:meth:`SongParserService.rewrite_chord_spans`.

    Args:
        chord_part: The chord, without any ``*duration``.
        semitones: Number of semitones to shift (positive = up).
        notation: The chord's notation.
        key: The key the chord lands in (American); its root and bass are then
            spelled by degree. None spells them by the plain table.
        next_chord: The chord after this one, as written. A diminished chord
            whose next chord's root or bass is a semitone above it is spelled
            with a sharp (``D#dim7 Em7``, not ``Ebdim7``). Used only with
            ``key``.
    """
    notation = _notation_str(notation)
    parsed = _parse_root(chord_part, notation)
    if parsed is None:
        return chord_part
    pc, style, is_lower, consumed = parsed
    leading = key is not None and leads_up(chord_part, next_chord)
    new_root = _spell((pc + semitones) % 12, style, notation, is_lower, key, leading)
    rest = chord_part[consumed:]
    if '/' in rest:
        pre, bass = rest.split('/', 1)
        return new_root + pre + '/' + _transpose_note(bass, semitones, notation, key)
    return new_root + rest


def _moved_key(key_str: str, semitones: int, notation: str):
    """Read a key name and move it: ``(Key, is_lower, rest)`` with the moved
    key in American spelling and ``rest`` whatever followed the root, or None
    when ``key_str`` doesn't start with a note."""
    minor = key_str.endswith('m')
    root_str = key_str[:-1] if minor else key_str
    parsed = _parse_root(root_str, notation)
    if parsed is None:
        return None
    pc, style, is_lower, consumed = parsed
    tonic = key_tonic((pc + semitones) % 12, minor, style)
    return Key(tonic, minor), is_lower, root_str[consumed:]


def transpose_key(key_str: str, semitones: int, notation: Union[Notation, str]) -> str:
    """Transpose a key name (e.g. 'C', 'Am', 'Do', 'Lam'), preserving form.

    A trailing 'm' marks a minor key and is kept. The new tonic is named by
    :func:`services.key_spelling.key_tonic`: the key with fewer accidentals
    (C up one is ``Db``, not ``C#``; Am down one is ``G#m``, not ``Abm``),
    the source's accidental style breaking a tie (``F#``/``Gb``,
    ``D#m``/``Ebm``). A key with no real signature is never written: a chord
    can be spelled D# or Gbm freely, but as *keys* those would need more
    than seven accidentals.
    """
    notation = _notation_str(notation)
    key_str = key_str.strip()
    if not key_str:
        return key_str
    moved = _moved_key(key_str, semitones, notation)
    if moved is None:
        return key_str
    key, is_lower, rest = moved
    return _in_notation(key.tonic, notation, is_lower) + rest + ('m' if key.minor else '')


def _transpose_key_directive(directive_text: str, semitones: int, notation: str) -> str:
    """Rewrite a ``{key: X}`` directive's value, preserving spacing/braces."""
    m = re.match(r'(\{[^:}]*:\s*)(.*?)(\s*\})\Z', directive_text)
    if not m:
        return directive_text
    new_value = transpose_key(m.group(2), semitones, notation)
    return m.group(1) + new_value + m.group(3)


def _resize_spaces(segment: str, target_len: int) -> str:
    """Grow/shrink a between-chord segment to ``target_len`` by adding or
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


def _insert_into_lyric(lyric: List[str], lo: int, hi: int, count: int) -> None:
    """Insert ``count`` characters into the lyric char-list to keep alignment.

    The syllable at column ``lo`` (this chord) must not move; the syllable at
    column ``hi`` (the next chord) must move right by ``count``. A space is
    inserted at an existing word gap in ``(lo, hi]`` when available (widening
    the run), otherwise a '-' is inserted mid-word just before ``hi``.
    """
    length = len(lyric)
    hi_c = min(hi, length)

    insert_at = None
    for p in range(hi_c, lo, -1):
        if (p - 1 < length and lyric[p - 1] == ' ') or (p < length and lyric[p] == ' '):
            insert_at = p
            break

    if insert_at is not None:
        lyric[insert_at:insert_at] = [' '] * count
    else:
        pos = min(hi_c, length)
        fill = ['-'] + [' '] * (count - 1)
        lyric[pos:pos] = fill


class _Anchor:
    """An immovable token on a line (chord or directive) with its rewrite."""

    __slots__ = ('rs', 're', 'new_text', 'old_text')

    def __init__(self, rs: int, re_: int, new_text: str, old_text: str):
        self.rs = rs
        self.re = re_
        self.new_text = new_text
        self.old_text = old_text


def _transposable(chord) -> bool:
    return chord.is_valid and not chord.is_relative and not chord.is_rest


def _directive_key(value: str, semitones: int, notation: str) -> Optional[Key]:
    """The key a ``{key: value}`` directive names after the transpose, as
    :func:`transpose_key` writes it; None when transpose can't read it (it
    then leaves the directive as it is)."""
    moved = _moved_key(value.strip(), semitones, notation)
    if moved is None or moved[2]:
        return None
    return moved[0]


def _spelling_plan(lines_model, semitones: int, notation: str
                   ) -> Dict[int, Tuple[Optional[Key], Optional[str]]]:
    """For each chord transpose can move, by its start offset: the key it
    lands in (None: spell by the plain table) and the chord after it.

    A chord's key is the last ``{key: ...}`` before it, moved with the song.
    Chords before the first one are in the key detected from them, when the
    detection is sure (:func:`services.key_spelling.detected_target`).
    """
    events = []
    for model in lines_model:
        for chord in model.chords:
            if _transposable(chord):
                events.append((chord.start, None, chord))
        for directive in model.directives:
            if directive.type == DirectiveType.KEY and directive.is_valid and directive.key:
                key = _directive_key(directive.key, semitones, notation)
                if key is not None:
                    events.append((directive.start, key, None))
    events.sort(key=lambda e: e[0])

    chords = [chord for _, _, chord in events if chord is not None]
    next_of = {chord.start: after.chord for chord, after in zip(chords, chords[1:])}
    plan: Dict[int, Tuple[Optional[Key], Optional[str]]] = {}
    head = []          # the chords before the first {key}
    key = None
    for _, directive_key, chord in events:
        if directive_key is not None:
            key = directive_key
        elif key is None:
            head.append(chord)
        else:
            plan[chord.start] = (key, next_of.get(chord.start))
    if head:
        pairs = [(chord.chord, next_of.get(chord.start)) for chord in head]
        detected = detected_target(pairs, semitones)
        for chord, (_, next_chord) in zip(head, pairs):
            plan[chord.start] = (detected, next_chord)
    return plan


def transpose_text(
    text: str,
    semitones: int,
    notation: Union[Notation, str],
    region: Optional[Tuple[int, int]] = None,
) -> str:
    """Transpose every absolute chord and key directive in ``text``.

    Args:
        text: Full document text.
        semitones: Number of semitones to shift (positive = up).
        notation: Document notation (``Notation`` enum or 'american'/'european').
        region: Optional ``(start, end)`` character range; only tokens whose
            span intersects it are transposed. ``None`` = whole document.

    Returns:
        The transposed text.
    """
    if semitones == 0:
        return text

    notation = _notation_str(notation)
    parser = SongParserService()
    lines_model = parser.detect_chords_in_text(text, notation)
    # Keys come from the whole song even for a region: a selection is still
    # in the key of the song around it.
    plan = _spelling_plan(lines_model, semitones, notation)

    text_lines = text.split('\n')
    n = len(text)
    if region is None:
        r_start, r_end = 0, n
    else:
        r_start, r_end = region
        r_start, r_end = max(0, min(r_start, r_end)), min(n, max(r_start, r_end))

    # Absolute start offset of each physical line.
    line_offsets = []
    off = 0
    for ln in text_lines:
        line_offsets.append(off)
        off += len(ln) + 1

    out_lines = list(text_lines)

    def _intersects(start: int, end: int) -> bool:
        return start < r_end and end > r_start

    def _is_lyric_line(idx: int) -> bool:
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

    for i, model in enumerate(lines_model):
        base = line_offsets[i]
        raw = text_lines[i]

        # Build anchors (all chords + all directives on this line) so that
        # non-transposed tokens stay put and inter-chord gaps stay pure.
        anchors: List[_Anchor] = []
        for chord in model.chords:
            rs, re_ = chord.start - base, chord.end - base
            old = raw[rs:re_]
            if _transposable(chord) and _intersects(chord.start, chord.end):
                trailing = old[len(chord.chord):]
                key, next_chord = plan.get(chord.start, (None, None))
                new = transpose_chord_token(chord.chord, semitones, notation,
                                            key, next_chord) + trailing
            else:
                new = old
            anchors.append(_Anchor(rs, re_, new, old))

        for directive in model.directives:
            rs, re_ = directive.start - base, directive.end - base
            old = raw[rs:re_]
            if directive.type == DirectiveType.KEY and _intersects(directive.start, directive.end):
                new = _transpose_key_directive(old, semitones, notation)
            else:
                new = old
            anchors.append(_Anchor(rs, re_, new, old))

        if not anchors or all(a.new_text == a.old_text for a in anchors):
            continue

        anchors.sort(key=lambda a: a.rs)

        lyric_idx = None
        if model.type == LineType.CHORD and _is_lyric_line(i + 1):
            lyric_idx = i + 1

        lyric = list(out_lines[lyric_idx]) if lyric_idx is not None else None
        shift = 0
        out: List[str] = []
        cursor = 0

        for k, a in enumerate(anchors):
            out.append(raw[cursor:a.rs])
            out.append(a.new_text)
            cursor = a.re
            delta = len(a.new_text) - (a.re - a.rs)

            if k < len(anchors) - 1:
                next_rs = anchors[k + 1].rs
                seg = raw[a.re:next_rs]
                seg_len = len(seg)

                if delta <= 0:
                    new_seg_len, new_ins = seg_len - delta, 0
                elif seg_len - delta >= 1:
                    new_seg_len, new_ins = seg_len - delta, 0
                else:
                    new_seg_len = 1
                    new_ins = delta - seg_len + 1

                out.append(_resize_spaces(seg, new_seg_len))
                cursor = next_rs

                if new_ins > 0 and lyric is not None:
                    _insert_into_lyric(lyric, a.rs + shift, next_rs + shift, new_ins)
                    shift += new_ins

        out.append(raw[cursor:])
        out_lines[i] = ''.join(out)
        if lyric is not None:
            out_lines[lyric_idx] = ''.join(lyric)

    return '\n'.join(out_lines)
