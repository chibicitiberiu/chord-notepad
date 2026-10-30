"""Licence notices of the desktop builds.

The inventory (resources/licenses/components.json) against what the builds
actually ship: Pipfile.lock, the Flatpak and snap package lists, the pinned
FluidSynth package in CI, the Flatpak manifest; the build-time check that
maps PyInstaller's files to components; and the loader behind the Licences
window (services.licence_catalog).
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packaging" / "licenses"))
sys.path.insert(0, str(REPO / "packaging" / "flatpak"))

import gather_texts  # noqa: E402
import licence_inventory as inv  # noqa: E402
from services import licence_catalog as cat  # noqa: E402

LICENSES = REPO / "resources" / "licenses"
DATA = json.loads((LICENSES / "components.json").read_text(encoding="utf-8"))
COMPONENTS = DATA["components"]
BY_ID = {c["id"]: c for c in COMPONENTS}
LOCK = json.loads((REPO / "Pipfile.lock").read_text(encoding="utf-8"))
COPYLEFT = re.compile(r"\b(L?GPL|AGPL|MPL)-")


def locked(section: str) -> dict:
    """Normalized name -> version of a Pipfile.lock section."""
    return {inv.normalize(n): v["version"].lstrip("=") for n, v in LOCK[section].items()}


# --- The inventory itself ---------------------------------------------------

def test_every_component_has_what_the_window_needs():
    ids = [c["id"] for c in COMPONENTS]
    assert len(ids) == len(set(ids))
    for c in COMPONENTS:
        assert c["name"].strip() and c["license"].strip(), c["id"]
        assert c["group"] in cat.GROUPS and c["group"] != "system", c["id"]
        assert c["texts"], f"{c['id']}: no licence text"
        assert c["builds"] and set(c["builds"]) <= set(inv.BUILDS), c["id"]
        assert c.get("url") or c["group"] == "app", f"{c['id']}: no home page"


def test_texts_exist_and_none_is_unused():
    used = {t for c in COMPONENTS for t in c["texts"]}
    on_disk = {p.stem for p in (LICENSES / "texts").glob("*.txt")}
    assert used - on_disk == set(), "texts that are missing"
    assert on_disk - used == set(), "texts nothing refers to"
    for name in used:
        assert len((LICENSES / "texts" / f"{name}.txt").read_text(encoding="utf-8")) > 30, name


def test_gather_table_covers_every_text():
    assert set(gather_texts.SOURCES) | set(gather_texts.ONE_OFF) == {
        p.name for p in (LICENSES / "texts").glob("*.txt")}


@pytest.mark.parametrize("dest", sorted(d for d, s in gather_texts.SOURCES.items() if s[0] in ("file", "dist")
                                        and not str(s[1]).startswith("/usr/share")))
def test_committed_text_matches_its_source(dest):
    """Repository files and installed distributions need no download: compare them here."""
    assert (LICENSES / "texts" / dest).read_text(encoding="utf-8") == gather_texts.read(
        gather_texts.SOURCES[dest], gather_texts.DEFAULT_CACHE), f"run packaging/licenses/gather_texts.py ({dest})"


def test_appropriate_legal_notices_of_the_app():
    """ADDITIONAL-TERMS.txt (its permission 2(b)) follows the AGPL; logo and guide have their own."""
    app = BY_ID["chord-notepad"]
    assert app["texts"] == ["AGPL-3.0", "ADDITIONAL-TERMS"]
    assert app["license"] == "AGPL-3.0-only WITH AdditionRef-ChordNotepad-Section7"
    assert (LICENSES / "texts/ADDITIONAL-TERMS.txt").read_text() == (REPO / "ADDITIONAL-TERMS.txt").read_text()
    assert BY_ID["chord-notepad-logo"]["texts"] == ["ARTWORK-TERMS"]
    assert BY_ID["chord-notepad-guide"]["license"] == "CC-BY-SA-4.0"
    assert "Attribution-ShareAlike 4.0 International" in (LICENSES / "texts/CC-BY-SA-4.0.txt").read_text()
    for c in (app, BY_ID["chord-notepad-logo"], BY_ID["chord-notepad-guide"]):
        assert set(c["builds"]) == set(inv.BUILDS)


def test_copyleft_components_have_their_source_or_say_why_not():
    for c in COMPONENTS:
        if COPYLEFT.search(c["license"]) and c["id"] != "chord-notepad":
            assert c.get("sources") or c.get("sourceNote"), f"{c['id']}: {c['license']} without sources"


def test_source_entries_are_pinned():
    for c in COMPONENTS:
        for s in c.get("sources", []):
            assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"]), s["file"]
            assert s["urls"] and all(u.startswith(("https://", "http://")) for u in s["urls"]), s["file"]
            assert "/" not in s["file"], s["file"]


# --- Against what the builds ship -------------------------------------------

def python_components(build=None):
    return {inv.normalize(c["pypi"]): c for c in COMPONENTS
            if c["group"] == "python" and (build is None or build in c["builds"])}


def test_every_runtime_package_in_pipfile_lock_has_an_entry_or_is_left_out():
    """A default package is bundled (entry with the locked version) or excluded from PyInstaller."""
    from importlib import metadata

    entries = python_components()
    modules = metadata.packages_distributions()
    for name, version in locked("default").items():
        if name in entries:
            assert entries[name]["version"] == version, f"{name}: inventory says {entries[name]['version']}"
            continue
        # mypyc-compiled packages also ship a "<hash>__mypyc" runtime module
        # that only the package itself imports.
        top = {module for module, dists in modules.items()
               if name in {inv.normalize(d) for d in dists}
               and not module.startswith("__") and not module.endswith("__mypyc")}
        assert top and top <= set(inv.PYINSTALLER_EXCLUDES), (
            f"{name} {version} is in Pipfile.lock but has no licence entry and isn't excluded "
            f"from the PyInstaller builds (modules {sorted(top)})")
    assert set(entries) <= set(locked("default")), "entries for packages that aren't in Pipfile.lock"


def test_pyinstaller_entry_matches_the_locked_version():
    assert BY_ID["pyinstaller"]["version"] == locked("develop")["pyinstaller"]


def test_linux_packages_install_exactly_the_inventory():
    """The Flatpak and the snap pip-install gen_python_deps.PACKAGES (with --no-deps)."""
    import gen_python_deps

    assert {inv.normalize(p) for p in gen_python_deps.PACKAGES} == set(python_components("flatpak"))
    assert set(python_components("snap")) == set(python_components("flatpak"))
    pins = dict(line.split("==") for line in (REPO / "packaging/linux/requirements.txt").read_text().splitlines()
                if "==" in line and not line.startswith("#"))
    assert {inv.normalize(k): v for k, v in pins.items()} == {
        n: c["version"] for n, c in python_components("snap").items()}


def test_pyinstaller_builds_bundle_every_python_package_but_jeepney_off_linux():
    """The spec excludes jeepney on Windows and macOS; nothing else differs."""
    spec = (REPO / "chord-notepad.spec").read_text()
    assert "excludes.append('jeepney')" in spec
    for name, c in python_components().items():
        expected = {"linux", "flatpak", "snap"} if name == "jeepney" else set(inv.BUILDS)
        assert set(c["builds"]) == expected, name


def test_spec_takes_excludes_and_fluidsynth_dlls_from_the_inventory():
    spec = (REPO / "chord-notepad.spec").read_text()
    assert "*licence_inventory.PYINSTALLER_EXCLUDES" in spec
    assert "licence_inventory.fluidsynth_dlls(fluidsynth_path)" in spec
    assert "('resources/licenses', 'resources/licenses')" in spec
    assert "licence_inventory.classify(" in spec


def test_ci_pins_the_fluidsynth_package_the_inventory_lists():
    workflow = (REPO / ".github/workflows/build.yml").read_text()
    zip_entry = BY_ID["fluidsynth-windows"]["sources"][0]
    assert zip_entry["file"] == "fluidsynth-2.3.4-win10-x64.zip"
    assert f'$sha256 = "{zip_entry["sha256"]}"' in workflow
    assert 'fluidsynth-$version-win10-x64.zip' in workflow and '$version = "2.3.4"' in workflow
    assert workflow.count("CHORD_NOTEPAD_LICENCE_CHECK: strict") == 2  # onefile and MSIX builds


def test_flatpak_manifest_sources_match_the_inventory():
    manifest = (REPO / "packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml").read_text()
    pairs = dict(re.findall(r"url: (\S+)\s+sha256: ([0-9a-f]{64})", manifest))
    for cid in ("fluidsynth-flatpak",):
        for s in BY_ID[cid]["sources"]:
            assert pairs.get(s["urls"][0]) == s["sha256"], s["file"]
    for name, entry in gather_texts.TEXT_ARCHIVES.items():
        assert pairs.get(entry["urls"][0]) == entry["sha256"], name
    python = re.search(r"Python-(3\.\d+\.\d+)\.tar\.xz", manifest).group(1)
    assert BY_ID["tkinter-flatpak"]["version"] == python
    assert "v" + BY_ID["fluidsynth-flatpak"]["version"] + ".tar.gz" in manifest


def test_guide_asset_entries_match_the_sphinx_stack_in_pipfile_lock():
    """The guide's _static files come from the docs toolchain the lock pins (installed in the venv)."""
    from importlib import metadata

    develop = locked("develop")
    for cid, dist in (("sphinx", "sphinx"), ("sphinx-rtd-theme", "sphinx-rtd-theme"), ("pygments", "pygments")):
        assert BY_ID[cid]["version"] == develop[dist], cid
    jquery = metadata.distribution("sphinxcontrib-jquery").locate_file("sphinxcontrib/jquery/jquery.js")
    assert f"jQuery v{BY_ID['jquery']['version']} " in Path(jquery).read_text(encoding="utf-8")[:200]
    stemmer = metadata.distribution("sphinx").locate_file("sphinx/search/non-minified-js/english-stemmer.js")
    assert f"Snowball {BY_ID['snowball-stemmers']['version']} " in Path(stemmer).read_text(encoding="utf-8")[:200]
    theme = Path(metadata.distribution("sphinx-rtd-theme").locate_file("sphinx_rtd_theme/static/css/theme.css"))
    assert f"Font Awesome {BY_ID['font-awesome']['version']} " in theme.read_text(encoding="utf-8")
    assert BY_ID["chord-notepad-guide"]["files"] and not any(
        inv.match("help/build/html/_static/x.js", [p]) for p in BY_ID["chord-notepad-guide"]["files"])


