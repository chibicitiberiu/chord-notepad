#!/usr/bin/env python3
"""Put the iOS app's licence list and the texts it names into the app.

The "Licences" build phase (ios/project.yml) runs this:

    python3 -I ios/tools/copy_licences.py <app>/licenses

It writes ``components.json`` (ios/Licenses/components.json,
the list of what the iOS app ships: docs/IOS.md, "About and licences") and
``texts/<name>.txt`` for each text an entry names, from
resources/licenses/texts (the desktop's), so no text is copied twice in the
repository and none the app doesn't list is shipped. A text that is missing
fails the build. Standard library only.
"""

import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
COMPONENTS = REPO / "ios/Licenses/components.json"
TEXTS = REPO / "resources/licenses/texts"


def main(argv: list) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    out = pathlib.Path(argv[1])
    components = json.loads(COMPONENTS.read_text(encoding="utf-8"))["components"]
    names = sorted({name for c in components for name in c["texts"]})
    missing = [name for name in names if not (TEXTS / f"{name}.txt").is_file()]
    if missing:
        print(f"error: licence texts missing from {TEXTS}: {', '.join(missing)}", file=sys.stderr)
        return 1
    if out.exists():
        shutil.rmtree(out)
    (out / "texts").mkdir(parents=True)
    shutil.copyfile(COMPONENTS, out / "components.json")
    for name in names:
        shutil.copyfile(TEXTS / f"{name}.txt", out / "texts" / f"{name}.txt")
    print(f"Wrote {out}: {len(components)} components, {len(names)} texts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
