"""Pytest configuration and fixtures."""

import pytest
from hypothesis import settings
from chordnotepad.chord.detector import ChordDetector
from chordnotepad.services.song_parser_service import SongParserService
from chordnotepad.models.notation import Notation

# Hypothesis: disable per-example deadlines globally so CI runner variance does
# not produce spurious flakes. Random exploration is preserved so the fuzz tests
# keep finding new bugs across runs.
settings.register_profile("default", deadline=None)
settings.load_profile("default")


def _qt_problem():
    """Why the Qt front end's tests (tests/qt) can't run here, or None.

    PySide6 and pytest-qt are dev packages. PySide6's QtGui also needs a few
    system libraries (libEGL, libGL, libxkbcommon, fontconfig); a machine
    without them fails the import with ImportError, not ModuleNotFoundError.
    """
    try:
        import PySide6.QtGui  # noqa: F401
        import PySide6.QtQuick  # noqa: F401
        import PySide6.QtTest  # noqa: F401
        import PySide6.QtWidgets  # noqa: F401  (pytest-qt imports it)
        import pytestqt.plugin  # noqa: F401
    except ImportError as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


#: None when the Qt tests can run; tests/qt/conftest.py skips them otherwise.
QT_PROBLEM = _qt_problem()


# Long fuzz and exhaustive grids (transpose, notation conversion) run on
# demand, not in CI: `make fuzz`, or `pytest --fuzz`.
def pytest_addoption(parser, pluginmanager):
    parser.addoption("--fuzz", action="store_true",
                     help="also run the long fuzz and exhaustive tests (marked 'fuzz')")
    # pytest-qt imports PySide6's QtGui and QtWidgets as it starts, and stops
    # the whole run when that fails. pytest.ini keeps it from loading by
    # itself (-p no:pytest-qt); it is registered here only when Qt imports,
    # so a machine without Qt still runs everything else.
    if QT_PROBLEM is None:
        pluginmanager.import_plugin("pytestqt.plugin")


def pytest_configure(config):
    config.addinivalue_line("markers", "fuzz: long fuzz/exhaustive test, run with --fuzz")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--fuzz"):
        return
    skip = pytest.mark.skip(reason="long fuzz test: run with --fuzz (make fuzz)")
    for item in items:
        if "fuzz" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def american_detector():
    """Create a ChordDetector with American notation."""
    return ChordDetector(notation='american')


@pytest.fixture
def european_detector():
    """Create a ChordDetector with European notation."""
    return ChordDetector(notation='european')


@pytest.fixture
def song_parser():
    """Create a SongParserService."""
    return SongParserService()


@pytest.fixture(autouse=True)
def _session_output_crosses_the_bridge():
    """Every session output a test recorded must encode for the bridge (DTO purity)."""
    from chordnotepad.session import testing

    testing.BRIDGE_FAILURES.clear()
    yield
    failures = list(testing.BRIDGE_FAILURES)
    testing.BRIDGE_FAILURES.clear()
    assert not failures, f"session outputs that can't cross the bridge: {failures}"
