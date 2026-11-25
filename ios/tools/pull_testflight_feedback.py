#!/usr/bin/env python3
"""Fetch TestFlight feedback (screenshots and crashes) into a folder.

After a T session (docs/IOS.md, "Device sessions"), on Linux:

    ASC_KEY_ID=… ASC_ISSUER_ID=… ASC_KEY_PATH=~/keys/AuthKey_….p8 \\
        python3 -I ios/tools/pull_testflight_feedback.py --out <folder outside the repo>

Writes, per submission, ``<out>/screenshots/<date>_<build>_<id>/`` with
``feedback.json`` (the submission's attributes: comment, device model, iOS
version, battery, connection, locale, …), ``comment.txt`` and the images
(``screenshot-1.png``, …), and ``<out>/crashes/<date>_<build>_<id>/`` with
``feedback.json``, ``comment.txt`` and ``crash.ips`` (the crash log's text, for
``ios/tools/symbolicate.sh``). A folder that is already complete is skipped,
so running it again fetches only what is new.

The App Store Connect API endpoints it calls (App Store Connect API 4.0,
checked against Apple's documentation on 2026-11-25):

- GET /v1/apps?filter[bundleId]=… (List apps)
  developer.apple.com/documentation/appstoreconnectapi/get-v1-apps
- GET /v1/apps/{id}/betaFeedbackScreenshotSubmissions (List All Beta Feedback
  Screenshot Submissions for an App; sort ``-createdDate``, ``include=build``)
  developer.apple.com/documentation/appstoreconnectapi/get-v1-apps-_id_-betafeedbackscreenshotsubmissions
  Each submission's ``screenshots`` attribute is a list of
  BetaFeedbackScreenshotImage: ``url``, ``width``, ``height``,
  ``expirationDate`` (the URL is fetched as is, without the API token).
- GET /v1/apps/{id}/betaFeedbackCrashSubmissions (List All Beta Feedback
  Crash Submissions for an App)
  developer.apple.com/documentation/appstoreconnectapi/get-v1-apps-_id_-betafeedbackcrashsubmissions
- GET /v1/betaFeedbackCrashSubmissions/{id}/crashLog (Read the Crash Log for
  a Beta Feedback Crash Submission; BetaCrashLog's ``logText``)
  developer.apple.com/documentation/appstoreconnectapi/get-v1-betafeedbackcrashsubmissions-_id_-crashlog

The key needs the Admin, App Manager or Developer role (Apple's "Beta
feedback screenshot submissions" and "Beta feedback crash submissions"
pages); the Admin Team key from enrollment day has it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import asc_api  # noqa: E402

DONE = ".complete"


def _builds(page_included: list) -> dict:
    return {item["id"]: item.get("attributes", {}).get("version", "")
            for item in page_included or [] if item.get("type") == "builds"}


def _folder_name(submission: dict, builds: dict) -> str:
    attributes = submission.get("attributes", {})
    date = re.sub(r"[^0-9T]", "", (attributes.get("createdDate") or "")[:19]) or "undated"
    build_id = ((submission.get("relationships") or {}).get("build") or {}).get("data") or {}
    build = builds.get(build_id.get("id", ""), "")
    parts = [date] + ([f"build{build}"] if build else []) + [re.sub(r"[^A-Za-z0-9-]", "", submission["id"])]
    return "_".join(parts)


def _image_suffix(url: str) -> str:
    match = re.search(r"\.(png|jpe?g|heic)(?:\?|$)", url, re.IGNORECASE)
    return "." + match.group(1).lower() if match else ".png"


def _list(client: asc_api.Client, path: str, limit: int) -> tuple[list, dict]:
    """A list endpoint's submissions, newest first, and the builds they name."""
    params = {"sort": "-createdDate", "limit": str(min(limit, 200)), "include": "build", "fields[builds]": "version"}
    page = client.get(path, params)
    items = list(page.get("data", []))
    builds = _builds(page.get("included"))
    following = (page.get("links") or {}).get("next")
    while following and len(items) < limit:
        page = client.get(following)
        items.extend(page.get("data", []))
        builds.update(_builds(page.get("included")))
        following = (page.get("links") or {}).get("next")
    return items[:limit], builds


def _write_feedback(folder: pathlib.Path, submission: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    attributes = submission.get("attributes", {})
    record = {"id": submission["id"], "type": submission.get("type"), "attributes": attributes}
    (folder / "feedback.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (folder / "comment.txt").write_text((attributes.get("comment") or "") + "\n", encoding="utf-8")


def pull(client: asc_api.Client, out: pathlib.Path, bundle_id: str = asc_api.BUNDLE_ID,
         limit: int = 200) -> dict:
    """Fetch what isn't in ``out`` yet; returns counts per kind."""
    app = asc_api.find_app(client, bundle_id)
    counts = {"screenshots": 0, "crashes": 0, "skipped": 0, "images": 0}

    submissions, builds = _list(client, f"/v1/apps/{app['id']}/betaFeedbackScreenshotSubmissions", limit)
    for submission in submissions:
        folder = out / "screenshots" / _folder_name(submission, builds)
        if (folder / DONE).exists():
            counts["skipped"] += 1
            continue
        _write_feedback(folder, submission)
        for number, image in enumerate(submission.get("attributes", {}).get("screenshots") or [], start=1):
            url = image.get("url")
            if not url:
                continue
            (folder / f"screenshot-{number}{_image_suffix(url)}").write_bytes(client.download(url))
            counts["images"] += 1
        (folder / DONE).touch()
        counts["screenshots"] += 1

    submissions, builds = _list(client, f"/v1/apps/{app['id']}/betaFeedbackCrashSubmissions", limit)
    for submission in submissions:
        folder = out / "crashes" / _folder_name(submission, builds)
        if (folder / DONE).exists():
            counts["skipped"] += 1
            continue
        _write_feedback(folder, submission)
        log = client.get(f"/v1/betaFeedbackCrashSubmissions/{submission['id']}/crashLog",
                         {"fields[betaCrashLogs]": "logText"})
        text = ((log.get("data") or {}).get("attributes") or {}).get("logText") or ""
        (folder / "crash.ips").write_text(text, encoding="utf-8")
        (folder / DONE).touch()
        counts["crashes"] += 1
    return counts


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch TestFlight feedback screenshots and crash logs.")
    parser.add_argument("--out", required=True, type=pathlib.Path,
                        help="where to write them (outside the repository)")
    parser.add_argument("--bundle-id", default=asc_api.BUNDLE_ID)
    parser.add_argument("--limit", type=int, default=200, help="at most this many of each kind (newest first)")
    args = parser.parse_args(argv)

    credentials = asc_api.Credentials.from_env()
    if credentials is None:
        print("error: set ASC_KEY_ID, ASC_ISSUER_ID and ASC_KEY_PATH (docs/IOS.md, \"Enrollment day\")",
              file=sys.stderr)
        return 2
    try:
        counts = pull(asc_api.Client.from_credentials(credentials), args.out, args.bundle_id, args.limit)
    except asc_api.ASCError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{counts['screenshots']} new screenshot submissions ({counts['images']} images),"
          f" {counts['crashes']} new crashes, {counts['skipped']} already there; in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
