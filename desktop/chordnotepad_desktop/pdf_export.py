"""Export PDF on the desktop: paint the session's layout and write the file.

The session lays the pages out (``chordnotepad.session.print_layout``) and
asks for them with a ``PaintPdfRequest``; :func:`paint_pdf` paints that
layout as it is, every position absolute, and :func:`answer_paint_request`
writes the file and answers. Painting is quick (a few milliseconds a
page), so it runs on the GUI thread in the request slot.

* :class:`QPdfWriter` into memory, with the page-layout margins at 0 (the
  layout's positions include the 15 mm margins). The bytes are then written
  straight into the picked file, as ``FileService.save_bytes`` writes a MIDI
  export (no temp file and rename, which the Flatpak's document portal
  wouldn't allow), so a failure has the system's reason.
* The bundled Noto Sans Mono (``editor_font``), whose advance is the 0.6 em
  the layout counts with; unhinted and without kerning, so the columns stay.
* The text near-black, the directive labels :data:`DIM_COLOUR`, the header
  (the song's name) and the footer (``1 / 3``) small and grey.
"""

import logging
from typing import Any, Callable, Mapping, Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QPointF, QSizeF
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter

from chordnotepad_desktop.editor_font import editor_monospace

logger = logging.getLogger(__name__)

#: The request this module answers.
PAINT_PDF_REQUEST = "PaintPdfRequest"

#: The song's text.
TEXT_COLOUR = "#1f2328"
#: A directive's label.
DIM_COLOUR = "#7a7f8a"
#: The header and the footer.
HEADER_COLOUR = "#7a7f8a"

#: QPdfWriter's resolution; positions in points are scaled to it. Qt rounds
#: a font to whole device pixels, and at 7200 dpi every size the layout
#: picks (0.1 pt steps) is a whole number of them, so the advance stays
#: exactly 0.6 em (at the default 1200 dpi a column drifted up to 0.3%).
RESOLUTION = 7200


def _font(size: float) -> QFont:
    font = QFont(editor_monospace())
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(size)
    font.setKerning(False)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def paint_pdf(layout: Mapping[str, Any]) -> bytes:
    """The PDF of ``layout`` (a ``PdfLayout`` as the bridge sends it: plain JSON data).

    Raises:
        RuntimeError: If Qt couldn't start painting.
    """
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QPdfWriter(buffer)
    writer.setResolution(RESOLUTION)
    writer.setCreator("Chord Notepad")
    writer.setTitle(str(layout["title"]))
    size = QPageSize(QSizeF(float(layout["page_width"]), float(layout["page_height"])),
                     QPageSize.Unit.Point, "", QPageSize.SizeMatchPolicy.FuzzyMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Orientation.Portrait,
                                     QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point))
    scale = RESOLUTION / 72.0

    def at(x: float, y: float) -> QPointF:
        return QPointF(x * scale, y * scale)

    body = _font(float(layout["font_size"]))
    small = _font(float(layout["small_font_size"]))
    painter = QPainter()
    if not painter.begin(writer):
        buffer.close()
        raise RuntimeError("Qt couldn't start the PDF")
    try:
        for number, page in enumerate(layout["pages"]):
            if number:
                writer.newPage()
            painter.setFont(small)
            painter.setPen(QColor(HEADER_COLOUR))
            painter.drawText(at(layout["title_x"], layout["title_y"]), str(layout["title"]))
            painter.drawText(at(page["footer_x"], layout["footer_y"]), str(page["footer"]))
            painter.setFont(body)
            for line in page["lines"]:
                for run in line["runs"]:
                    painter.setPen(QColor(DIM_COLOUR if run["dim"] else TEXT_COLOUR))
                    painter.drawText(at(run["x"], line["y"]), str(run["text"]))
    finally:
        painter.end()
        buffer.close()
    return bytes(data.data())


def write_pdf(path: str, layout: Mapping[str, Any]) -> str:
    """Paint ``layout`` into the file at ``path``: ``""`` when it was written,
    else why not (``PaintPdfRequest``'s answer)."""
    try:
        pdf = paint_pdf(layout)
    except RuntimeError as e:
        logger.error("Painting the PDF for %s failed: %s", path, e)
        return str(e)
    try:
        logger.info("Writing file: %s", path)
        with open(path, "wb") as f:
            f.write(pdf)
    except PermissionError:
        logger.error("Permission denied: %s", path)
        return "Permission denied"
    except OSError as e:
        logger.error("Error writing file: %s", e, exc_info=True)
        return f"Failed to write file: {e.strerror or e}"
    return ""


def answer_paint_request(data: Mapping[str, Any],
                         respond: Callable[[int, Optional[str]], None]) -> None:
    """Paint and write a ``PaintPdfRequest`` (``data``, as the bridge sends
    it) and give ``respond(request_id, answer)`` the answer. Always answers:
    whatever goes wrong is logged and answered with its reason, so the
    session's flow never waits."""
    request_id = int(data["request_id"])
    try:
        answer = write_pdf(str(data["ref"]["id"]), data["layout"])
    except Exception as e:
        logger.exception("Exporting the PDF failed")
        answer = f"{type(e).__name__}: {e}"
    respond(request_id, answer)
