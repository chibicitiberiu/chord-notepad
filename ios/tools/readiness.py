#!/usr/bin/env python3
"""Is everything ready for a device session? (docs/IOS.md, "Device sessions")

Run on Linux the day before a session on the borrowed Mac or iPhone:

    python3 -I ios/tools/readiness.py S0|T|S1|S2 [--date 2026-12-05] [--issues FILE]

It checks, through ``gh`` (logged in, read access is enough):

- the latest finished ios.yml run on main that tested the app (a push or a
  dispatch) is green;
- that run's artifacts the session needs exist and won't have expired by
  the session date: ``ios-build-inputs`` (the prebuilt frameworks, Python
  bundle and guide for the SSD; S0, S1, S2), ``ios-catalog`` and
  ``ios-screenshots`` (S1);
- the release lanes' artifacts from the latest run that made them:
  ``ios-development`` (the development IPA and its dSYM, S2) and
  ``ios-testflight-dsyms`` (T);

and, when App Store Connect credentials are set (ASC_KEY_ID, ASC_ISSUER_ID,
ASC_KEY_PATH, as for asc_api.py):

- the newest TestFlight build is processed (VALID), not expired, and won't
  expire within 30 days of the session (T);
- the tester (``--tester-email`` or CN_TESTER_EMAIL) has accepted the
  invitation (T);
- her iPhone's UDID (``--udid`` or CN_DEVICE_UDID) is registered and
  enabled (S2);

and that the session's numbered issue list (``--issues``, kept outside the
repository) has an expected result for every issue (T, S1, S2). Then it
prints the session's plan and the manual checklist from docs/IOS.md.

Exit status 0 means ready, 1 not ready, 2 a usage error. Before enrollment
there are no credentials: the App Store Connect checks show as skipped, and
fail only for T, which can't happen without them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import asc_api  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
IOS_DOC = REPO_ROOT / "docs" / "IOS.md"
WORKFLOW = "ios.yml"
TESTFLIGHT_MARGIN_DAYS = 30

# What each session needs. "artifacts": from the latest green test run;
# "lane_artifacts": from the latest run of a release lane; "asc": the App
# Store Connect checks; "issues": a numbered issue list is required.
SESSIONS = {
    "S0": {"title": "bootstrap and enrollment", "artifacts": ["ios-build-inputs", "ios-screenshots"],
           "lane_artifacts": [], "asc": [], "issues": False},
    "T": {"title": "TestFlight smoke", "artifacts": [], "lane_artifacts": ["ios-testflight-dsyms"],
          "asc": ["build", "tester"], "issues": True},
    "S1": {"title": "layout polish", "artifacts": ["ios-build-inputs", "ios-catalog", "ios-screenshots"],
           "lane_artifacts": [], "asc": [], "issues": True},
    "S2": {"title": "device debugging and Instruments", "artifacts": ["ios-build-inputs"],
           "lane_artifacts": ["ios-development"], "asc": ["device"], "issues": True},
}

OK, FAIL, SKIP = "ok", "FAIL", "skip"


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _end_of(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)


# --- GitHub ---------------------------------------------------------------

GhRunner = Callable[[list], str]


def run_gh(args: list) -> str:
    """``gh <args>``; its output, or an error naming the command."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


class GitHub:
    def __init__(self, gh: GhRunner, repo: str, branch: str = "main"):
        self.gh = gh
        self.repo = repo
        self.branch = branch
        self._runs: Optional[list] = None
        self._artifacts: dict = {}

    def runs(self) -> list:
        """ios.yml's recent runs on the branch, newest first."""
        if self._runs is None:
            out = self.gh(["run", "list", "--repo", self.repo, "--workflow", WORKFLOW, "--branch", self.branch,
                           "--limit", "50", "--json", "databaseId,status,conclusion,headSha,event,createdAt,url"])
            self._runs = sorted(json.loads(out), key=lambda run: run["createdAt"], reverse=True)
        return self._runs

    def artifacts(self, run_id: int) -> list:
        if run_id not in self._artifacts:
            out = self.gh(["api", f"repos/{self.repo}/actions/runs/{run_id}/artifacts?per_page=100"])
            self._artifacts[run_id] = json.loads(out).get("artifacts", [])
        return self._artifacts[run_id]


