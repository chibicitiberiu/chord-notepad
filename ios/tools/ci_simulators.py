#!/usr/bin/env python3
"""Pick the iPhone and iPad simulators CI tests on (docs/IOS.md, "CI").

    python3 ios/tools/ci_simulators.py >> "$GITHUB_ENV"

Prints ``IPHONE_UDID=…``, ``IPAD_UDID=…`` and their names and runtime. The
newest iOS runtime the image has wins (it matches the pinned Xcode, whose
SDK version the image's runtimes follow); within it the preferred models
below, else the first iPhone and iPad. The choice goes to stderr for the log.
"""

import json
import re
import subprocess
import sys

PREFERRED = {
    "iphone": ["iPhone 17", "iPhone 17 Pro", "iPhone 16"],
    "ipad": ["iPad Air 11-inch (M4)", "iPad Air 11-inch (M3)", "iPad (A16)"],
}


def runtime_version(key: str) -> tuple:
    """``com.apple.CoreSimulator.SimRuntime.iOS-26-5`` -> (26, 5)."""
    match = re.search(r"\.iOS-(\d+)-(\d+)(?:-(\d+))?$", key)
    return tuple(int(part) for part in match.groups() if part) if match else ()


def main() -> int:
    listing = json.loads(subprocess.run(["xcrun", "simctl", "list", "devices", "available", "-j"],
                                        check=True, capture_output=True, text=True).stdout)
    runtimes = sorted((key for key in listing["devices"] if runtime_version(key)), key=runtime_version,
                      reverse=True)
    for runtime in runtimes:
        devices = listing["devices"][runtime]
        chosen = {}
        for kind, names in PREFERRED.items():
            prefix = "iPhone" if kind == "iphone" else "iPad"
            candidates = [d for d in devices if d["name"] in names]
            candidates.sort(key=lambda d: names.index(d["name"]))
            candidates += [d for d in devices if d["name"].startswith(prefix)]
            if candidates:
                chosen[kind] = candidates[0]
        if len(chosen) == 2:
            version = ".".join(str(v) for v in runtime_version(runtime))
            for kind, device in chosen.items():
                upper = kind.upper()
                print(f"{upper}_UDID={device['udid']}")
                print(f"{upper}_NAME={device['name']}")
                print(f"Using {device['name']} ({device['udid']}) on iOS {version}", file=sys.stderr)
            print(f"SIM_RUNTIME={version}")
            return 0
    print("No iOS runtime has both an iPhone and an iPad simulator", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
