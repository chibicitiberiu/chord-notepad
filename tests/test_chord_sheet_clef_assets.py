"""Tests for the Pillow-free clef asset API shared with Android.

``chord_sheet.clef_assets`` holds the embedded PNGs, the placement math and the
image-key grammar; ``ui.chord_sheet.clef_images`` (Pillow) only decodes. These
check the shared half and the Android export tool built on it.
"""

import importlib.util
import json
import struct
from pathlib import Path

import pytest

from chord_sheet import clef_assets as ca

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_EXPORT_TOOL = Path(__file__).parent.parent / "android" / "tools" / "export_clef_glyphs.py"


def _png_size(data: bytes):
    """(width, height) from a PNG's IHDR chunk."""
    assert data[:8] == _PNG_SIGNATURE
    return struct.unpack(">II", data[16:24])


def test_base_assets_are_the_seven_glyphs():
    assert ca.BASE_ASSETS == (
        "clef_treble", "clef_bass", "clef_treble_8vb", "glyph_notehead_whole",
        "glyph_accidental_sharp", "glyph_accidental_flat", "glyph_accidental_natural",
    )


# Bravura's SMuFL bounding boxes (bravura_metadata.json, staff spaces from the
# glyph origin, which sits on the G line for both treble clefs): gClef spans
# 4.392 above to 2.632 below; gClef8vb has the same top and its 8 reaches
# 3.512 below.
@pytest.mark.parametrize("kind,above,below", [
    ("treble", 4.392, 2.632),
    ("treble_8vb", 4.392, 3.512),
])
def test_treble_clefs_register_on_the_g_line(kind, above, below):
    base = ca._CLEF_BASE[kind]
    assert base.baseline_y / base.px_per_staff_space == pytest.approx(above, abs=0.01)
    assert base.height / base.px_per_staff_space == pytest.approx(above + below, abs=0.02)


def test_octave_lower_treble_is_drawn_at_the_treble_size():
    # Same staff space -> the same clef body height above the G line, so the
    # 8vb clef is the plain treble with the 8 added below.
    s = 10.0
    treble = ca.clef_placement("treble", s)
    lower = ca.clef_placement("treble_8vb", s)
    assert lower.baseline_y == pytest.approx(treble.baseline_y, abs=0.5)
    assert lower.height - lower.baseline_y == pytest.approx(3.512 * s, abs=0.6)


def test_base_glyph_pngs_are_pngs_of_the_recorded_size():
    pngs = ca.base_glyph_pngs()
    assert list(pngs) == list(ca.BASE_ASSETS)
    for asset, data in pngs.items():
        assert _png_size(data) == ca.base_size(asset)


@pytest.mark.parametrize("kind", ["treble", "bass", "treble_8vb"])
def test_clef_key_parses_back_to_its_placement(kind):
    placement = ca.clef_placement(kind, 9.0)
    parsed = ca.parse_image_key(placement.key)
    assert parsed == ca.ImageKey(f"clef_{kind}", placement.height, None)
    assert ca.scaled_width(parsed.asset, parsed.height) == placement.width


def test_tinted_glyph_key_parses_with_its_color():
    placement = ca.glyph_placement("accidental_flat", 11.0, "#A04848")
    parsed = ca.parse_image_key(placement.key)
    assert parsed == ca.ImageKey("glyph_accidental_flat", placement.height, "a04848")
    assert ca.scaled_width(parsed.asset, parsed.height) == placement.width


@pytest.mark.parametrize("bad", [
    "", "clef_treble", "clef_treble:", "clef_foo:10", "clef_treble:abc",
    "clef_treble:0", "clef_treble:10:3a5a8a", "nope:10", "glyph_bogus:64",
    "glyph_notehead_whole:64:xyz", "glyph_notehead_whole:64:3a5a8a:9",
])
def test_malformed_keys_do_not_parse(bad):
    assert ca.parse_image_key(bad) is None


def test_unknown_asset_raises():
    with pytest.raises(KeyError):
        ca.base_png("glyph_bogus")


def test_export_tool_writes_pngs_and_index(tmp_path):
    spec = importlib.util.spec_from_file_location("export_clef_glyphs", _EXPORT_TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)

    assert tool.main(["--out-dir", str(tmp_path)]) == 0

    index = json.loads((tmp_path / "glyphs.json").read_text())
    assert index["version"] == 1
    assert sorted(index["assets"]) == sorted(ca.BASE_ASSETS)
    for asset in ca.BASE_ASSETS:
        data = (tmp_path / f"{asset}.png").read_bytes()
        assert data == ca.base_png(asset)
        width, height = ca.base_size(asset)
        assert index["assets"][asset] == {"width": width, "height": height}
