"""Export PDF's pages: the song text as it is, laid out for a front end to paint.

The export is barebones on purpose: the text verbatim in a monospace font,
with each ``{directive}`` replaced by a dimmer plain-text label, a header
with the song's name and "1 / 3" page numbers. Both front ends (the Qt
desktop's ``pdf_export.py``, Android's ``PdfExporter.kt``) paint
:class:`PdfLayout` and nothing else, so the pages are the same on both.

**Lines** (:func:`printable_lines`):

* The directives are parsed once over the whole text
  (``SongParserService.detect_chords_in_text``, which also says which lines
  are chord lines), so a ``{loop}`` is checked against the labels above it
  as the editor checks it. Directives in comments and on ``.`` text lines
  aren't directives there either: those lines print as written.
* Directives with only whitespace between them become one dim run, their
  labels joined with " | " (``{key: A} {time: 4/4} {bpm: 200}`` is
  ``Key: A | Time: 4/4 | BPM: 200``). :func:`directive_label` has the labels.
* **Columns:** a label shorter than the directives it replaces is padded with
  spaces to their width, so the chords after it keep their columns over the
  lyrics. A longer one takes its overflow from the run of spaces after it,
  keeping at least one, and pushes the rest of its line right only for what
  those spaces can't give.
* Tabs are expanded to :data:`TAB_SIZE` columns (a known limit: the editor
  sets no tab stops of its own). Every other character counts one column
  (Noto Sans Mono has no CJK or Hebrew to be wider).

**Pages** (:func:`paginate`):

* A4 or Letter (:data:`PAGE_SIZES`), with :data:`MARGIN` all round.
* The font shrinks from :data:`MAX_FONT_SIZE` until the longest chord line
  fits the width, down to :data:`MIN_FONT_SIZE`; a chord line counts up to
  the end of its last chord or directive (:attr:`PrintLine.measure`), so a
  comment after the chords wraps rather than shrinking the song. Any longer
  line wraps at a space after its indent (or mid-word, for a word longer
  than the width), its continuation indented by its own indent plus two
  spaces. A chord line too long even at the smallest size is cut at the same
  column as its lyric line, and the rows interleave: chords, lyric, chords,
  lyric.
* A page never ends on a chord line whose next line is its lyric line, nor
  on a comment-only or directive-only line (a heading) with a line under
  it: those move to the next page with it (at most half a page of them).
  Blank lines at the top of a page are dropped.
* Every position is absolute, in PDF points from the top-left corner of the
  page; ``y`` is a baseline. Every word is a run of its own at its column,
  so a glyph the painter's font lacks (Android's monospace has no ♯ or ♭)
  can't move the words after it. A monospace character is
  :data:`ADVANCE_EM` wide, and a line :data:`LINE_HEIGHT_EM` high (Noto Sans
  Mono's ascent plus descent, :data:`ASCENT_EM` + :data:`DESCENT_EM`).

Pure: no state, no I/O.
"""

import math
import re
from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Sequence, Tuple

from chordnotepad.models.directive import Directive, DirectiveType
from chordnotepad.services.song_parser_service import SongParserService

#: Page sizes in PDF points (1/72 in), portrait: ``export_pdf``'s ``page``.
PAGE_SIZES = {
    "a4": (595.276, 841.89),
    "letter": (612.0, 792.0),
}
#: The territories (ISO 3166 codes) that use Letter paper (CLDR's
#: ``paperSize`` data); every other one uses A4.
LETTER_TERRITORIES = frozenset({
    "BZ", "CA", "CL", "CO", "CR", "GT", "MX", "NI", "PA", "PH", "PR", "SV", "US", "VE",
})

#: 15 mm on every side, in points.
MARGIN = 15 * 72 / 25.4
#: The body's largest and smallest font size, in points.
MAX_FONT_SIZE = 10.0
MIN_FONT_SIZE = 7.0
#: The header's and footer's font size, in points.
SMALL_FONT_SIZE = 8.0
#: Space between the header and the body, and the body and the footer, in points.
HEADER_GAP = 12.0

#: Noto Sans Mono's metrics, in em (``hhea``: 1069 and 293 of 1000 units;
#: every glyph advances 600).
ADVANCE_EM = 0.6
ASCENT_EM = 1.069
DESCENT_EM = 0.293
LINE_HEIGHT_EM = ASCENT_EM + DESCENT_EM

