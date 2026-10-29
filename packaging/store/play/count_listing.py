#!/usr/bin/env python3
"""Check the Play listing text against Play Console's length limits."""
import re
import sys
from pathlib import Path

LIMITS = {"Title": 30, "Short description": 80, "Full description": 4000, "Release notes (first release)": 500}
text = Path(__file__).with_name("listing-en-US.txt").read_text(encoding="utf-8")
sections = dict(re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M))
ok = True
for name, limit in LIMITS.items():
    body = sections[name].strip()
    n = len(body)
    ok &= n <= limit
    print(f"{name:32} {n:5} / {limit}  {'ok' if n <= limit else 'TOO LONG'}")
sys.exit(0 if ok else 1)