def test_android_lists_the_same_guide_assets():
    android = json.loads((REPO / "android/app/src/main/assets/licenses/components.json").read_text(encoding="utf-8"))
    guide = {c["id"]: c for c in android["components"] if c["group"] == "guide"}
    assert set(guide) == {c["id"] for c in COMPONENTS if c["group"] == "guide"}
    for cid, c in guide.items():
        assert (c["version"], c["license"], c["texts"]) == (
            BY_ID[cid]["version"], BY_ID[cid]["license"], BY_ID[cid]["texts"]), cid


@pytest.mark.skipif(not (REPO / "help/build/html/_static").is_dir(), reason="user guide not built (make docs-html)")
def test_every_file_of_the_built_guide_has_an_entry():
    """What the strict build check sees for the guide (help/build/html, as the spec bundles it)."""
    root = REPO / "help/build/html"
    entries = [("help/build/html/" + p.relative_to(root).as_posix(), str(p), "DATA")
               for p in sorted(root.rglob("*")) if p.is_file()]
    report = inv.classify(entries, "linux", owners={}, stdlib_roots=[], pyinstaller_root="")
    assert report.uncovered == [], inv.format_uncovered(report)
    assert {"sphinx", "sphinx-rtd-theme", "jquery", "snowball-stemmers", "pygments", "font-awesome", "lato",
            "roboto-slab", "chord-notepad-guide"} <= set(report.covered)


