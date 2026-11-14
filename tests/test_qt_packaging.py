"""The Qt window in the packages (the packaging tracer, C5 of the Qt migration).

PySide6 goes into every desktop build next to Tk: the licence entries, the
Flatpak's per-architecture wheels, the parts of the wheel each build keeps
(packaging/qt_bundle.py), the PyInstaller spec, the Flatpak and snap
manifests, and the CI steps that start ``--ui qt --smoke`` from each package.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packaging"))
sys.path.insert(0, str(REPO / "packaging" / "flatpak"))
sys.path.insert(0, str(REPO / "packaging" / "licenses"))

import gen_python_deps  # noqa: E402
import licence_inventory as inv  # noqa: E402
import qt_bundle  # noqa: E402

COMPONENTS = {c["id"]: c for c in inv.load_components()}
LOCK = json.loads((REPO / "Pipfile.lock").read_text(encoding="utf-8"))


def test_pyside6_is_a_runtime_package():
    """Every build ships it now, so it is locked with the app's packages, not the dev tools."""
    assert {"pyside6-essentials", "shiboken6"} <= set(LOCK["default"])
    assert not {"pyside6-essentials", "shiboken6"} & set(LOCK["develop"])
    assert LOCK["default"]["pyside6-essentials"]["version"].startswith("==6.12.")


def test_the_flatpak_takes_one_locked_wheel_per_architecture():
    module = json.loads((REPO / "packaging/flatpak/python3-deps.json").read_text(encoding="utf-8"))
    for package in sorted(gen_python_deps.ARCH_WHEELS):
        version = LOCK["default"][package]["version"].lstrip("=")
        prefix = package.replace("-", "_") + f"-{version}-"
        wheels = [s for s in module["sources"] if s["url"].rsplit("/", 1)[1].startswith(prefix)]
        assert sorted(a for s in wheels for a in s["only-arches"]) == ["aarch64", "x86_64"], package
        for source in wheels:
            name = source["url"].rsplit("/", 1)[1]
            assert "manylinux" in name and name.endswith(f"_{source['only-arches'][0]}.whl"), name
            assert f"sha256:{source['sha256']}" in LOCK["default"][package]["hashes"], name
    assert "pyside6-essentials shiboken6" in module["build-commands"][0]


# --- The parts of PySide6 the builds keep (packaging/qt_bundle.py) ----------

# Bundle paths as PyInstaller names them on Linux, Windows and macOS.
KEPT = [
    "PySide6/Qt/lib/libQt6Core.so.6", "PySide6/Qt/lib/libQt6QuickControls2Basic.so.6",
    "PySide6/Qt/lib/libicudata.so.73", "PySide6/Qt6Quick.dll", "PySide6/Qt6Svg.dll",
    "PySide6/Qt/lib/QtQml.framework/Versions/A/QtQml", "PySide6/Qt/lib/QtGui.framework/Resources/Info.plist",
    "PySide6/QtCore.abi3.so", "PySide6/QtQuickControls2.pyd",
    "PySide6/Qt/plugins/platforms/libqxcb.so", "PySide6/plugins/platforms/qwindows.dll",
    "PySide6/Qt/plugins/platforms/libqcocoa.dylib", "PySide6/Qt/plugins/platforms/libqwayland.so",
    "PySide6/Qt/plugins/wayland-shell-integration/libxdg-shell.so",
    "PySide6/Qt/plugins/platforminputcontexts/libibusplatforminputcontextplugin.so",
    "PySide6/plugins/imageformats/qsvg.dll",
    "PySide6/Qt/qml/QtQuick/Controls/Basic/Button.qml", "PySide6/qml/QtQuick/Layouts/qmldir",
    "PySide6/Qt/qml/builtins.qmltypes",
]
DROPPED = [
    "PySide6/Qt/lib/libQt6Designer.so.6", "PySide6/Qt/lib/libQt6Lottie.so.6",
    "PySide6/Qt/lib/libQt6WaylandCompositor.so.6", "PySide6/Qt6QuickTimeline.dll",
    "PySide6/Qt/lib/QtLabsStyleKit.framework/Versions/A/QtLabsStyleKit",
    "PySide6/Qt/lib/libQt6QuickControls2Material.so.6", "PySide6/QtWidgets.abi3.so", "PySide6/QtDesigner.pyd",
    "PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so",
    "PySide6/Qt/plugins/platformthemes/libqgtk3.so", "PySide6/plugins/tls/qopensslbackend.dll",
    "PySide6/Qt/plugins/qmltooling/libqmldbg_debugger.so", "PySide6/Qt/plugins/egldeviceintegrations/x.so",
    "PySide6/Qt/plugins/wayland-shell-integration/libwl-shell-plugin.so",
    "PySide6/Qt/qml/QtQuick/VirtualKeyboard/qmldir", "PySide6/Qt/qml/QtWayland/Compositor/qmldir",
    "PySide6/qml/QtQuick/Controls/Material/Button.qml", "PySide6/Qt/qml/Qt/labs/StyleKit/qmldir",
    "PySide6/Qt/translations/qtbase_de.qm", "PySide6/translations/qt_fr.qm", "PySide6/opengl32sw.dll",
]


@pytest.mark.parametrize("path", KEPT)
def test_the_qt_window_s_parts_are_kept(path):
    assert qt_bundle.wanted(path) is True


@pytest.mark.parametrize("path", DROPPED)
def test_gpl_only_and_unused_qt_parts_are_left_out(path):
    assert qt_bundle.wanted(path) is False


