# GitHub Actions Workflows

This directory contains automated build and release workflows for Chord Notepad.

## Workflow Overview

The `build.yml` workflow handles four scenarios:

### 1. Continuous Testing (On Push/PR)
- **Trigger**: Every push to `master`/`main` or pull request
- **Action**: Runs test suite only
- **Purpose**: Ensure code quality

### 2. Nightly Builds (Weekly)
- **Trigger**: Every Monday at 00:00 UTC (cron schedule), or manual workflow_dispatch with `build_type: nightly`
- **Condition**: Scheduled run only proceeds if there were commits in the last 7 days
- **Action**:
  - Runs tests
  - Builds executables for Linux, Windows, macOS
  - Creates pre-release with tag `nightly-YYYYMMDD`
  - Version format: `v<BASE_VERSION> nightly <YYYYMMDD> (<short-commit>)`
- **Retention**: Keeps latest 5 nightly releases, deletes older ones

### 3. Full Releases (Manual Dispatch)
- **Trigger**: Run workflow manually with `build_type: release` in the Actions tab
- **Action**:
  - Reads base version from the `VERSION` file at the repo root
  - Runs tests
  - Builds executables for Linux, Windows, macOS plus the PDF user guide
  - Creates a (non-prerelease) GitHub release with tag `v<BASE_VERSION>-build<run_number>`
  - Version format: `v<BASE_VERSION> build <run_number> (<short-commit>)`
- **Notes**: The tag is created automatically by the release action. Bump `VERSION` to publish a new version (e.g. change `0.1` → `0.2` and dispatch).

### 4. Legacy Tag-Push Releases
- **Trigger**: Pushing a version tag (e.g., `v1.0.0`, `v2.1.3`)
- **Action**: Same as full releases, but the tag name itself is used as the version.

## Version Source

The base version lives in the **`VERSION` file at the repo root** (one line, e.g. `0.1`).
Both `src/build_info.py` (for local dev) and the CI workflow read from it, so there is one source of truth.

To publish a new release:
1. Edit `VERSION` (e.g. `0.1` → `0.2`), commit, push.
2. Run the **Build and Release** workflow manually with `build_type: release`.

The build number comes from `${{ github.run_number }}`, which is monotonic across the repo.

## Version Information

Version information is automatically embedded in the built executables:

### Development Builds (local)
```python
BASE_VERSION = "0.1"   # read from VERSION file
BUILD_NUMBER = "0"
VERSION = "v0.1 (dev-local)"
BUILD_TYPE = "development"
```

### Nightly Builds
```python
BASE_VERSION = "0.1"
BUILD_NUMBER = "47"
VERSION = "v0.1 nightly 20260530 (a1b2c3d)"
BUILD_TYPE = "nightly"
COMMIT_HASH = "full-commit-hash"
BUILD_DATE = "2026-05-30 00:00:00 UTC"
```

### Full Releases
```python
BASE_VERSION = "0.1"
BUILD_NUMBER = "47"
VERSION = "v0.1 build 47 (a1b2c3d)"
BUILD_TYPE = "release"
COMMIT_HASH = "full-commit-hash"
BUILD_DATE = "2026-05-30 12:34:56 UTC"
```

This information is:
- Written to `src/build_info.py` during CI build
- Embedded in the Windows exe via `version_info.txt` (visible in Explorer Properties → Details)
- Displayed in Help > About dialog
- Logged to console at application startup

## Creating a Release

### Full Release (Recommended)

1. As you work, write release notes into `CHANGELOG.md` at the repo root.
2. Bump `VERSION` (e.g. `0.1` → `0.2`), commit, push.
3. Open **Actions → Build and Release → Run workflow**.
4. Select `build_type: release` and click **Run**.

The workflow then:
- Runs tests
- Builds binaries + PDF docs
- Creates tag `v0.2-build<run_number>` and publishes a GitHub release whose description is built from `CHANGELOG.md`
- Runs the `rotate-changelog` job, which prepends `CHANGELOG.md`'s notes to `CHANGELOG_HISTORY.md` under a `## v0.2-build<N> — YYYY-MM-DD` header, resets `CHANGELOG.md` to the empty template, and pushes a commit (`[skip ci]`) back to `main`.

### Changelog Conventions

- **`CHANGELOG.md`** — staging area for the *next* release. Edit freely. Everything except the `# Changelog` header and HTML comments ends up in the release description.
- **`CHANGELOG_HISTORY.md`** — append-only log of past releases, written by CI. Don't edit by hand unless you're fixing a mistake.

If `CHANGELOG.md` is empty when you dispatch a release, the release notes show `_No release notes provided._` and the same placeholder is recorded in history.

### Legacy: Tag-Push Release

For ad-hoc releases at an arbitrary commit you can still push a `v*.*.*` tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```
The workflow detects the tag and produces a release named after it. **Note:** tag-push releases do *not* trigger the changelog rotation — `main` may have moved past the tagged commit, and we don't want to clobber that work. Manage the changelog manually in this flow.

### Manual Testing Before Release

To test the build process without creating a release:

1. Push changes to a branch
2. Check the Actions tab on GitHub
3. Tests will run automatically
4. Once tests pass, create the tag for release

## Build Artifacts

Each build produces three artifacts:

- `ChordNotepad-linux-x64` - Linux executable
- `ChordNotepad-windows-x64.exe` - Windows executable
- `ChordNotepad-macos-arm64` - macOS executable (Apple Silicon)

### Platform-Specific Notes

**Linux:**
- Requires `libfluidsynth3` at runtime
- Built on Ubuntu latest (glibc 2.35+)

**Windows:**
- No external dependencies needed
- Statically links FluidSynth

**macOS:**
- Requires FluidSynth from Homebrew at runtime
- Built for arm64 (Apple Silicon). Intel Macs are not supported by the current pipeline.

## Troubleshooting

### Tests Failing
- Workflow won't proceed to build stage if tests fail
- Check the Actions logs for test output
- Fix issues and push again

### Build Failing on Specific Platform
- Check Actions logs for that platform's runner
- Common issues:
  - Missing system dependencies
  - Python package conflicts
  - PyInstaller spec file issues

### Nightly Not Creating
- Check if there were commits in the last 7 days
- Verify the cron schedule is correct
- Check Actions logs for the `check-changes` job

### Release Not Uploading Artifacts
- Ensure you have `GITHUB_TOKEN` permissions (automatic in GitHub Actions)
- Check the `create-release` job logs
- Verify artifacts were created in previous jobs

## Maintenance

### Updating Python Version
Edit `.github/workflows/build.yml`:
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.12'  # Change this
```

### Changing Nightly Schedule
Edit the cron expression:
```yaml
schedule:
  - cron: '0 0 * * 1'  # Monday at 00:00 UTC
```

Cron format: `minute hour day-of-month month day-of-week`

### Adjusting Nightly Retention
Change how many nightly builds to keep:
```yaml
- name: Delete old nightly releases
  uses: dev-drprasad/delete-older-releases@v0.3.2
  with:
    keep_latest: 5  # Change this number
```

## Local Development

For local development, `src/build_info.py` reads the base version from `VERSION` at import time and tags the build as `(dev-local)`:
```python
BASE_VERSION = "0.1"   # from VERSION file
VERSION = "v0.1 (dev-local)"
BUILD_TYPE = "development"
```

The file is checked into git but is rewritten by CI before PyInstaller runs, so it never conflicts with release builds.
