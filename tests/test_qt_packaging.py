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
    # QtQuick.Dialogs' FileDialog (G1's Browse, F3's pickers).
    "PySide6/Qt/lib/libQt6QuickDialogs2.so.6", "PySide6/Qt6QuickDialogs2QuickImpl.dll",
    "PySide6/Qt/lib/libQt6QuickDialogs2Utils.so.6", "PySide6/Qt/lib/libQt6LabsFolderListModel.so.6",
    "PySide6/Qt/qml/QtQuick/Dialogs/qmldir", "PySide6/Qt/qml/QtQuick/Dialogs/quickimpl/qml/FileDialog.qml",
    "PySide6/Qt/qml/Qt/labs/folderlistmodel/qmldir",
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
    "PySide6/Qt/qml/QtQuick/Dialogs/quickimpl/qml/+Material/FileDialog.qml",
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


# --- macOS ----------------------------------------------------------------------

WORKFLOW = (REPO / ".github/workflows/build.yml").read_text(encoding="utf-8")


def test_macos_needs_qt_6_12_s_floor():
    """Qt 6.12 runs on macOS 14.4 and later; FluidSynth is built for the same."""
    assert "'LSMinimumSystemVersion': '14.4'" in SPEC
    assert "MACOSX_DEPLOYMENT_TARGET:-14.4}" in (REPO / "packaging/macos/build_fluidsynth.sh").read_text()


def test_macos_thins_the_universal_wheels_before_pyinstaller():
    thin = WORKFLOW.index("packaging/macos/thin_wheels.sh")
    assert WORKFLOW.index("run: pipenv sync --dev", WORKFLOW.index("  build:")) < thin
    assert thin < WORKFLOW.index("pipenv run pyinstaller --clean chord-notepad.spec")


# --- Flatpak and snap -----------------------------------------------------------

def _yaml(path):
    import yaml

    return yaml.safe_load((REPO / path).read_text(encoding="utf-8"))


def test_the_flatpak_gives_the_qt_window_wayland_and_the_gpu():
    manifest = _yaml("packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml")
    args = manifest["finish-args"]
    assert {"--socket=wayland", "--device=dri"} <= set(args)
    assert "--socket=x11" in args  # Tk, the default, needs X11 even on Wayland sessions
    app = next(m for m in manifest["modules"] if isinstance(m, dict) and m["name"] == "chord-notepad")
    assert any("packaging/qt_bundle.py trim" in c for c in app["build-commands"])



def test_the_flatpak_builds_the_kerberos_library_qtnetwork_links():
    """The freedesktop runtime has no libgssapi_krb5 (QtQml links QtNetwork, which needs it)."""
    manifest = _yaml("packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml")
    krb5 = next(m for m in manifest["modules"] if isinstance(m, dict) and m["name"] == "krb5")
    source = COMPONENTS["krb5-flatpak"]["sources"][0]
    assert (krb5["sources"][0]["url"], krb5["sources"][0]["sha256"]) == (source["urls"][0], source["sha256"])
    assert source["file"] == f"krb5-{COMPONENTS['krb5-flatpak']['version']}.tar.gz"
    names = [m if isinstance(m, str) else m["name"] for m in manifest["modules"]]
    assert names.index("krb5") < names.index("python3-deps.json")


def test_the_snap_gives_the_qt_window_wayland_opengl_and_its_libraries():
    snap = _yaml("snap/snapcraft.yaml")
    assert {"x11", "wayland", "opengl"} <= set(snap["apps"]["chord-notepad"]["plugs"])
    staged = set(snap["parts"]["qt-runtime"]["stage-packages"])
    assert {"libxcb-cursor0", "libxkbcommon-x11-0", "libxcb-icccm4", "libegl1", "libgl1",
            "libwayland-client0"} <= staged
    assert "packaging/qt_bundle.py trim" in snap["parts"]["chord-notepad"]["override-build"]


def test_the_linux_packages_smoke_test_imports_the_qt_front_end():
    """packaging/linux/smoke_test.py (make flatpak-check, snap-check) walks all three packages."""
    smoke = (REPO / "packaging/linux/smoke_test.py").read_text(encoding="utf-8")
    assert '"chordnotepad_desktop": APP / "desktop"' in smoke
    assert "desktop/chordnotepad_desktop/qml/app/Main.qml" in smoke


# --- CI -------------------------------------------------------------------------

def _job(name):
    import yaml

    return yaml.safe_load(WORKFLOW)["jobs"][name]


def _step(job, name):
    return next(s for s in job["steps"] if s.get("name") == name)


