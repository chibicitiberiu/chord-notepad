"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import pytest
from chord.detector import ChordDetector
from services.song_parser_service import SongParserService
from models.notation import Notation


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
