"""ios/tools/readiness.py, offline: gh and App Store Connect from fixtures."""

import copy
import datetime as dt
import json

import pytest

from tests.ios_tools_support import ROOT, FakeTransport, fixture, load_tool

readiness = load_tool("readiness")
asc_api = load_tool("asc_api")

DATA = fixture("readiness.json")
EMAIL = "tester@example.invalid"
UDID = "00008110-0000000000000000"
DAY = dt.date(2026, 12, 5)


def fake_gh(data):
    def gh(args):
        if args[:2] == ["run", "list"]:
            return json.dumps(data["runs"])
        if args[0] == "api":
            run_id = args[1].split("/runs/")[1].split("/")[0]
            return json.dumps({"artifacts": data["artifacts"].get(run_id, [])})
        if args[:2] == ["repo", "view"]:
            return "owner/repo\n"
        raise AssertionError(f"unexpected gh call {args}")
    return gh


def github(data=DATA):
    return readiness.GitHub(fake_gh(data), "owner/repo")


def client(asc=None):
    return asc_api.Client(lambda: "TOKEN", FakeTransport(asc if asc is not None else DATA["asc"]))


def by_name(checks):
    return {check.name: check for check in checks}


def issues_file(tmp_path, text="1. The chord sheet is cut off\n   Expected: it fits the width\n"):
    path = tmp_path / "issues.md"
    path.write_text(text)
    return path


def test_ci_takes_the_newest_finished_test_run():
    check, run = readiness.check_ci(github())
    assert check.status == readiness.OK
    assert run["databaseId"] == 45509459724
    assert "1 newer run(s) still going" in check.detail


def test_ci_red_when_the_latest_finished_run_failed():
    data = copy.deepcopy(DATA)
    data["runs"] = [r for r in data["runs"] if r["databaseId"] not in (45509459724, 45507000001)]
    check, _ = readiness.check_ci(github(data))
    assert check.status == readiness.FAIL and "failure" in check.detail


def test_schedule_runs_dont_count_as_tested():
    data = copy.deepcopy(DATA)
    data["runs"] = [r for r in data["runs"] if r["event"] == "schedule"]
    check, run = readiness.check_ci(github(data))
    assert run is None and check.status == readiness.FAIL


def test_s0_ready_before_enrollment():
    checks = readiness.evaluate("S0", github(), None, DAY, None, None, None)
    assert readiness.ready(checks)
    names = by_name(checks)
    assert names["artifact ios-build-inputs"].status == readiness.OK
    assert "until 2026-12-24" in names["artifact ios-build-inputs"].detail


def test_artifact_expiring_before_the_session_fails():
    checks = readiness.evaluate("S0", github(), None, dt.date(2026, 12, 28), None, None, None)
    check = by_name(checks)["artifact ios-build-inputs"]
    assert check.status == readiness.FAIL and "before the session" in check.detail


def test_s1_needs_the_issue_list(tmp_path):
    checks = readiness.evaluate("S1", github(), None, DAY, None, None, None)
    assert not readiness.ready(checks)
    assert by_name(checks)["issue list"].status == readiness.FAIL
    checks = readiness.evaluate("S1", github(), None, DAY, issues_file(tmp_path), None, None)
    assert readiness.ready(checks), [c for c in checks if c.status == readiness.FAIL]


def test_issue_list_needs_expected_results(tmp_path):
    path = issues_file(tmp_path, "1. Cut off\n   Expected: fits\n2. Title truncates\n3. Rotation\n   expected: keeps\n")
    [check] = readiness.check_issues(path, True)
    assert check.status == readiness.FAIL and "2" in check.detail and "3" not in check.detail
    [check] = readiness.check_issues(issues_file(tmp_path, "notes only\n"), True)
    assert check.status == readiness.FAIL


def test_t_without_credentials_is_not_ready(tmp_path):
    checks = readiness.evaluate("T", github(), None, DAY, issues_file(tmp_path), EMAIL, None)
    assert not readiness.ready(checks)
    assert by_name(checks)["App Store Connect: build"].status == readiness.FAIL


def test_t_ready_with_a_processed_build_and_an_accepted_tester(tmp_path):
    checks = readiness.evaluate("T", github(), client(), DAY, issues_file(tmp_path), EMAIL, None)
    assert readiness.ready(checks), [c for c in checks if c.status == readiness.FAIL]
    names = by_name(checks)
    assert "IN_BETA_TESTING" in names["TestFlight build"].detail
    assert names["tester"].detail == "t…@example.invalid: ACCEPTED"
    # The lane's dSYMs come from the newest successful dispatch, not the expired schedule run.
    assert "45507000001" in names["artifact ios-testflight-dsyms"].detail
    assert "not the latest tested 1ddcdfb" in names["artifact ios-testflight-dsyms"].detail