# --- The build-time check (chord-notepad.spec) --------------------------------

def test_fluidsynth_dlls_takes_only_the_listed_ones(tmp_path):
    names = ["libfluidsynth-3.dll", "libgcc_s_sjlj-1.dll", "libglib-2.0-0.dll", "libgobject-2.0-0.dll",
             "libgomp-1.dll", "libgthread-2.0-0.dll", "libinstpatch-2.dll", "libintl-8.dll",
             "libsndfile-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll", "fluidsynth.exe"]
    for n in names:
        (tmp_path / n).write_bytes(b"")
    picked = sorted(Path(src).name for src, dest in inv.fluidsynth_dlls(str(tmp_path)))
    assert picked == sorted(set(names) - {"libgobject-2.0-0.dll", "libinstpatch-2.dll", "fluidsynth.exe"})
    (tmp_path / "libsndfile-1.dll").unlink()
    with pytest.raises(SystemExit, match="libsndfile"):
        inv.fluidsynth_dlls(str(tmp_path))


def classify(entries, build, **kw):
    kw.setdefault("owners", {})
    kw.setdefault("stdlib_roots", [os.path.normcase("/py")])
    kw.setdefault("pyinstaller_root", os.path.normcase("/site/PyInstaller"))
    kw.setdefault("repo", Path("/repo"))
    return inv.classify(entries, build, **kw)


