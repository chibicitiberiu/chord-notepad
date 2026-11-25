#!/usr/bin/env python3
"""A small App Store Connect API client for the iOS tools (docs/IOS.md).

Standard library plus the ``openssl`` command, so it runs on Linux with no
packages: readiness.py, pull_testflight_feedback.py and the device
registration below use it.

Credentials come from the environment, never from the repository:

    ASC_KEY_ID      the API key's ID (App Store Connect > Users and Access >
                    Integrations > App Store Connect API)
    ASC_ISSUER_ID   the issuer ID shown on the same page
    ASC_KEY_PATH    the downloaded AuthKey_<key id>.p8 (keep it outside the repo)

Authentication is Apple's documented JWT: ES256 over the P-256 key, header
``{"alg": "ES256", "kid": <key id>, "typ": "JWT"}``, payload ``{"iss":
<issuer id>, "iat", "exp" (at most 20 minutes later), "aud":
"appstoreconnect-v1"}`` (developer.apple.com/documentation/appstoreconnectapi/
generating-tokens-for-api-requests). openssl signs with DER-encoded (r, s);
JWS wants the two 32-byte integers concatenated, which ``der_to_raw`` does.

Command line (Linux, after enrollment):

    python3 -I ios/tools/asc_api.py register-device --udid <udid> --name "<name>"
    python3 -I ios/tools/asc_api.py devices

``register-device`` is POST /v1/devices (attributes name, platform IOS,
udid), which the development IPA lane needs before S2 (docs/IOS.md,
"Enrollment day").
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterator, Optional

API_ROOT = "https://api.appstoreconnect.apple.com"
AUDIENCE = "appstoreconnect-v1"
BUNDLE_ID = "com.tibich.chordnotepad"
TOKEN_LIFETIME = 15 * 60  # Apple allows up to 20 minutes.


class ASCError(RuntimeError):
    """An API call failed; the message carries Apple's error details."""


# --- JWT ------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _der_length(data: bytes, pos: int) -> tuple[int, int]:
    first = data[pos]
    if first < 0x80:
        return first, pos + 1
    count = first & 0x7F
    return int.from_bytes(data[pos + 1:pos + 1 + count], "big"), pos + 1 + count


def der_to_raw(der: bytes, size: int = 32) -> bytes:
    """Convert an ECDSA signature from DER ``SEQUENCE {r, s}`` to ``r || s``."""
    if not der or der[0] != 0x30:
        raise ValueError("not a DER ECDSA signature")
    _, pos = _der_length(der, 1)
    parts = []
    for _ in range(2):
        if der[pos] != 0x02:
            raise ValueError("expected an INTEGER in the signature")
        length, pos = _der_length(der, pos + 1)
        value = der[pos:pos + length]
        pos += length
        value = value.lstrip(b"\x00")
        if len(value) > size:
            raise ValueError("integer longer than the curve size")
        parts.append(value.rjust(size, b"\x00"))
    return parts[0] + parts[1]


def raw_to_der(raw: bytes) -> bytes:
    """The inverse of ``der_to_raw`` (the tests verify a token with openssl)."""
    half = len(raw) // 2

    def integer(value: bytes) -> bytes:
        value = value.lstrip(b"\x00") or b"\x00"
        if value[0] & 0x80:
            value = b"\x00" + value
        return b"\x02" + bytes([len(value)]) + value

    body = integer(raw[:half]) + integer(raw[half:])
    return b"\x30" + bytes([len(body)]) + body


def sign_es256(key_path: str, message: bytes) -> bytes:
    """Sign with openssl (SHA-256, the key's curve) and return ``r || s``."""
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_path, "-binary"],
        input=message, capture_output=True, check=False)
    if result.returncode != 0:
        raise ASCError(f"openssl couldn't sign with {key_path}: {result.stderr.decode(errors='replace').strip()}")
    return der_to_raw(result.stdout)


def make_token(key_id: str, issuer_id: str, key_path: str, now: Optional[float] = None,
               lifetime: int = TOKEN_LIFETIME) -> str:
    """A signed App Store Connect API token."""
    issued = int(now if now is not None else time.time())
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {"iss": issuer_id, "iat": issued, "exp": issued + lifetime, "aud": AUDIENCE}
    signing_input = (_b64url(json.dumps(header, separators=(",", ":")).encode()) + "."
                     + _b64url(json.dumps(payload, separators=(",", ":")).encode()))
    signature = sign_es256(key_path, signing_input.encode("ascii"))
    return signing_input + "." + _b64url(signature)


# --- HTTP -----------------------------------------------------------------

# (method, url, headers, body) -> (status, body bytes)
Transport = Callable[[str, str, dict, Optional[bytes]], tuple[int, bytes]]