def latest_test_run(github: GitHub) -> Optional[dict]:
    """The newest finished run that ran the tests: a push or a dispatch (the
    monthly schedule runs only the TestFlight lane)."""
    for run in github.runs():
        if run["event"] in ("push", "workflow_dispatch") and run["status"] == "completed":
            return run
    return None


def check_ci(github: GitHub) -> tuple[Check, Optional[dict]]:
    run = latest_test_run(github)
    if run is None:
        return Check("CI", FAIL, f"no finished {WORKFLOW} run on {github.branch}"), None
    pending = [r for r in github.runs() if r["status"] != "completed" and r["createdAt"] > run["createdAt"]]
    note = f"; {len(pending)} newer run(s) still going" if pending else ""
    detail = f"run {run['databaseId']} ({run['event']}, {run['headSha'][:7]}): {run['conclusion']}{note} {run['url']}"
    return Check("CI", OK if run["conclusion"] == "success" else FAIL, detail), run


def _artifact_check(name: str, artifacts: list, run: dict, session_day: dt.date) -> Check:
    found = [a for a in artifacts if a.get("name") == name]
    if not found:
        return Check(f"artifact {name}", FAIL, f"not in run {run['databaseId']}")
    artifact = found[0]
    if artifact.get("expired"):
        return Check(f"artifact {name}", FAIL, f"expired (run {run['databaseId']}); run the workflow again")
    expires = _parse_time(artifact["expires_at"]) if artifact.get("expires_at") else None
    size = f"{artifact.get('size_in_bytes', 0) / 1e6:.0f} MB"
    if expires and expires < _end_of(session_day):
        return Check(f"artifact {name}", FAIL,
                     f"expires {expires:%Y-%m-%d}, before the session; run the workflow again")
    until = f", until {expires:%Y-%m-%d}" if expires else ""
    return Check(f"artifact {name}", OK, f"run {run['databaseId']} ({run['headSha'][:7]}), {size}{until}")


def check_artifacts(github: GitHub, run: Optional[dict], names: list, session_day: dt.date) -> list:
    if not names:
        return []
    if run is None:
        return [Check(f"artifact {name}", FAIL, "no test run to take it from") for name in names]
    artifacts = github.artifacts(run["databaseId"])
    return [_artifact_check(name, artifacts, run, session_day) for name in names]


def check_lane_artifacts(github: GitHub, names: list, session_day: dt.date, tested_sha: Optional[str]) -> list:
    """Each name from the newest successful run that has it (a dispatch or
    the schedule: the release lanes)."""
    checks = []
    for name in names:
        for run in github.runs():
            if run["status"] != "completed" or run["conclusion"] != "success" or run["event"] == "push":
                continue
            if any(a.get("name") == name for a in github.artifacts(run["databaseId"])):
                check = _artifact_check(name, github.artifacts(run["databaseId"]), run, session_day)
                if check.status == OK and tested_sha and run["headSha"] != tested_sha:
                    check.detail += f"; built from {run['headSha'][:7]}, not the latest tested {tested_sha[:7]}"
                checks.append(check)
                break
        else:
            checks.append(Check(f"artifact {name}", FAIL, "no release-lane run has made it yet (docs/IOS.md, \"Release lanes\")"))
    return checks


# --- App Store Connect ----------------------------------------------------

