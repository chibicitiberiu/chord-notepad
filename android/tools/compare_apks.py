#!/usr/bin/env python3
"""Compare two APKs entry by entry, recursing into nested zips (Chaquopy .imy).

A lightweight stand-in for diffoscope: reports entries that exist in only one
APK, entries whose content differs (by sha256), and zip metadata differences
(timestamps, order, compression) that change the APK bytes even when the
contents match. For differing .pyc files it also prints the header (flags and
source mtime / hash), the usual culprit.

Usage: python3 compare_apks.py a.apk b.apk
"""

import hashlib
import io
import struct
import sys
import zipfile

NESTED = (".imy", ".zip", ".jar", ".whl")


def _entries(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return [(i, zf.read(i)) for i in zf.infolist() if not i.is_dir()]


def _pyc_header(data: bytes) -> str:
    if len(data) < 16:
        return "short"
    flags, = struct.unpack_from("<I", data, 4)
    if flags & 1:
        return f"hash-based (checked={bool(flags & 2)}) hash={data[8:16].hex()}"
    mtime, size = struct.unpack_from("<II", data, 8)
    return f"timestamp mtime={mtime} size={size}"


def compare(a: bytes, b: bytes, prefix: str, out: list) -> None:
    ea = {i.filename: (i, d) for i, d in _entries(a)}
    eb = {i.filename: (i, d) for i, d in _entries(b)}
    for name in sorted(set(ea) - set(eb)):
        out.append(f"only in A: {prefix}{name}")
    for name in sorted(set(eb) - set(ea)):
        out.append(f"only in B: {prefix}{name}")
    order_a = [n for n in ea if n in eb]
    order_b = [n for n in eb if n in ea]
    if order_a != order_b:
        out.append(f"entry order differs: {prefix or '(top level)'}")
    for name in sorted(set(ea) & set(eb)):
        (ia, da), (ib, db) = ea[name], eb[name]
        if da != db:
            if name.endswith(NESTED):
                compare(da, db, f"{prefix}{name}!", out)
                out.append(f"content differs: {prefix}{name} (nested, see above)")
            else:
                line = f"content differs: {prefix}{name} ({len(da)} vs {len(db)} bytes)"
                if name.endswith(".pyc"):
                    line += f"\n    A: {_pyc_header(da)}\n    B: {_pyc_header(db)}"
                out.append(line)
        else:
            meta = []
            if ia.date_time != ib.date_time:
                meta.append(f"date {ia.date_time} vs {ib.date_time}")
            if ia.compress_type != ib.compress_type:
                meta.append(f"compression {ia.compress_type} vs {ib.compress_type}")
            if ia.external_attr != ib.external_attr:
                meta.append(f"attrs {ia.external_attr:o} vs {ib.external_attr:o}")
            if meta:
                out.append(f"metadata differs: {prefix}{name}: {', '.join(meta)}")


def main(argv) -> int:
    a, b = (open(p, "rb").read() for p in argv[1:3])
    print(f"A {argv[1]}: {len(a)} bytes sha256 {hashlib.sha256(a).hexdigest()}")
    print(f"B {argv[2]}: {len(b)} bytes sha256 {hashlib.sha256(b).hexdigest()}")
    if a == b:
        print("IDENTICAL")
        return 0
    out = []
    compare(a, b, "", out)
    print("\n".join(out) if out else "entries identical; difference is in zip structure/signature only")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
