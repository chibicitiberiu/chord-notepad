"""ios/tools/asc_api.py and pull_testflight_feedback.py, offline.

The API answers come from tests/fixtures/ios_tools/asc_feedback.json
(synthetic, from Apple's documented schema); the JWT is signed with a key
made here and checked with openssl, the way App Store Connect checks it.
"""

import base64
import json
import shutil
import subprocess

import pytest

from tests.ios_tools_support import FakeTransport, fixture, load_tool

asc_api = load_tool("asc_api")
feedback = load_tool("pull_testflight_feedback")

needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def test_der_to_raw_pads_and_strips():
    r = b"\x00" + b"\x80" + b"\x11" * 31  # high bit set: DER adds a zero byte
    s = b"\x05" * 30                       # short: raw pads it to 32
    der = b"\x30" + bytes([4 + len(r) + len(s)]) + b"\x02" + bytes([len(r)]) + r + b"\x02" + bytes([len(s)]) + s
    raw = asc_api.der_to_raw(der)
    assert len(raw) == 64
    assert raw[:32] == b"\x80" + b"\x11" * 31
    assert raw[32:] == b"\x00\x00" + b"\x05" * 30
    assert asc_api.der_to_raw(asc_api.raw_to_der(raw)) == raw


def test_der_to_raw_refuses_garbage():
    with pytest.raises(ValueError):
        asc_api.der_to_raw(b"\x04\x00")


@needs_openssl
def test_token_is_es256_and_verifies(tmp_path):
    key = tmp_path / "AuthKey_TEST.p8"
    subprocess.run(["openssl", "genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256",
                    "-out", str(key)], check=True, capture_output=True)
    public = tmp_path / "public.pem"
    subprocess.run(["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(public)],
                   check=True, capture_output=True)

    token = asc_api.make_token("KEYID12345", "issuer-uuid", str(key), now=1_800_000_000)
    header, payload, signature = token.split(".")
    assert json.loads(_unb64(header)) == {"alg": "ES256", "kid": "KEYID12345", "typ": "JWT"}
    claims = json.loads(_unb64(payload))
    assert claims == {"iss": "issuer-uuid", "iat": 1_800_000_000, "exp": 1_800_000_000 + 900,
                      "aud": "appstoreconnect-v1"}
    raw = _unb64(signature)
    assert len(raw) == 64

    (tmp_path / "input").write_bytes(f"{header}.{payload}".encode())
    (tmp_path / "sig.der").write_bytes(asc_api.raw_to_der(raw))
    result = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(public), "-signature",
                             str(tmp_path / "sig.der"), str(tmp_path / "input")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_credentials_need_all_three():
    assert asc_api.Credentials.from_env({"ASC_KEY_ID": "a", "ASC_ISSUER_ID": "b"}) is None
    creds = asc_api.Credentials.from_env({"ASC_KEY_ID": "a", "ASC_ISSUER_ID": "b", "ASC_KEY_PATH": "/k.p8"})
    assert (creds.key_id, creds.issuer_id, creds.key_path) == ("a", "b", "/k.p8")


def _client(data):
    transport = FakeTransport(data)
    return asc_api.Client(lambda: "TOKEN", transport), transport


def test_errors_carry_apples_detail():
    client, _ = _client({"responses": []})
    with pytest.raises(asc_api.ASCError, match="NOT_FOUND"):
        client.get("/v1/apps/none")


def test_register_device_adds_once():
    data = {"responses": [
        {"request": "GET /v1/devices?filter[platform]=IOS&filter[udid]=00008110-AAAA", "body": {"data": []}},
        {"request": "POST /v1/devices", "status": 201,
         "body": {"data": {"type": "devices", "id": "D1", "attributes": {"name": "Test iPhone", "status": "ENABLED"}}}},
    ]}
    client, transport = _client(data)
    result = asc_api.register_device(client, "00008110-AAAA", "Test iPhone")
    assert result["already"] is False
    post = transport.calls[-1]
    assert post["method"] == "POST"
    assert json.loads(post["body"]) == {"data": {"type": "devices", "attributes": {
        "name": "Test iPhone", "platform": "IOS", "udid": "00008110-AAAA"}}}
    assert post["headers"]["Authorization"] == "Bearer TOKEN"

    data["responses"][0]["body"] = {"data": [{"type": "devices", "id": "D1", "attributes": {"udid": "00008110-AAAA"}}]}
    client, transport = _client(data)
    assert asc_api.register_device(client, "00008110-AAAA", "Test iPhone")["already"] is True
    assert all(call["method"] == "GET" for call in transport.calls)


def test_pull_writes_each_submission_once(tmp_path):
    client, transport = _client(fixture("asc_feedback.json"))
    counts = feedback.pull(client, tmp_path)
    assert counts == {"screenshots": 2, "crashes": 1, "skipped": 0, "images": 3}

    shots = sorted(p.name for p in (tmp_path / "screenshots").iterdir())
    assert shots == ["20261201T090000_build56_shot-0001", "20261203T180411_build57_shot-0002"]
    newest = tmp_path / "screenshots" / shots[1]
    assert (newest / "screenshot-1.png").read_bytes() == b"PNG-A"
    assert (newest / "screenshot-2.jpg").read_bytes() == b"JPG-B"
    assert (newest / "comment.txt").read_text() == "The chord sheet is cut off on the right\n"
    record = json.loads((newest / "feedback.json").read_text())
    assert record["attributes"]["deviceModel"] == "iPhone16,1"

    crash = tmp_path / "crashes" / "20261203T181000_build57_crash-0001"
    assert crash.joinpath("crash.ips").read_text().startswith('{"app_name":"ChordNotepad"')

    # Image URLs are pre-signed: fetched without the API token.
    image_calls = [c for c in transport.calls if c["url"].startswith("https://example.invalid/")]
    assert len(image_calls) == 3 and all("Authorization" not in c["headers"] for c in image_calls)

    client, transport = _client(fixture("asc_feedback.json"))
    again = feedback.pull(client, tmp_path)
    assert again == {"screenshots": 0, "crashes": 0, "skipped": 3, "images": 0}
    assert not any("crashLog" in c["url"] or "example.invalid" in c["url"] for c in transport.calls)


def test_pull_without_an_app_record(tmp_path):
    data = {"responses": [{"request": "GET /v1/apps?fields[apps]=bundleId,name&filter[bundleId]=com.tibich.chordnotepad",
                           "body": {"data": []}}]}
    client, _ = _client(data)
    with pytest.raises(asc_api.ASCError, match="create the app record"):
        feedback.pull(client, tmp_path)


def test_cli_without_credentials(monkeypatch, capsys, tmp_path):
    for name in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH"):
        monkeypatch.delenv(name, raising=False)
    assert feedback.main(["--out", str(tmp_path)]) == 2
    assert "ASC_KEY_PATH" in capsys.readouterr().err
    assert asc_api.main(["devices"]) == 2
