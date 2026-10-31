"""Windowed builds start without stdout/stderr (utils/std_streams.py)."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# A windowed build as the app sees it: no std streams, and numpy/matplotlib
# left out, so music21 warns on stderr while it's imported.
SCRIPT = textwrap.dedent(f"""
    import sys
    sys.path.insert(0, {str(SRC)!r})
    for name in ("numpy", "matplotlib"):
        sys.modules[name] = None
    out = sys.stdout
    sys.stdout = sys.stderr = None
    if sys.argv[1] == "fixed":
        from utils.std_streams import ensure_std_streams
        ensure_std_streams()
    try:
        import music21  # noqa: F401
    except Exception as exc:
        out.write(f"{{type(exc).__name__}}: {{exc}}")
        sys.exit(1)
""")


def run(mode: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", SCRIPT, mode], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "PYTHONPATH": ""})


def test_music21_crashes_a_windowed_build_without_the_fix():
    result = run("plain")
    assert result.returncode == 1 and "'write'" in result.stdout, result.stdout + result.stderr


def test_ensure_std_streams_lets_music21_import():
    result = run("fixed")
    assert result.returncode == 0, result.stdout + result.stderr


def test_ensure_std_streams_keeps_existing_streams():
    from utils.std_streams import ensure_std_streams

    out, err = sys.stdout, sys.stderr
    ensure_std_streams()
    assert sys.stdout is out and sys.stderr is err


def test_ensure_std_streams_fills_missing_ones(monkeypatch):
    from utils.std_streams import ensure_std_streams

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_std_streams()
    try:
        assert sys.stdout is not None and sys.stderr is not None
        sys.stderr.write("discarded")
    finally:
        sys.stdout.close()
        sys.stderr.close()