#: A tab goes to the next multiple of this many columns.
TAB_SIZE = 8
#: A wrapped line's continuation starts with this.
WRAP_INDENT = "  "
#: Joins the labels of directives next to each other.
LABEL_JOIN = " | "
#: Ends a title too long for the header.
ELLIPSIS = "…"


# -- the layout (crosses the bridge in PaintPdfRequest) ------------------------------


@dataclass(frozen=True)
class PdfRun:
    """Text in one colour, drawn from ``x`` on its line's baseline.

    Attributes:
        x: Where the text starts, in points from the page's left edge.
        text: The text (no tabs or newlines).
        dim: A directive's label (the dimmer colour); else the song's text.
    """

    x: float
    text: str
    dim: bool


@dataclass(frozen=True)
class PdfLine:
    """One printed line.

    Attributes:
        y: Its baseline, in points from the page's top edge.
        runs: Its words, left to right, one run each (no spaces).
    """

    y: float
    runs: Tuple[PdfRun, ...]


@dataclass(frozen=True)
class PdfPage:
    """One page's body and its page number.

    Attributes:
        lines: The body's lines, top to bottom (blank lines are left out:
            their space is between the ``y`` of the others).
        footer: The page number, ``1 / 3``.
        footer_x: Where the footer starts (it is centred), in points.
    """

    lines: Tuple[PdfLine, ...]
    footer: str
    footer_x: float


@dataclass(frozen=True)
class PdfLayout:
    """The pages of a PDF export, every position absolute (see the module).

    Attributes:
        page_width: The page's width, in points.
        page_height: The page's height, in points.
        font_size: The body's monospace size, in points.
        line_height: The distance between two body baselines, in points.
        small_font_size: The header's and footer's size, in points.
        title: The header: the song's name (shortened with "…" to fit).
        title_x: Where the header starts, in points.
        title_y: The header's baseline on every page, in points.
        footer_y: The footer's baseline on every page, in points.
        page_count: How many pages (``len(pages)``, at least 1).
        pages: The pages.
    """

    page_width: float
    page_height: float
    font_size: float
    line_height: float
    small_font_size: float
    title: str
    title_x: float
    title_y: float
    footer_y: float
    page_count: int
    pages: Tuple[PdfPage, ...]


# -- the lines ----------------------------------------------------------------------


class PrintLine(NamedTuple):
    """A line of the song as it prints: ``text`` with a ``dim`` flag per character.

    ``chord`` says whether it is a chord line (the editor's detection).
    ``measure`` is how many columns must fit across the page: a chord line's
    up to the end of its last chord or directive, any other line's all of it.
    """

    text: str
    dim: Tuple[bool, ...]
    chord: bool
    measure: int = 0

    def runs(self) -> List[Tuple[int, str, bool]]:
        """``(column, text, dim)`` for each stretch of one colour, spaces included."""
        out: List[Tuple[int, str, bool]] = []
        start = 0
        for i in range(1, len(self.text) + 1):
            if i == len(self.text) or self.dim[i] != self.dim[start]:
                out.append((start, self.text[start:i], self.dim[start]))
                start = i
        return out


def page_for_territory(code: Optional[str]) -> str:
    """``letter`` for a territory that uses Letter paper (``US``), else ``a4``."""
    return "letter" if (code or "").upper() in LETTER_TERRITORIES else "a4"


def _value(text: str, directive: Directive) -> str:
    """What a directive says after its colon, as written."""
    return text[directive.start + 1:directive.end - 1].partition(":")[2].strip()


def directive_label(text: str, directive: Directive) -> str:
    """The plain text a directive prints as.

    ``Key: A`` (the key as written, European too), ``Time: 4/4``,
    ``BPM: 200`` (``{tempo}`` too; a change as written: ``BPM: +10``),
    ``Capo: 3``, a label's name (``Chorus``), ``Repeat verse ×3`` or
    ``Repeat from the start ×2``. An invalid or unknown directive prints the
    text inside its braces.
    """
    if not directive.is_valid or directive.type == DirectiveType.UNKNOWN:
        return text[directive.start + 1:directive.end - 1].strip()
    kind = directive.type
    if kind == DirectiveType.KEY:
        return f"Key: {_value(text, directive)}"
    if kind == DirectiveType.TIME_SIGNATURE:
        return f"Time: {directive.beats}/{directive.unit}"
    if kind == DirectiveType.BPM:
        return f"BPM: {_value(text, directive)}"
    if kind == DirectiveType.CAPO:
        return f"Capo: {directive.capo}"
    if kind == DirectiveType.LABEL:
        return directive.label or ""
    if kind == DirectiveType.LOOP:
        if directive.label == "@start":
            return f"Repeat from the start ×{directive.loop_count}"
        return f"Repeat {directive.label} ×{directive.loop_count}"
    return text[directive.start + 1:directive.end - 1].strip()


