#!/usr/bin/env python3
"""Capture the Android user guide's screenshots on the emulator.

Every shot is described in ``help_shots.json`` (next to this script; see
HELP_SHOTS.md for the format and which page each image is for). For each one
the tool:

1. resets the app (force-stop, a fresh ``settings.json`` built from the
   manifest's ``config`` plus the shot's, no recent list, no UI preferences),
2. puts the emulator in the shot's theme and orientation,
3. starts the debug-only ``HelpShotActivity`` with the shot's ``scene``
   (actions applied inside the app: load a song, Edit/Play, the chord sheet,
   the playhead, a frozen "playing" state, ...),
4. runs the shot's ``steps`` (taps on Compose test tags or on text/content
   descriptions read from ``uiautomator dump``, typing, keys, more in-app
   actions),
5. takes the screenshot, crops it, scales it, draws the numbered callouts
   and writes ``help/images/android/<name>.png`` (``<name>.dark.png`` for the
   dark variant), quantized and optimized.

The emulator is shared: the tool takes an exclusive lock
(``$ANDROID_ROOT/emulator.lock``) for as long as it uses it, boots the AVD
headless if it isn't running (``nice``, 2 GB, 2 cores, ``swangle_indirect``),
installs the debug APK when the device has another build, and stops the
emulator at the end unless ``--keep-emulator``.

Usage (``source android/local.env`` first, build with
``./gradlew :app:assembleDebug``)::

    python3 android/tools/help_screenshots.py --list
    python3 android/tools/help_screenshots.py                 # every shot
    python3 android/tools/help_screenshots.py --only player-labeled,drawer
    python3 android/tools/help_screenshots.py --only player-labeled --keep-emulator --debug

Needs Pillow (with libimagequant for the palette step; it falls back to
plain RGB PNGs without it).
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MANIFEST = HERE / "help_shots.json"
OUT_DIR = REPO / "help" / "images" / "android"
PACKAGE = "io.github.chibicitiberiu.chordnotepad"
ACTIVITY = f"{PACKAGE}/.helpshot.HelpShotActivity"
BROADCAST = f"{PACKAGE}.HELP_SHOT"
CONFIG_PATH = "files/config/chord-notepad/settings.json"
APK_MARK = "/data/local/tmp/helpshot_apk.sha256"
LOG_TAG = "HelpShot"

# Callout colours: the app's primary (docs/design/android-ui-spec.md).
PRIMARY = {"light": (0x3F, 0x51, 0xB5), "dark": (0xB6, 0xC3, 0xFF)}
ON_PRIMARY = {"light": (0xFF, 0xFF, 0xFF), "dark": (0x1B, 0x2A, 0x6B)}
HALO = {"light": (0xFF, 0xFF, 0xFF), "dark": (0x12, 0x13, 0x18)}

FONT_CANDIDATES = [
    "/usr/share/fonts/google-roboto/Roboto-Bold.ttf",
    "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/google-roboto/RobotoCondensed-Bold.ttf",
]


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------
# Environment, lock, emulator
# --------------------------------------------------------------------------

def env_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set: source android/local.env first")
    return Path(value)


@contextmanager
def emulator_lock(path: Path, wait_s: int):
    """Hold an exclusive flock on ``path`` (other tools and agents use the same file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        deadline = time.time() + wait_s
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() > deadline:
                    f.seek(0)
                    sys.exit(f"The emulator is locked by someone else ({path}: {f.read().strip()!r})")
                time.sleep(5)
        f.seek(0)
        f.truncate()
        f.write(f"pid {os.getpid()} help_screenshots.py since {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.flush()
        try:
            yield
        finally:
            f.seek(0)
            f.truncate()
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)


def run(cmd: list[str], check: bool = True, capture: bool = True, input: bytes | None = None,
        timeout: float | None = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, input=input, timeout=timeout)


class Device:
    """One emulator, by adb serial."""

    def __init__(self, serial: str):
        self.serial = serial

    def adb(self, *args: str, check: bool = True, input: bytes | None = None,
            timeout: float | None = 120) -> str:
        r = run(["adb", "-s", self.serial, *args], check=check, input=input, timeout=timeout)
        return r.stdout.decode("utf-8", "replace")

    def sh(self, command: str, check: bool = True, input: bytes | None = None, timeout: float | None = 120) -> str:
        return self.adb("shell", command, check=check, input=input, timeout=timeout)

    def screencap(self) -> Image.Image:
        data = run(["adb", "-s", self.serial, "exec-out", "screencap", "-p"]).stdout
        return Image.open(io.BytesIO(data)).convert("RGB")


def emulators() -> list[str]:
    out = run(["adb", "devices"]).stdout.decode()
    return [line.split()[0] for line in out.splitlines()[1:]
            if line.startswith("emulator-") and line.split()[-1] == "device"]


def avd_name(serial: str) -> str | None:
    try:
        out = run(["adb", "-s", serial, "emu", "avd", "name"], timeout=10).stdout.decode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return out.splitlines()[0].strip() if out.strip() else None


def stop_emulator(serial: str) -> None:
    log(f"stopping {serial}")
    run(["adb", "-s", serial, "emu", "kill"], check=False)
    for _ in range(60):
        if serial not in emulators():
            return
        time.sleep(1)


def ensure_emulator(avd: str) -> tuple[Device, bool]:
    """The running emulator with ``avd``, booting it if needed. Returns (device, started_here)."""
    for serial in emulators():
        name = avd_name(serial)
        if name == avd:
            return Device(serial), False
        log(f"{serial} runs {name}, not {avd}: stopping it (we hold the emulator lock)")
        stop_emulator(serial)
    log(f"booting {avd} (headless)")
    cmd = ["nice", "-n", "10", "emulator", "-avd", avd, "-no-window", "-no-snapshot", "-no-boot-anim",
           "-no-audio", "-gpu", "swangle_indirect", "-memory", "2048", "-cores", "2"]
    log_file = open(env_path("ANDROID_ROOT") / f"emulator-{avd}.log", "w")
    subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        for serial in emulators():
            if avd_name(serial) == avd:
                dev = Device(serial)
                if dev.sh("getprop sys.boot_completed", check=False).strip() == "1":
                    time.sleep(5)
                    return dev, True
        time.sleep(3)
    sys.exit(f"{avd} did not boot in 5 minutes")


def apk_path(variant: str = "debug") -> Path:
    root = os.environ.get("CHORD_NOTEPAD_ANDROID_BUILD_ROOT")
    android = REPO / "android"
    if root:
        sub = str(android).lstrip("/").replace("/", "_")
        return Path(root) / sub / "app" / "outputs" / "apk" / variant / f"app-{variant}.apk"
    return android / "app" / "build" / "outputs" / "apk" / variant / f"app-{variant}.apk"


def ensure_installed(dev: Device, apk: Path) -> None:
    if not apk.exists():
        sys.exit(f"{apk} is missing: build it (cd android && ./gradlew :app:assembleDebug)")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    installed = dev.sh(f"cat {APK_MARK} 2>/dev/null", check=False).strip()
    has_pkg = PACKAGE in dev.sh(f"pm list packages {PACKAGE}", check=False)
    if installed == digest and has_pkg:
        return
    log(f"installing {apk.name}")
    dev.adb("install", "-r", "-g", str(apk), timeout=600)
    dev.sh(f"echo {digest} > {APK_MARK}")


def prepare_device(dev: Device) -> None:
    """Clean status bar, no animations, fixed fonts and density, screen on."""
    cmds = [
        "settings put global sysui_demo_allowed 1",
        "settings put global window_animation_scale 0",
        "settings put global transition_animation_scale 0",
        "settings put global animator_duration_scale 0",
        "settings put system font_scale 1.0",
        "settings put secure spell_checker_enabled 0",
        "settings put secure show_ime_with_hard_keyboard 1",
        "settings put system accelerometer_rotation 0",
        "wm density reset",
        "wm size reset",
        "svc power stayon true",
        "input keyevent KEYCODE_WAKEUP",
        "wm dismiss-keyguard",
    ]
    for c in cmds:
        dev.sh(c, check=False)
    # Leave and re-enter demo mode: entering right after boot can leave a
    # second Wi-Fi icon behind.
    demo = [
        "-e command exit",
        "-e command enter",
        "-e command clock -e hhmm 0941",
        "-e command battery -e level 100 -e plugged false -e powersave false",
        "-e command network -e wifi show -e level 4 -e fully true",
        "-e command network -e mobile hide",
        "-e command notifications -e visible false",
        "-e command status -e volume hide -e bluetooth hide -e location hide -e alarm hide -e sync hide",
    ]
    for d in demo:
        dev.sh(f"am broadcast -a com.android.systemui.demo {d}", check=False)
        time.sleep(0.5)


# --------------------------------------------------------------------------
# UI tree
# --------------------------------------------------------------------------

@dataclass
class Node:
    tag: str
    desc: str
    text: str
    bounds: tuple[int, int, int, int]
    cls: str

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bounds
        return (x0 + x1) / 2, (y0 + y1) / 2


BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def dump_ui(dev: Device, attempts: int = 4) -> list[Node]:
    for i in range(attempts):
        out = dev.sh("uiautomator dump /sdcard/helpshot_ui.xml", check=False, timeout=60)
        if "dumped to" in out:
            xml = dev.sh("cat /sdcard/helpshot_ui.xml")
            root = ET.fromstring(xml)
            nodes = []
            for el in root.iter("node"):
                m = BOUNDS.match(el.get("bounds", ""))
                if not m:
                    continue
                rid = el.get("resource-id", "")
                nodes.append(Node(rid.split("/")[-1], el.get("content-desc", ""), el.get("text", ""),
                                  tuple(int(v) for v in m.groups()), el.get("class", "")))
            return nodes
        time.sleep(1 + i)
    raise RuntimeError(f"uiautomator dump failed: {out.strip()}")


def matches(node: Node, sel: dict) -> bool:
    for key, want in sel.items():
        if key == "tag" and node.tag != want:
            return False
        if key == "desc" and node.desc != want:
            return False
        if key == "desc_prefix" and not node.desc.startswith(want):
            return False
        if key == "text" and node.text != want:
            return False
        if key == "text_prefix" and not node.text.startswith(want):
            return False
        if key == "contains" and want not in node.text and want not in node.desc:
            return False
    return True


def find(nodes: list[Node], sel: dict) -> Node | None:
    sel = dict(sel)
    if sel.pop("window", False):
        # The top window's root: a dialog's or sheet's own bounds.
        return nodes[0] if nodes else None
    index = sel.pop("index", 0)
    for k in ("at", "pad"):
        sel.pop(k, None)
    hits = [n for n in nodes if matches(n, sel)]
    # Text nodes are often wrapped in a clickable parent of the same bounds; any will do.
    if not hits or index >= len(hits) or index < -len(hits):
        return None
    return hits[index]


def find_or_fail(dev: Device, sel: dict, timeout: float = 10) -> tuple[Node, list[Node]]:
    deadline = time.time() + timeout
    while True:
        nodes = dump_ui(dev)
        node = find(nodes, sel)
        if node:
            return node, nodes
        if time.time() > deadline:
            raise RuntimeError(f"no node matches {sel}")
        time.sleep(1)


# --------------------------------------------------------------------------
# Running a shot
# --------------------------------------------------------------------------

def b64(obj) -> str:
    return base64.b64encode(json.dumps(obj, ensure_ascii=False).encode("utf-8")).decode("ascii")


def wait_log(dev: Device, token: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = dev.adb("logcat", "-d", "-s", f"{LOG_TAG}:*", check=False)
        if re.search(rf"\bdone {re.escape(token)}\b", out):
            return
        m = re.search(rf"failed {re.escape(token)} (.*)", out)
        if m:
            raise RuntimeError(f"scene failed: {m.group(1)}")
        time.sleep(0.5)
    raise RuntimeError(f"scene {token} timed out")


def resolve_actions(actions: list[dict]) -> list[dict]:
    """Load song files (``file`` relative to the repo) into ``text``."""
    out = []
    for a in actions:
        a = dict(a)
        if a.get("do") == "song" and "file" in a:
            a["text"] = (REPO / a.pop("file")).read_text(encoding="utf-8")
        out.append(a)
    return out


def write_config(dev: Device, config: dict) -> None:
    data = json.dumps(config, indent=2).encode("utf-8")
    dev.sh(f"run-as {PACKAGE} mkdir -p {os.path.dirname(CONFIG_PATH)}")
    dev.adb("shell", f"run-as {PACKAGE} sh -c 'cat > {CONFIG_PATH}'", input=data)


def reset_app(dev: Device, config: dict) -> None:
    dev.sh(f"am force-stop {PACKAGE}")
    dev.sh(f"run-as {PACKAGE} rm -f files/recent_documents.json shared_prefs/ui.xml", check=False)
    write_config(dev, config)


def set_display(dev: Device, theme: str, orientation: str, natural: str) -> None:
    dev.sh(f"cmd uimode night {'yes' if theme == 'dark' else 'no'}")
    # Rotation 0 is the device's natural orientation (a tablet's is landscape).
    dev.sh(f"wm user-rotation lock {0 if orientation == natural else 1}")
    time.sleep(1.5)


def tap(dev: Device, sel: dict, timeout: float = 10) -> None:
    node, _ = find_or_fail(dev, sel, timeout)
    fx, fy = sel.get("at", (0.5, 0.5))
    x0, y0, x1, y1 = node.bounds
    dev.sh(f"input tap {x0 + (x1 - x0) * fx:.0f} {y0 + (y1 - y0) * fy:.0f}")


def run_steps(dev: Device, steps: list[dict], shot: str) -> None:
    for i, step in enumerate(steps):
        if "tap" in step:
            tap(dev, step["tap"], step.get("timeout", 10))
        elif "wait_for" in step:
            find_or_fail(dev, step["wait_for"], step.get("timeout", 20))
        elif "type" in step:
            text = step["type"].replace(" ", "%s")
            dev.sh(f"input text {shlex.quote(text)}")
        elif "key" in step:
            dev.sh(f"input keyevent {step['key']}")
        elif "swipe" in step:
            node, _ = find_or_fail(dev, step["swipe"])
            fx, fy = step["swipe"].get("at", (0.5, 0.5))
            x0, y0, x1, y1 = node.bounds
            x, y = x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy
            dx, dy = step.get("by", (0, 0))
            dev.sh(f"input swipe {x:.0f} {y:.0f} {x + dx:.0f} {y + dy:.0f} {step.get('ms', 400)}")
        elif "actions" in step:
            token = f"{shot}-{i}"
            dev.sh("logcat -c", check=False)
            dev.sh(f"am broadcast -a {BROADCAST} -p {PACKAGE} --es token {token} "
                   f"--es actions_b64 {b64(resolve_actions(step['actions']))}")
            wait_log(dev, token, step.get("timeout", 60))
        elif "sleep" not in step:
            raise ValueError(f"unknown step {step}")
        time.sleep(step.get("sleep", 0.8))


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def union(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def crop_box(crop: dict | None, nodes: list[Node], size: tuple[int, int], density: float) -> tuple[int, int, int, int]:
    w, h = size
    if not crop:
        return 0, 0, w, h
    boxes = []
    for sel in crop.get("nodes", []):
        node = find(nodes, sel)
        if not node:
            raise RuntimeError(f"crop: no node matches {sel}")
        boxes.append(node.bounds)
    if "rect_dp" in crop:
        boxes.append(tuple(int(v * density) for v in crop["rect_dp"]))
    x0, y0, x1, y1 = union(boxes)
    pad = crop.get("pad_dp", 8) * density
    pads = crop.get("pads_dp")  # [left, top, right, bottom]
    l, t, r, b = ([p * density for p in pads] if pads else [pad] * 4)
    if crop.get("full_width"):
        x0, x1, l, r = 0, w, 0, 0
    if "height_dp" in crop:
        y1 = y0 + crop["height_dp"] * density
    if "top_dp" in crop:
        y0 = y0 + crop["top_dp"] * density
    return max(0, int(x0 - l)), max(0, int(y0 - t)), min(w, int(x1 + r)), min(h, int(y1 + b))


def draw_callouts(img: Image.Image, callouts: list[dict], nodes: list[Node], box: tuple[int, int, int, int],
                  scale: float, theme: str) -> None:
    """Numbered circles with leader lines; positions in output pixels."""
    draw = ImageDraw.Draw(img)
    radius = 14
    font = load_font(18)
    primary, on_primary, halo = PRIMARY[theme], ON_PRIMARY[theme], HALO[theme]
    W, H = img.size
    for c in callouts:
        node = find(nodes, c["target"])
        if not node:
            raise RuntimeError(f"callout {c['n']}: no node matches {c['target']}")
        fx, fy = c["target"].get("at", (0.5, 0.5))
        x0, y0, x1, y1 = node.bounds
        ax = (x0 + (x1 - x0) * fx - box[0]) * scale
        ay = (y0 + (y1 - y0) * fy - box[1]) * scale
        dx, dy = c.get("offset", (0, 0))
        cx = min(max(ax + dx, radius + 2), W - radius - 3)
        cy = min(max(ay + dy, radius + 2), H - radius - 3)
        dist = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
        if dist > radius + 2:
            ex = cx + (ax - cx) * radius / dist
            ey = cy + (ay - cy) * radius / dist
            draw.line([(ex, ey), (ax, ay)], fill=halo, width=5)
            draw.line([(ex, ey), (ax, ay)], fill=primary, width=2)
            draw.ellipse([ax - 4.5, ay - 4.5, ax + 4.5, ay + 4.5], fill=halo)
            draw.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=primary)
        draw.ellipse([cx - radius - 2, cy - radius - 2, cx + radius + 2, cy + radius + 2], fill=halo)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=primary)
        draw.text((cx, cy + 0.5), str(c["n"]), fill=on_primary, font=font, anchor="mm")


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if features.check("libimagequant"):
        out = img.quantize(colors=256, method=Image.Quantize.LIBIMAGEQUANT, dither=Image.Dither.FLOYDSTEINBERG)
    else:
        out = img
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def expand(manifest: dict) -> list[dict]:
    """One entry per image: a shot with ``dark: true`` gives a light and a dark capture."""
    out = []
    for shot in manifest["shots"]:
        out.append({**shot, "theme": "light", "file": f"{shot['name']}.png"})
        if shot.get("dark"):
            out.append({**shot, "theme": "dark", "file": f"{shot['name']}.dark.png"})
    return out


def capture(dev: Device, manifest: dict, shot: dict, debug_dir: Path | None) -> Path:
    device_cfg = manifest["devices"][shot.get("device", "phone")]
    orientation = shot.get("orientation", "portrait")
    config = {**manifest["config"], **shot.get("config", {})}
    reset_app(dev, config)
    set_display(dev, shot["theme"], orientation, device_cfg.get("natural", "portrait"))
    dev.sh("logcat -c", check=False)
    token = f"{shot['name']}-launch"
    scene = shot.get("scene", [])
    if isinstance(scene, str):
        scene = manifest["scenes"][scene]
    scene = resolve_actions(scene + shot.get("scene_extra", []))
    dev.sh(f"am start -W -n {ACTIVITY} --es token {token} --es orientation {orientation} "
           f"--es actions_b64 {b64(scene)}")
    wait_log(dev, token, shot.get("timeout", 200))
    time.sleep(1.0)
    run_steps(dev, shot.get("steps", []), shot["name"])
    time.sleep(shot.get("settle", 1.2))
    img = dev.screencap()
    nodes = dump_ui(dev) if (shot.get("crop") or shot.get("callouts")) else []
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        img.save(debug_dir / f"{shot['file']}.raw.png")
        (debug_dir / f"{shot['file']}.nodes.txt").write_text(
            "\n".join(f"{n.bounds} tag={n.tag!r} desc={n.desc!r} text={n.text!r} {n.cls}" for n in nodes))
    density = device_cfg["density"]
    box = crop_box(shot.get("crop"), nodes, img.size, density)
    img = img.crop(box)
    scale = shot.get("scale", device_cfg["scale"])
    if scale != 1:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    if shot.get("callouts"):
        draw_callouts(img, shot["callouts"], nodes, box, scale, shot["theme"])
    path = OUT_DIR / shot["file"]
    save_png(img, path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="list the shots and exit")
    ap.add_argument("--markdown", action="store_true", help="print the shot table for HELP_SHOTS.md and exit")
    ap.add_argument("--only", help="comma-separated shot names")
    ap.add_argument("--theme", choices=["light", "dark"], help="only this theme")
    ap.add_argument("--keep-emulator", action="store_true", help="leave the emulator running")
    ap.add_argument("--debug", action="store_true", help="keep raw captures and UI dumps in $ANDROID_ROOT/helpshot-debug")
    ap.add_argument("--lock-wait", type=int, default=1800, help="seconds to wait for the emulator lock")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    shots = expand(manifest)
    if args.list:
        for s in manifest["shots"]:
            dark = " (+dark)" if s.get("dark") else ""
            log(f"{s['name']:<28} {s.get('device', 'phone'):<6} {s.get('orientation', 'portrait'):<9} {s.get('page', '')}{dark}")
        return
    if args.markdown:
        log("| Image | Shows | For (page: section) |")
        log("|---|---|---|")
        for s in manifest["shots"]:
            files = f"`{s['name']}.png`" + (f"<br>`{s['name']}.dark.png`" if s.get("dark") else "")
            where = s.get("device", "phone") + (", landscape" if s.get("orientation") == "landscape" else "")
            log(f"| {files} | {s.get('what', '')} ({where}) | {s.get('page', '')} |")
        return
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {s["name"] for s in shots}
        if unknown:
            sys.exit(f"unknown shots: {', '.join(sorted(unknown))}")
        shots = [s for s in shots if s["name"] in wanted]
    if args.theme:
        shots = [s for s in shots if s["theme"] == args.theme]

    android_root = env_path("ANDROID_ROOT")
    debug_dir = android_root / "helpshot-debug" if args.debug else None
    apk = apk_path()
    failures = []
    with emulator_lock(android_root / "emulator.lock", args.lock_wait):
        started: list[str] = []
        try:
            by_device: dict[str, list[dict]] = {}
            for s in shots:
                by_device.setdefault(s.get("device", "phone"), []).append(s)
            for device, group in by_device.items():
                dev, fresh = ensure_emulator(manifest["devices"][device]["avd"])
                if fresh:
                    started.append(dev.serial)
                ensure_installed(dev, apk)
                prepare_device(dev)
                for shot in group:
                    t0 = time.time()
                    try:
                        path = capture(dev, manifest, shot, debug_dir)
                        log(f"{shot['file']:<34} {path.stat().st_size // 1024:>4} KB  {time.time() - t0:4.0f} s")
                    except Exception as e:  # noqa: BLE001 - report and go on with the next shot
                        failures.append(shot["file"])
                        log(f"{shot['file']:<34} FAILED: {e}")
                        if debug_dir:
                            debug_dir.mkdir(parents=True, exist_ok=True)
                            dev.screencap().save(debug_dir / f"{shot['file']}.failed.png")
                dev.sh("cmd uimode night no", check=False)
                dev.sh("wm user-rotation lock 0", check=False)
                dev.sh(f"am force-stop {PACKAGE}", check=False)
        finally:
            if not args.keep_emulator:
                for serial in started:
                    stop_emulator(serial)
    if failures:
        sys.exit(f"{len(failures)} failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