def test_classify_maps_files_to_components():
    owners = {os.path.normcase("/site/PIL/_imaging.pyd"): "pillow",
              os.path.normcase("/site/pillow.libs/libjpeg.dll"): "pillow"}
    entries = [
        ("fluidsynth\\libfluidsynth-3.dll", "/fs/bin/libfluidsynth-3.dll", "BINARY"),
        ("VCRUNTIME140.dll", "/py/vcruntime140.dll", "BINARY"),
        ("libcrypto-3.dll", "/py/DLLs/libcrypto-3.dll", "BINARY"),
        ("_ssl.pyd", "/py/DLLs/_ssl.pyd", "EXTENSION"),
        ("json", "/py/Lib/json/__init__.py", "PYMODULE"),
        ("PIL._imaging", "/site/PIL/_imaging.pyd", "EXTENSION"),
        ("pillow.libs/libjpeg.dll", "/site/pillow.libs/libjpeg.dll", "BINARY"),
        ("main", "/repo/src/main.py", "PYSOURCE"),
        ("resources/soundfont/GeneralUser-GS.sf2", "/repo/resources/soundfont/GeneralUser-GS.sf2", "DATA"),
        ("resources/icon-32.png", "/repo/resources/icon-32.png", "DATA"),
        ("help/build/html/index.html", "/repo/help/build/html/index.html", "DATA"),
        ("pyi_rth_inspect", "/site/PyInstaller/hooks/rthooks/pyi_rth_inspect.py", "PYSOURCE"),
        ("_tcl_data/init.tcl", "/py/tcl/tcl8.6/init.tcl", "DATA"),
        ("libfoo.so", "libbar.so", "SYMLINK"),
        ("help/build/html/_static/jquery.js", "/repo/help/build/html/_static/jquery.js", "DATA"),
        ("help/build/html/_static/css/fonts/lato-bold.woff2", "/repo/help/build/html/_static/css/fonts/lato-bold.woff2",
         "DATA"),
        ("help/build/html/_static/custom.css", "/repo/help/build/html/_static/custom.css", "DATA"),
    ]
    report = classify(entries, "windows", owners=owners, own_static={"custom.css"})
    assert report.uncovered == []
    assert report.covered["fluidsynth-windows"] == ["fluidsynth/libfluidsynth-3.dll"]
    assert report.covered["msvc-runtime"] == ["VCRUNTIME140.dll"]
    assert report.covered["openssl"] == ["libcrypto-3.dll"]
    assert report.covered["cpython"] == ["_ssl.pyd", "json"]
    assert report.covered["pillow"] == ["PIL._imaging", "pillow.libs/libjpeg.dll"]
    assert report.covered["generaluser-gs"] == ["resources/soundfont/GeneralUser-GS.sf2"]
    assert report.covered["chord-notepad-logo"] == ["resources/icon-32.png"]
    assert report.covered["chord-notepad-guide"] == ["help/build/html/index.html"]
    assert report.covered["chord-notepad"] == ["main", "help/build/html/_static/custom.css"]
    assert report.covered["jquery"] == ["help/build/html/_static/jquery.js"]
    assert report.covered["lato"] == ["help/build/html/_static/css/fonts/lato-bold.woff2"]
    assert report.covered["pyinstaller"] == ["pyi_rth_inspect"]
    assert report.covered["tcl-tk"] == ["_tcl_data/init.tcl"]


def test_classify_reports_what_nothing_covers():
    owners = {os.path.normcase("/site/numpy/__init__.py"): "numpy"}
    entries = [
        ("numpy", "/site/numpy/__init__.py", "PYMODULE"),
        ("libmystery.dll", "/py/DLLs/libmystery.dll", "BINARY"),   # under the stdlib, still needs an entry
        ("fluidsynth/libinstpatch-2.dll", "/fs/libinstpatch-2.dll", "BINARY"),
        ("jeepney", "/site/jeepney/__init__.py", "PYMODULE"),
        # A file the next Sphinx or theme release adds is not the app's, though it lies under the repository
        ("help/build/html/_static/new-widget.js", "/repo/help/build/html/_static/new-widget.js", "DATA"),
    ]
    owners[os.path.normcase("/site/jeepney/__init__.py")] = "jeepney"
    report = classify(entries, "windows", owners=owners, own_static={"custom.css"})
    assert [u[0] for u in report.uncovered] == [e[0] for e in entries]
    assert "numpy" in inv.format_uncovered(report)
    assert classify(entries[3:4], "linux", owners=owners).uncovered == []  # jeepney is Linux-only