def check_testflight_build(client: asc_api.Client, app_id: str, session_day: dt.date) -> Check:
    page = client.get("/v1/builds", {
        "filter[app]": app_id, "sort": "-uploadedDate", "limit": "1",
        "fields[builds]": "version,uploadedDate,expirationDate,expired,processingState,buildBetaDetail",
        "include": "buildBetaDetail", "fields[buildBetaDetails]": "internalBuildState"})
    builds = page.get("data", [])
    if not builds:
        return Check("TestFlight build", FAIL, "no build uploaded yet (dispatch ios.yml with testflight)")
    build = builds[0]["attributes"]
    beta = next((i.get("attributes", {}) for i in page.get("included", []) if i.get("type") == "buildBetaDetails"), {})
    internal = beta.get("internalBuildState", "unknown")
    expires = _parse_time(build["expirationDate"]) if build.get("expirationDate") else None
    detail = (f"build {build.get('version')} uploaded {build.get('uploadedDate', '')[:10]}, "
              f"{build.get('processingState')}, internal testing {internal}"
              + (f", expires {expires:%Y-%m-%d}" if expires else ""))
    if build.get("processingState") != "VALID" or build.get("expired"):
        return Check("TestFlight build", FAIL, detail)
    if internal not in ("IN_BETA_TESTING", "READY_FOR_BETA_TESTING"):
        return Check("TestFlight build", FAIL, detail + " (not available to internal testers yet)")
    margin = dt.timedelta(days=TESTFLIGHT_MARGIN_DAYS)
    if expires and expires < _end_of(session_day) + margin:
        return Check("TestFlight build", FAIL, detail + f"; less than {TESTFLIGHT_MARGIN_DAYS} days left at the"
                     " session: dispatch ios.yml with testflight")
    return Check("TestFlight build", OK, detail)


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return (name[:1] + "…@" + domain) if domain else "…"


def check_tester(client: asc_api.Client, app_id: str, email: Optional[str]) -> Check:
    if not email:
        return Check("tester", FAIL, "pass --tester-email or set CN_TESTER_EMAIL")
    testers = list(client.get_all("/v1/betaTesters", {"filter[apps]": app_id, "filter[email]": email,
                                                       "fields[betaTesters]": "state,inviteType"}))
    if not testers:
        return Check("tester", FAIL, f"{_mask(email)} isn't a tester of the app yet")
    state = testers[0].get("attributes", {}).get("state", "unknown")
    status = OK if state in ("ACCEPTED", "INSTALLED") else FAIL
    return Check("tester", status, f"{_mask(email)}: {state}")


def check_device(client: asc_api.Client, udid: Optional[str]) -> Check:
    if not udid:
        return Check("device", FAIL, "pass --udid or set CN_DEVICE_UDID (recorded in S0)")
    devices = list(client.get_all("/v1/devices", {"filter[udid]": udid, "filter[platform]": "IOS"}))
    if not devices:
        return Check("device", FAIL, "the UDID isn't registered: ios/tools/asc_api.py register-device")
    attributes = devices[0].get("attributes", {})
    status = OK if attributes.get("status") == "ENABLED" else FAIL
    return Check("device", status, f"{attributes.get('model') or attributes.get('name')}: {attributes.get('status')}"
                 " (the development IPA must be built after it was registered)")


def check_asc(client: Optional[asc_api.Client], needs: list, session_day: dt.date,
              email: Optional[str], udid: Optional[str], required: bool) -> list:
    if not needs:
        return []
    if client is None:
        status = FAIL if required else SKIP
        return [Check(f"App Store Connect: {need}", status, "no credentials (ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH)")
                for need in needs]
    checks = []
    try:
        app_id = asc_api.find_app(client)["id"] if {"build", "tester"} & set(needs) else ""
        for need in needs:
            if need == "build":
                checks.append(check_testflight_build(client, app_id, session_day))
            elif need == "tester":
                checks.append(check_tester(client, app_id, email))
            elif need == "device":
                checks.append(check_device(client, udid))
    except asc_api.ASCError as error:
        checks.append(Check("App Store Connect", FAIL, str(error)))
    return checks


# --- Issue list and docs --------------------------------------------------