def test_ci_runs_the_qt_tests_offscreen_and_fails_when_they_would_skip():
    test = _job("test")
    installed = _step(test, "Install system dependencies")["run"]
    for package in ("libegl1", "libgl1", "libxkbcommon0", "libfontconfig1"):
        assert package in installed, package
    assert "--ignore=tests/qt" in _step(test, "Run tests")["run"]
    qt = _step(test, "Run the Qt tests and qmllint (offscreen)")
    assert qt["env"] == {"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"}
    assert "pytest tests/qt" in qt["run"] and "import PySide6.QtGui" in qt["run"]
    assert "Qt not available|qmllint not installed" in qt["run"]


@pytest.mark.parametrize("step, command", [
    ("Smoke-test the Qt window (Linux binary)", "--smoke"),
    ("Smoke-test the Qt window (macOS)", "packaging/macos/smoke_test_qt.sh"),
    ("Smoke-test the Qt window (Windows exe)", "packaging/windows/smoke_test_qt.ps1"),
    ("Smoke-test the Qt window (snap)", "make snap-qt-check"),
    ("Smoke-test the Qt window (Flatpak)", "make flatpak-qt-check"),
    ("Smoke-test the Qt window (Store build)", "packaging/windows/smoke_test_qt.ps1"),
])
def test_every_package_the_build_job_makes_starts_the_qt_window(step, command):
    build = _job("build")
    names = [s.get("name") for s in build["steps"]]
    assert command in _step(build, step)["run"]
    # Right after the step that makes or checks that package, so a Qt failure points at it.
    before = {"(Linux binary)": "Prepare artifact (Linux)", "(macOS)": "Smoke-test disk image (macOS)",
              "(Windows exe)": "Prepare artifact (Windows)", "(snap)": "Smoke-test snap",
              "(Flatpak)": "Smoke-test Flatpak bundle", "(Store build)": "Smoke-test Store package"}
    previous = next(v for k, v in before.items() if step.endswith(k))
    assert names.index(step) == names.index(previous) + 1
    if "xvfb-run" in _step(build, step)["run"]:
        assert "xvfb" in _step(build, "Install system dependencies (Linux)")["run"]


def test_the_linux_build_runner_has_the_libraries_pyinstaller_bundles_for_qt():
    installed = _step(_job("build"), "Install system dependencies (Linux)")["run"]
    for package in ("libxcb-cursor0", "libxkbcommon-x11-0", "libxcb-icccm4", "libegl1", "libgssapi-krb5-2"):
        assert package in installed, package


def test_the_make_targets_the_build_job_calls_exist():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "\nflatpak-qt-check:\n" in makefile and "\nsnap-qt-check:\n" in makefile
    # Never the real ~/.var/app: a throwaway HOME and a private session bus.
    assert "HOME=$(CURDIR)/build/flatpak-qt-home" in makefile and "dbus-run-session --" in makefile


# --- Tk stays (the 0.6.0 --ui tk fallback) --------------------------------------

def test_every_build_keeps_the_tk_front_end_for_the_fallback():
    """0.6.0 switches the default to Qt but keeps ``--ui tk``: no package may drop Tk yet."""
    spec = (REPO / "chord-notepad.spec").read_text(encoding="utf-8")
    assert "['desktop/chordnotepad_desktop/__main__.py']" in spec
    assert "'chordnotepad_tk'," in spec and "'PIL._tkinter_finder'," in spec
    assert not {"tkinter", "_tkinter", "PIL", "chordnotepad_tk"} & set(inv.PYINSTALLER_EXCLUDES)
    assert set(COMPONENTS["tcl-tk"]["builds"]) == {"windows", "macos", "linux"}
    assert {"tcl-tk-flatpak", "tkinter-flatpak", "pillow", "jeepney"} <= set(COMPONENTS)

    manifest = _yaml("packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml")
    names = [m if isinstance(m, str) else m["name"] for m in manifest["modules"]]
    assert {"tcl", "tk", "tkinter"} <= set(names)
    assert "--socket=x11" in manifest["finish-args"]

    snap = _yaml("snap/snapcraft.yaml")
    assert "python3.14-tk" in snap["parts"]["python-runtime"]["stage-packages"]
    assert "x11" in snap["apps"]["chord-notepad"]["plugs"]

    for launcher in ("packaging/flatpak/chord-notepad.sh", "packaging/snap/chord-notepad.sh"):
        assert "-m chordnotepad_desktop " in (REPO / launcher).read_text(encoding="utf-8"), launcher
    smoke = (REPO / "packaging/linux/smoke_test.py").read_text(encoding="utf-8")
    assert '"chordnotepad_tk": APP / "desktop"' in smoke and '"PIL.ImageTk"' in smoke