def test_classify_lists_system_packages_on_linux():
    pkg = inv.SystemPackage("libglib2.0-0t64", "2.80.0-6", "glib2.0", "2.80.0-6", "LGPL-2.1+", [])
    entries = [("libglib-2.0.so.0", "/usr/lib/x86_64-linux-gnu/libglib-2.0.so.0", "BINARY"),
               ("libgthread-2.0.so.0", "/usr/lib/x86_64-linux-gnu/libgthread-2.0.so.0", "BINARY"),
               ("libweird.so", "/opt/libweird.so", "BINARY")]
    report = classify(entries, "linux", resolve_system=lambda p: pkg if "/usr/lib/" in p else None)
    assert list(report.system) == ["libglib2.0-0t64"]
    assert report.system["libglib2.0-0t64"].files == ["libglib-2.0.so.0", "libgthread-2.0.so.0"]
    assert [u[0] for u in report.uncovered] == ["libweird.so"]


def test_system_notices_round_trip_into_the_catalog(tmp_path):
    copyright_file = tmp_path / "copyright"
    copyright_file.write_text("Format: dep5\n\nFiles: *\nLicense: LGPL-2.1+\n\nLicense: LGPL-2.1+\n text\n")
    pkg = inv.SystemPackage("libglib2.0-0t64", "2.80.0-6", "glib2.0", "2.80.0-6",
                            inv._dep5_licenses(copyright_file.read_text()), [str(copyright_file)],
                            files=["libglib-2.0.so.0"])
    out = tmp_path / "licenses"
    datas = inv.write_system_notices({pkg.name: pkg}, out)
    assert ("resources/licenses" in {d for _, d in datas}) and len(datas) == 2
    entries = cat.parse_system_packages(json.loads((out / "system.json").read_text()), out)
    assert [(e.id, e.version, e.license, e.group) for e in entries] == [
        ("system:libglib2.0-0t64", "2.80.0-6", "LGPL-2.1+", "system")]
    assert "License: LGPL-2.1+" in cat.LicenceCatalog.text_of(entries[0])