def test_t_build_too_close_to_expiry(tmp_path):
    late = dt.date(2027, 2, 1)  # 21 days before the build expires
    checks = readiness.evaluate("T", github(), client(), late, issues_file(tmp_path), EMAIL, None)
    check = by_name(checks)["TestFlight build"]
    assert check.status == readiness.FAIL and "less than 30 days" in check.detail


@pytest.mark.parametrize("change, expected", [
    ({"processingState": "PROCESSING"}, "PROCESSING"),
    ({"expired": True}, "VALID"),
])
def test_t_build_not_usable(tmp_path, change, expected):
    asc = copy.deepcopy(DATA["asc"])
    asc["responses"][1]["body"]["data"][0]["attributes"].update(change)
    checks = readiness.evaluate("T", github(), client(asc), DAY, issues_file(tmp_path), EMAIL, None)
    check = by_name(checks)["TestFlight build"]
    assert check.status == readiness.FAIL and expected in check.detail


def test_t_tester_only_invited(tmp_path):
    asc = copy.deepcopy(DATA["asc"])
    asc["responses"][2]["body"]["data"][0]["attributes"]["state"] = "INVITED"
    checks = readiness.evaluate("T", github(), client(asc), DAY, issues_file(tmp_path), EMAIL, None)
    assert by_name(checks)["tester"].status == readiness.FAIL


def test_s2_needs_the_development_ipa_and_the_registered_device(tmp_path):
    checks = readiness.evaluate("S2", github(), client(), DAY, issues_file(tmp_path), None, UDID)
    assert readiness.ready(checks), [c for c in checks if c.status == readiness.FAIL]
    assert by_name(checks)["device"].detail.startswith("iPhone 15: ENABLED")

    data = copy.deepcopy(DATA)
    data["artifacts"]["45507000001"] = []
    checks = readiness.evaluate("S2", github(data), client(), DAY, issues_file(tmp_path), None, UDID)
    assert by_name(checks)["artifact ios-development"].status == readiness.FAIL

    checks = readiness.evaluate("S2", github(), client(), DAY, issues_file(tmp_path), None, "00008110-FFFF")
    assert by_name(checks)["device"].status == readiness.FAIL


def test_s2_before_enrollment_skips_the_device_check(tmp_path):
    checks = readiness.evaluate("S2", github(), None, DAY, issues_file(tmp_path), None, UDID)
    assert by_name(checks)["App Store Connect: device"].status == readiness.SKIP


def test_doc_section_stops_at_the_next_heading():
    doc = "# A\n## Device sessions\n#### S0: boot\nplan 0\n#### T: smoke\nplan T\n### Readiness checklist (x)\n- [ ] a\n## CI\nno\n"
    assert readiness.doc_section(doc, "#### S0:") == "#### S0: boot\nplan 0"
    text = readiness.manual_text("T", doc)
    assert "plan T" in text and "- [ ] a" in text and "no" not in text.split("- [ ] a")[1]


def test_main_prints_and_exits(capsys, tmp_path):
    doc = tmp_path / "IOS.md"
    doc.write_text("#### S0: boot\nbring the SSD\n### Readiness checklist\n- [ ] consent\n")
    code = readiness.main(["S0", "--date", "2026-12-05"], gh=fake_gh(DATA), doc_path=doc)
    out = capsys.readouterr().out
    assert code == 0
    assert "READY" in out and "bring the SSD" in out and "- [ ] consent" in out
    code = readiness.main(["S0", "--date", "2026-12-30", "--no-checklist"], gh=fake_gh(DATA), doc_path=doc)
    assert code == 1 and "NOT READY" in capsys.readouterr().out


@pytest.mark.parametrize("session", sorted(readiness.SESSIONS))
def test_docs_have_each_sessions_plan_and_the_checklist(session):
    """readiness.py prints docs/IOS.md's "#### <session>:" plan and the readiness checklist."""
    text = readiness.manual_text(session, (ROOT / "docs/IOS.md").read_text(encoding="utf-8"))
    assert text.startswith(f"#### {session}:")
    assert "### Readiness checklist" in text and "- [ ] her consent" in text
    assert (ROOT / "ios/tools/session_logs" / f"{session}.md").is_file()
