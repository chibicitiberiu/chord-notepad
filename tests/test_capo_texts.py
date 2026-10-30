"""The Insert Capo texts say what a capo really does (todo #13).

A capo never changes the key, but a fretboard voicing plays the shapes it
picks for the capo, so the notes heard can change: "It changes the shapes,
not the sound" was wrong.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _android_string(name):
    import xml.etree.ElementTree as ET
    for path in (ROOT / "android/app/src/main/res").glob("values*/strings*.xml"):
        for node in ET.parse(path).getroot().iter("string"):
            if node.get("name") == name:
                yield path, node.text


def test_android_insert_capo_hint():
    found = list(_android_string("insert_capo_hint"))
    assert found
    for path, text in found:
        assert "not the sound" not in text, path
        assert "fretboard voicing" in text, path


def test_help_capo_caption():
    text = (ROOT / "help/interface.rst").read_text(encoding="utf-8")
    assert "not the sound" not in text
