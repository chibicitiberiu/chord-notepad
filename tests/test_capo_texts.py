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


def test_suggest_capo_texts_match_on_desktop_and_android():
    """Suggest Capo's explanation, spinner line and hint are the same words
    on both front ends (the desktop has them in its QML and the session's
    formatting constants, Android in strings_tools.xml)."""
    from chordnotepad.session import formatting

    qml = (ROOT / "desktop/chordnotepad_desktop/qml/app/CapoDialog.qml").read_text(encoding="utf-8")
    hint = dict(_android_string("capo_hint"))
    assert len(hint) == 1
    (text,) = hint.values()
    assert text in qml
    assert "recommended" in text.lower()
    assert list(dict(_android_string("capo_finding")).values()) == [formatting.CAPO_FINDING]
    assert list(dict(_android_string("capo_stop_to_apply")).values()) == [formatting.CAPO_STOP_TO_APPLY]


def test_help_describes_the_ranked_list():
    text = (ROOT / "help/chord_sheet.rst").read_text(encoding="utf-8")
    for word in ("Recommended", "Current", "Easier", "About the same", "Harder", "Apply"):
        assert word in text, word
    assert "Suggest buttons" not in text
