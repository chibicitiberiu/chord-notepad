"""The iOS find bar's character tables are this Python's ``re``.

``ios/tools/gen_find_tables.py`` writes ``Generated/PythonText.swift``: the
simple lowercase, the cased characters, ``\\w`` and ``_casefix``'s extra
cases, which the kit's Swift matching uses to find exactly what the core's
``text_ops.find_all`` finds. This fails while the file is stale (no Swift
toolchain needed); the kit's ``FindReplaceTests`` check the Swift side
against the running interpreter.
"""

import importlib.util
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "ios" / "tools" / "gen_find_tables.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_find_tables", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_generated_tables_are_current(gen):
    current = gen.OUTPUT.read_text(encoding="utf-8")
    if f'"{unicodedata.unidata_version}"' not in current:
        pytest.skip(f"the tables are for another Unicode version than this Python's {unicodedata.unidata_version}")
    assert current == gen.generate(), (
        "ios/.../Generated/PythonText.swift is stale; run python3 -I ios/tools/gen_find_tables.py")


def test_the_tables_hold_what_re_folds_with(gen):
    text = gen.generate()
    # ſ folds with s, K (Kelvin) lowercases to k, and İ to a plain i.
    assert "0x73: [0x17F]," in text
    assert "0x212A, 0x6B," in text
    assert "0x130, 0x69," in text
