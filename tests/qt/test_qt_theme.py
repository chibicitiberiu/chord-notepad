"""The theme, the fonts and the QML sources: CNTheme, CNStyle, Main.qml.

Static checks of the QML (the scaling and text recipe can't regress quietly),
the start-up font set-up, and ``pyside6-qmllint`` over every file.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

if QT_PROBLEM:
    pytest.skip(f"Qt not available: {QT_PROBLEM}", allow_module_level=True)

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from chordnotepad.app_paths import AppPaths  # noqa: E402
from chordnotepad_desktop import fonts  # noqa: E402
from chordnotepad_desktop.main import QML_DIR  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
QML_FILES = sorted(QML_DIR.rglob("*.qml"))


def qml(name):
    return (QML_DIR / name).read_text(encoding="utf-8")


def code_of(path):
    """A QML file without its // comments (they name the pitfalls they avoid)."""
    return "\n".join(line.split("//")[0] for line in path.read_text(encoding="utf-8").splitlines())


def test_every_mockup_control_and_the_theme_module_are_there():
    """All of the mockup's CNStyle folder: 30 files plus qmldir (the plan's "31"),
    and the BusyIndicator Suggest Capo added."""
    controls = [p for p in (QML_DIR / "CNStyle").glob("*.qml")]
    assert len(controls) == 31
    listed = re.findall(r"^(?:internal )?(\w+) (?:6\.0 )?(\w+)\.qml$", qml("CNStyle/qmldir"), re.M)
    assert sorted(f"{file}.qml" for _, file in listed) == sorted(p.name for p in controls)
    assert set(re.findall(r"(\w+)\.qml", qml("CNTheme/qmldir"))) == {
        "Theme", "SText", "SnapTranslate", "SnapLine"}


def test_every_qt_font_turns_hinting_off():
    """Hinting isn't inherited (pitfall 11): each Qt.font names it."""
    calls = [(p.name, call) for p in QML_FILES
             for call in re.findall(r"Qt\.font\(\{[^}]*\}\)", code_of(p))]
    assert len(calls) >= 8
    # The editor's monospace is the one font with the default hinting (Theme.editorFont).
    editor = [c for c in calls if "hintingPreference: editorHinting" in c[1]]
    assert [c[0] for c in editor] == ["Theme.qml"]
    assert [c for c in calls if "hintingPreference: hinting" not in c[1] and c not in editor] == []
    assert "readonly property int editorHinting: Font.PreferDefaultHinting" in qml("CNTheme/Theme.qml")
    assert "readonly property int hinting: Font.PreferNoHinting" in qml("CNTheme/Theme.qml")


def test_no_qml_sets_a_font_part_by_part():
    """A font.family / font.pointSize override would build a font without the hinting choice."""
    found = [(p.name, m) for p in QML_FILES
             for m in re.findall(r"\bfont\.(?:family|pointSize|pixelSize|weight|bold|hintingPreference)\s*:",
                                 code_of(p))]
    assert found == []


@pytest.mark.parametrize("pattern, why", [
    (r"\bIconImage\b", "IconImage blurs at a fractional ratio; use PixelIcon (pitfall 14)"),
    (r"\bMultiEffect\b", "the software backend has no MultiEffect (pitfall 15)"),
    (r"\bScreen\.devicePixelRatio\b", "wrong on KDE Wayland; Theme.dpr comes from Python (pitfall 9)"),
    (r"\binline:", "an inline: URL hangs engine.load (pitfall 24)"),
    (r"\bMock\b|\bShotMode\b", "mockup-only context properties"),
])
def test_the_qml_avoids_the_known_pitfalls(pattern, why):
    found = [p.relative_to(QML_DIR).as_posix() for p in QML_FILES if re.search(pattern, code_of(p))]
    assert found == [], why


def test_no_property_is_named_like_a_handler():
    """A property called on<Capital> is read as a signal handler (pitfall 1)."""
    found = [(p.name, m) for p in QML_FILES
             for m in re.findall(r"\bproperty\s+\w+\s+(on[A-Z]\w*)", code_of(p))]
    assert found == []


