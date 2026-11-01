#!/usr/bin/env python3
"""Check each language of the newest whats-new-<version>.txt against Partner
Center's 1500-character limit for "What's new in this version"."""
import re
import sys
from pathlib import Path

LIMIT = 1500
newest = max(Path(__file__).parent.glob("whats-new-*.txt"),
             key=lambda p: [int(n) for n in re.findall(r"\d+", p.stem)])
text = newest.read_text(encoding="utf-8")
blocks = dict(re.findall(r"^== (.+?) ==\n(.*?)(?=^== |\Z)", text, flags=re.S | re.M))
ok = True
print(newest.name)
for language, body in blocks.items():
    n = len(body.strip())
    ok &= n <= LIMIT
    print(f"{language:8} {n:5} / {LIMIT}  {'ok' if n <= LIMIT else 'TOO LONG'}")
sys.exit(0 if ok else 1)
