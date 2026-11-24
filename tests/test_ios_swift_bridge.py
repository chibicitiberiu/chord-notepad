"""The iOS kit's generated Swift bridge types match android/bridge_schema.json.

``ios/tools/gen_swift_bridge.py`` writes ``Generated/Bridge.swift`` and the
test samples from the schema; this fails while either is stale (no Swift
toolchain needed). Regenerate with ``make ios-bridge-gen``.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "ios" / "tools" / "gen_swift_bridge.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("gen_swift_bridge", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def schema():
    return json.loads((ROOT / "android" / "bridge_schema.json").read_text(encoding="utf-8"))


def test_generated_swift_is_current(gen, schema):
    assert gen.BRIDGE_SWIFT.read_text(encoding="utf-8") == gen.gen_bridge(schema), (
        "ios/.../Generated/Bridge.swift is stale; run `make ios-bridge-gen`")
    assert gen.SAMPLES_SWIFT.read_text(encoding="utf-8") == gen.gen_samples(schema), (
        "ios/.../Generated/CommandSamples.swift is stale; run `make ios-bridge-gen`")


def test_check_mode_reports_current_files(gen):
    assert gen.main(["--check"]) == 0


def test_every_dto_command_and_enum_is_generated(gen, schema):
    swift = gen.gen_bridge(schema)
    for name in schema["types"]:
        assert f"public struct {name}: Codable" in swift
    for name in schema["enums"]:
        assert f"public enum {name}: String, Codable" in swift
    for command in schema["commands"]:
        assert f"public static func {gen.ident(command)}(" in swift
    for request in schema["answers"]:
        assert f"public static func respondTo{request}(" in swift


def test_keywords_are_backticked_and_none_is_renamed(gen, schema):
    swift = gen.gen_bridge(schema)
    assert "public var `repeat`: Bool" in swift
    assert 'case noScreen = "none"' in swift
    assert gen.ident("default") == "`default`"
    assert gen.ident("text_revision") == "textRevision"
    with pytest.raises(ValueError):
        gen.case_name("Anything", "none")


def test_required_nullable_keys_are_always_encoded(gen, schema):
    swift = gen.gen_bridge(schema)
    # decode_args rejects these keys when missing; the builders write them as null.
    for command, param in [("restore_draft", "document"), ("open_recovered", "document"),
                           ("set_key", "key"), ("set_chord_sheet_on_screen", "on_screen")]:
        start = swift.index(f"public static func {gen.ident(command)}(")
        body = swift[start:swift.index("\n    }\n", start)]
        swift_name = gen.ident(param)
        assert f"try container.encode({swift_name}, forKey: .{swift_name})" in body
        assert "encodeIfPresent" not in body
