"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from hypothesis import settings
from chord.detector import ChordDetector
from services.song_parser_service import SongParserService
from models.notation import Notation

# Hypothesis: disable per-example deadlines globally so CI runner variance does
# not produce spurious flakes. Random exploration is preserved so the fuzz tests
# keep finding new bugs across runs.
settings.register_profile("default", deadline=None)
settings.load_profile("default")


# Long fuzz and exhaustive grids (transpose, notation conversion) run on
# demand, not in CI: `make fuzz`, or `pytest --fuzz`.
def pytest_addoption(parser):
    parser.addoption("--fuzz", action="store_true",
                     help="also run the long fuzz and exhaustive tests (marked 'fuzz')")


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
    from session import testing

    testing.BRIDGE_FAILURES.clear()
    yield
    failures = list(testing.BRIDGE_FAILURES)
    testing.BRIDGE_FAILURES.clear()
    assert not failures, f"session outputs that can't cross the bridge: {failures}"
