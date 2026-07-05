"""Round-trip tests for the chord-sheet config fields."""

from models.config import Config


def test_defaults():
    config = Config()
    assert config.chord_sheet_visible is False
    assert config.chord_sheet_view == "keyboard"
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
    assert config.chord_sheet_view == "keyboard"
    assert config.chord_sheet_height == 160


def test_allow_capo_defaults_false():
    assert Config().allow_capo is False
    assert Config.from_dict({}).allow_capo is False


def test_allow_capo_round_trips():
    original = Config(allow_capo=True)
    assert original.to_dict()["allow_capo"] is True
    assert Config.from_dict(original.to_dict()).allow_capo is True


# --------------------------------------------------------------------------
# chord_sheet_zoom (per-view display zoom factors)
# --------------------------------------------------------------------------


def test_chord_sheet_zoom_defaults_empty():
    assert Config().chord_sheet_zoom == {}
    assert Config.from_dict({}).chord_sheet_zoom == {}


def test_chord_sheet_zoom_round_trips():
    original = Config(chord_sheet_zoom={"staff": 1.5, "keyboard": 0.5})
    data = original.to_dict()
    assert data["chord_sheet_zoom"] == {"staff": 1.5, "keyboard": 0.5}
    restored = Config.from_dict(data)
    assert restored.chord_sheet_zoom == {"staff": 1.5, "keyboard": 0.5}


def test_chord_sheet_zoom_sanitizes_on_load():
    config = Config.from_dict({
        "chord_sheet_zoom": {
            "a": 5.0,        # clamped down to max
            "b": 0.1,        # clamped up to min
            "c": "x",        # non-numeric -> dropped
            "d": True,       # bool -> dropped
            "e": 1.234567,   # rounded to 3 decimals
        }
    })
    z = config.chord_sheet_zoom
    assert z["a"] == 2.5
    assert z["b"] == 0.5
    assert "c" not in z
    assert "d" not in z
    assert z["e"] == 1.235


def test_chord_sheet_zoom_non_dict_becomes_empty():
    assert Config.from_dict({"chord_sheet_zoom": ["nope"]}).chord_sheet_zoom == {}
    assert Config.from_dict({"chord_sheet_zoom": None}).chord_sheet_zoom == {}
