"""Helpers for the tests of the iOS tools in ios/tools (no network, no Mac)."""

import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ios" / "tools"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ios_tools"


def load_tool(name: str):
    """Import ios/tools/<name>.py as a module (the tools aren't a package)."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    if name in sys.modules and getattr(sys.modules[name], "__file__", "") == str(TOOLS / f"{name}.py"):
        return sys.modules[name]  # one module object, so its exception classes match
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def request_key(method: str, url: str) -> str:
    """``GET /path?a=1&b=2`` with the query decoded and sorted."""
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    encoded = "&".join(f"{k}={v}" for k, v in sorted(query))
    return f"{method} {parts.path}" + (f"?{encoded}" if encoded else "")


class FakeTransport:
    """Answers from a fixture's ``responses`` and ``files``; records each call."""

    def __init__(self, fixture: dict):
        self.responses = {r["request"]: r for r in fixture.get("responses", [])}
        self.files = fixture.get("files", {})
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if url in self.files:
            return 200, self.files[url].encode()
        key = request_key(method, url)
        if key not in self.responses:
            return 404, json.dumps({"errors": [{"status": "404", "code": "NOT_FOUND",
                                                "detail": f"no fixture for {key}"}]}).encode()
        response = self.responses[key]
        return response.get("status", 200), json.dumps(response.get("body", {})).encode()


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
