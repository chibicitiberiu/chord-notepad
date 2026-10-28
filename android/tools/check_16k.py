#!/usr/bin/env python3
"""Check an APK for 16 KB page-size compatibility.

For every ``lib/<abi>/*.so`` in the APK:
- the entry must be stored uncompressed at a 16384-byte-aligned offset
  (so it can be mmapped straight from the APK), and
- every ELF PT_LOAD segment must have p_align >= 16384.

ELF files nested in Chaquopy's assets (``assets/chaquopy/**.so`` and the
``*.imy`` zips, which Chaquopy extracts at runtime) only need the ELF check.

Usage: python3 check_16k.py app.apk [more.apk ...]   (exit code 1 on failure)
"""

import io
import struct
import sys
import zipfile

PAGE = 16384


def elf_load_aligns(data: bytes):
    """Return the p_align of every PT_LOAD segment, or None if not ELF64."""
    if data[:4] != b"\x7fELF" or data[4] != 2:  # ELFCLASS64 only
        return None
    endian = "<" if data[5] == 1 else ">"
    e_phoff, = struct.unpack_from(endian + "Q", data, 0x20)
    e_phentsize, e_phnum = struct.unpack_from(endian + "HH", data, 0x36)
    aligns = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, = struct.unpack_from(endian + "I", data, off)
        if p_type == 1:  # PT_LOAD
            p_align, = struct.unpack_from(endian + "Q", data, off + 0x30)
            aligns.append(p_align)
    return aligns


def local_data_offset(apk: bytes, info: zipfile.ZipInfo) -> int:
    header = info.header_offset
    name_len, extra_len = struct.unpack_from("<HH", apk, header + 26)
    return header + 30 + name_len + extra_len


def check_elf(label: str, data: bytes, problems: list, rows: list) -> None:
    aligns = elf_load_aligns(data)
    if aligns is None:
        return
    ok = all(a >= PAGE for a in aligns)
    rows.append((label, min(aligns) if aligns else 0, ok))
    if not ok:
        problems.append(f"{label}: PT_LOAD align {sorted(set(aligns))}")


def check_apk(path: str) -> list:
    problems, rows = [], []
    raw = open(path, "rb").read()
    with zipfile.ZipFile(io.BytesIO(raw)) as apk:
        for info in apk.infolist():
            name = info.filename
            if name.startswith("lib/") and name.endswith(".so"):
                offset = local_data_offset(raw, info)
                if info.compress_type != zipfile.ZIP_STORED:
                    problems.append(f"{name}: compressed (needs useLegacyPackaging=false)")
                elif offset % PAGE:
                    problems.append(f"{name}: zip data offset {offset} not 16 KB aligned")
                check_elf(name, apk.read(info), problems, rows)
            elif name.startswith("assets/chaquopy/") and name.endswith(".so"):
                check_elf(name, apk.read(info), problems, rows)
            elif name.startswith("assets/chaquopy/") and name.endswith(".imy"):
                with zipfile.ZipFile(io.BytesIO(apk.read(info))) as inner:
                    for sub in inner.infolist():
                        if ".so" in sub.filename.rsplit("/", 1)[-1]:
                            check_elf(f"{name}!{sub.filename}", inner.read(sub), problems, rows)
    print(f"{path}: {len(rows)} ELF files checked")
    for label, align, ok in rows:
        print(f"  {'ok ' if ok else 'BAD'} {align:>6}  {label}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    return problems


def main(argv) -> int:
    failed = False
    for path in argv[1:]:
        failed |= bool(check_apk(path))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
