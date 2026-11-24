"""Python helpers for ChordNotepadKit's Swift tests (RuntimeTests, BridgeCodecTests,
SheetPainterTests, the fixture recording).

Each function takes and returns strings (``PythonRuntime.call``). The command
and answer checks import the core with its packages, the glyph helpers only
``chord_sheet.clef_assets`` (standard library only); the rest need nothing but
``_cnbridge``.
"""

import json
import sys
import threading
import time

import _cnbridge


def runtime_facts() -> str:
    """How the interpreter was started, as JSON."""
    return json.dumps({
        "utf8_mode": sys.flags.utf8_mode,
        "isolated": sys.flags.isolated,
        "version": list(sys.version_info[:2]),
        "is_main_thread": threading.current_thread() is threading.main_thread(),
        "path": sys.path,
        "filesystem_encoding": sys.getfilesystemencoding(),
    })


def fail(message: str) -> str:
    """Raise, so the Swift side sees the traceback."""
    raise ValueError(message)


def emit_from_threads(count: str) -> None:
    """Emit ``count`` events from each of two Python threads, in order per thread."""
    def run(name: str) -> None:
        for i in range(int(count)):
            _cnbridge.emit("Ping", json.dumps({"thread": name, "i": i, "text": "Ré ♯ 😀"}))

    threads = [threading.Thread(target=run, args=(name,), name=name) for name in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def _attempt(fn, *args):
    """``fn(*args)`` as ``{"ok": result}`` or ``{"error": class name, "message": str(exc)}``."""
    try:
        result = fn(*args)
    except Exception as e:  # noqa: BLE001 (reported to the test)
        return {"error": type(e).__name__, "message": str(e),
                "is_store_error": isinstance(e, _cnbridge.StoreError)}
    if isinstance(result, bytes):
        return {"ok_bytes": list(result)}
    return {"ok": result}


def store_round_trip(document_id: str) -> str:
    """Every ``_cnbridge.store_*`` call against the registered Swift store."""
    return json.dumps({
        "write": _attempt(_cnbridge.store_write_bytes, document_id, "Am  G\nRé 😀".encode()),
        "read": _attempt(_cnbridge.store_read_bytes, document_id),
        "read_missing": _attempt(_cnbridge.store_read_bytes, "missing"),
        "copy": _attempt(_cnbridge.store_copy_from_file, document_id, "/tmp/export.wav"),
        "available": _attempt(_cnbridge.store_is_available, document_id),
        "available_missing": _attempt(_cnbridge.store_is_available, "missing"),
        "add_recent": _attempt(_cnbridge.store_add_recent, document_id, "Song.txt", "Files"),
        "set_max_recent": _attempt(_cnbridge.store_set_max_recent, 7),
        "recent": _attempt(_cnbridge.store_recent),
        "describe": _attempt(_cnbridge.store_describe, document_id),
        "describe_missing": _attempt(_cnbridge.store_describe, "missing"),
        "rename": _attempt(_cnbridge.store_rename, document_id, "New.txt"),
        "rename_refused": _attempt(_cnbridge.store_rename, "locked", "New.txt"),
        "write_empty": _attempt(_cnbridge.store_write_bytes, "empty", b""),
        "read_empty": _attempt(_cnbridge.store_read_bytes, "empty"),
    })


def gil_released_during_store_call(document_id: str) -> str:
    """Whether another Python thread ran while the store blocked in Swift.

    The Swift test store sleeps in ``read_bytes`` for ids starting with
    ``slow``; a ticking thread must keep ticking meanwhile.
    """
    ticks = []
    stop = threading.Event()

    def tick() -> None:
        while not stop.is_set():
            ticks.append(time.monotonic())
            time.sleep(0.005)

    t = threading.Thread(target=tick)
    t.start()
    time.sleep(0.02)
    before = len(ticks)
    _cnbridge.store_read_bytes(document_id)
    during = len(ticks) - before
    stop.set()
    t.join()
    return json.dumps({"ticks_during_call": during})


def scene_fixture(path: str, scene_json: str, files_dir: str, record: str) -> str:
    """Compare (or with ``record == "1"`` write) one ios/Fixtures scene.

    ``scene_json`` holds the session's JSON exactly as it crossed the bridge;
    it is written sorted and indented, with ``files_dir`` (a temp folder)
    replaced by ``$FILES_DIR``, so the file is the same on every run.

    Returns:
        ``""`` when the file matches (or was written), else what differs.
    """
    import difflib
    from pathlib import Path

    text = scene_json.replace(files_dir, "$FILES_DIR")
    canonical = json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    target = Path(path)
    if record == "1":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(canonical, encoding="utf-8")
        return ""
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    if current == canonical:
        return ""
    diff = difflib.unified_diff(current.splitlines(), canonical.splitlines(),
                                str(target), "this run", lineterm="", n=1)
    return "\n".join(list(diff)[:40]) or f"{target} is missing"


def check_command(command: str, args_json: str) -> str:
    """``""`` if the core's bridge accepts ``args_json`` for ``command``, else why not."""
    from chordnotepad.session.bridge import BridgeError, decode_args
    try:
        decode_args(command, args_json)
    except BridgeError as e:
        return str(e)
    return ""


def check_answer(request_type: str, args_json: str) -> str:
    """``""`` if ``respond``'s args decode for a pending ``request_type``, else why not."""
    from chordnotepad.session import bridge
    from chordnotepad.session.bridge import BridgeError, decode_args
    try:
        kwargs = decode_args("respond", args_json)
        cls = next(t for t in bridge.REQUEST_TYPES if t.__name__ == request_type)
        # Only the request's type matters to the answer's decoder.
        bridge._decode_answer(object.__new__(cls), kwargs["value"])
    except BridgeError as e:
        return str(e)
    return ""


def glyph_index() -> str:
    """The base clef and glyph sizes as ``glyphs.json`` holds them
    (android/tools/export_clef_glyphs.py, which the app's build runs)."""
    from chordnotepad.chord_sheet.clef_assets import base_glyph_pngs, base_size

    assets = {}
    for asset in base_glyph_pngs():
        width, height = base_size(asset)
        assets[asset] = {"width": width, "height": height}
    return json.dumps({"version": 1, "assets": assets}, sort_keys=True)


def scaled_widths(keys_json: str) -> str:
    """``clef_assets.scaled_width`` for each image key: the width every
    renderer of a key must use, as ``{key: width}``."""
    from chordnotepad.chord_sheet.clef_assets import parse_image_key, scaled_width

    widths = {}
    for key in json.loads(keys_json):
        parsed = parse_image_key(key)
        widths[key] = None if parsed is None else scaled_width(parsed.asset, parsed.height)
    return json.dumps(widths)
