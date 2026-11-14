"""Where the app's files are: ``AppPaths`` and the desktop resolver.

Before ``AppPaths`` several modules walked a fixed number of folders up from
their own ``__file__`` to find VERSION, the SoundFont or the licences. Moving
the code to another folder would have broken that without an error (VERSION
read as "0.0", no SoundFont until audio starts), so the front end now
resolves the paths once and passes them down, and the guard at the end keeps
the core from walking up again.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

from chordnotepad.app_paths import NO_BUNDLED_FILES, UNKNOWN_VERSION, AppPaths
from chordnotepad_tk import desktop_paths
from chordnotepad_tk.desktop_paths import (
    FLATPAK_APP_ID, INSTALL_SUBDIR, SNAP_NAME, paths_under, resolve_desktop_paths)

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "core" / "chordnotepad"
DESKTOP = REPO / "desktop" / "chordnotepad_tk"


@pytest.fixture
def not_frozen(monkeypatch):
    """No PyInstaller bundle, whatever the test runner's interpreter is."""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)


@pytest.fixture
def checkout(not_frozen) -> AppPaths:
    """The resolver's answer when running from this checkout."""
    return resolve_desktop_paths(env={})


# ---------------------------------------------------------------------------
# Running from source: every file the app needs is found
# ---------------------------------------------------------------------------

def test_checkout_root_is_this_repo(checkout):
    assert desktop_paths.CHECKOUT_ROOT == REPO
    assert checkout.root == REPO


def test_checkout_finds_the_bundled_files(checkout):
    assert checkout.version_file.is_file()
    assert checkout.resources.is_dir()
    assert checkout.soundfont.is_file()
    assert checkout.soundfont.name == "GeneralUser-GS.sf2"
    assert (checkout.licenses / "components.json").is_file()
    assert checkout.quickstart.is_dir()
    assert any(checkout.quickstart.glob("*.png"))
    assert (checkout.resources / "icon-32.png").is_file()


def test_checkout_finds_the_built_help(checkout):
    if not (REPO / "help" / "build" / "html").is_dir():
        pytest.skip("help not built (make docs-html)")
    assert (checkout.help_html / "index.html").is_file()


def test_checkout_reads_the_real_version(checkout):
    expected = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert checkout.read_version() == expected
    assert checkout.read_version() != UNKNOWN_VERSION