def test_pixel_sizes_are_units_except_the_hairline():
    """Every dimension in pt or Theme units (checklist 12): no literal px in the controls."""
    found = []
    for p in QML_FILES:
        # FatalError.qml uses neither the theme nor the style on purpose: it
        # shows why start-up failed, which may be that they didn't load.
        if p.name in ("Theme.qml", "FatalError.qml"):
            continue
        for code in code_of(p).splitlines():
            m = re.search(r"\b(?:[wW]idth|[hH]eight|[xy]|[mM]argins?|[pP]adding|spacing|radius|[sS]ize)"
                          r"\s*:\s*(\d+(?:\.\d+)?)\s*$", code)
            if m and float(m.group(1)) != 0:
                found.append(f"{p.name}: {code.strip()}")
    assert found == []


def test_the_bundled_inter_is_loaded(qapp):
    assert "Inter" in QFontDatabase.families()
    folder = fonts.font_folder(AppPaths(resources=REPO / "resources"))
    assert folder == REPO / "resources" / "fonts"
    assert sorted(p.name for p in folder.glob(fonts.UI_FONT_GLOB)) == [
        "Inter-Bold.ttf", "Inter-Medium.ttf", "Inter-Regular.ttf", "Inter-SemiBold.ttf"]
    assert QFontDatabase.styles("Inter")


def test_a_missing_font_folder_is_logged_not_fatal(qapp, caplog, tmp_path):
    assert fonts.load_bundled_fonts(tmp_path) == []
    assert fonts.load_bundled_fonts(None) == []
    assert "bundled Inter font was not found" in caplog.text


def test_start_up_text_settings(qapp):
    assert QQuickWindow.textRenderType() == QQuickWindow.TextRenderType.NativeTextRendering
    assert QGuiApplication.font().hintingPreference() == QFont.HintingPreference.PreferNoHinting
    assert QQuickStyle.name() == "CNStyle"
    assert fonts.unhinted(QFont("Inter", 10)).hintingPreference() == QFont.HintingPreference.PreferNoHinting


def qmllint():
    found = shutil.which("pyside6-qmllint", path=str(Path(sys.executable).parent))
    return found or shutil.which("pyside6-qmllint")


#: qmllint 6.12 says this about a singleton linted on its own, though qmldir
#: declares it (the files that use Theme lint clean).
QMLLINT_FALSE_POSITIVES = [
    "Theme.qml:: Type Theme not declared as singleton in qmldir but using pragma Singleton [import]",
]


@pytest.mark.skipif(qmllint() is None, reason="pyside6-qmllint not installed")
def test_qmllint_finds_nothing():
    result = subprocess.run(
        [qmllint(), "-I", str(QML_DIR), *map(str, QML_FILES)],
        capture_output=True, text=True, timeout=120)
    lines = [line for line in (result.stdout + result.stderr).splitlines()
             if line.strip() and not any(line.endswith(known) for known in QMLLINT_FALSE_POSITIVES)]
    assert result.returncode == 0 and lines == [], "\n".join(lines)


def test_points_are_sized_at_96_dpi_on_every_os(qapp):
    """macOS draws a point as one logical pixel (72 dpi), Windows and Linux as
    4/3 (96 dpi): Theme scales its points on macOS so the UI, the editor and
    the chord sheet (pixels at 96 dpi) come out the same size everywhere."""
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    engine = QQmlEngine()
    engine.addImportPath(str(QML_DIR))
    component = QQmlComponent(engine)
    component.setData(b"import QtQuick\nimport CNTheme\nQtObject {\n"
                      b"    property real pointScale: Theme.pointScale\n"
                      b"    property real baseSize: Theme.baseSize\n}\n",
                      QUrl())
    probe = component.create()
    assert probe is not None, component.errorString()
    expected = 96 / 72 if sys.platform == "darwin" else 1.0
    assert probe.property("pointScale") == pytest.approx(expected)
    assert probe.property("baseSize") == pytest.approx(10 * expected, abs=0.002)
    # The editor's size (the session's points) goes through the same factor.
    assert "pointSize * scale * pointScale" in qml("CNTheme/Theme.qml")
