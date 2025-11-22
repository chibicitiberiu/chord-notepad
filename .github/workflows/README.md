# GitHub Actions Workflows

This directory contains automated build and release workflows for Chord Notepad.

## Workflow Overview

The `build.yml` workflow handles three scenarios:

### 1. Continuous Testing (On Push/PR)
- **Trigger**: Every push to `master`/`main` or pull request
- **Action**: Runs test suite only
- **Purpose**: Ensure code quality

### 2. Nightly Builds (Weekly)
- **Trigger**: Every Monday at 00:00 UTC (cron schedule)
- **Condition**: Only runs if there were commits in the last 7 days
- **Action**:
  - Runs tests
  - Builds executables for Linux, Windows, macOS
  - Creates pre-release with tag `nightly-YYYYMMDD`
  - Version format: `nightly-YYYYMMDD-<short-commit-hash>`
- **Retention**: Keeps latest 5 nightly releases, deletes older ones

### 3. Release Builds (On Tag Push)
- **Trigger**: Pushing a version tag (e.g., `v1.0.0`, `v2.1.3`)
- **Action**:
  - Runs tests
  - Builds executables for Linux, Windows, macOS
  - Creates official release with the tag name
  - Version format: Uses the tag name (e.g., `v1.0.0`)

## Version Information

Version information is automatically embedded in the built executables:

### Development Builds (local)
```python
VERSION = "dev-local"
BUILD_TYPE = "development"
```

### Nightly Builds
```python
VERSION = "nightly-20241121-a1b2c3d"
BUILD_TYPE = "nightly"
COMMIT_HASH = "full-commit-hash"
BUILD_DATE = "2024-11-21 00:00:00 UTC"
```

### Release Builds
```python
VERSION = "v1.0.0"
BUILD_TYPE = "release"
COMMIT_HASH = "full-commit-hash"
BUILD_DATE = "2024-11-21 12:34:56 UTC"
```

This information is:
- Written to `src/build_info.py` during CI build
- Displayed in Help > About dialog
- Logged to console at application startup

## Creating a Release

### Automatic Release (Recommended)

1. Commit and push your changes:
   ```bash
   git add .
   git commit -m "Prepare release v1.0.0"
   git push
   ```

2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. GitHub Actions will automatically:
   - Run tests
   - Build binaries for all platforms
   - Create a GitHub release
   - Upload binaries as release assets

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
- `ChordNotepad-macos-x64` - macOS executable

### Platform-Specific Notes

**Linux:**
- Requires `libfluidsynth3` at runtime
- Built on Ubuntu latest (glibc 2.35+)

**Windows:**
- No external dependencies needed
- Statically links FluidSynth

**macOS:**
- Requires FluidSynth from Homebrew at runtime
- Built for x64 (Intel) architecture

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

For local development, `src/build_info.py` contains default values:
```python
VERSION = "dev-local"
BUILD_TYPE = "development"
```

This file is checked into git and won't interfere with CI builds, as the workflow overwrites it during the build process.
