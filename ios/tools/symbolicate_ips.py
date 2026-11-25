#!/usr/bin/env python3
"""Symbolicate an iOS crash report on Linux (ios/tools/symbolicate.sh runs this).

    python3 -I ios/tools/symbolicate_ips.py <crash.ips> <dSYM folder or .dSYM>... \\
        [--symbolizer llvm-symbolizer-18] [--demangler swift-demangle]

The report is the ``.ips`` format iOS writes since iOS 15 (Settings >
Privacy > Analytics Data, TestFlight's crash feedback, Xcode's Organizer):
one line of JSON (the header: app, version, OS, incident) and then a JSON
body with ``usedImages`` (each binary's load address, size and UUID) and
``threads`` / ``lastExceptionBacktrace`` (frames as ``imageIndex`` plus
``imageOffset``). The older text format (a "Binary Images:" list and frames
like ``3  ChordNotepad  0x… 0x100… + 1234``) is read too.

Each image is matched to a dSYM by UUID, read from the dSYM's own Mach-O
(LC_UUID), never by name: a dSYM from another build gives believable but
wrong lines, so an image of the app (one under ``.app/``) with no matching
dSYM stops the run unless ``--allow-missing`` is given. The address looked
up is the dSYM's __TEXT vmaddr plus the frame's offset; for every frame
but a thread's first, one byte less, since those are return addresses
(the line of the call, not of the instruction after it).

llvm-symbolizer (``--output-style=JSON``, LLVM 14 or later) turns addresses
into function, file and line; Swift names go through ``swift-demangle`` when
one is on PATH (the Swift toolchain's), C++ names through the symbolizer's
own demangler.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

# Mach-O constants (mach-o/loader.h, mach-o/fat.h)
MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_64 = 0xCAFEBABF
LC_SEGMENT_64 = 0x19
LC_UUID = 0x1B
CPU_TYPES = {0x0100000C: "arm64", 0x01000007: "x86_64"}


@dataclass
class Slice:
    path: pathlib.Path
    arch: str
    uuid: str
    text_vmaddr: int


@dataclass
class Image:
    index: int
    name: str
    path: str
    uuid: str
    base: int
    arch: str = "arm64"


@dataclass
class Frame:
    image: int
    offset: int
    symbol: str = ""
    first: bool = False
    resolved: list = field(default_factory=list)


@dataclass
class Thread:
    title: str
    frames: list
    triggered: bool = False


@dataclass
class Report:
    header: dict
    body: dict
    images: list
    threads: list


# --- Mach-O ---------------------------------------------------------------

def _thin_slice(data: bytes, offset: int, path: pathlib.Path) -> Optional[Slice]:
    magic, cputype, _, _, ncmds, _, _, _ = struct.unpack_from("<IiiIIIII", data, offset)
    if magic != MH_MAGIC_64:
        return None
    pos = offset + 32
    uuid, vmaddr = "", 0
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, pos)
        if cmd == LC_UUID:
            raw = data[pos + 8:pos + 24].hex().upper()
            uuid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
        elif cmd == LC_SEGMENT_64:
            name = data[pos + 8:pos + 24].rstrip(b"\x00").decode()
            if name == "__TEXT":
                vmaddr = struct.unpack_from("<Q", data, pos + 24)[0]
        pos += size
    if not uuid:
        return None
    return Slice(path, CPU_TYPES.get(cputype & 0xFFFFFFFF, hex(cputype)), uuid, vmaddr)


def macho_slices(path: pathlib.Path) -> list:
    """(arch, UUID, __TEXT vmaddr) of each slice of a Mach-O file."""
    data = path.read_bytes()
    if len(data) < 32:
        return []
    magic_be = struct.unpack_from(">I", data, 0)[0]
    if magic_be in (FAT_MAGIC, FAT_MAGIC_64):
        count = struct.unpack_from(">I", data, 4)[0]
        slices = []
        for n in range(count):
            if magic_be == FAT_MAGIC:
                _, _, offset, _, _ = struct.unpack_from(">iiIII", data, 8 + n * 20)
            else:
                _, _, offset, _, _, _ = struct.unpack_from(">iiQQII", data, 8 + n * 32)
            found = _thin_slice(data, offset, path)
            if found:
                slices.append(found)
        return slices
    found = _thin_slice(data, 0, path)
    return [found] if found else []


def index_dsyms(paths: list) -> dict:
    """UUID -> Slice for every DWARF file in the .dSYM bundles under ``paths``."""
    found: dict = {}
    for root in paths:
        root = pathlib.Path(root)
        candidates = [root] if root.is_file() else list(root.rglob("Contents/Resources/DWARF/*"))
        for candidate in candidates:
            if candidate.is_file():
                for item in macho_slices(candidate):
                    found[item.uuid] = item
    return found


# --- Reports --------------------------------------------------------------

def _uuid(text: str) -> str:
    raw = re.sub(r"[^0-9A-Fa-f]", "", text or "").upper()
    if len(raw) != 32:
        return (text or "").upper()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def _frames(raw_frames: list) -> list:
    frames = []
    for n, raw in enumerate(raw_frames or []):
        frames.append(Frame(image=raw.get("imageIndex", -1), offset=raw.get("imageOffset", 0),
                            symbol=raw.get("symbol", ""), first=(n == 0)))
    return frames


def parse_ips(text: str) -> Report:
    """The JSON .ips format: a header line, then the body."""
    first, _, rest = text.lstrip().partition("\n")
    header = json.loads(first)
    body = json.loads(rest) if rest.strip() else {}
    if "usedImages" not in body and "usedImages" in header:
        header, body = {}, header  # a body saved on its own
    images = [Image(n, img.get("name") or pathlib.PurePosixPath(img.get("path", "?")).name,
                    img.get("path", ""), _uuid(img.get("uuid", "")), img.get("base", 0), img.get("arch", "arm64"))
              for n, img in enumerate(body.get("usedImages", []))]
    threads = []
    if body.get("lastExceptionBacktrace"):
        threads.append(Thread("Last Exception Backtrace", _frames(body["lastExceptionBacktrace"])))
    for n, thread in enumerate(body.get("threads", [])):
        title = f"Thread {n}" + (f" ({thread['queue']})" if thread.get("queue") else "") + \
            (f" {thread['name']}" if thread.get("name") else "")
        threads.append(Thread(title, _frames(thread.get("frames")), bool(thread.get("triggered"))))
    return Report(header, body, images, threads)


_TEXT_IMAGE = re.compile(r"^\s*0x([0-9a-f]+)\s+-\s+0x[0-9a-f]+\s+\+?(\S+)\s+(\S+)\s+<([0-9a-f-]+)>\s+(\S.*)$", re.I)
_TEXT_FRAME = re.compile(r"^(\d+)\s+(\S+)\s+0x([0-9a-f]+)\s+(.*)$", re.I)


def parse_text(text: str) -> Report:
    """The older text crash report."""
    lines = text.splitlines()
    images, by_name = [], {}
    in_images = False
    for line in lines:
        if line.startswith("Binary Images:"):
            in_images = True
            continue
        if in_images:
            match = _TEXT_IMAGE.match(line)
            if match:
                image = Image(len(images), match.group(2), match.group(5).strip(), _uuid(match.group(4)),
                              int(match.group(1), 16), match.group(3))
                images.append(image)
                by_name.setdefault(image.name, image)
    threads, current = [], None
    for line in lines:
        if re.match(r"^(Thread \d+|Last Exception Backtrace)", line) and line.rstrip().endswith(":"):
            current = Thread(line.rstrip(": "), [], "Crashed" in line)
            threads.append(current)
            continue
        match = _TEXT_FRAME.match(line)
        if current is not None and match:
            image = by_name.get(match.group(2))
            address = int(match.group(3), 16)
            offset = address - image.base if image else 0
            current.frames.append(Frame(image.index if image else -1, offset, match.group(4).strip(),
                                        first=not current.frames))
        elif current is not None and not line.strip():
            current = None
    header = {"text": "\n".join(lines[:12])}
    return Report(header, {}, images, threads)


def parse(text: str) -> Report:
    stripped = text.lstrip()
    return parse_ips(text) if stripped.startswith("{") else parse_text(text)


def is_app_image(image: Image) -> bool:
    return ".app/" in image.path


# --- Symbolication --------------------------------------------------------

def symbolize(symbolizer: str, dwarf: pathlib.Path, arch: str, addresses: list) -> list:
    """llvm-symbolizer's frames (inlined ones first) for each address."""
    if not addresses:
        return []
    result = subprocess.run([symbolizer, f"--obj={dwarf}", f"--default-arch={arch}", "--inlining", "--demangle",
                             "--output-style=JSON", *[hex(a) for a in addresses]],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{symbolizer} failed: {result.stderr.strip()}")
    out = json.loads(result.stdout)
    if isinstance(out, dict):
        out = [out]
    return [entry.get("Symbol", []) for entry in out]


def demangle(names: list, demangler: Optional[str]) -> dict:
    swift = sorted({n for n in names if n.startswith(("$s", "_$s", "$S", "_T0"))})
    if not swift or not demangler:
        return {}
    result = subprocess.run([demangler, "--simplified", *swift], capture_output=True, text=True, check=False)
    lines = result.stdout.splitlines() if result.returncode == 0 else []
    return dict(zip(swift, lines)) if len(lines) == len(swift) else {}


def symbolicate(report: Report, dsyms: dict, symbolizer: str, demangler: Optional[str] = None,
                allow_missing: bool = False) -> list:
    """Fill each frame's ``resolved``; returns the app images with no dSYM."""
    missing = [img for img in report.images if is_app_image(img) and img.uuid not in dsyms]
    used = {f.image for t in report.threads for f in t.frames}
    missing = [img for img in missing if img.index in used]
    if missing and not allow_missing:
        return missing
    for image in report.images:
        dsym = dsyms.get(image.uuid)
        if dsym is None:
            continue
        frames = [f for t in report.threads for f in t.frames if f.image == image.index]
        addresses = [dsym.text_vmaddr + f.offset - (0 if f.first else 1) for f in frames]
        for frame, resolved in zip(frames, symbolize(symbolizer, dsym.path, image.arch or dsym.arch, addresses)):
            frame.resolved = [r for r in resolved if r.get("FunctionName") not in (None, "", "??")]
    names = [r["FunctionName"] for t in report.threads for f in t.frames for r in f.resolved]
    mapping = demangle(names, demangler)
    for thread in report.threads:
        for frame in thread.frames:
            for r in frame.resolved:
                r["FunctionName"] = mapping.get(r["FunctionName"], r["FunctionName"])
    return missing


def _location(entry: dict) -> str:
    line = entry.get("Line") or 0
    name = pathlib.PurePosixPath(entry.get("FileName") or "").name
    return f" ({name}:{line})" if name and line else ""


def render(report: Report) -> str:
    out = []
    header, body = report.header, report.body
    if "app_name" in header:
        out.append(f"{header.get('app_name')} {header.get('app_version', '')} ({header.get('build_version', '')}),"
                   f" {header.get('os_version', '')}, {header.get('timestamp', '')}")
        out.append(f"Incident {header.get('incident_id', '')}")
    elif header.get("text"):
        out.append(header["text"])
    exception = body.get("exception") or {}
    if exception:
        out.append(f"Exception: {exception.get('type', '')} {exception.get('signal', '')}"
                   f" {exception.get('codes', '')}".rstrip())
    termination = body.get("termination") or {}
    if termination:
        out.append(f"Termination: {termination.get('namespace', '')} {termination.get('indicator', '')}"
                   f" {' '.join(termination.get('reasons', []) or [])}".rstrip())
    for key in ("asi", "ktriageinfo"):
        if body.get(key):
            out.append(f"{key}: {json.dumps(body[key])}")
    for thread in report.threads:
        out.append("")
        out.append(thread.title + (" (crashed)" if thread.triggered else ""))
        for n, frame in enumerate(thread.frames):
            image = report.images[frame.image] if 0 <= frame.image < len(report.images) else None
            name = image.name if image else "???"
            address = (image.base + frame.offset) if image else frame.offset
            if frame.resolved:
                for depth, entry in enumerate(frame.resolved):
                    prefix = f"{n:<3}" if depth == 0 else "   "
                    inlined = "" if depth == len(frame.resolved) - 1 else " [inlined]"
                    out.append(f"{prefix} {name:<28} 0x{address:016x} {entry['FunctionName']}{_location(entry)}{inlined}")
            else:
                out.append(f"{n:<3} {name:<28} 0x{address:016x} {frame.symbol or f'+ {frame.offset}'}")
    return "\n".join(out) + "\n"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Symbolicate an iOS crash report with llvm-symbolizer.")
    parser.add_argument("report", type=pathlib.Path)
    parser.add_argument("dsyms", nargs="+", type=pathlib.Path, help=".dSYM bundles or folders holding them")
    parser.add_argument("--symbolizer", default=shutil.which("llvm-symbolizer") or "llvm-symbolizer")
    parser.add_argument("--demangler", default=shutil.which("swift-demangle"))
    parser.add_argument("--allow-missing", action="store_true",
                        help="go on when an image of the app has no dSYM with its UUID")
    args = parser.parse_args(argv)

    report = parse(args.report.read_text(encoding="utf-8", errors="replace"))
    dsyms = index_dsyms(args.dsyms)
    try:
        missing = symbolicate(report, dsyms, args.symbolizer, args.demangler, args.allow_missing)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if missing and not args.allow_missing:
        print("error: no dSYM with the UUID of " + ", ".join(f"{i.name} ({i.uuid})" for i in missing)
              + ". dSYMs found: " + (", ".join(f"{s.path.name} {u}" for u, s in sorted(dsyms.items())) or "none")
              + ". Take them from the same CI run as the build (docs/IOS.md, \"Crash reports\").", file=sys.stderr)
        return 1
    sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