def _columns(raw: str) -> List[int]:
    """The editor's column of each character of ``raw`` (tabs expanded), and
    of its end."""
    cols = [0]
    for ch in raw:
        col = cols[-1]
        cols.append(col + (TAB_SIZE - col % TAB_SIZE if ch == "\t" else 1))
    return cols


def _groups(text: str, line_start: int,
            directives: Sequence[Directive]) -> List[Tuple[int, int, List[Directive]]]:
    """A line's directives as ``(start, end, directives)``, offsets in the
    line; neighbours with only whitespace between them are one group."""
    groups: List[Tuple[int, int, List[Directive]]] = []
    for d in sorted(directives, key=lambda d: d.start):
        start, end = d.start - line_start, d.end - line_start
        if groups and not text[line_start + groups[-1][1]:d.start].strip():
            last = groups[-1]
            groups[-1] = (last[0], end, last[2] + [d])
        else:
            groups.append((start, end, [d]))
    return groups


def printable_lines(text: str, notation: str = "american") -> List[PrintLine]:
    """The song's lines as they print (see the module).

    Args:
        text: The song.
        notation: ``american`` or ``european``, for which lines are chord lines.
    """
    parsed = SongParserService().detect_chords_in_text(text, notation)
    out: List[PrintLine] = []
    line_start = 0
    for raw, line in zip(text.split("\n"), parsed):
        cols = _columns(raw)
        expanded = "".join(" " * (cols[i + 1] - cols[i]) if ch == "\t" else ch
                           for i, ch in enumerate(raw))
        chars: List[str] = []
        dim: List[bool] = []
        # Each offset of raw -> its column in the printed line.
        where = [0] * (len(raw) + 1)
        debt = 0        # columns a longer label still wants from the spaces after it

        def plain(a: int, b: int) -> None:
            nonlocal debt
            segment = expanded[cols[a]:cols[b]]
            lead = len(segment) - len(segment.lstrip(" "))
            removed = min(debt, lead - 1) if 0 < lead < len(segment) else 0
            debt = 0
            base = len(chars)
            for i in range(a, b + 1):
                where[i] = base + max(0, cols[i] - cols[a] - removed)
            chars.extend(segment[removed:])
            dim.extend([False] * (len(segment) - removed))

        pos = 0
        items = line.items
        directives = [item for item in items if isinstance(item, Directive)]
        for start, end, group in _groups(text, line_start, directives):
            plain(pos, start)
            width = cols[end] - cols[start]
            label = LABEL_JOIN.join(directive_label(text, d) for d in group)
            chars.extend(label)
            dim.extend([True] * len(label))
            padding = width - len(label)
            if padding > 0:
                chars.extend(" " * padding)
                dim.extend([False] * padding)
            debt = max(0, -padding)
            where[end] = len(chars)
            pos = end
        plain(pos, len(raw))
        printed = "".join(chars)
        if line.is_chord_line() and items:
            measure = max(where[item.end - line_start] for item in items)
        else:
            measure = len(printed.rstrip())
        out.append(PrintLine(printed, tuple(dim), line.is_chord_line(), measure))
        line_start += len(raw) + 1
    return out


# -- the pages ----------------------------------------------------------------------


class _Row(NamedTuple):
    """One printed row: a line, or a part of a wrapped one."""

    text: str
    dim: Tuple[bool, ...]
    keep_with_next: bool


def _fitting_size(lines: Sequence[PrintLine], width: float) -> float:
    """The largest body size (0.1 pt steps) the longest chord line fits at,
    within :data:`MIN_FONT_SIZE`..:data:`MAX_FONT_SIZE`. A chord line counts
    to the end of its last chord or directive (a comment after it wraps)."""
    longest = max((line.measure for line in lines if line.chord), default=0)
    if longest * ADVANCE_EM * MAX_FONT_SIZE <= width:
        return MAX_FONT_SIZE
    size = math.floor(width / (ADVANCE_EM * longest) * 10) / 10
    return max(MIN_FONT_SIZE, size)


