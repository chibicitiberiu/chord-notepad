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
