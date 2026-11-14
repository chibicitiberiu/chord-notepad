"""The icon provider (image://icons) and the icon files in resources/qt-icons."""

import logging
import re
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

from chordnotepad.app_paths import AppPaths  # noqa: E402
from chordnotepad_desktop.icons import IconProvider, icon_folders  # noqa: E402
from chordnotepad_desktop.main import QML_DIR  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ICONS = REPO / "resources" / "qt-icons"
FOLDERS = icon_folders(AppPaths(resources=REPO / "resources"))


@pytest.fixture
def provider(qapp):
    return IconProvider(FOLDERS)


def request(provider, ident):
    size = QSize()
    image = provider.requestImage(ident, size, QSize())
    return image, size


def test_the_folders_are_mdi_then_ours():
    assert FOLDERS == [ICONS / "mdi", ICONS / "own"]
    assert icon_folders(AppPaths()) == []


def test_an_icon_is_drawn_at_whole_device_pixels_and_tagged_with_the_ratio(provider):
    image, size = request(provider, "undo?c=%23ff0000&s=30&d=1.25")
    assert (image.width(), image.height()) == (30, 30)
    assert (size.width(), size.height()) == (30, 30)
    assert image.devicePixelRatio() == 1.25


def test_the_icon_is_tinted_to_one_colour(provider):
    image, _ = request(provider, "stop?c=%233f51b5&s=24&d=1")
    opaque = {image.pixelColor(x, y).rgb() for x in range(24) for y in range(24)
              if image.pixelColor(x, y).alpha() == 255}
    assert opaque == {QColor("#3f51b5").rgb()}
    assert image.pixelColor(0, 0).alpha() == 0     # the rounded square's corner stays clear


def test_the_cache_keeps_the_most_recent_images(qapp):
    provider = IconProvider(FOLDERS, cache_size=2)
    first, _ = request(provider, "undo?c=%23000000&s=24&d=1")
    request(provider, "redo?c=%23000000&s=24&d=1")
    again, _ = request(provider, "undo?c=%23000000&s=24&d=1")
    assert again.cacheKey() == first.cacheKey()          # served from the cache
    request(provider, "play?c=%23000000&s=24&d=1")        # evicts redo, the least recent
    assert provider.cached_count() == 2
    request(provider, "undo?c=%23000000&s=24&d=1")
    assert request(provider, "undo?c=%23000000&s=24&d=1")[0].cacheKey() == first.cacheKey()


def test_a_colour_or_size_change_is_a_new_image(provider):
    black, _ = request(provider, "undo?c=%23000000&s=24&d=1")
    white, _ = request(provider, "undo?c=%23ffffff&s=24&d=1")
    big, _ = request(provider, "undo?c=%23000000&s=36&d=1.5")
    assert len({black.cacheKey(), white.cacheKey(), big.cacheKey()}) == 3


@pytest.mark.parametrize("name", ["no-such-icon", "../own/capo", "UNDO", "undo.svg"])
def test_an_unknown_or_unsafe_name_draws_nothing_and_logs_once(provider, caplog, name):
    with caplog.at_level(logging.WARNING, logger="chordnotepad_desktop.icons"):
        image, size = request(provider, f"{name}?s=20")
        request(provider, f"{name}?s=22")
    assert (size.width(), size.height()) == (20, 20)
    assert all(image.pixelColor(x, y).alpha() == 0 for x in range(20) for y in range(20))
    assert len([r for r in caplog.records if "No icon named" in r.message]) == 1


def test_a_bad_query_falls_back_to_the_defaults(provider):
    image, _ = request(provider, "undo?s=big&d=x")
    assert (image.width(), image.devicePixelRatio()) == (24, 1.0)


def all_icons():
    return sorted(ICONS.glob("*/*.svg"))


def test_every_icon_is_a_valid_svg_in_one_of_the_two_folders():
    assert {p.parent.name for p in all_icons()} == {"mdi", "own"}
    assert set(ICONS.iterdir()) == {ICONS / "mdi", ICONS / "own", ICONS / "README.md"}
    for path in all_icons():
        assert QSvgRenderer(str(path)).isValid(), path


def test_icon_names_are_unique_across_the_folders():
    names = [p.stem for p in all_icons()]
    assert len(names) == len(set(names))


def test_the_readme_lists_every_changed_mdi_icon():
    readme = (ICONS / "README.md").read_text(encoding="utf-8")
    changed = sorted(p.name for p in (ICONS / "mdi").glob("*.svg")
                     if "<!-- Changed from" in p.read_text(encoding="utf-8"))
    assert changed == ["pal-tempo-reset.svg", "transpose.svg", "volume-off.svg", "volume.svg"]
    for name in changed + ["braces.svg", "pal-label.svg", "pal-tempo.svg"]:
        assert f"`{name}`" in readme, name


def names_used_in_qml():
    """Icon names the QML spells out: iconUrl("x"), name: "x", and ChevronIcon's directions."""
    names = set()
    for path in QML_DIR.rglob("*.qml"):
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r'iconUrl\("([a-z0-9-]+)"\)', text))
        names |= set(re.findall(r'\bname: "([a-z0-9-]+)"(?!\s*\+)', text))
        if '"chevron-" + direction' in text:
            names |= {"chevron-down", "chevron-right", "chevron-up"}
    return names


def test_every_icon_the_qml_names_exists(provider):
    used = names_used_in_qml()
    assert {"check", "chevron-down", "undo", "play"} <= used
    missing = sorted(n for n in used if provider.find(n) is None)
    assert missing == []
