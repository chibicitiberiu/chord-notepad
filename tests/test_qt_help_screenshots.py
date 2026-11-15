"""The Qt screenshot tool (packaging/tools/qt_help_screenshots.py).

It starts the real Qt window offscreen, so these run in a child process and
skip where Qt isn't available. Two runs of one shot must give the same bytes
(the images are committed, so a regeneration must not churn them), and every
committed light image has its dark twin.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "packaging" / "tools" / "qt_help_screenshots.py"


def load_tool():
    """The tool as a module (its shot list; nothing of Qt is imported)."""
    spec = importlib.util.spec_from_file_location("qt_help_screenshots", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module      # dataclasses look their module up
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def run_tool(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                          timeout=120)


def test_the_shot_list_names_every_image():
    result = run_tool("--list")
    assert result.returncode == 0, result.stderr
    names = {line.split()[0] for line in result.stdout.splitlines()}
    # What the desktop guide and the Quick Start refer to.
    assert {"editor-main-window", "main-window-labeled", "chord_sheet_qt"} <= names


def test_an_unknown_shot_is_refused():
    result = run_tool("--only", "no-such-shot")
    assert result.returncode != 0 and "no-such-shot" in result.stderr


@pytest.mark.skipif(QT_PROBLEM is not None, reason=f"Qt not available: {QT_PROBLEM}")
def test_a_shot_has_the_fixed_size_and_is_the_same_every_time(tmp_path):
    from PIL import Image

    first, second = tmp_path / "a", tmp_path / "b"
    for out in (first, second):
        result = run_tool("--only", "editor-main-window", "--out", str(out))
        assert result.returncode == 0, result.stderr
    for name in ("editor-main-window.png", "editor-main-window.dark.png"):  # both themes
        one, two = first / name, second / name
        assert Image.open(one).size == (1280, 800)
        assert one.read_bytes() == two.read_bytes(), name
    # Not the same picture twice: the dark one is darker.
    light, dark = (Image.open(first / n).convert("L") for n in ("editor-main-window.png",
                                                                  "editor-main-window.dark.png"))
    assert sum(dark.getdata()) < sum(light.getdata()) / 2


def test_the_images_are_named_per_theme():
    tool = load_tool()
    images = tool.images()
    assert images["editor-main-window.dark"][1] == "dark"
    assert images["chord_sheet_qt.dark"][1] == "dark"
    assert images["04-play-staff-dark"][1] == "dark"     # the store's dark names end in -dark
    assert images["04-play-staff"][1] == "light"
    assert len(images) == 2 * len(tool.SHOTS)


def test_every_committed_image_has_its_dark_twin():
    tool = load_tool()
    folders = {"help": tool.HELP_OUT, "store": tool.STORE_OUT, "quickstart": tool.QUICK_START_OUT}
    missing = [f"{folders[shot.dest].relative_to(REPO)}/{name}.png"
               for name, (shot, _) in tool.images().items()
               if not (folders[shot.dest] / f"{name}.png").is_file()]
    assert missing == []
    # And nothing in the help's folder that the tool doesn't make (a stale name).
    made = {f"{name}.png" for name, (shot, _) in tool.images().items() if shot.dest == "help"}
    assert {p.name for p in tool.HELP_OUT.glob("*.png")} == made
