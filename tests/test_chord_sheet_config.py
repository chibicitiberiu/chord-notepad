"""Round-trip tests for the chord-sheet config fields."""

from models.config import Config


def test_defaults():
    config = Config()
    assert config.chord_sheet_visible is False
    assert config.chord_sheet_view == "name"
    assert config.chord_sheet_height == 160


def test_to_dict_includes_chord_sheet_fields():
    data = Config(
        chord_sheet_visible=True,
        chord_sheet_view="keyboard",
        chord_sheet_height=220,
    ).to_dict()
    assert data["chord_sheet_visible"] is True
    assert data["chord_sheet_view"] == "keyboard"
    assert data["chord_sheet_height"] == 220


def test_from_dict_reads_chord_sheet_fields():
    config = Config.from_dict({
        "chord_sheet_visible": True,
        "chord_sheet_view": "fret",
        "chord_sheet_height": 300,
    })
    assert config.chord_sheet_visible is True
    assert config.chord_sheet_view == "fret"
    assert config.chord_sheet_height == 300


def test_round_trip_preserves_chord_sheet_fields():
    original = Config(
        chord_sheet_visible=True,
        chord_sheet_view="staff",
        chord_sheet_height=180,
    )
    restored = Config.from_dict(original.to_dict())
    assert restored.chord_sheet_visible == original.chord_sheet_visible
    assert restored.chord_sheet_view == original.chord_sheet_view
    assert restored.chord_sheet_height == original.chord_sheet_height


def test_from_dict_defaults_when_missing():
    config = Config.from_dict({})
    assert config.chord_sheet_visible is False
    assert config.chord_sheet_view == "name"
    assert config.chord_sheet_height == 160