def test_build_info_has_the_real_version():
    import importlib

    from chordnotepad_tk import build_info
    importlib.reload(build_info)
    assert build_info.BASE_VERSION == (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert build_info.BASE_VERSION != UNKNOWN_VERSION


def test_checkout_has_the_dev_dll_folder(checkout):
    assert checkout.dev_dll_dir == REPO / ".tools" / "bin"


def test_licence_catalog_loads_from_the_resolved_folder(checkout):
    from chordnotepad.services.licence_catalog import load_for_this_app

    assert load_for_this_app(checkout.licenses).get("chord-notepad") is not None


def test_resource_service_joins_onto_the_root(checkout):
    from chordnotepad.services.resource_service import ResourceService

    resources = ResourceService(checkout)
    assert Path(resources.get_resource_path("resources/icon-32.png")).is_file()
    assert resources.paths is checkout
    with pytest.raises(ValueError):
        ResourceService(NO_BUNDLED_FILES)


# ---------------------------------------------------------------------------
# The bundles: PyInstaller, Flatpak, snap
# ---------------------------------------------------------------------------

def _expect_layout(paths: AppPaths, root: Path) -> None:
    assert paths.root == root
    assert paths.version_file == root / "VERSION"
    assert paths.resources == root / "resources"
    assert paths.soundfont == root / "resources" / "soundfont" / "GeneralUser-GS.sf2"
    assert paths.licenses == root / "resources" / "licenses"
    assert paths.quickstart == root / "resources" / "quickstart"
    assert paths.help_html == root / "help" / "build" / "html"
    assert paths.dev_dll_dir is None


def test_pyinstaller_bundle(monkeypatch, tmp_path):
    (tmp_path / "VERSION").write_text("9.8.7\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    paths = resolve_desktop_paths(env={})
    _expect_layout(paths, tmp_path)
    assert paths.read_version() == "9.8.7"


def test_pyinstaller_wins_over_the_sandbox_variables(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    env = {"FLATPAK_ID": FLATPAK_APP_ID, "SNAP": "/snap/x/1", "SNAP_NAME": SNAP_NAME}
    assert resolve_desktop_paths(env=env).root == tmp_path


def test_flatpak(not_frozen, tmp_path):
    paths = resolve_desktop_paths(env={"FLATPAK_ID": FLATPAK_APP_ID}, flatpak_prefix=tmp_path)
    _expect_layout(paths, tmp_path / "share" / "chord-notepad")


def test_snap(not_frozen, tmp_path):
    paths = resolve_desktop_paths(env={"SNAP": str(tmp_path), "SNAP_NAME": SNAP_NAME})
    _expect_layout(paths, tmp_path / "share" / "chord-notepad")


def test_another_apps_sandbox_is_still_the_checkout(not_frozen, tmp_path):
    """A checkout run from a terminal inside another Flatpak or snap (an IDE)."""
    for env in ({"FLATPAK_ID": "com.visualstudio.code"},
                {"SNAP": str(tmp_path), "SNAP_NAME": "code"}):
        assert resolve_desktop_paths(env=env, flatpak_prefix=tmp_path).root == REPO


def test_a_missing_version_file_reads_as_unknown(tmp_path):
    assert paths_under(tmp_path).read_version() == UNKNOWN_VERSION
    assert NO_BUNDLED_FILES.read_version() == UNKNOWN_VERSION
    assert NO_BUNDLED_FILES.licenses is None and NO_BUNDLED_FILES.quickstart is None


def test_the_resolver_matches_the_packaging():
    """The ids and install folders are the ones the manifests use."""
    manifest = (REPO / "packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml").read_text()
    assert re.search(rf"^app-id: {re.escape(FLATPAK_APP_ID)}$", manifest, re.M)
    assert f"${{FLATPAK_DEST}}/{INSTALL_SUBDIR.as_posix()}" in manifest
    launcher = (REPO / "packaging/flatpak/chord-notepad.sh").read_text()
    assert f"{desktop_paths.FLATPAK_PREFIX.as_posix()}/{INSTALL_SUBDIR.as_posix()}/" in launcher

    snapcraft = (REPO / "snap/snapcraft.yaml").read_text()
    assert re.search(rf"^name: {re.escape(SNAP_NAME)}$", snapcraft, re.M)
    assert f'app="$CRAFT_PART_INSTALL/{INSTALL_SUBDIR.as_posix()}"' in snapcraft
    assert f"$SNAP/{INSTALL_SUBDIR.as_posix()}/" in (REPO / "packaging/snap/chord-notepad.sh").read_text()


def test_the_resolver_matches_the_pyinstaller_spec(tmp_path):
    """The spec bundles each file where :func:`paths_under` looks for it."""
    spec = (REPO / "chord-notepad.spec").read_text()
    datas = dict(re.findall(r"\('([^']+)',\s*'([^']+)'\)", spec))
    paths = paths_under(tmp_path)
    rel = {name: getattr(paths, name).relative_to(tmp_path).as_posix()
           for name in ("soundfont", "licenses", "quickstart", "help_html")}
    assert datas[rel["soundfont"]] == Path(rel["soundfont"]).parent.as_posix()
    for name in ("licenses", "quickstart", "help_html"):
        assert datas[rel[name]] == rel[name]


def test_the_pyinstaller_spec_bundles_the_version_file(tmp_path):
    """VERSION lands at the bundle's root, where the resolver reads it; without
    it a local build says "v0.0" (CI's build_info.py hides that in releases)."""
    spec = (REPO / "chord-notepad.spec").read_text()
    datas = dict(re.findall(r"\('([^']+)',\s*'([^']+)'\)", spec))
    rel = paths_under(tmp_path).version_file.relative_to(tmp_path).as_posix()
    assert rel == "VERSION"
    assert datas[rel] == "."


# ---------------------------------------------------------------------------
# The SoundFont reaches playback
# ---------------------------------------------------------------------------

def _service_over(paths: AppPaths, configured=None):
    from unittest.mock import Mock

    from chordnotepad.services.playback_service import PlaybackService

    config = Mock()
    config.get.side_effect = lambda key, default=None: (
        configured if key == "soundfont_path" else default)
    return PlaybackService(
        config, bundled_soundfont=str(paths.soundfont) if paths.soundfont else None)


def _soundfont_passed(service) -> object:
    from unittest.mock import MagicMock, patch

    with patch("chordnotepad.services.playback_service.NotePlayer", return_value=MagicMock()) as cls:
        assert service.initialize_player()
    return cls.call_args.kwargs["soundfont_path"]


def test_playback_falls_back_to_the_bundled_soundfont(checkout):
    assert _soundfont_passed(_service_over(checkout)) == str(checkout.soundfont)


def test_the_settings_soundfont_wins(checkout):
    assert _soundfont_passed(_service_over(checkout, configured="/mine.sf2")) == "/mine.sf2"


def test_a_missing_bundled_soundfont_is_not_passed(tmp_path):
    """NotePlayer then says "No soundfont found. Choose one in Settings.", as before."""
    assert _soundfont_passed(_service_over(paths_under(tmp_path))) is None
    assert _soundfont_passed(_service_over(NO_BUNDLED_FILES)) is None


def test_core_services_carry_the_paths(checkout, tmp_path):
    from chordnotepad.services.appdata_service import AppDataService
    from chordnotepad.session.bootstrap import build_core_services
    from chordnotepad.session.host import HostDispatch
    from chordnotepad.session.testing import FakePlayer, ManualHost

    services = build_core_services(AppDataService(root=tmp_path), HostDispatch(ManualHost()),
                                   paths=checkout, player=FakePlayer())
    assert services.paths is checkout
    assert services.playback._bundled_soundfont == str(checkout.soundfont)


# ---------------------------------------------------------------------------
# The entry points pass their paths (the default is for tests only)
# ---------------------------------------------------------------------------

def _keywords_of_calls(path: Path, func_name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and getattr(node.func, "id", getattr(node.func, "attr", None)) == func_name]
    return [{kw.arg for kw in call.keywords} for call in calls]


@pytest.mark.parametrize("entry", [
    DESKTOP / "application.py",
    REPO / "android/app/src/main/python/chordnotepad_android/host.py",
])
def test_front_ends_pass_their_paths_to_the_core(entry):
    calls = _keywords_of_calls(entry, "build_core_services")
    assert calls, f"{entry.name} no longer builds the core services"
    assert all("paths" in keywords for keywords in calls), (
        f"{entry.name} must pass paths= to build_core_services (the default has no files)")


def test_main_resolves_the_paths_and_hands_them_to_the_application():
    source = (DESKTOP / "main.py").read_text(encoding="utf-8")
    assert "APP_PATHS = resolve_desktop_paths()" in source
    assert "Application.main(APP_PATHS)" in source


# ---------------------------------------------------------------------------
# Guard: the core never walks up from its own __file__
# ---------------------------------------------------------------------------

_PATH_WRAPPERS = {"Path", "PurePath", "abspath", "realpath", "normpath", "fspath", "str",
                  "resolve", "absolute"}


def _call_name(node: ast.AST):
    func = node.func if isinstance(node, ast.Call) else None
    return getattr(func, "id", getattr(func, "attr", None))


def _hops_up(node: ast.AST, parents: dict) -> int:
    """How many folders up from the module's own file an expression goes.

    ``Path(__file__)`` is 0, ``Path(__file__).parent`` (the module's own
    folder) is 1, ``.parent.parent`` or ``.parents[1]`` is 2.
    """
    hops = 0
    while node in parents:
        parent = parents[node]
        if isinstance(parent, ast.Call) and node is not parent.func:
            name = _call_name(parent)
            if name == "dirname":
                hops += 1
            elif name not in _PATH_WRAPPERS:
                break
        elif isinstance(parent, ast.Call):
            pass  # the call of .resolve() / .absolute()
        elif isinstance(parent, ast.Attribute):
            if parent.attr == "parent":
                hops += 1
            elif parent.attr == "parents":
                sub = parents.get(parent)
                index = getattr(getattr(sub, "slice", None), "value", None)
                if not isinstance(sub, ast.Subscript) or not isinstance(index, int):
                    return 99
                hops += index + 1
                parent = sub
            elif parent.attr not in _PATH_WRAPPERS:
                break
        else:
            break
        node = parent
    return hops


def _violations(source: str) -> list:
    """Each line where ``source`` reaches outside its own package."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = []
    uses_file = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__file__":
            uses_file = True
            if _hops_up(node, parents) > 1:
                found.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "_MEIPASS":
            found.append(node.lineno)
        elif isinstance(node, ast.Constant) and node.value == "_MEIPASS":
            found.append(node.lineno)
    if uses_file:
        # A folder taken from __file__ and walked up later, in another statement.
        for lineno, line in enumerate(source.splitlines(), 1):
            if re.search(r"\.parent\.parent|\.parents\[|['\"]\.\.['\"]|dirname\([^)]*dirname\(",
                         line):
                found.append(lineno)
    return sorted(set(found))


@pytest.mark.parametrize("source, bad", [
    ("from pathlib import Path\nX = Path(__file__).parent / 'data.json'\n", False),
    ("import os\nX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'a.png')\n", False),
    ("from pathlib import Path\nX = Path(__file__).resolve().parent.parent / 'VERSION'\n", True),
    ("from pathlib import Path\nX = Path(__file__).parents[2]\n", True),
    ("import os\nX = os.path.dirname(os.path.dirname(__file__))\n", True),
    ("import os\nX = os.path.join(os.path.dirname(__file__), '..', 'resources')\n", True),
    ("from pathlib import Path\nHERE = Path(__file__).parent\nROOT = HERE.parent.parent\n", True),
    ("import sys\nX = getattr(sys, '_MEIPASS', None)\n", True),
    ("import sys\nX = sys._MEIPASS\n", True),
])
def test_the_guard_tells_package_local_from_walking_up(source, bad):
    assert bool(_violations(source)) is bad


def test_no_core_module_walks_up_from_its_own_file():
    # The whole chordnotepad package; only the front ends (desktop/, the
    # Android glue) find files themselves.
    offenders = []
    checked = 0
    for path in sorted(CORE.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if "__pycache__" in rel:
            continue
        checked += 1
        for lineno in _violations(path.read_text(encoding="utf-8")):
            offenders.append(f"{rel}:{lineno}")
    assert checked > 100
    assert not offenders, (
        "These core modules find files from their own location; take the path from "
        "AppPaths (core/chordnotepad/app_paths.py) instead:\n  " + "\n  ".join(offenders))
