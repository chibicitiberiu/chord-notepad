"""Export PDF on the desktop: pdf_export.py paints the session's layout.

QtPdf isn't installed here and a PDF's text is glyph ids, so the file is
checked by its header, its page objects and its font; the layout itself is
tested in tests/test_print_layout.py.
"""

import html
import re
import shutil
import subprocess

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QFontMetricsF, QPdfWriter

from chordnotepad.session import print_layout
from chordnotepad.session.bridge import to_json_value
from chordnotepad_desktop import pdf_export

PAGE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def layout_of(text, page="a4", title="Song"):
    return to_json_value(print_layout.layout_song(text, "american", title, page))


def page_count(pdf: bytes) -> int:
    return len(PAGE.findall(pdf))


def test_one_page_object_per_page(qapp):
    layout = layout_of("\n".join(f"line {i}" for i in range(120)))
    assert layout["page_count"] == 3
    pdf = pdf_export.paint_pdf(layout)
    assert pdf.startswith(b"%PDF")
    assert page_count(pdf) == 3
    # The bundled monospace, embedded.
    assert b"NotoSansMono" in pdf


def test_an_empty_song_is_one_page(qapp):
    pdf = pdf_export.paint_pdf(layout_of(""))
    assert pdf.startswith(b"%PDF") and page_count(pdf) == 1


@pytest.mark.parametrize("page, size", [("a4", b"595"), ("letter", b"612")])
def test_the_page_size(qapp, page, size):
    pdf = pdf_export.paint_pdf(layout_of("C G", page))
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", pdf)
    assert box is not None and box.group(1).startswith(size)


def test_the_font_advances_as_the_layout_counts(qapp):
    buffer = QBuffer(QByteArray())
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QPdfWriter(buffer)
    writer.setResolution(pdf_export.RESOLUTION)
    for size in (print_layout.MAX_FONT_SIZE, print_layout.MIN_FONT_SIZE, 8.5, 9.3):
        metrics = QFontMetricsF(pdf_export._font(size), writer)
        em = metrics.horizontalAdvance("M" * 100) / 100 / (size * pdf_export.RESOLUTION / 72)
        assert em == pytest.approx(print_layout.ADVANCE_EM, abs=1e-4)


def test_write_pdf_writes_the_file_and_answers_empty(qapp, tmp_path):
    out = tmp_path / "song.pdf"
    out.write_bytes(b"old content that is replaced")
    assert pdf_export.write_pdf(str(out), layout_of("C G\nla la")) == ""
    assert out.read_bytes().startswith(b"%PDF")


def test_write_pdf_answers_why_it_failed(qapp, tmp_path):
    answer = pdf_export.write_pdf(str(tmp_path), layout_of("C G"))     # a folder
    assert answer.startswith("Failed to write file: ")


def test_a_request_is_answered_with_its_id(qapp, tmp_path):
    out = tmp_path / "x.pdf"
    request = {"request_id": 7, "ref": {"id": str(out), "display_name": "x.pdf",
                                        "location": str(out)},
               "layout": layout_of("C")}
    answers = []
    pdf_export.answer_paint_request(request, lambda request_id, answer: answers.append(
        (request_id, answer)))
    assert answers == [(7, "")]
    assert out.read_bytes().startswith(b"%PDF")


def test_a_request_that_can_not_be_painted_is_still_answered(qapp, tmp_path, caplog):
    request = {"request_id": 8, "ref": {"id": str(tmp_path / "x.pdf"), "display_name": "x.pdf",
                                        "location": "x.pdf"},
               "layout": {"title": "broken"}}
    answers = []
    pdf_export.answer_paint_request(request, lambda request_id, answer: answers.append(
        (request_id, answer)))
    [(request_id, answer)] = answers
    assert request_id == 8 and answer      # the reason, never "" and never no answer
    assert "PDF" in caplog.text


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler's pdftotext")
@pytest.mark.parametrize("page", ["a4", "letter"])
def test_every_word_starts_at_its_column_in_the_pdf(qapp, tmp_path, page):
    """pdftotext -bbox gives each word's x: margin + column × 0.6 × size."""
    song = ("{key: A} {time: 4/4} {bpm: 200}\n"
            "F#m   Bb    C/E     Dsus4\n"
            "Twinkle, twinkle, little star\n"
            "\tG\tD\n"
            "// a comment with {key: B} in it\n"
            + " ".join(["Am7"] * 30) + "\n" + "la " * 40)
    layout = print_layout.layout_song(song, "american", "Song", page)
    out = tmp_path / "song.pdf"
    assert pdf_export.write_pdf(str(out), to_json_value(layout)) == ""
    bbox = tmp_path / "song.html"
    subprocess.run(["pdftotext", "-bbox", str(out), str(bbox)], check=True)
    words = re.findall(r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>',
                       bbox.read_text(encoding="utf-8"))
    advance = print_layout.ADVANCE_EM * layout.font_size
    expected = []
    for page_ in layout.pages:
        for line in page_.lines:
            for run in line.runs:
                column = (run.x - round(print_layout.MARGIN, 2)) / advance
                assert column == pytest.approx(round(column), abs=1e-6)
                expected.append((run.x, run.text))
    found = [(float(x), html.unescape(w)) for x, w in words]
    # The header and the footer are words too: keep the body's, in order.
    body = [w for w in found if w[1] not in ("Song", "1", "/")]
    assert [w for _, w in body] == [w for _, w in expected]
    for (x, word), (want, _) in zip(body, expected):
        assert x == pytest.approx(want, abs=0.01), word