def test_excluded_modules_are_not_needed_by_the_app():
    """Import every app module with the PyInstaller excludes made unimportable."""
    script = textwrap.dedent(f"""
        import importlib, pkgutil, sys
        BLOCKED = {sorted(set(inv.PYINSTALLER_EXCLUDES) - {"setuptools", "pkg_resources", "_distutils_hack"})!r}
        # As if not installed: import raises ImportError, find_spec returns None.
        for name in BLOCKED:
            sys.modules[name] = None
        src = {str(REPO / "src")!r}
        sys.path.insert(0, src)
        names = [m.name for m in pkgutil.walk_packages([src])]
        failures = []
        for name in sorted(set(names)) + ["mido", "music21.harmony", "music21.chord", "PIL.ImageTk", "requests"]:
            try:
                importlib.import_module(name)
            except Exception as exc:
                failures.append(f"{{name}}: {{type(exc).__name__}}: {{exc}}")
        from chord.helper import ChordHelper
        loaded = sorted(m for m, mod in sys.modules.items() if mod is not None and m.split(".")[0] in BLOCKED)
        print("\\n".join(failures + [f"loaded: {{m}}" for m in loaded]))
        sys.exit(1 if failures or loaded else 0)
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=300,
                            env={**os.environ, "PYTHONPATH": ""})
    assert result.returncode == 0, result.stdout + result.stderr


# --- The loader behind the Licences window ------------------------------------

@pytest.mark.parametrize("build", inv.BUILDS)
def test_catalog_lists_the_components_of_each_build(build):
    catalog = cat.load_catalog(LICENSES, build)
    assert {e.id for e in catalog.entries} == {c["id"] for c in COMPONENTS if build in c["builds"]}
    assert catalog.entries[0].id == "chord-notepad"
    groups = [g for g, _, _ in catalog.groups()]
    assert groups == [g for g in cat.GROUPS if g in groups]
    for entry in catalog.entries:
        text = catalog.text_of(entry)
        assert len(text) > 100 and "[Licence text not found" not in text, entry.id
    assert "third-party-sources.tar" in catalog.source_offer


def test_catalog_from_source_lists_everything_and_fills_runtime_versions():
    catalog = cat.load_catalog(LICENSES, None)
    assert len(catalog.entries) == len(COMPONENTS)
    import platform
    assert catalog.get("cpython").version == platform.python_version()
    app_text = catalog.text_of(catalog.get("chord-notepad"))
    assert app_text.index("GNU AFFERO GENERAL PUBLIC LICENSE") < app_text.index("section 7")
    assert cat.TEXT_SEPARATOR in app_text


def test_windows_list_has_the_fluidsynth_package_and_not_the_flatpak_one():
    ids = {e.id for e in cat.load_catalog(LICENSES, "windows").entries}
    assert {"fluidsynth-windows", "glib-windows", "libsndfile-windows", "gcc-runtime-windows"} <= ids
    assert "fluidsynth-flatpak" not in ids and "jeepney" not in ids
    flatpak = {e.id for e in cat.load_catalog(LICENSES, "flatpak").entries}
    assert "fluidsynth-flatpak" in flatpak and "cpython" not in flatpak and "fluidsynth-windows" not in flatpak


def test_missing_text_shows_a_placeholder(tmp_path):
    entry = cat.LicenceEntry("x", "X", None, "data", "MIT", text_paths=(str(tmp_path / "nope.txt"),))
    assert "Licence text not found: nope.txt" in cat.LicenceCatalog.text_of(entry)


def test_bad_group_and_duplicate_ids_are_errors(tmp_path):
    (tmp_path / "texts").mkdir()
    data = {"components": [{"id": "a", "name": "A", "group": "app", "license": "MIT", "texts": [], "builds": []}]}
    (tmp_path / "components.json").write_text(json.dumps({"components": data["components"] * 2}))
    with pytest.raises(ValueError, match="duplicate"):
        cat.load_catalog(tmp_path)
    data["components"][0]["group"] = "nonsense"
    (tmp_path / "components.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown group"):
        cat.load_catalog(tmp_path)


# Shaped like snapcraft's snap/manifest.yaml (SNAPCRAFT_BUILD_INFO=1): each
# part repeats its stage-packages and lists the build container's packages.
SNAP_MANIFEST = """\
snapcraft-version: 8.12.1
snapcraft-started-at: '2026-10-30T21:14:03.118263Z'
snapcraft-os-release-id: ubuntu
snapcraft-os-release-version-id: '26.04'
name: chord-notepad
version: 0.4.1
summary: A text editor for musicians
base: core26
grade: stable
confinement: strict
apps:
  chord-notepad:
    command: bin/chord-notepad
    plugs:
    - x11
parts:
  audio:
    plugin: nil
    stage-packages:
    - libfluidsynth3=2.5.1-1
    - libpulse0=1:17.0-1
    stage: []
    prime: []
    build-packages: []
    uname: Linux 6.8.0-1017-azure #20-Ubuntu SMP x86_64 GNU/Linux
    installed-packages:
    - adduser=3.137ubuntu1
    - apt=3.1.6ubuntu2
    - libc6=2.42-0ubuntu3
    - libglib2.0-0t64=2.86.0-2
    installed-snaps:
    - core26=1234
    - snapcraft=8.12.1
  chord-notepad:
    plugin: python
    stage-packages: []
    build-packages:
    - findutils=4.10.0-3
    - python3-dev=3.14.0-1
    installed-packages:
    - adduser=3.137ubuntu1
    - gcc-15=15.2.0-4ubuntu1
architectures:
- amd64
build-packages: []
build-snaps: []
primed-stage-packages:
- libfluidsynth3=2.5.1-1
- libglib2.0-0t64:amd64=2.86.0-2ubuntu1
- libpulse0=1:17.0-1
image-info:
  build-request-id: lp-123
"""


def test_snap_manifest_lists_only_the_primed_stage_packages(tmp_path):
    """Not the build container's packages (installed-packages, build-packages)."""
    expected = [("libfluidsynth3", "2.5.1-1"), ("libglib2.0-0t64", "2.86.0-2ubuntu1"), ("libpulse0", "1:17.0-1")]
    assert cat.primed_stage_packages(SNAP_MANIFEST) == expected
    import make_source_bundle

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(SNAP_MANIFEST)
    assert make_source_bundle.snap_packages(manifest) == expected
    assert cat.primed_stage_packages("primed-stage-packages: []\nparts: {}\n") == []
    assert cat.primed_stage_packages("parts:\n  a:\n    primed-stage-packages:\n    - x=1\n") == []
    assert cat.primed_stage_packages(SNAP_MANIFEST.replace("primed-stage-packages:\n", "primed:\n")) == []


def test_snap_packages_come_from_their_copyright_files(tmp_path):
    for name, licence in (("libfluidsynth3", "LGPL-2.1+"), ("libpulse0", "LGPL-2.1+")):
        doc = tmp_path / "usr/share/doc" / name
        doc.mkdir(parents=True)
        (doc / "copyright").write_text(f"Files: *\nLicense: {licence}\n\nFiles: x\nLicense: MIT\n")
    (tmp_path / "snap").mkdir()
    (tmp_path / "snap/manifest.yaml").write_text(SNAP_MANIFEST)
    entries = cat.snap_packages(tmp_path)
    assert [(e.name, e.version, e.license) for e in entries] == [
        ("libfluidsynth3", "2.5.1-1", "LGPL-2.1+ / MIT"), ("libpulse0", "1:17.0-1", "LGPL-2.1+ / MIT")]
    catalog = cat.load_catalog(LICENSES, "snap", snap_root=tmp_path)
    assert catalog.get("system:libfluidsynth3").group == "system"
    assert catalog.groups()[-1][0] == "system"


def test_detect_build():
    assert cat.detect_build({"FLATPAK_ID": "x"}, "linux", True, "/nonexistent") == "flatpak"
    assert cat.detect_build({"SNAP": "/snap/x/1", "SNAP_NAME": "chord-notepad"}, "linux", False,
                            "/nonexistent") == "snap"
    assert cat.detect_build({}, "win32", True, "/nonexistent") == "windows"
    assert cat.detect_build({}, "darwin", True, "/nonexistent") == "macos"
    assert cat.detect_build({}, "linux", True, "/nonexistent") == "linux"
    assert cat.detect_build({}, "linux", False, "/nonexistent") is None


def test_bundled_resources_reach_the_flatpak_and_snap():
    """Both copy resources/ wholesale, so the window finds its data there too."""
    assert "cp -r resources ${FLATPAK_DEST}/share/chord-notepad/" in (
        REPO / "packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml").read_text()
    assert re.search(r"cp -r src resources examples VERSION", (REPO / "snap/snapcraft.yaml").read_text())


def test_session_hands_out_the_catalog():
    """The Tk window gets the list through the session (tests/test_main_window_guard.py)."""
    from session.session import AppSession

    catalog = AppSession.licence_catalog(None, str(REPO))  # uses no session state
    assert catalog.get("chord-notepad") is not None


def test_malformed_components_are_value_errors(tmp_path):
    """The Licences window shows an error for ValueError (main_window.show_licences), not a traceback."""
    (tmp_path / "texts").mkdir()
    good = {"id": "a", "name": "A", "group": "app", "license": "MIT", "texts": [], "builds": []}
    for broken in ({k: v for k, v in good.items() if k != "name"}, {**good, "license": ""},
                   {k: v for k, v in good.items() if k != "id"}, {**good, "texts": "MIT"}, "a string"):
        with pytest.raises(ValueError):
            cat.parse_components({"components": [broken]}, tmp_path / "texts", None)
    for data in ({}, {"components": {}}, []):
        with pytest.raises(ValueError):
            cat.parse_components(data, tmp_path / "texts", None)
    (tmp_path / "components.json").write_text(json.dumps({"components": [{"id": "a", "group": "app"}]}))
    with pytest.raises(ValueError, match="missing name, license"):
        cat.load_catalog(tmp_path)


def test_resolve_dpkg_survives_an_unreadable_copyright_file(monkeypatch):
    def run(*args):
        if args[1] == "-S":
            return "zlib1g:amd64: /usr/lib/x86_64-linux-gnu/libz.so.1"
        return "zlib1g\t1:1.3.dfsg-3\tzlib\t1:1.3.dfsg-3"

    class Unreadable(type(Path())):
        def is_file(self):
            return True

        def read_text(self, *args, **kwargs):
            raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(inv, "_run", run)
    monkeypatch.setattr(inv, "Path", Unreadable)
    pkg = inv.resolve_dpkg("/usr/lib/x86_64-linux-gnu/libz.so.1")
    assert (pkg.name, pkg.source_name, pkg.license, pkg.licence_files) == ("zlib1g", "zlib", "Unknown", [])


def test_source_bundle_fetches_only_gpl_family_ubuntu_sources(tmp_path, monkeypatch):
    import make_source_bundle as msb

    assert msb.wants_source({"LGPL-2.1+"}) and msb.wants_source({"BSD-3-clause / GPL-2+"})
    assert msb.wants_source({"GPL-3.0-or-later"}) and msb.wants_source({"LGPL-2.1-only"})
    assert msb.wants_source({"GPL (free-form copyright file)"}) and msb.wants_source({None, "MIT"})
    assert not msb.wants_source({"MIT", "Expat / BSD-3-clause"}) and not msb.wants_source({"AGPL-3+"})
    assert not msb.wants_source({"PSF-2.0 / GFDL-1.2+"})
    assert msb.copyright_licences("Files: *\nLicense: LGPL-2.1+\n\nLicense: LGPL-2.1+\n text\n") == "LGPL-2.1+"
    assert msb.copyright_licences("This package is under the GNU Lesser General Public License.") is not None
    assert msb.copyright_licences("Copyright 2001 X. Permission is hereby granted, free of charge") is None

    system = tmp_path / "system.json"
    system.write_text(json.dumps({"packageFormat": "deb", "packages": [
        {"name": "libglib2.0-0t64", "version": "2.80.0-6", "sourcePackage": "glib2.0", "sourceVersion": "2.80.0-6",
         "license": "LGPL-2.1+ / Expat"},
        {"name": "libexpat1", "version": "2.6.1-2", "sourcePackage": "expat", "sourceVersion": "2.6.1-2",
         "license": "MIT"}]}))
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(SNAP_MANIFEST)
    docs = tmp_path / "doc"
    for name, text in (("libfluidsynth3", "License: LGPL-2.1+\n"), ("libpulse0", "License: LGPL-2.1+\n")):
        (docs / name).mkdir(parents=True)
        (docs / name / "copyright").write_text(text)
    monkeypatch.setattr(msb, "ubuntu_source_of", lambda binary, version: (binary.split(":")[0] + "-src", version))
    items = {i["source"]: i for i in msb.ubuntu_packages([system], [manifest], docs)}
    assert set(items) == {"glib2.0", "expat", "libfluidsynth3-src", "libglib2.0-0t64-src", "libpulse0-src"}
    wanted = sorted(s for s, i in items.items() if msb.wants_source(i["licences"]))
    # libglib2.0-0t64 has no copyright file in the snap: unknown licence, fetched to be safe
    assert wanted == ["glib2.0", "libfluidsynth3-src", "libglib2.0-0t64-src", "libpulse0-src"]
    assert items["expat"]["licences"] == {"MIT"} and items["libpulse0-src"]["builds"] == {"snap"}


ANDROID_TEXTS = REPO / "android/app/src/main/assets/licenses/texts"


@pytest.mark.parametrize("copy, original", [
    ("AGPL-3.0.txt", "LICENSE"),
    ("ADDITIONAL-TERMS.txt", "ADDITIONAL-TERMS.txt"),
    ("ARTWORK-TERMS.txt", "ARTWORK-TERMS.txt"),
    ("help-LICENSE.txt", "help/LICENSE"),
])
def test_licence_copies_are_the_repository_files_byte_for_byte(copy, original):
    """The Android app and the desktop builds show these, so they must be exactly the files at the root."""
    assert (ANDROID_TEXTS / copy).read_bytes() == (REPO / original).read_bytes(), (
        f"android/.../texts/{copy}: run android/tools/gather_licenses.py")
    assert (LICENSES / "texts" / copy).read_bytes() == (REPO / original).read_bytes(), (
        f"resources/licenses/texts/{copy}: run packaging/licenses/gather_texts.py")


@pytest.mark.parametrize("dest", ["Tcl", "Tk", "Tcl.framework/Versions/9.0/Tcl", "_tk_data/tk.tcl"])
def test_macos_tcl_tk_frameworks_are_covered(dest):
    """python.org's macOS Python bundles Tcl and Tk as frameworks named plain Tcl and Tk."""
    assert inv.match(dest, BY_ID["tcl-tk"]["files"])