@pytest.mark.parametrize("path", ["PySide6/__init__.py", "PySide6/libpyside6.abi3.so.6.12", "PySide6/msvcp140.dll",
                                  "PySide6/pyside6.abi3.dll", "shiboken6/Shiboken.abi3.so", "music21/__init__.py"])
def test_everything_else_is_the_callers_to_decide(path):
    assert qt_bundle.wanted(path) is None


def test_only_libraries_and_bindings_stop_a_build_when_unlisted():
    assert qt_bundle.is_qt_code("PySide6/Qt/lib/libQt6Designer.so.6")
    assert qt_bundle.is_qt_code("PySide6/QtWidgets.abi3.so") and qt_bundle.is_qt_code("PySide6/Qt6Help.dll")
    assert not qt_bundle.is_qt_code("PySide6/Qt/plugins/platformthemes/libqgtk3.so")
    assert not qt_bundle.is_qt_code("PySide6/Qt/lib/libicuuc.so.73")
    assert not qt_bundle.is_qt_code("PySide6/opengl32sw.dll")


def test_hook_results_are_filtered_by_destination():
    toc = [("/w/PySide6/Qt/plugins/platforms/libqxcb.so", "PySide6/Qt/plugins/platforms"),
           ("/w/PySide6/Qt/plugins/platforms/libqeglfs.so", "PySide6/Qt/plugins/platforms"),
           ("C:\\w\\PySide6\\qml\\QtQuick\\Timeline\\qmldir", "PySide6\\qml\\QtQuick\\Timeline")]
    assert qt_bundle.filter_toc(toc) == toc[:1]


@pytest.mark.parametrize("path", [p for p in KEPT if not qt_bundle._BINDING.match(p.split("/")[-1])
                                  and "libicu" not in p])
def test_the_kept_qt_parts_have_a_qt_licence_entry(path):
    hits = [cid for cid in ("qt-wayland", "qt") if inv.match(path, COMPONENTS[cid]["files"])]
    assert hits, path
    assert hits[0] == ("qt-wayland" if "wayland" in path else "qt"), path


def test_icu_has_its_own_entry():
    assert inv.match("PySide6/Qt/lib/libicudata.so.73", COMPONENTS["icu"]["files"])


def test_trim_leaves_what_the_window_needs(tmp_path):
    files = {
        "PySide6/__init__.py": "", "PySide6/QtCore.abi3.so": "", "PySide6/QtCore.pyi": "",
        "PySide6/QtDesigner.abi3.so": "", "PySide6/designer": "#!", "PySide6/qmllint": "#!",
        "PySide6/include/QtCore/qobject.h": "", "PySide6/typesystems/x.xml": "", "PySide6/glue/x.cpp": "",
        "PySide6/Qt/lib/libQt6Core.so.6": "", "PySide6/Qt/lib/libQt6Designer.so.6": "",
        "PySide6/Qt/libexec/qmlcachegen": "#!", "PySide6/Qt/metatypes/x.json": "",
        "PySide6/Qt/plugins/platforms/libqxcb.so": "", "PySide6/Qt/plugins/sqldrivers/libqsqlite.so": "",
        "PySide6/Qt/qml/QtQuick/qmldir": "", "PySide6/Qt/qml/QtQuick/Timeline/qmldir": "",
        "PySide6/Qt/translations/qt_de.qm": "", "PySide6/support/deprecated.py": "",
        "shiboken6/Shiboken.abi3.so": "", "shiboken6/include/x.h": "", "other/keep.py": "",
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if text == "#!":
            path.chmod(0o755)
    qt_bundle.trim(tmp_path)
    left = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert left == ["PySide6/Qt/lib/libQt6Core.so.6", "PySide6/Qt/plugins/platforms/libqxcb.so",
                    "PySide6/Qt/qml/QtQuick/qmldir", "PySide6/QtCore.abi3.so", "PySide6/__init__.py",
                    "PySide6/support/deprecated.py", "other/keep.py", "shiboken6/Shiboken.abi3.so"]
    assert not (tmp_path / "PySide6/Qt/translations").exists()


# --- The PyInstaller spec -----------------------------------------------------

SPEC = (REPO / "chord-notepad.spec").read_text(encoding="utf-8")


def test_the_spec_bundles_the_qt_window():
    for data in ("('desktop/chordnotepad_desktop/qml', 'chordnotepad_desktop/qml')",
                 "('resources/qt-icons', 'resources/qt-icons')", "('resources/fonts', 'resources/fonts')"):
        assert data in SPEC
    assert "'PySide6'," not in SPEC  # no longer excluded
    assert "'PySide2'," in SPEC and "'PyQt6'," in SPEC
    assert "qt_bundle.is_qt_code(" in SPEC and "qt_bundle.wanted(" in SPEC


def test_the_qml_folder_the_spec_bundles_is_the_one_the_window_loads():
    main = (REPO / "desktop/chordnotepad_desktop/main.py").read_text(encoding="utf-8")
    assert 'QML_DIR = Path(__file__).resolve().parent / "qml"' in main


@pytest.mark.parametrize("module", ["QtGui", "QtQml", "QtNetwork"])
def test_hooks_trim_the_qt_modules_that_collect_plugins(module):
    hook = (REPO / "hooks/pyinstaller" / f"hook-PySide6.{module}.py").read_text(encoding="utf-8")
    assert "qt_bundle.filter_toc(" in hook and "add_qt6_dependencies(__file__)" in hook


def test_the_qt_window_s_assets_are_in_every_build():
    for cid in ("material-design-icons-mdi", "inter", "noto-sans-mono"):
        assert set(COMPONENTS[cid]["builds"]) == set(inv.BUILDS), cid
