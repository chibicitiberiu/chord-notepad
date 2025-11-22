# Release Process

This document describes how to create releases for Chord Notepad.

## Quick Release Guide

### Creating a New Release

1. **Update code and test locally:**
   ```bash
   make test
   make build
   ```

2. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: Add new feature"
   git push
   ```

3. **Wait for CI tests to pass** (check GitHub Actions tab)

4. **Create a version tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

5. **GitHub Actions will automatically:**
   - Build for Linux, Windows, and macOS
   - Create a GitHub Release
   - Upload binaries

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- `v1.0.0` - Major release (breaking changes)
- `v1.1.0` - Minor release (new features, backwards compatible)
- `v1.0.1` - Patch release (bug fixes)

### Nightly Builds

Nightly builds are created automatically every Monday if there are changes in the last 7 days.

- **Format**: `nightly-YYYYMMDD-<commit>`
- **Purpose**: Testing latest development changes
- **Retention**: Latest 5 nightlies kept, older ones deleted
- **Not for production use**

## Version Information

All builds automatically embed version information:

### In the Application
- View via **Help → About**
- Shows version, build type, commit, and build date

### In Logs
Version information is printed when the application starts:
```
============================================================
Chord Notepad
============================================================
Version:    v1.0.0
Build Type: release
Commit:     abc123def456...
Build Date: 2024-11-21 12:34:56 UTC
============================================================
```

### Build Types

- **development** - Local builds from source
- **nightly** - Automated weekly builds
- **release** - Official tagged releases

## Pre-Release Checklist

Before creating a release tag:

- [ ] All tests pass locally (`make test`)
- [ ] Application runs correctly (`make run`)
- [ ] Local build succeeds (`make build`)
- [ ] CHANGELOG updated (if applicable)
- [ ] Version number follows semantic versioning
- [ ] All changes committed and pushed
- [ ] CI tests pass on GitHub

## Post-Release

After creating a release:

1. **Verify the release** on GitHub:
   - Check all three platform binaries uploaded
   - Verify release notes are correct
   - Test download links

2. **Update documentation** if needed:
   - README.md
   - Installation instructions

3. **Announce the release:**
   - Create release announcement
   - Update project website/documentation

## Troubleshooting

### Tag Already Exists
If you need to re-tag:
```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin :refs/tags/v1.0.0

# Create new tag
git tag v1.0.0
git push origin v1.0.0
```

### Release Failed
1. Check GitHub Actions logs
2. Fix the issue
3. Delete the failed release on GitHub
4. Delete and re-create the tag

### Wrong Version in Build
The version is determined by:
- **Release builds**: Git tag name
- **Nightly builds**: Date + commit hash
- **Local builds**: "dev-local"

Make sure you're pushing the correct tag format: `v*.*.*`

## Manual Release (Not Recommended)

If you need to create a release manually:

```bash
# Build for your platform
make build

# The binary will be in dist/
ls dist/
```

Note: Manual builds won't have proper version information and won't be multi-platform.
