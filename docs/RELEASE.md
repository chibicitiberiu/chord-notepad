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

## Microsoft Store (Supporter Edition)

The Store listing is a paid "supporter edition" of the **same app** as the free
GitHub download. There is no feature difference and no build flag; people pay
for the Store install/auto-update convenience and to support the project.

It ships as an MSIX built from a *onedir* PyInstaller build
(`CHORD_NOTEPAD_ONEDIR=1`), because a onefile exe inside a package would unpack
itself to `%TEMP%` on every launch. MSIX is used rather than submitting the
`.exe` because paid pricing for EXE/MSI Store submissions has been unreliable.

The package is **unsigned**: the Store re-signs it with Microsoft's
certificate, so Trusted Signing is not involved and SmartScreen does not apply.

### One-time setup

1. Register a developer account at <https://storedeveloper.microsoft.com>.
2. In Partner Center, create a new **MSIX or PWA app** and reserve its name.
3. Open **Product management → Product identity** and copy the three values
   into GitHub **repo Variables** (Settings → Secrets and variables → Actions →
   Variables):

   | Variable | Partner Center field |
   |---|---|
   | `STORE_IDENTITY_NAME` | `Package/Identity/Name` |
   | `STORE_PUBLISHER` | `Package/Identity/Publisher` (`CN=...`) |
   | `STORE_PUBLISHER_DISPLAY_NAME` | `Package/Properties/PublisherDisplayName` |
   | `STORE_DISPLAY_NAME` | Only if the reserved name is not `Chord Notepad` |

4. Fill in the submission: price, category (Music), age rating questionnaire,
   Store listing (description, at least one screenshot), and a privacy policy
   URL if asked (the app collects nothing, so a short page saying that works).
5. Under **Submission options → Restricted capabilities**, justify
   `runFullTrust`: "Desktop (Win32) application packaged with MSIX; needs full
   trust to run its Python runtime and FluidSynth audio engine."

### Each Store release

1. Bump `VERSION`. The package version is `MAJOR.MINOR.PATCH.0` (the Store
   reserves the 4th field) and every submission must be higher than the last
   published one, so a rebuild of an already-published `VERSION` is rejected.
2. Release as usual (tag push or *release* dispatch). Tag pushes and every
   manual dispatch also build the MSIX; scheduled nightlies don't.
3. Download the `ChordNotepad-store-msix` artifact from the workflow run. It is
   never attached to the GitHub release.
4. In Partner Center, start a new submission, upload the `.msix` under
   **Packages**, and submit for certification (usually 1-3 days).

After building, CI runs `packaging/msix/smoke_test.ps1`: it signs a throwaway
copy with a self-signed cert, installs it on the runner, launches the app
through its package identity, and fails the job if no startup log appears in
the package's private AppData or the process dies. The full app log is printed
in the step output. Runners have no audio device, so a missing soundfont load
is only a warning there.

Without the `STORE_*` variables CI still builds an MSIX with a placeholder
identity (`CN=ChordNotepadUnreserved`) and prints a warning. That package is
fine for local testing but Partner Center will reject it.

### Building and testing locally (Windows)

Needs the Windows SDK (`makeappx.exe`, `makepri.exe`) and ImageMagick.

```powershell
$env:CHORD_NOTEPAD_ONEDIR = '1'
pipenv run pyinstaller --clean --noconfirm --distpath dist-store --workpath build-store chord-notepad.spec
./packaging/msix/build_msix.ps1 -AppDir dist-store/ChordNotepad -OutFile dist-store/ChordNotepad.msix `
    -Version (Get-Content VERSION) -IdentityName ChordNotepad.Unreserved `
    -Publisher 'CN=ChordNotepadUnreserved' -PublisherDisplayName 'Chord Notepad Contributors'
```

The package is unsigned, so double-clicking it fails ("publisher certificate
could not be verified"). There are two ways to install it.

**Quick: Developer Mode, no signing.** Turn on *Settings → System → For
developers → Developer Mode*, then register the unpacked package. Works with
the `.msix` straight from the CI artifact, no Windows SDK needed:

```powershell
$dir = "$env:USERPROFILE\ChordNotepadTest"
Copy-Item ChordNotepad-0.4.0-x64.msix ChordNotepad.zip   # Expand-Archive wants .zip
Expand-Archive ChordNotepad.zip -DestinationPath $dir
# MSIX stores names percent-encoded; a plain unzip leaves libstdc%2B%2B-6.dll,
# and FluidSynth then fails to load ("or one of its dependencies").
Get-ChildItem $dir -Recurse -File | Where-Object Name -like '*%*' |
    Rename-Item -NewName { [uri]::UnescapeDataString($_.Name) }
Add-AppxPackage -Register "$dir\AppxManifest.xml"
# Remove: Get-AppxPackage ChordNotepad.Unreserved | Remove-AppxPackage
```

Launch it from the Start menu. Running `ChordNotepad.exe` from the folder
starts it *without* package identity, so AppData isn't redirected. The app
runs from that folder (not the read-only `WindowsApps`), so keep it in place
while testing. Everything else (Start tile, icons, AppData redirection)
behaves like a Store install.

**Exact: signed install.** Sign it with a self-signed certificate whose
subject equals `-Publisher`, trust that certificate, then add the package
(needs `signtool` from the Windows SDK). CI does this on every run in
`smoke_test.ps1`:

```powershell
$cert = New-SelfSignedCertificate -Type Custom -Subject 'CN=ChordNotepadUnreserved' `
    -KeyUsage DigitalSignature -CertStoreLocation Cert:\CurrentUser\My `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}')
$pwd = ConvertTo-SecureString -String 'test' -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath test.pfx -Password $pwd
signtool sign /fd SHA256 /f test.pfx /p test dist-store/ChordNotepad.msix
# Elevated prompt:
Import-PfxCertificate -FilePath test.pfx -CertStoreLocation Cert:\LocalMachine\TrustedPeople -Password $pwd
Add-AppxPackage dist-store/ChordNotepad.msix
```

### Things that behave differently in the Store build

- **Settings location.** Writes to `%APPDATA%\ChordNotepad` are redirected to
  the package's private folder
  (`%LOCALAPPDATA%\Packages\<package family>\LocalCache\Roaming\ChordNotepad`).
  Store and GitHub installs on the same machine do not share settings or logs.
- **Install folder is read-only.** Nothing may be written next to the exe.
  The app only writes under `%APPDATA%` today; keep it that way.

## Manual Release (Not Recommended)

If you need to create a release manually:

```bash
# Build for your platform
make build

# The binary will be in dist/
ls dist/
```

Note: Manual builds won't have proper version information and won't be multi-platform.