Piece = Tuple[str, Tuple[bool, ...]]


def _leading(text: str) -> int:
    return len(text) - len(text.lstrip(" "))


def _wrap(text: str, dim: Tuple[bool, ...], columns: int) -> List[Piece]:
    """``text`` cut into rows of at most ``columns``, at a space when there
    is one after the line's indent; the rows after the first keep the indent
    plus :data:`WRAP_INDENT`."""
    lead = min(_leading(text), max(0, columns - 1))
    cont = " " * lead + WRAP_INDENT if lead + len(WRAP_INDENT) < columns // 2 else WRAP_INDENT
    rows: List[Piece] = []
    indent, floor = "", lead
    while True:
        room = max(1, columns - len(indent))
        if len(text) <= room:
            rows.append((indent + text, (False,) * len(indent) + dim))
            return rows
        cut = text.rfind(" ", floor + 1, room + 1)
        if cut <= floor:
            cut = room
        head = text[:cut].rstrip()
        rows.append((indent + head, (False,) * len(indent) + dim[:len(head)]))
        rest = text[cut:]
        skip = _leading(rest)
        text, dim = rest[skip:], dim[cut + skip:]
        indent, floor = cont, 0
        if not text:
            return rows


def _pair_cut(chords: str, lyric: str, room: int) -> int:
    """Where to cut a chord line and its lyric line together: a column at most
    ``room`` with a space in both (not before half of ``room``), else one with
    a space in the chord line, else ``room``."""
    def space(text: str, column: int) -> bool:
        return column >= len(text) or text[column] == " "

    for column in range(room, max(1, room // 2) - 1, -1):
        if space(chords, column) and space(lyric, column):
            return column
    for column in range(room, 0, -1):
        if space(chords, column):
            return column
    return room


def _interleave(chords: Piece, lyric: Piece, columns: int) -> List[_Row]:
    """A chord line too long for the page and its lyric line, cut at the same
    columns: chords, lyric, chords, lyric... (each continuation indented by
    :data:`WRAP_INDENT`, both alike, so the chords stay over their words)."""
    (ct, cd), (lt, ld) = chords, lyric
    rows: List[_Row] = []
    indent = ""
    while True:
        room = max(1, columns - len(indent))
        pad = (False,) * len(indent)
        done = len(ct) <= room and len(lt) <= room
        cut = room if done else _pair_cut(ct, lt, room)
        c_head, l_head = ct[:cut].rstrip(), lt[:cut].rstrip()
        if c_head.strip():
            rows.append(_Row(indent + c_head, pad + cd[:len(c_head)], True))
        if l_head.strip():
            rows.append(_Row(indent + l_head, pad + ld[:len(l_head)], False))
        if done:
            return rows
        ct, cd, lt, ld = ct[cut:], cd[cut:], lt[cut:], ld[cut:]
        if not ct.strip():
            ct, cd = "", ()
        if not lt.strip():
            lt, ld = "", ()
        if not ct and not lt:
            return rows
        # Drop the spaces both rests start with, the same number for both.
        skip = min(_leading(rest) for rest in (ct, lt) if rest)
        ct, cd, lt, ld = ct[skip:], cd[skip:], lt[skip:], ld[skip:]
        indent = WRAP_INDENT


def _heading(text: str, line: PrintLine) -> bool:
    """A comment-only line, or one of directives only (all dim)."""
    stripped = text.strip()
    if not stripped or line.chord:
        return False
    if stripped.startswith("//"):
        return True
    return all(d for ch, d in zip(text, line.dim) if ch != " ")


def _rows(lines: Sequence[PrintLine], columns: int) -> List[_Row]:
    """Every line as rows, trailing spaces and blank lines at the end dropped."""
    trimmed = [(line.text.rstrip(), line) for line in lines]
    while trimmed and not trimmed[-1][0]:
        trimmed.pop()
    rows: List[_Row] = []
    i = 0
    while i < len(trimmed):
        text, line = trimmed[i]
        dim = line.dim[:len(text)]
        following = trimmed[i + 1] if i + 1 < len(trimmed) else None
        has_next = following is not None and bool(following[0].strip())
        # A chord line stays on the page of the lyric line under it.
        lyric_next = line.chord and has_next and not following[1].chord
        if lyric_next and len(text) > columns:
            lyric_text, lyric_line = following
            rows.extend(_interleave((text, dim), (lyric_text, lyric_line.dim[:len(lyric_text)]),
                                    columns))
            i += 2
            continue
        keep = lyric_next or (has_next and _heading(text, line))
        for row_text, row_dim in _wrap(text, dim, columns) if text else [("", ())]:
            rows.append(_Row(row_text, row_dim, keep))
        i += 1
    return rows


def _pages(rows: Sequence[_Row], per_page: int) -> List[List[_Row]]:
    """``rows`` in pages of ``per_page``: rows kept with the next move down
    with it (at most half a page of them), and a page starts without blank rows."""
    pages: List[List[_Row]] = [[]]
    for row in rows:
        page = pages[-1]
        if len(page) >= per_page:
            moved: List[_Row] = []
            while len(page) > 1 and page[-1].keep_with_next and len(moved) < per_page // 2:
                moved.insert(0, page.pop())
            page = moved
            pages.append(page)
        if not page and len(pages) > 1 and not row.text.strip():
            continue
        page.append(row)
    return pages


def _shorten(text: str, columns: int) -> str:
    """``text`` cut to ``columns`` characters with "…" when it is longer."""
    if len(text) <= columns:
        return text
    return text[:max(0, columns - 1)].rstrip() + ELLIPSIS


def _round(value: float) -> float:
    return round(value, 2)


_WORD = re.compile(r"\S+")


def _line_runs(row: _Row, x0: float, advance: float) -> Tuple[PdfRun, ...]:
    """A row's words, one run each at its own column (so a glyph drawn wider
    or narrower, from a font that lacks it, can't move the words after it)."""
    runs = []
    for column, text, dim in PrintLine(row.text, row.dim, False).runs():
        for word in _WORD.finditer(text):
            runs.append(PdfRun(_round(x0 + (column + word.start()) * advance), word.group(), dim))
    return tuple(runs)


def paginate(lines: Sequence[PrintLine], title: str, page: str) -> PdfLayout:
    """Lay ``lines`` out on pages (see the module).

    Args:
        lines: :func:`printable_lines`' output.
        title: The header, the song's name.
        page: A key of :data:`PAGE_SIZES` (``a4`` or ``letter``).

    Raises:
        ValueError: For another page size.
    """
    if page not in PAGE_SIZES:
        raise ValueError(f"Unknown page size {page!r}: expected one of {sorted(PAGE_SIZES)}")
    width, height = PAGE_SIZES[page]
    text_width = width - 2 * MARGIN
    size = _fitting_size(lines, text_width)
    advance = ADVANCE_EM * size
    columns = max(1, int(text_width / advance + 1e-9))
    line_height = LINE_HEIGHT_EM * size

    small = SMALL_FONT_SIZE
    small_line = LINE_HEIGHT_EM * small
    title_y = MARGIN + ASCENT_EM * small
    footer_y = height - MARGIN - DESCENT_EM * small
    body_top = MARGIN + small_line + HEADER_GAP
    body_bottom = height - MARGIN - small_line - HEADER_GAP
    per_page = max(1, int((body_bottom - body_top) / line_height + 1e-9))

    pages = _pages(_rows(lines, columns), per_page)
    count = len(pages)
    out = []
    for number, rows in enumerate(pages, start=1):
        body = []
        for k, row in enumerate(rows):
            runs = _line_runs(row, MARGIN, advance)
            if runs:
                body.append(PdfLine(_round(body_top + k * line_height + ASCENT_EM * size), runs))
        footer = f"{number} / {count}"
        out.append(PdfPage(tuple(body), footer,
                           _round((width - len(footer) * ADVANCE_EM * small) / 2)))
    title_columns = int(text_width / (ADVANCE_EM * small) + 1e-9)
    return PdfLayout(
        page_width=_round(width), page_height=_round(height), font_size=size,
        line_height=_round(line_height), small_font_size=small,
        title=_shorten(title, title_columns), title_x=_round(MARGIN), title_y=_round(title_y),
        footer_y=_round(footer_y), page_count=count, pages=tuple(out))


def layout_song(text: str, notation: str, title: str, page: str) -> PdfLayout:
    """:func:`paginate` over :func:`printable_lines`: a song's PDF pages."""
    return paginate(printable_lines(text, notation), title, page)
