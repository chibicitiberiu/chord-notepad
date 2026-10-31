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
- [ ] Android `versionCode` bumped with `VERSION` (see "Android" below)
- [ ] All changes committed and pushed
- [ ] CI tests pass on GitHub
- [ ] A `test` dispatch is green on every platform (Actions → Build and Release →
      Run workflow, Build type `test`)
- [ ] An `android-signing` dispatch is green: it builds and verifies the signed Play
      AAB and FOSS APK as workflow artifacts and publishes nothing

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

## Licence compliance

`LICENSE` (AGPL-3.0, verbatim), `ADDITIONAL-TERMS.txt` (the section 7
permissions for app stores and the terms about the name) and
`ARTWORK-TERMS.txt` (logo and store material) are the authoritative texts.
What a release has to do to stay within them:

- **Every store listing**, in every language (Play, Microsoft Store, Snap
  Store, later Apple), states that the app is licensed under the GNU
  AGPL-3.0 and gives the source URL, https://github.com/chibicitiberiu/chord-notepad.
  The listing texts are in `packaging/store/` (Play's English listing, the
  Microsoft Store's Romanian one); the English Microsoft Store listing exists
  only in Partner Center, so check it there. The About screens (desktop and
  both Android flavours) show both too.
- **Never upload a custom EULA** in Partner Center or App Store Connect: keep
  the store's standard licence terms, or leave the custom licence field empty
  (or set it to the AGPL). Permission 2(c) only covers restrictions the store
  operator sets.
- **Licence inventory (desktop).** `resources/licenses/components.json` lists
  every component each desktop build bundles (`windows`, `macos`, `linux`,
  `flatpak`, `snap`) with its version, licence texts and, for copyleft
  components, pinned source downloads. `packaging/licenses/licence_inventory.py`
  reads it; the Licences window (`src/services/licence_catalog.py`) shows
  it. The texts in `resources/licenses/texts/` are committed copies made by
  `pipenv run python packaging/licenses/gather_texts.py` (`--check` verifies
  them); rerun it when a component or its version changes.
  `tests/test_licences.py` keeps the inventory in step with `Pipfile.lock`,
  the spec, CI's FluidSynth zip, the Flatpak manifest and the built guide.
- **Strict PyInstaller check.** `chord-notepad.spec` maps every collected
  file to a component of the inventory. CI sets
  `CHORD_NOTEPAD_LICENCE_CHECK=strict`, so a file without an entry fails the
  build; local builds only warn. On Linux the spec also looks up the system
  libraries it copied (dpkg or rpm) and bundles their packages' licence files
  (`resources/licenses/system.json` in the build).
- **Source bundles.** Each release carries `ChordNotepad-<version>-source.tar.gz`
  (`android/tools/make_source_tarball.py`: the app, build scripts and every
  submodule at the built commit) and
  `ChordNotepad-<version>-third-party-sources.tar`
  (`packaging/licenses/make_source_bundle.py`: every `sources` entry of the
  inventory, SHA-256-checked, plus the Ubuntu source packages of the GPL and
  LGPL libraries in the Linux binary and the snap). The written offer the
  apps show is `resources/licenses/SOURCE-OFFER.txt`. The `create-release`
  job builds both bundles from the licence data the build jobs upload.
- **Android** has its own inventory and licences screen (`docs/ANDROID.md`,
  "About and the licences screen").

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

## Flatpak bundle (Linux)

Every Linux CI build also produces `ChordNotepad-linux-x64.flatpak`, attached
to the GitHub release next to the PyInstaller binary. It is a single-file
bundle; installing it pulls the `org.freedesktop.Platform` runtime from
Flathub. Bundles don't auto-update; a self-hosted Flatpak repo would fix that.

Unlike the other builds it is built **from source**, not from PyInstaller:
`packaging/flatpak/io.github.chibicitiberiu.ChordNotepad.yml` builds Tcl/Tk,
the `_tkinter` extension (from the CPython release matching the runtime's
Python), FluidSynth, the Python packages, and installs `src/` with a small
launcher. The build reuses the help HTML, icons and `build_info.py` generated
earlier in the job, so run `make flatpak` (which builds docs and icons first),
not flatpak-builder directly.

```bash
make flatpak        # -> dist/ChordNotepad-linux-x64.flatpak
flatpak install --user dist/ChordNotepad-linux-x64.flatpak
flatpak run io.github.chibicitiberiu.ChordNotepad
```

Locally it uses `flatpak-builder` if installed, otherwise the
`org.flatpak.Builder` flatpak (`flatpak install --user flathub org.flatpak.Builder`).

**Python packages** come from `packaging/flatpak/python3-deps.json`, generated
by `packaging/flatpak/gen_python_deps.py` from the versions in `Pipfile.lock`.
Re-run it after changing app dependencies. The list is explicit on purpose:
music21's numpy/matplotlib dependencies are never imported by the app and are
left out. If you add a dependency, add it to `PACKAGES` in that script.

**Sandbox:** X11 (Tk has no Wayland backend), PulseAudio, and network (only so
the host browser can reach the help server on 127.0.0.1). There is no
filesystem permission: open/save go through the XDG FileChooser portal
(`src/utils/file_dialogs.py`). Settings and logs live in
`~/.var/app/io.github.chibicitiberiu.ChordNotepad/`.

**Desktop integration** files are in `packaging/linux/` (the `.desktop` file
and AppStream metainfo). Add a `<release>` entry to the metainfo for each
version.

**Flathub:** not pursued for now. These files were written with AI assistance,
which Flathub's policy does not allow in submitted manifests; a Flathub
submission would need a hand-written manifest and metainfo.

## Snap Store (Linux)

`snap/snapcraft.yaml` builds a strictly confined snap on `core26` (Ubuntu
26.04). It reuses the Flatpak's pieces: the same pinned Python packages
(`packaging/linux/requirements.txt`, written by `gen_python_deps.py`), the
`.desktop` file and metainfo in `packaging/linux/` (the store listing's title,
summary, description and icon come from the metainfo), and the smoke test.

- **Python and Tk:** `core26` ships no Python, so Python 3.14 and its tkinter
  (Tk 8.6, which Ubuntu still builds Python against) are staged from the 26.04
  archive, as are FluidSynth 2.4 and libpulse.
- **Interfaces:** `x11`, `desktop`, `desktop-legacy`, `audio-playback`, `home`,
  `network-bind`. All auto-connect, so revisions pass automated review.
- **Launcher** (`packaging/snap/chord-notepad.sh`) points libpulse at the
  user's sound server; inside a snap `XDG_RUNTIME_DIR` is per-snap.

```bash
make snap           # -> dist/ChordNotepad-linux-x64.snap (needs snapcraft + LXD)
make snap-check     # installs it with --dangerous and runs the smoke test
```

### One-time setup

1. Create an account at <https://snapcraft.io> and register the name
   `chord-notepad` (`snapcraft register chord-notepad`). New names are
   reviewed by hand, which can take days.
2. Export a CI credential and add it as the repo **secret**
   `SNAPCRAFT_STORE_CREDENTIALS`:
   ```bash
   snapcraft export-login --snaps=chord-notepad --acls package_access,package_push,package_update,package_release -
   ```

CI then uploads every Linux build: tagged releases to `stable`, nightlies and
manual dispatches to `edge`. Without the secret the snap is still built and
kept as the `ChordNotepad-snap` workflow artifact.

## Android

One app, two build flavours, two channels, two signing keys. Both are free
with every feature; they differ only in how people can support development
(`docs/ANDROID.md`, "Startup screen and support prompt"):

- **Google Play** (`play` flavour): free, with an optional one-time
  "supporter" purchase through Google Play Billing and a support prompt from
  day 7 after install. CI builds an AAB signed with the **upload key**. You
  upload it to Play Console by hand, like the MSIX. Google re-signs it with
  the app signing key it keeps (Play App Signing).
- **GitHub release** (`foss` flavour): no Google libraries, no prompt, a
  Ko-fi link in About. CI builds a universal APK (arm64-v8a + x86_64) signed
  with the offline **FOSS key** and attaches it as
  `ChordNotepad-android.apk`, together with the full source tarball.

Play policy forbids pointing users to outside payment pages, so the Ko-fi
link lives only in the `foss` flavour's source set; the shared User Guide
never mentions it.

Because the keys differ, a Play install and a GitHub install can't update
each other. Switching channels means uninstalling first (songs are ordinary
files and stay where the user saved them; settings may not carry over).

F-Droid is not set up; see "F-Droid" below. Build details (toolchain,
natives, wheelhouse) are in `docs/ANDROID.md`.

### Version numbers

- `versionName` is the `VERSION` file.
- `versionCode` is `(MAJOR*10000 + MINOR*100 + PATCH)*10 + rebuild`, written as
  a plain number in `android/app/build.gradle.kts` (`versionCode = 4010` for
  0.4.1). It stays a literal because F-Droid's tooling reads it from that file
  with a regex; deriving it in Gradle would hide it from F-Droid.
- **Bump both together.** If `VERSION` changes and the literal doesn't, every
  Gradle build fails with the value to use, and so does
  `tests/test_android_version.py` (part of `make test`).
- The last digit is for re-releasing the same `VERSION` on Play (Play never
  accepts a versionCode twice): 4010, then 4011. Normally it's 0.
- Builds carry no run number or date. The About screen shows the commit
  (`BuildConfig.COMMIT`, which CI passes as `-PcnCommit`).

### Keys and GitHub setup (one time)

1. **Generate the keys** on your machine, into a directory outside the repo.
   Run it yourself (in Claude Code, prefix with `!`) so the passwords stay out
   of any transcript:
   ```bash
   source android/local.env
   android/tools/make_keys.sh /some/private/dir/chord-notepad-android-keys
   ```
   It creates `foss.p12` and `upload.p12` (PKCS12, RSA-4096, valid 50 years,
   aliases `foss` and `upload`), their public certificates and
   `fingerprints.txt`, then prints the next commands.
2. **Back up the directory twice**, encrypted, on two offline media in two
   places, with the passwords in your password manager. Test that one backup
   restores. Losing the FOSS key means GitHub installs can never be updated
   again. Losing the upload key is recoverable (Play Console lets you request
   an upload key reset).
3. **Create the environment**: repo Settings > Environments > New environment
   `android-release`. Under *Deployment branches and tags* choose *Selected
   branches and tags* and add the tag rule `v*` and the branch `main` (release
   dispatches run on `main`; without it they get a failed `android-release`
   job, while the desktop release still goes out). A required reviewer is
   optional; it would pause only the Android job.
4. **Add the secrets** to that environment with the `gh secret set ... --env
   android-release` commands the script printed. The password ones prompt for
   the value, so nothing lands in your shell history.

   | Secret | Value |
   |---|---|
   | `ANDROID_FOSS_KEYSTORE_B64` | `base64 -w0 foss.p12` |
   | `ANDROID_FOSS_STORE_PASSWORD` | FOSS keystore password |
   | `ANDROID_UPLOAD_KEYSTORE_B64` | `base64 -w0 upload.p12` |
   | `ANDROID_UPLOAD_STORE_PASSWORD` | upload keystore password |

5. **Pin the FOSS certificate** (optional, recommended): add the variable
   `ANDROID_FOSS_CERT_SHA256` (environment or repo variable) with the FOSS
   certificate's SHA-256 as lowercase hex without colons (the form `apksigner
   verify --print-certs` prints). CI then refuses an APK signed with anything
   else, for example after a mixed-up secret.
6. **Record the fingerprints** in "Signing certificates" below.

Note that CI holds the FOSS key as an environment secret so the GitHub APK is
signed automatically. If you'd rather keep it strictly offline, leave the FOSS
secrets unset: CI then builds an unsigned APK (and attaches only the source
tarball), and you sign locally and upload the APK yourself (see "Signing
locally").

### Each Android release

- [ ] `VERSION` and `versionCode` bumped in the same commit.
- [ ] CHANGELOG entries for Android-only changes start with "Android:".
- [ ] `make test` and, in `android/`, `./gradlew testFossDebugUnitTest testPlayDebugUnitTest
      lintFossDebug lintPlayDebug assembleFossDebug assemblePlayDebug`.
- [ ] Tag `v<VERSION>` (exactly the `VERSION` file) and push it, or run the
      *release* dispatch.

On a `v<VERSION>` tag push or a *release* dispatch, the `android-release` job
(environment `android-release`) builds, checks and uploads:

| Artifact | Contents | Where it goes |
|---|---|---|
| `ChordNotepad-android-play` | `ChordNotepad-<v>-play.aab`, upload-key signed | Workflow artifact only; upload to Play by hand |
| `ChordNotepad-android` | `ChordNotepad-android.apk` (FOSS-signed, v2 + v3), `ChordNotepad-<v>-source.tar.gz`, `SHA256SUMS` | `attach-android` puts them on the GitHub release |

Checks before upload: `apksigner verify --print-certs` (v2 and v3 present,
certificate pin if set), `jarsigner -verify` on the AAB, 16 KB page alignment
(`check_16k.py`, `zipalign -c -P 16`) and the merged manifests
(`check_manifest.py --flavor foss` on the APK; `--flavor play` on an unsigned
`assemblePlayRelease` APK, since aapt2 can't read the AAB).

- A tag that isn't exactly `v<VERSION>` fails the Android job only.
- Without the secrets the job still builds, warns, and produces unsigned
  outputs; an unsigned APK is never attached.
- `attach-android` runs only after both `create-release` and
  `android-release` succeeded, then adds an "Android" section to the release
  notes (APK, certificate SHA-256, source tarball). An Android failure never
  blocks or fails the desktop release.
- Nightlies, test dispatches and pushes never use the release keys; the
  `android` job keeps building debug APKs there.
- The source tarball is the AGPL-3.0 section 6 / LGPL source offer: the app,
  build scripts and every checked-out submodule (FluidSynth, libsndfile and
  its codecs, Oboe) at the built commit, made by
  `android/tools/make_source_tarball.py` (reproducible: same commit, same
  bytes). The pinned Python packages are pure-Python wheels whose source is
  the wheel itself (`android/requirements.txt`).

Then, for Play, download `ChordNotepad-android-play` from the workflow run and
upload the `.aab` in Play Console (Test and release > the track > Create new
release).

### Google Play (first time)

The account is a personal one (registered 2026-10, identity verification
pending at the time of writing). Things to know first:

- **The app is Free, and that's final.** An app published free can never
  become paid. Support comes from the in-app purchase instead.
- **The developer address is public.** An account that sells anything,
  in-app purchases included, must show a contact address on the store
  listing, and in the EU must declare **trader status** (Digital Services
  Act) with a public address, phone and email. Use ones you're happy to
  publish.
- **Payments profile before the product.** In-app products need a linked
  payments (merchant) profile.
- **Personal accounts** (created after November 2023) must run a closed test
  with at least 12 testers opted in for 14 days in a row before they can apply
  for production access. Organization accounts skip this.
- **Testing purchases**: add your Google account (and any helpers) as
  **license testers** (Play Console > Settings > License testing). Their
  purchases use test cards and are never charged. Use the **internal
  testing** track for your own installs (no review wait) and the closed track
  for the 12-tester run. The app is free, so testers need no promo codes.

Setup, roughly in order:

1. Create the app: name "Chord Notepad", app (not game), **Free**, category
   Music & Audio. Package name `com.tibich.chordnotepad`.
2. App signing: keep Play App Signing with a Google-generated app signing key.
   The first uploaded AAB registers the upload key (or upload
   `upload-cert.pem` when asked for the upload certificate).
3. App content: privacy policy URL (the GitHub link to `PRIVACY.md`); ads: no;
   **Data safety: no data collected, no data shared**; content rating (IARC
   questionnaire: a music utility, no user-generated content shared, no
   violence, **digital purchases inside the app: yes**); target audience 13+
   (not designed for children, to stay out of the Families program, whose
   rules restrict purchase prompts).

   Data safety reasoning, so it can be re-checked on each billing-library
   update: the Play Billing library brings Google Play services and Google's
   `datatransport` telemetry, but the `play` manifest removes INTERNET and
   ACCESS_NETWORK_STATE, plus datatransport's CCT backend registration and
   its two schedulers (`android/app/src/play/AndroidManifest.xml`;
   `check_manifest.py --flavor play` enforces it). Telemetry events are then
   dropped before they are stored, and nothing in the app's process can send
   data. The purchase itself happens in
   the Play Store app, under Google's own data handling. The app stores only
   the date it last showed the support prompt, on the device.
4. Store listing: short and full description, 512 px icon, 1024x500 feature
   graphic, phone and tablet screenshots. The full description includes the
   licence notice and source link (`packaging/store/play/listing-en-US.txt`).
   It may mention the optional purchase but must not link to any outside
   payment page.
5. Internal testing release with the CI AAB. Play only lets you create
   in-app products once an AAB with the BILLING permission is uploaded, so
   do this before step 6.
6. Monetize > Products > One-time products: create `supporter` ("Chord
   Notepad supporter"), €4.99, activate it. Play converts the price for other
   countries; check the converted prices.
7. Install from Play on your phone as a license tester and check: audio, file
   open/save, Open with on a `.txt`, the About screen's version and commit,
   and the purchase:
   - buy: the thank-you appears and Settings shows the supporter badge;
   - a slow test card (pending): kill the app, let the payment complete,
     reopen: the badge appears and the purchase is acknowledged (not refunded
     after 3 days);
   - uninstall and reinstall: the badge comes back;
   - refund the test order with "remove entitlement" (Order management): the
     badge goes away on the next start.
8. Closed test (personal account: 12 testers, 14 days), then production.

### Developer verification

Google's developer verification requires apps on certified Android devices to
come from a registered developer: from September 2026 in Brazil, Indonesia,
Singapore and Thailand, and worldwide from 2027. A Play developer account does
this in Play Console, and one package name can have several signing keys, so
the Play build and the GitHub/F-Droid APK both stay installable under
`com.tibich.chordnotepad`. Play's help page for this:
https://support.google.com/googleplay/android-developer/answer/16762301

1. **Play build.** Play registers the package with Play's app signing key once
   the first AAB is uploaded (Play App Signing, Google-managed key). Check it
   under Play Console > **Android developer verification** > **Package
   names**. If the package isn't listed, register it there.
2. **The FOSS key** (GitHub APK, F-Droid). On that page, select
   `com.tibich.chordnotepad` > **Add key**, enter the FOSS key's SHA-256
   (`ANDROID_FOSS_CERT_SHA256`, also in `fingerprints.txt`):
   `BB:DF:72:E7:70:C1:48:E7:2B:5A:C1:CC:3B:15:2E:9F:1A:5C:96:FA:0C:C5:28:92:CC:8F:BE:05:62:1D:30:B1`,
   and select **Add key**. It takes a few minutes to reach the registry.
3. **Proof of ownership, if the console asks for it.** Select **Verify** next
   to the key and copy the snippet. Put it in
   `android/app/src/foss/assets/adi-registration.properties`, then build a foss
   release APK signed with the FOSS key: either locally, as in "Signing
   locally" below, or with a release dispatch, which signs
   `ChordNotepad-android.apk` with the FOSS key. Select **Upload** on the same
   page and upload that APK. The snippet only identifies the developer
   account, so the file can stay in the repo.

### Signing locally

Rarely needed (CI signs). With the keystore paths and passwords in the
environment, never on the command line:

```bash
cd android && source local.env
export CN_FOSS_STORE_FILE=/some/private/dir/chord-notepad-android-keys/foss.p12 CN_FOSS_KEY_ALIAS=foss
read -rs CN_FOSS_STORE_PASSWORD && export CN_FOSS_STORE_PASSWORD
nice -n 10 ./gradlew --no-configuration-cache assembleFossRelease -PcnSigning=foss -PcnCommit=$(git rev-parse --short=9 HEAD)
```

`-PcnSigning` is `debug` (default, so local release builds install), `none`
(unsigned), `upload` or `foss`; the `CN_UPLOAD_*` variables work the same way.
`--no-configuration-cache` keeps the passwords out of Gradle's configuration
cache.

### Reproducing the GitHub APK

Anyone can check that `ChordNotepad-android.apk` was built from the published
source: build it unsigned with the same toolchain and compare everything but
the signature.

1. Get the source: the release's `ChordNotepad-<v>-source.tar.gz`, or a clone
   of the tag with its submodules (`docs/ANDROID.md`, "Native sources"). The
   tarball names its commit: `zcat ChordNotepad-<v>-source.tar.gz | git
   get-tar-commit-id`.
2. Use CI's toolchain (`.github/workflows/build.yml`, job `android-release`):
   Linux x86_64, Temurin JDK 21, Python 3.14.8 as `CHAQUOPY_BUILD_PYTHON`
   (with `android/docs-requirements.txt` installed), NDK 27.3.13750724, CMake
   3.31.6, build-tools 36.1.0, platform `android-37.0`.
3. Build:
   ```bash
   cd android
   export PYTHONHASHSEED=0 SOURCE_DATE_EPOCH=1700000000   # any value; it must be set
   "$CHAQUOPY_BUILD_PYTHON" -I tools/build_wheelhouse.py fetch
   ./gradlew assembleFossRelease -PcnSigning=none -PcnCommit=<first 9 characters of the commit>
   ```
4. Compare with the release APK:
   ```bash
   python3 tools/compare_apks.py ChordNotepad-android.apk app/build/outputs/apk/foss/release/app-foss-release-unsigned.apk
   # -> "entries identical; difference is in zip structure/signature only"
   apksigcopier compare ChordNotepad-android.apk --unsigned app/build/outputs/apk/foss/release/app-foss-release-unsigned.apk
   # -> exit 0: byte-identical once the signature is copied over
   ```

Status: on the dev machine, an unsigned build plus the FOSS-signed build's
signature (`apksigcopier copy`) gives the signed APK byte for byte, and two
clean builds in different paths give identical APKs (`docs/ANDROID.md`,
"Reproducibility"). Not yet checked: a CI build against a local one (different
machine, user and Python micro build). Do that on the first tagged release
before claiming reproducibility anywhere.

### F-Droid

Not submitted; Tibi decides at release time (the F-Droid AI-policy question,
`docs/ANDROID.md`, "Decisions and constraints"). IzzyOnDroid is out: its policy rejects
AI-written code. If F-Droid goes ahead, its recipe builds the `foss`
flavour (`gradle: [foss]`) with `-PcnSigning=none` (the output is
`app-foss-release-unsigned.apk`); run `fdroid scanner` on it locally first,
since the `play` flavour's billing dependency sits in the same
`build.gradle.kts`. With a
verified reproducible build it can publish the FOSS-signed GitHub APK
(`Binaries:`), so F-Droid and GitHub installs update each other; otherwise
F-Droid signs with its own key, permanently. Fastlane metadata and
changelogs are not written yet.

### Signing certificates

Fill in from `fingerprints.txt` after running `make_keys.sh`, and the Play
app signing key from Play Console > Test and release > App integrity. These
are public; users can compare them with `apksigner verify --print-certs`.

| Key | SHA-256 |
|---|---|
| FOSS (GitHub APK) | `BB:DF:72:E7:70:C1:48:E7:2B:5A:C1:CC:3B:15:2E:9F:1A:5C:96:FA:0C:C5:28:92:CC:8F:BE:05:62:1D:30:B1` |
| Play upload | `96:E1:3E:EA:10:B9:FE:67:54:68:DB:2C:42:08:70:31:90:70:A8:C5:6C:52:45:32:8E:54:2F:C2:0A:53:D2:2C` |
| Play app signing (Google) | _after the first Play upload_ |

## Manual Release (Not Recommended)

If you need to create a release manually:

```bash
# Build for your platform
make build

# The binary will be in dist/
ls dist/
```

Note: Manual builds won't have proper version information and won't be multi-platform.