def check_issues(path: Optional[pathlib.Path], required: bool) -> list:
    """A numbered list (``1. …``); each item needs an ``Expected:`` line."""
    if path is None:
        return [Check("issue list", FAIL if required else SKIP, "pass --issues FILE")] if required else []
    if not path.is_file():
        return [Check("issue list", FAIL, f"{path} doesn't exist")]
    items: list = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\d+\.\s", line):
            items.append([line])
        elif items:
            items[-1].append(line)
    if not items:
        return [Check("issue list", FAIL, f"{path} has no numbered items")]
    missing = [item[0].split(".")[0] for item in items if not any("expected" in l.lower() for l in item)]
    if missing:
        return [Check("issue list", FAIL, f"no expected result for item(s) {', '.join(missing)}")]
    return [Check("issue list", OK, f"{len(items)} issues, each with an expected result")]


def doc_section(text: str, heading: str) -> str:
    """The section under the first heading line starting with ``heading``,
    up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    for start, line in enumerate(lines):
        if line.startswith(heading):
            break
    else:
        return ""
    out = [lines[start]]
    for line in lines[start + 1:]:
        match = re.match(r"^(#+)\s", line)
        if match and len(match.group(1)) <= level:
            break
        out.append(line)
    return "\n".join(out).strip()


def manual_text(session: str, doc: str) -> str:
    plan = doc_section(doc, f"#### {session}:")
    checklist = doc_section(doc, "### Readiness checklist")
    return "\n\n".join(part for part in (plan, checklist) if part)


# --- Main -----------------------------------------------------------------

def evaluate(session: str, github: GitHub, client: Optional[asc_api.Client], session_day: dt.date,
             issues: Optional[pathlib.Path], email: Optional[str], udid: Optional[str]) -> list:
    needs = SESSIONS[session]
    ci, run = check_ci(github)
    checks = [ci]
    checks += check_artifacts(github, run, needs["artifacts"], session_day)
    checks += check_lane_artifacts(github, needs["lane_artifacts"], session_day, run["headSha"] if run else None)
    checks += check_asc(client, needs["asc"], session_day, email, udid, required=(session == "T"))
    checks += check_issues(issues, needs["issues"])
    return checks


def ready(checks: list) -> bool:
    return all(check.status != FAIL for check in checks)


def main(argv: Optional[list] = None, gh: GhRunner = run_gh, client: Optional[asc_api.Client] = None,
         doc_path: pathlib.Path = IOS_DOC, today: Optional[dt.date] = None) -> int:
    parser = argparse.ArgumentParser(description="Check that a device session is ready (docs/IOS.md).")
    parser.add_argument("session", choices=sorted(SESSIONS))
    parser.add_argument("--date", help="the session's date, YYYY-MM-DD (default today)")
    parser.add_argument("--issues", type=pathlib.Path, help="the session's numbered issue list")
    parser.add_argument("--repo", help="OWNER/REPO (default: gh's repository here)")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--tester-email", default=os.environ.get("CN_TESTER_EMAIL"))
    parser.add_argument("--udid", default=os.environ.get("CN_DEVICE_UDID"))
    parser.add_argument("--no-checklist", action="store_true", help="don't print the manual checklist")
    args = parser.parse_args(argv)

    try:
        session_day = dt.date.fromisoformat(args.date) if args.date else (today or dt.date.today())
    except ValueError:
        parser.error(f"--date {args.date}: use YYYY-MM-DD")
    try:
        repo = args.repo or gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
        if client is None:
            credentials = asc_api.Credentials.from_env()
            client = asc_api.Client.from_credentials(credentials) if credentials else None
        checks = evaluate(args.session, GitHub(gh, repo, args.branch), client, session_day,
                          args.issues, args.tester_email, args.udid)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    title = SESSIONS[args.session]["title"]
    print(f"Session {args.session} ({title}) on {session_day:%Y-%m-%d}\n")
    for check in checks:
        print(f"  [{check.status:>4}] {check.name}: {check.detail}")
    verdict = ready(checks)
    print(f"\n{'READY' if verdict else 'NOT READY'} (automated checks)")
    if not args.no_checklist:
        print("\nBy hand (docs/IOS.md):\n")
        print(manual_text(args.session, doc_path.read_text(encoding="utf-8")))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
