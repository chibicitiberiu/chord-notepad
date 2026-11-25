"""Which ios.yml jobs run for which event, read from the workflow itself.

The release lanes must never run on a push, a plain dispatch must run the
same four jobs as before, and the monthly schedule only the gate and the
TestFlight lane. This evaluates each job's ``if:`` the way Actions does for
these expressions (``==``, ``!=``, ``&&``, ``||``, ``!``, ``always()``, and a
job whose needs didn't all succeed is skipped unless its condition calls
always()), with every job that runs assumed to succeed. No dispatch needed.
"""

import re

import pytest
import yaml

from tests.ios_tools_support import ROOT

WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ios.yml").read_text())
JOBS = WORKFLOW["jobs"]
TESTS = {"kit", "simulator", "device", "merge"}
TOKEN = re.compile(r"\s*(?:(\|\||&&|==|!=|!|\(|\))|'([^']*)'|(always\(\))|([A-Za-z_][A-Za-z0-9_.-]*))")


def evaluate(expression, context):
    """A GitHub expression (the subset ios.yml uses) as a Python value."""
    expression = expression.strip()
    if expression.startswith("${{"):
        expression = expression[3:-2]
    out, pos = [], 0
    while pos < len(expression.rstrip()):
        match = TOKEN.match(expression, pos)
        assert match, f"can't read {expression[pos:]!r}"
        op, string, always, name = match.groups()
        if op:
            out.append({"||": " or ", "&&": " and ", "!": " not ", "==": " == ", "!=": " != "}.get(op, op))
        elif string is not None:
            out.append(repr(string))
        elif always:
            out.append("True")
        else:
            out.append(repr(context(name)))
        pos = match.end()
    return eval("".join(out))  # noqa: S307 - our own workflow's expressions, tokenized above


def run_jobs(event, inputs=None, gate_outputs=None, ref="refs/heads/main"):
    """{job: "success" | "skipped"} for an event, every running job succeeding."""
    inputs = inputs or {}
    gate_outputs = gate_outputs or {}
    results = {}

    def context(name):
        if name == "github.event_name":
            return event
        if name == "github.ref":
            return ref
        if name.startswith("inputs."):
            return inputs.get(name.split(".", 1)[1], False) if event == "workflow_dispatch" else ""
        if name.startswith("needs."):
            _, job, field, *rest = name.split(".")
            if field == "result":
                return results[job]
            if results[job] != "success":
                return ""
            return gate_outputs.get(rest[0], "") if job == "release-gate" else ""
        raise AssertionError(f"unknown context {name}")

    pending = dict(JOBS)
    while pending:
        for name, job in list(pending.items()):
            needs = job.get("needs", [])
            needs = [needs] if isinstance(needs, str) else needs
            if any(n not in results for n in needs):
                continue
            condition = str(job.get("if", ""))
            if not condition or "always()" not in condition:
                if any(results[n] != "success" for n in needs):
                    results[name] = "skipped"
                    del pending[name]
                    continue
            results[name] = "success" if not condition or evaluate(condition, context) else "skipped"
            del pending[name]
    return results


def running(results):
    return {name for name, result in results.items() if result == "success"}


def test_a_push_runs_exactly_the_tests():
    assert running(run_jobs("push")) == TESTS


def test_a_plain_dispatch_runs_exactly_the_tests():
    assert running(run_jobs("workflow_dispatch")) == TESTS


def test_the_schedule_without_secrets_runs_only_the_gate():
    results = run_jobs("schedule", gate_outputs={"testflight": "false", "development": "false"})
    assert running(results) == {"release-gate"}


def test_the_schedule_with_secrets_uploads_to_testflight_only():
    results = run_jobs("schedule", gate_outputs={"testflight": "true", "development": "false"})
    assert running(results) == {"release-gate", "testflight"}


@pytest.mark.parametrize("inputs, outputs, lanes", [
    ({"testflight": True}, {"testflight": "false", "development": "false"}, set()),
    ({"testflight": True}, {"testflight": "true", "development": "false"}, {"testflight"}),
    ({"development_ipa": True}, {"testflight": "false", "development": "true"}, {"development"}),
    ({"unsigned_archive": True}, {}, {"archive-check"}),
])
def test_dispatch_lanes(inputs, outputs, lanes):
    results = run_jobs("workflow_dispatch", inputs, outputs)
    gate = {"release-gate"} if inputs.get("testflight") or inputs.get("development_ipa") else set()
    assert running(results) == TESTS | gate | lanes


def test_lanes_need_green_tests_on_a_dispatch():
    """A dispatch whose tests fail uploads nothing (the schedule's commit was tested by its own run)."""
    condition = str(JOBS["testflight"]["if"])
    assert "needs.kit.result == 'success'" in condition and "needs.simulator.result == 'success'" in condition
    assert "needs.device.result == 'success'" in str(JOBS["development"]["if"])


def test_lanes_only_from_main():
    results = run_jobs("workflow_dispatch", {"testflight": True}, {"testflight": "true"}, ref="refs/heads/other")
    assert "testflight" not in running(results) and "release-gate" not in running(results)


def test_secrets_stay_in_the_ios_release_environment():
    for name, job in JOBS.items():
        uses_secrets = "secrets." in yaml.safe_dump(job)
        assert uses_secrets == (job.get("environment") == "ios-release"), name
