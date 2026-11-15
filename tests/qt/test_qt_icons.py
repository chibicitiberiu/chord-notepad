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
    """Icon names the QML spells out: iconUrl("x"), name: "x", iconName: "x"
    (IconButton), and ChevronIcon's directions; in the app and the tests' sample."""
    names = set()
    sample = Path(__file__).resolve().parent / "qml"
    for path in [*QML_DIR.rglob("*.qml"), *sample.rglob("*.qml")]:
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r'iconUrl\("([a-z0-9-]+)"\)', text))
        names |= set(re.findall(r'\b(?:name|iconName): "([a-z0-9-]+)"(?!\s*\+)', text))
        if '"chevron-" + direction' in text:
            names |= {"chevron-down", "chevron-right", "chevron-up"}
    return names


def test_every_icon_the_qml_names_exists(provider):
    used = names_used_in_qml()
    assert {"check", "chevron-down", "menu", "undo", "play"} <= used
    missing = sorted(n for n in used if provider.find(n) is None)
    assert missing == []


# -- The ratio tag (Tibi's rail icons cut on the right at 125%) ------------------------
#
# A QPainter opened on a QImage that already has a device pixel ratio paints in
# logical pixels, so the SVG came out `ratio` times too big and lost its right
# and bottom edge at every ratio but 1. The tag must change nothing but the tag.

def untagged(image):
    copy = image.copy()
    copy.setDevicePixelRatio(1.0)
    return copy


@pytest.mark.parametrize("ratio", [1.25, 1.5, 2.0])
def test_the_ratio_tag_does_not_change_the_drawing(provider, ratio):
    changed = []
    for name in sorted(p.stem for p in all_icons()):
        for px in sorted({round(18 * ratio), round(24 * ratio), 27, 28}):
            plain, _ = request(provider, f"{name}?c=%23000000&s={px}&d=1")
            tagged, _ = request(provider, f"{name}?c=%23000000&s={px}&d={ratio}")
            assert tagged.devicePixelRatio() == ratio
            if untagged(tagged) != untagged(plain):
                changed.append(f"{name}@{px}")
    assert changed == []


def ink_margins(image):
    """Transparent rows/columns around the ink: (left, top, right, bottom)."""
    w, h = image.width(), image.height()
    xs = [x for x in range(w) for y in range(h) if image.pixelColor(x, y).alpha() > 8]
    ys = [y for x in range(w) for y in range(h) if image.pixelColor(x, y).alpha() > 8]
    return min(xs), min(ys), w - 1 - max(xs), h - 1 - max(ys)


@pytest.mark.parametrize("ratio, px", [(1.25, 28), (1.25, 27), (1.5, 33), (2.0, 44)])
@pytest.mark.parametrize("name", ["braces", "piano", "cog"])
def test_a_centred_icon_keeps_even_margins_at_a_fractional_ratio(provider, name, ratio, px):
    # The rail's icons (size iconSize + gap1, 28 device px at 125%) and the gear.
    image, _ = request(provider, f"{name}?c=%23000000&s={px}&d={ratio}")
    left, top, right, bottom = ink_margins(image)
    assert right >= 1 and bottom >= 1, (left, top, right, bottom)
    assert abs(left - right) <= 1 and abs(top - bottom) <= 1, (left, top, right, bottom)


def pixel_icon_in(quick_item):
    """The first PixelIcon (an item with devicePx) under quick_item."""
    for child in quick_item.childItems():
        if child.property("devicePx") is not None:
            return child
        found = pixel_icon_in(child)
        if found is not None:
            return found
    return None


@pytest.mark.parametrize("ratio", [1.25, 1.5, 2.0])
def test_the_rail_icons_are_whole_in_the_window(main_window, qtbot, ratio):
    """Theme.dpr apart from the window's own ratio (offscreen renders at 1.0),
    as on KDE Wayland where the two disagree: the rail's icons come out whole,
    with the same space on both sides, not cut at the item's right edge."""
    from PySide6.QtCore import QRectF
    from PySide6.QtQml import qmlEngine
    from PySide6.QtQuick import QQuickItem

    from chordnotepad_desktop.dpr import DprWatcher

    window = main_window.window
    DprWatcher(window, ratio=lambda: ratio, settle_ms=10, parent=window)
    theme = qmlEngine(window).singletonInstance("CNTheme", "Theme")
    qtbot.waitUntil(lambda: window.property("contentReady") and theme.property("dpr") == ratio,
                    timeout=3000)
    for key in ("directives", "identifier"):
        button = window.findChild(QQuickItem, f"rail:{key}")
        icon = pixel_icon_in(button)
        qtbot.waitUntil(lambda: icon.property("source").toString().endswith(f"&d={ratio:g}"),
                        timeout=2000)
    qtbot.wait(50)
    grab = window.grabWindow()
    assert grab.devicePixelRatio() == 1.0
    for key in ("directives", "identifier"):
        button = window.findChild(QQuickItem, f"rail:{key}")
        icon = pixel_icon_in(button)
        rect = icon.mapRectToScene(QRectF(0, 0, icon.width(), icon.height())).toAlignedRect()
        crop = grab.copy(rect)
        paper = crop.pixelColor(0, 0)

        def inked(x, y):
            c = crop.pixelColor(x, y)
            return max(abs(c.red() - paper.red()), abs(c.green() - paper.green()),
                       abs(c.blue() - paper.blue())) > 40

        columns = [x for x in range(crop.width()) if any(inked(x, y) for y in range(crop.height()))]
        rows = [y for y in range(crop.height()) if any(inked(x, y) for x in range(crop.width()))]
        left, right = columns[0], crop.width() - 1 - columns[-1]
        top, bottom = rows[0], crop.height() - 1 - rows[-1]
        assert right >= 1 and bottom >= 1, (key, left, top, right, bottom)
        assert abs(left - right) <= 1 and abs(top - bottom) <= 1, (key, left, top, right, bottom)
