"""ios/tools/mac_bootstrap.sh and prepare_ssd.sh on Linux.

The macOS tools (sw_vers, xcrun, xcodebuild, xip, gh for prepare_ssd) are
stubs on PATH that log their arguments; git, tar, unzip and sha256sum are
the real ones. ios.yml runs mac_bootstrap.sh --verify for real on a macOS
runner (bash 3.2, the BSD tools); this covers the dry run, the refusals and
the idempotent steps.
"""

import hashlib
import os
import shutil
import stat
import subprocess
import zipfile

import pytest

from tests.ios_tools_support import ROOT, TOOLS

BOOTSTRAP = TOOLS / "mac_bootstrap.sh"
PREPARE = TOOLS / "prepare_ssd.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None,
                                reason="needs bash and git")


def stub(bin_dir, name, body):
    path = bin_dir / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def mac(tmp_path):
    """Stub macOS tools, an SSD folder and a work folder."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    stub(bin_dir, "sw_vers", 'echo "${SW_VERS:-26.2}"')
    stub(bin_dir, "uname", 'if [ "$1" = -s ]; then echo "${UNAME_S:-Darwin}"; else echo arm64; fi')
    stub(bin_dir, "df", 'echo "Filesystem 1024-blocks Used Available Capacity Mounted"; '
                        'echo "/dev/disk3s1 500000000 1 ${DF_FREE_KB:-104857600} 50% /"')
    stub(bin_dir, "xcrun", f'''
if [ "$1" = git ]; then shift; exec git "$@"; fi
if [ "$1" = python3 ]; then shift; exec python3 "$@"; fi
echo "xcrun $*" >> {log}
case "$*" in
  "--sdk iphonesimulator --show-sdk-version") echo 26.5 ;;
  "simctl list runtimes") echo "== Runtimes =="; [ -n "$HAVE_RUNTIME" ] && echo "iOS 26.5 (26.5 - 23F77) - com.apple.CoreSimulator.SimRuntime.iOS-26-5" ;;
esac
exit 0''')
    for name in ("xip", "xcodebuild", "sudo", "su"):
        stub(bin_dir, name, f'echo "{name} $*" >> {log}; exit 0')
    ssd = tmp_path / "ssd"
    ssd.mkdir()
    (ssd / "xcode-version").write_text("26.5\n")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path / "home"), "LANG": "C",
           "CN_XCODE_APP": str(tmp_path / "Applications" / "Xcode_26.5.app")}
    (tmp_path / "home").mkdir()
    return {"tmp": tmp_path, "bin": bin_dir, "log": log, "ssd": ssd, "env": env, "work": tmp_path / "work"}


def bootstrap(mac, *args, **env):
    full_env = dict(mac["env"], **env)
    return subprocess.run(["bash", str(BOOTSTRAP), "--ssd", str(mac["ssd"]), "--workdir", str(mac["work"]),
                           "--report-dir", str(mac["tmp"] / "report"), *args],
                          capture_output=True, text=True, env=full_env)


def calls(mac):
    return mac["log"].read_text() if mac["log"].exists() else ""


def test_shellcheck_clean():
    shellcheck = shutil.which("shellcheck")
    if not shellcheck:
        pytest.skip("shellcheck not installed")
    result = subprocess.run([shellcheck, str(BOOTSTRAP), str(PREPARE)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_dry_run_changes_nothing(mac):
    for name in ("Xcode_26.5_Universal.xip", "iOS_26.5_Simulator_Runtime.dmg", "xcodegen.zip", "chord-notepad.bundle",
                 "ios-build-inputs.tar.gz"):
        (mac["ssd"] / name).write_text("x")
    (mac["ssd"] / "chord-notepad.ref").write_text("0" * 40 + "\n")
    result = bootstrap(mac, "--dry-run")
    # The stand-in xcodegen.zip isn't the pinned one: the dry run says so,
    # goes on to show the rest, and exits 1.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "xcodegen.zip's SHA-256 is" in result.stderr
    out = result.stdout
    for expected in ("DRY: (cd", "xip --expand", "DRY (admin): mv", "DRY: xcrun simctl runtime add",
                     "DRY: xcrun git init -q", "DRY: xcrun git -C", "DRY: tar -xzf", "generate --spec",
                     "DRY: xcodebuild build", "DRY: xcrun simctl boot/install/launch"):
        assert expected in out, expected
    assert not mac["work"].exists()
    assert "xip" not in calls(mac) and "sudo" not in calls(mac)
    report = (mac["tmp"] / "report" / "report.txt").read_text()
    assert "macos: 26.2" in report and "free_disk_gb: 100" in report
    assert "no SHA256SUMS" in report


def test_refuses_a_macos_older_than_xcode_needs(mac):
    result = bootstrap(mac, SW_VERS="15.6.1")
    assert result.returncode == 1
    assert "Xcode 26.5 needs macOS 26.2 or later; this Mac has 15.6.1" in result.stderr


def test_refuses_too_little_disk(mac):
    result = bootstrap(mac, DF_FREE_KB=str(40 * 1048576))
    assert result.returncode == 1 and "only 40 GB free, 60 GB needed" in result.stderr


def test_refuses_on_linux_unless_dry(mac):
    result = bootstrap(mac, UNAME_S="Linux")
    assert result.returncode == 1 and "this is Linux, not macOS" in result.stderr


def test_checksums_are_checked(mac):
    (mac["ssd"] / "xcodegen.zip").write_text("x")
    digest = hashlib.sha256(b"y").hexdigest()
    (mac["ssd"] / "SHA256SUMS").write_text(f"{digest}  xcodegen.zip\n")
    result = bootstrap(mac, "--dry-run")
    assert result.returncode == 1 and "don't match SHA256SUMS" in result.stderr


def test_verify_needs_xcode_installed(mac):
    result = bootstrap(mac, "--verify")
    assert result.returncode == 1 and "isn't in" in result.stderr and "run without --verify first" in result.stderr


def make_source_repo(tmp_path, xcodegen_sha):
    """A small repo with what the steps read: the pins, the version, the project spec."""
    repo = tmp_path / "source"
    (repo / ".github/actions/ios-app-setup").mkdir(parents=True)
    (repo / ".github/actions/ios-app-setup/action.yml").write_text(
        "runs:\n  steps:\n    - env:\n        XCODEGEN_VERSION: '2.46.0'\n"
        f"        XCODEGEN_SHA256: {xcodegen_sha}\n")
    (repo / "ios").mkdir()
    (repo / "ios/.xcode-version").write_text("26.5\n")
    (repo / "ios/project.yml").write_text("name: ChordNotepad\n")
    (repo / "VERSION").write_text("0.6.2\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    return repo, head


def make_xcodegen_zip(path):
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("xcodegen/bin/xcodegen")
        info.external_attr = 0o755 << 16
        archive.writestr(info, "#!/bin/sh\necho \"Version: 2.46.0\"\necho \"xcodegen $*\" >> \"$XG_LOG\"\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.skipif(shutil.which("unzip") is None or shutil.which("tar") is None, reason="needs unzip and tar")
def test_repo_xcodegen_inputs_project_are_idempotent(mac):
    ssd, tmp = mac["ssd"], mac["tmp"]
    sha = make_xcodegen_zip(ssd / "xcodegen.zip")
    repo, head = make_source_repo(tmp, sha)
    subprocess.run(["git", "-C", str(repo), "bundle", "create", str(ssd / "chord-notepad.bundle"), "main"],
                   check=True, capture_output=True)
    (ssd / "chord-notepad.ref").write_text(head + "\n")
    inputs = tmp / "inputs"
    (inputs / "Frameworks/Python.xcframework").mkdir(parents=True)
    (inputs / "python-bundle/app").mkdir(parents=True)
    (inputs / "help").mkdir()
    (inputs / "INPUTS_COMMIT").write_text(head + "\n")
    subprocess.run(["tar", "-czf", str(ssd / "ios-build-inputs.tar.gz"), "-C", str(inputs),
                    "Frameworks", "python-bundle", "help", "INPUTS_COMMIT"], check=True)
    steps = "repo xcodegen inputs project"
    env = {"XG_LOG": str(tmp / "xcodegen.log")}

    first = bootstrap(mac, "--only", steps, **env)
    assert first.returncode == 0, first.stdout + first.stderr
    clone = mac["work"] / "chord-notepad"
    assert (clone / "ios/build/Frameworks/Python.xcframework").is_dir()
    assert subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip() == head
    report = (tmp / "report/report.txt").read_text()
    assert "xcodegen: 2.46.0" in report and f"inputs_commit: {head}" in report and "warning" not in report

    (clone / "my-work.txt").write_text("kept")
    second = bootstrap(mac, "--only", steps, **env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "exists; left as it is" in second.stdout
    assert "XcodeGen 2.46.0 is in" in second.stdout
    assert "The build inputs are unpacked" in second.stdout
    assert (clone / "my-work.txt").read_text() == "kept"
    assert (tmp / "xcodegen.log").read_text().count("generate --spec") == 2


def test_xcodegen_zip_with_the_wrong_hash_is_refused(mac):
    ssd, tmp = mac["ssd"], mac["tmp"]
    make_xcodegen_zip(ssd / "xcodegen.zip")
    repo, head = make_source_repo(tmp, "0" * 64)
    subprocess.run(["git", "-C", str(repo), "bundle", "create", str(ssd / "chord-notepad.bundle"), "main"],
                   check=True, capture_output=True)
    (ssd / "chord-notepad.ref").write_text(head)
    result = bootstrap(mac, "--only", "repo xcodegen")
    assert result.returncode == 1 and "ios.yml pins 0000" in result.stderr


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="needs sha256sum")
def test_prepare_ssd_fills_the_ssd(mac):
    tmp = mac["tmp"]
    bin_dir = mac["bin"]
    zip_source = tmp / "xcodegen-src.zip"
    sha = make_xcodegen_zip(zip_source)
    repo, head = make_source_repo(tmp, sha)
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", head], check=True)
    inputs = tmp / "artifact"
    inputs.mkdir()
    (inputs / "ios-build-inputs.tar.gz").write_bytes(b"tarball")
    stub(bin_dir, "gh", f'''
case "$1 $2" in
  "run list") echo 111; echo 222 ;;
  "api repos/{{owner}}/{{repo}}/actions/runs/111/artifacts") ;;
  "api repos/{{owner}}/{{repo}}/actions/runs/222/artifacts") echo ios-build-inputs ;;
  "run view") echo {head} ;;
  "run download") mkdir -p "$7"; cp {inputs}/ios-build-inputs.tar.gz "$7/" ;;
  *) echo "unexpected gh $*" >&2; exit 1 ;;
esac''')
    stub(bin_dir, "curl", f'while [ $# -gt 0 ]; do if [ "$1" = -o ]; then cp {zip_source} "$2"; fi; shift; done')
    ssd = mac["ssd"]
    (ssd / "Xcode_26.5.xip").write_text("x")
    result = subprocess.run(["bash", str(PREPARE), str(ssd), "--repo", str(repo)], capture_output=True, text=True,
                            env=mac["env"])
    assert "Inputs from run 222" in result.stdout, result.stdout + result.stderr
    assert result.returncode == 1  # the runtime .dmg is missing
    assert "MISSING: *[Ss]imulator*[Rr]untime*.dmg" in result.stdout
    assert (ssd / "chord-notepad.ref").read_text().strip() == head
    assert (ssd / "ios-build-inputs.tar.gz").read_bytes() == b"tarball"
    assert (ssd / "xcode-version").read_text().strip() == "26.5"
    assert os.access(ssd / "mac_bootstrap.sh", os.X_OK)
    sums = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=ssd, capture_output=True, text=True)
    assert sums.returncode == 0, sums.stdout
    clone = tmp / "clone"  # as mac_bootstrap.sh's repo step takes it
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "fetch", "-q", str(ssd / "chord-notepad.bundle"),
                    "+refs/*:refs/remotes/ssd/*"], check=True)
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "-B", "main", head], check=True)
    assert (clone / "VERSION").read_text() == "0.6.2\n"

    (ssd / "iOS_26.5_Simulator_Runtime.dmg").write_text("x")
    again = subprocess.run(["bash", str(PREPARE), str(ssd), "--repo", str(repo)], capture_output=True, text=True,
                           env=mac["env"])
    assert again.returncode == 0, again.stdout + again.stderr
    assert "xcodegen.zip 2.46.0 is already there" in again.stdout


def test_the_real_pins_parse():
    """mac_bootstrap.sh and prepare_ssd.sh read XcodeGen's pin from the action with sed."""
    action = (ROOT / ".github/actions/ios-app-setup/action.yml").read_text()
    assert "XCODEGEN_VERSION: '2.46.0'" in action or "XCODEGEN_VERSION: '" in action
    result = subprocess.run(["sed", "-n", r"s/^ *XCODEGEN_SHA256: '\{0,1\}\([0-9A-Za-z.]*\)'\{0,1\}$/\1/p",
                             str(ROOT / ".github/actions/ios-app-setup/action.yml")], capture_output=True, text=True)
    assert len(result.stdout.strip()) == 64


def test_verify_sees_an_installed_xcode(mac):
    """Xcode's version is read whole: a pipe into head made xcodebuild abort on CI."""
    developer = mac["tmp"] / "Applications/Xcode_26.5.app/Contents/Developer/usr/bin"
    developer.mkdir(parents=True)
    stub(developer, "xcodebuild", 'echo "Xcode 26.5"; echo "Build version 17F42"')
    result = bootstrap(mac, "--verify", "--only", "preflight", HAVE_RUNTIME="1")
    assert result.returncode == 0, result.stdout + result.stderr
    report = (mac["tmp"] / "report/report.txt").read_text()
    assert "error" not in report


def test_a_bundle_without_a_ref_is_refused(mac):
    ssd, tmp = mac["ssd"], mac["tmp"]
    repo, head = make_source_repo(tmp, "0" * 64)
    subprocess.run(["git", "-C", str(repo), "bundle", "create", str(ssd / "chord-notepad.bundle"), "HEAD"],
                   check=True, capture_output=True)
    (ssd / "chord-notepad.ref").write_text(head)
    result = bootstrap(mac, "--only", "repo")
    assert result.returncode == 1 and "has no branch holding" in result.stderr
    assert not (mac["work"] / "chord-notepad").exists()  # the next run starts clean
