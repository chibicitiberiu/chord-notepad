#!/usr/bin/env python3
"""Generate the voicings editor fixtures for the Kotlin Settings tests.

Runs a real ``AppSession`` (platform "android", a temporary config dir) and
writes what the bridge would send, as ``<name>.json`` holding
``{"type": ..., "json": <payload>}``:

- ``schema``: ``VoicingEditorSchema`` (``request_voicing_editor_schema``).
- ``settings``: the ``SettingsState`` at startup.
- ``fretboard_invalid``: a new voicing whose tuning has a bad pitch and a
  relaxed span smaller than the normal span (a field error and a form error).
- ``ensemble``: the same voicing switched to an ensemble, with a bad low
  pitch in voice 1 (a records cell error) and a voice whose low is above its
  high (a form error).
- ``piano``: switched to a piano, untouched.

The Kotlin tests (``ui/settings``) decode them with ``BridgeCodec`` and build
the form from the schema, so the renderer is checked against what Python
actually sends.

Usage (from the repo root): python3 -I android/tools/gen_voicing_form_fixtures.py
Output: android/app/src/test/resources/voicing_form/
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "android/app/src/test/resources/voicing_form"


class _Recorder:
    """Keeps every output the session sends, encoded as the bridge does."""

    def __init__(self, encode):
        self._encode = encode
        self.outputs = []

    def __call__(self, output):
        self.outputs.append(self._encode(output))

    def last(self, type_name):
        for name, payload in reversed(self.outputs):
            if name == type_name:
                return {"type": name, "json": json.loads(payload)}
        raise LookupError(type_name)


def main() -> int:
    sys.path.insert(0, str(REPO / "src"))
    from services.appdata_service import AppDataService
    from session.bootstrap import build_core_services, create_session
    from session.bridge import encode
    from session.host import HostDispatch
    from session.testing import FakePlayer, InMemoryDocumentStore, ManualHost

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        host = ManualHost()
        services = build_core_services(AppDataService(root=Path(tmp)), HostDispatch(host),
                                       player=FakePlayer())
        session = create_session(host, services, InMemoryDocumentStore(), chord_sheet=False,
                                 platform="android")
        recorder = _Recorder(encode)
        session.subscribe(recorder)
        session.start()

        fixtures = {"settings": recorder.last("SettingsState")}
        session.begin_settings_edit()
        session.request_voicing_editor_schema()
        fixtures["schema"] = recorder.last("VoicingEditorSchema")

        session.add_voicing()
        session.set_voicing_values({"tuning": "E2 A2 X9 G3", "relaxed_span": "2"})
        fixtures["fretboard_invalid"] = recorder.last("VoicingEditorState")

        session.set_voicing_model("ensemble")
        voices = recorder.last("VoicingEditorState")["json"]["values"]["voices"]
        voices[1]["low"] = "H9"
        voices[0]["low"], voices[0]["high"] = "C5", "C4"
        session.set_voicing_values({"voices": voices})
        fixtures["ensemble"] = recorder.last("VoicingEditorState")

        session.set_voicing_model("piano")
        fixtures["piano"] = recorder.last("VoicingEditorState")
        session.cancel_settings_edit()

    for name, fixture in fixtures.items():
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
