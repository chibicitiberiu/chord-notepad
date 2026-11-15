"""The Qt screenshot tool (packaging/tools/qt_help_screenshots.py).

It starts the real Qt window offscreen, so these run in a child process and
skip where Qt isn't available. Two runs of one shot must give the same bytes
(the images are committed, so a regeneration must not churn them).
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import QT_PROBLEM

TOOL = Path(__file__).resolve().parents[1] / "packaging" / "tools" / "qt_help_screenshots.py"


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
    one, two = (first / "editor-main-window.png"), (second / "editor-main-window.png")
    assert Image.open(one).size == (1280, 800)
    assert one.read_bytes() == two.read_bytes()