def urllib_transport(method: str, url: str, headers: dict, body: Optional[bytes]) -> tuple[int, bytes]:
    """The real transport: urllib, 60 s timeout; HTTP errors come back as status codes."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class Credentials:
    """The API key: its ID, the issuer and the .p8 file's path."""

    def __init__(self, key_id: str, issuer_id: str, key_path: str):
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.key_path = key_path

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> Optional["Credentials"]:
        """ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH, or None when any is missing."""
        env = os.environ if env is None else env
        values = [env.get(name, "").strip() for name in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_KEY_PATH")]
        if not all(values):
            return None
        return cls(*values)


class Client:
    """GET/POST against the API with a fresh token per request batch."""

    def __init__(self, token: Callable[[], str], transport: Transport = urllib_transport,
                 root: str = API_ROOT):
        self._token = token
        self._transport = transport
        self._root = root

    @classmethod
    def from_credentials(cls, credentials: Credentials, transport: Transport = urllib_transport) -> "Client":
        cache: dict = {}

        def token() -> str:
            if cache.get("expires", 0) - 60 < time.time():
                cache["token"] = make_token(credentials.key_id, credentials.issuer_id, credentials.key_path)
                cache["expires"] = time.time() + TOKEN_LIFETIME
            return cache["token"]

        return cls(token, transport)

    def _url(self, path: str, params: Optional[dict] = None) -> str:
        url = path if path.startswith("https://") else self._root + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[],")
        return url

    def request(self, method: str, path: str, params: Optional[dict] = None,
                body: Optional[dict] = None) -> dict:
        headers = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        status, raw = self._transport(method, self._url(path, params), headers, data)
        parsed = json.loads(raw) if raw else {}
        if status >= 400:
            errors = parsed.get("errors") or [{}]
            detail = "; ".join(f"{e.get('status', status)} {e.get('code', '')}: {e.get('detail', e.get('title', ''))}"
                               for e in errors)
            raise ASCError(f"{method} {path} failed: {detail}")
        return parsed

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        return self.request("GET", path, params)

    def get_all(self, path: str, params: Optional[dict] = None, limit: int = 1000) -> Iterator[dict]:
        """Every resource of a list endpoint, following ``links.next``."""
        page = self.get(path, params)
        seen = 0
        while True:
            for item in page.get("data", []):
                yield item
                seen += 1
                if seen >= limit:
                    return
            following = (page.get("links") or {}).get("next")
            if not following:
                return
            page = self.get(following)

    def post(self, path: str, body: dict) -> dict:
        return self.request("POST", path, body=body)

    def download(self, url: str) -> bytes:
        """A file URL from the API (screenshot images are pre-signed, no token)."""
        status, raw = self._transport("GET", url, {}, None)
        if status >= 400:
            raise ASCError(f"download failed ({status}): {url.split('?')[0]}")
        return raw


def find_app(client: Client, bundle_id: str = BUNDLE_ID) -> dict:
    """The app record for a bundle ID (GET /v1/apps?filter[bundleId]=…)."""
    apps = client.get("/v1/apps", {"filter[bundleId]": bundle_id, "fields[apps]": "bundleId,name"}).get("data", [])
    matching = [app for app in apps if app.get("attributes", {}).get("bundleId") == bundle_id]
    if not matching:
        raise ASCError(f"no App Store Connect app with bundle ID {bundle_id}; create the app record first")
    return matching[0]


def register_device(client: Client, udid: str, name: str) -> dict:
    """POST /v1/devices; an already registered UDID is reported, not re-added."""
    for device in client.get_all("/v1/devices", {"filter[udid]": udid, "filter[platform]": "IOS"}):
        return {"already": True, "device": device}
    created = client.post("/v1/devices", {"data": {"type": "devices", "attributes": {
        "name": name, "platform": "IOS", "udid": udid}}})
    return {"already": False, "device": created.get("data", {})}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register-device", help="register an iPhone's UDID for development builds")
    reg.add_argument("--udid", required=True)
    reg.add_argument("--name", required=True, help="a label for the device, shown in the developer portal")
    sub.add_parser("devices", help="list the registered devices")
    args = parser.parse_args(argv)

    credentials = Credentials.from_env()
    if credentials is None:
        print("error: set ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH (docs/IOS.md, \"Enrollment day\")",
              file=sys.stderr)
        return 2
    client = Client.from_credentials(credentials)
    try:
        if args.command == "register-device":
            result = register_device(client, args.udid.strip(), args.name)
            attributes = result["device"].get("attributes", {})
            state = "already registered" if result["already"] else "registered"
            print(f"{state}: {attributes.get('name')} ({attributes.get('model') or 'model not known yet'}),"
                  f" status {attributes.get('status')}")
        else:
            for device in client.get_all("/v1/devices", {"filter[platform]": "IOS"}):
                attributes = device.get("attributes", {})
                print(f"{attributes.get('name')}\t{attributes.get('model')}\t{attributes.get('status')}\t"
                      f"{attributes.get('udid')}")
    except ASCError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
