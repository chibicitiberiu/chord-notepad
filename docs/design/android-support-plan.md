# Android: free release with a support nag and a supporter badge

## Context

The plan was to sell the Android app on Google Play, as with the paid MS Store supporter edition. On
2026-10-30 Tibi changed this:
- **Android is free**, with no locked features.
- **A friendly support request** appears at startup, a few days after install.
- **Supporters get a badge** in Settings and a thank-you message.

Two independent reviews (Play/billing/Android, and core/UX) reshaped the first draft. Their fixes are
folded in below.

**Decisions (Tibi, 2026-10-30):**
- **Android only.** Desktop stays as it is: free on GitHub, Snap and Flatpak, paid on the MS Store.
- **Play build:**
  - One one-time in-app product at €4.99, through Google Play Billing.
  - It can be bought from the nag and from a card in Settings.
  - Play policy forbids links to outside payment pages, so the Play binary carries no Ko-fi link.
- **FOSS build (GitHub APK, F-Droid):**
  - No nag and no Google libraries.
  - About gets "Support development" → https://ko-fi.com/tiberiualexandruchibici (later GitHub
    Sponsors).
- **Nag:**
  - Starts on day 7 after install and shows at most once per calendar day.
  - It appears only when the app is opened directly; never when it's opened with a file, never for
    supporters.
  - The buttons are "Support · {price}" and "Not now", with no opt-out.
- **Open with, `.txt` only** (`text/plain`). No ChordPro types and no Share target.

## Design

### 1. Core (Python): the session decides the startup screen

This fixes the Quick Start/nag race and keeps the decision out of Kotlin.
- **New `src/session/support.py`:** `NAG_DELAY_DAYS = 7` and a pure
  `should_show_support_prompt(today, installed_on, last_shown_on, can_ask)` taking ISO local dates.
  It returns false on the install day and before day 7. It returns true if `last_shown_on` is in the
  future, i.e. the clock was moved back.
- **New command `app_started(launch_kind, today, installed_on, can_ask_for_support)`:**
  - `launch_kind` is `direct`, `document` or `restore`. Kotlin sends it on every activity creation.
  - The session acts only on the first call per session, which makes rotation a no-op.
  - It always answers with a **state**, not an event: `StartupState(screen)`, where screen is `none`,
    `quick_start` or `support_prompt`.
  - `document` and `restore` give `none`. `direct` gives the nag when the policy allows; otherwise
    `quick_start` if that setting is on, otherwise `none`.
- **New command `dismiss_startup_screen()`:** clears the state. If the screen was the nag, it records
  `support_prompt_last_shown = today` and saves the config right away.
- **Config:** add one field, `support_prompt_last_shown: str | None`, to the dataclass, `to_dict` and
  `from_dict`.
  - Keep it out of `_ALL_SCALAR_FIELDS` and `SettingsValues`; otherwise saving Settings overwrites it
    (`settings_viewmodel.py:233`).
  - No version bump. The supporter status is **not** stored in Config: Play Billing is the source of
    truth and caches purchases offline.
- **Bridge, the full checklist:**
  - `bridge.py` and the committed `android/bridge_schema.json`.
  - The "every output crosses the bridge" test (`tests/test_session_bridge.py:685-722`).
  - Kotlin: `BridgeCodec.serializers`, `SessionRepository.publish`, `CommandNames`/`SessionCommands`
    and their tests.
  - The lists in `docs/architecture/session.md` and the "Bridge contract" section of `ANDROID.md`.
- **Remove** `QuickStartLaunch.decide` (`ui/help/QuickStartModel.kt:55-73`) and
  `AppGraph.quickStartShown`. `MainScreen` shows whatever `StartupState` says.
- **Desktop is unaffected.** It never calls `app_started`; its Quick Start path stays as it is.

### 2. Android launch and Open with (`MainActivity`, manifest, `SafDocumentStore`)

- **`android:launchMode="singleTask"`**, so a VIEW intent never stacks a second `MainActivity` on the
  shared `AppGraph`.
  - `onNewIntent` calls `setIntent()` and routes the intent.
  - A launcher tap while the task is alive doesn't create a new activity, so no new `app_started`.
- **Launch kind in `onCreate`:**
  - **direct:** `savedInstanceState == null` and the action is `MAIN`, or the launch came from history
    (`FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY`).
  - **document:** a VIEW intent that isn't from history.
  - **restore:** `savedInstanceState != null`.
  - **Anything else,** including a null action: never the nag.
- **Handling the VIEW intent:** handle it once, then `setIntent(Intent(ACTION_MAIN))` so rotation
  doesn't reopen it. Queue the open **after** the draft restore, on the same IO job, so a restored
  draft can't overwrite the opened file.
- **Opening the file:** goes through the existing open flow, so the unsaved-changes confirmation still
  applies.
  - Reading caps the size (5 MB, checked through `OpenableColumns.SIZE`) instead of the unbounded
    `readBytes()` at `SafDocumentStore.kt:60`.
  - Decoding matches the desktop's `FileService` behaviour; check it first.
- **Read-only grants:**
  - A file opened without a write grant (`checkUriPermission`) is opened read-only through a new core
    flag.
  - Save on a read-only document runs the Save As flow. That's a core change in `session.py`; today a
    failed save only emits `UserError`.
- **Recent:** files whose grant can't be persisted already drop out (`SafDocumentStore.kt:142-146`).
  Check this; no new code is expected.
- **Excluded from the nag:** `HelpShotActivity` and the debug activities pass `restore`.

### 3. Flavours `play` and `foss`

- **One dimension, `store`.** Both keep `applicationId = com.tibich.chordnotepad` and the same
  versionCode. There's no `SUPPORT_MODE` field: a `SupportBilling` interface in `main` has
  implementations in `src/play` (Play Billing) and `src/foss` (unavailable, plus the Ko-fi URL and
  About row). The Ko-fi URL therefore never reaches the Play dex.
- **`play` depends on `com.android.billingclient:billing-ktx` 9.1.x.** That pulls in
  `play-services-base`, `play-services-location` and Google's `datatransport` telemetry.
  - `src/play/AndroidManifest.xml` removes `INTERNET` and `ACCESS_NETWORK_STATE`
    (`tools:node="remove"`). Billing talks to the Play Store app over IPC; the telemetry then can't
    send anything.
  - Check the merged manifest. On the internal track, confirm that a purchase works with no INTERNET.
- **`android/tools/check_manifest.py` gets a `--flavor` argument:**
  - no INTERNET in either flavour (a hard check);
  - `foss` stays strict as today;
  - `play` may add BILLING, `com.google.android.gms` entries and the datatransport components.
  - Check the Play variant through the `assemblePlayRelease` APK, because aapt2 can't read an AAB.
  - Update the "no Google Play services" comments (`AndroidManifest.xml:5-7`,
    `check_manifest.py:1-9`).
- **Per-variant names**, which are silently broken today:
  - `build.gradle.kts:609-615` hard-codes `testDebugUnitTest`, `prepareLibraryDefinitionsDebug` and
    `generated/aboutLibraries/debug`. Wire them per variant.
  - Give each flavour its own licence-text directory, so billing's "Android SDK License" exists only
    in `play`. `LicencesTest` must not skip.
- **CI (`.github/workflows/build.yml`):**
  - Debug: `assembleFossDebug assemblePlayDebug`, the unit tests and `lint` for both.
  - Release: `bundlePlayRelease` (upload key) and `assembleFossRelease` (FOSS key), with the paths at
    `:891-900` and `:1055-1078` updated.
  - The reproducibility recipe uses `assembleFossRelease`.
- **Other paths:**
  - `RELEASE.md:424,525,552-558`, `ANDROID.md:140-170,934`, `ANDROID_PORT_PLAN.md:62,186,281,333`.
  - `android/tools/HELP_SHOTS.md:14`, `packaging/store/play/screenshots/README.md:13`.
  - `help_screenshots.py:28,200-211`, which gets a flavour argument and defaults to `foss`.
- **Licence:** add an AGPL §7 additional permission so the Play build may link the Google Play
  Billing Library. It goes in the LICENSE notice and README, and Tibi approves the wording. The Play
  variant's AboutLibraries list shows billing.

### 4. Billing (`src/play/.../support/PlayBilling.kt`, owned by `AppGraph`, so it survives rotation)

- **Setup:** `enablePendingPurchases(PendingPurchasesParams…enableOneTimeProducts())` and
  `enableAutoServiceReconnection()`.
- **Product:** product `supporter`, `ProductType.INAPP`. The price and offer token come from
  `getOneTimePurchaseOfferDetailsList()`.
- **One `process(purchases)` path** for both `onPurchasesUpdated` and `queryPurchasesAsync`:
  - PURCHASED makes the user a supporter, and it's acknowledged if it isn't yet.
  - PENDING shows "pending" and is never granted.
  - It never consumes.
- **When it queries:** at startup and on every `onResume`.
- **Results:**
  - `ITEM_ALREADY_OWNED`: re-query, then treat the user as a supporter.
  - `USER_CANCELED`: back to idle, with no error.
  - Supporter becomes false only after a query that returned OK with no purchase (a refund). Never on
    SERVICE_UNAVAILABLE or BILLING_UNAVAILABLE.
- **Exposed to the UI:** `isSupporter`, `price` and `purchaseState` (idle, pending, error) as
  StateFlows. Purchase results and the thank-you are app-scoped state.
- **Startup gating:** the Play build sends `app_started` once billing has connected and finished its
  query and product lookup, with a 2 s timeout. Python startup takes about that long anyway.
  - `can_ask_for_support` = billing OK, a price known and no purchase.
  - With an unknown price, there's **no nag at all**: a de-Googled phone or a sideloaded Play APK never
    gets one.
  - FOSS always passes false.
- **Dates:** Kotlin passes `today` and `installed_on` (from `firstInstallTime`) as local ISO dates,
  using `Calendar` (no `java.time` at minSdk 24).
- **Debug override:** a debug-only (`src/debug`) way to fake the install date and today, for testing.

### 5. Support UI (Kotlin, `ui/support/`)

- **Nag:** a Material `AlertDialog` with an icon, as in `ErrorPresenter.kt:41`.
  - It gets theming, dark mode, tablet width and back handling from that.
  - Back or a tap outside means "Not now". The heart icon is decorative, the title is a heading, and
    the body scrolls.
  - It isn't shown while a session request is pending.
  - Draft text, for Tibi to edit:
    > **Support Chord Notepad**
    > I build Chord Notepad on my own time. It's free with every feature included, and it'll stay that
    > way. If it's useful to you, a one-time purchase (no subscription) helps pay for the hours that
    > go into it. Supporters get a badge in Settings, and my thanks.
    >
    > [Not now]  [Support · €4,99]

    The localized price appears only on the button.
- **Thank-you dialog** after the purchase completes: "Thank you! Your support keeps Chord Notepad
  going."
  - Pending: "Payment pending. Your badge appears once Google Play confirms it."
- **Settings card** at the top of `PagesList` (`ui/settings/SettingsScreen.kt:202-216`), Play flavour
  only:
  - A non-supporter sees "Support Chord Notepad" plus the button.
  - A supporter sees "♥ Supporter. Thank you for supporting Chord Notepad."
  - Pending shows the line above.
  - With billing unavailable, the card is hidden.
- **FOSS About:** a "Support development" row after the source link (`ui/about/AboutScreen.kt` ~:102),
  using `openLink`.

### 6. Docs, listing, help, Play Console

- **Listing:** `packaging/store/play/listing-en-US.txt:29` changes to "free; an optional one-time
  purchase supports development". "No internet permission" (`:28`) stays true.
- **`docs/RELEASE.md`:**
  - Play setup (`:461-498`): the app is **Free**, and that's a one-way door; there are no promo codes
    (`:475-478`).
  - Then the console steps, in order:
    1. A payments (merchant) profile.
    2. EU trader (DSA) status, with a public address, phone and email.
    3. Upload an AAB with BILLING first.
    4. Create the `supporter` product at €4.99.
    5. License testers.
    6. Update the IARC questionnaire: there are now purchases inside the app (`:490`).
    7. Data safety: "no data collected". Record why: INTERNET is removed and purchase data stays on
       the device and in the Play app.
    8. Target audience stays 13+.
  - F-Droid section (`:569-577`): the recipe uses `gradle: [foss]`; run `fdroid scanner` locally.
- **`PRIVACY.md`:**
  - `:21-23`: the Play build declares BILLING.
  - `:51-55`: Play handles the optional purchase; the app keeps only the date of the last support
    prompt.
- **`README.md:77-79`:** free on Play with optional support.
- **`CHANGELOG.md`:** `:19` "paid" → free, plus entries for Open with and the support purchase.
- **Help** (one Android edition, shipped in both flavours, so never mention Ko-fi):
  - "In the Google Play version…" paragraph in `introduction.rst:219-224`.
  - Opening `.txt` files from a file manager.
  - Reconcile Quick Start's "first time" wording (`getting_started.rst:20-24`).
  - `make docs-check` must pass.
- **UI spec** (`docs/design/android-ui-spec.md`): Open with, the startup screen, the support card and
  the dialogs.
- **Memory:** update android-port.md and record the monetisation decision.

## Order of work (2 background agents, one owner per file)

1. **Agent A (Opus): core and launch.**
   - `src/session/*`, `src/models/config.py`, the bridge and schema, the Kotlin bridge DTOs.
   - `MainActivity`, the main manifest, `AppGraph`, `MainScreen`, `QuickStartModel`, `SafDocumentStore`,
     plus tests.
2. **Agent B (Opus), in parallel: flavours and billing.**
   - `build.gradle.kts`, `src/play/**`, `src/foss/**`, `check_manifest.py`, CI, licence directories,
     `help_screenshots.py`.
   - Adds `SupportBilling` to `main` as a new file only.
3. **After both land:** Agent B builds `ui/support/`, the Settings card and the FOSS About row.
4. **Me:** docs, listing, help, RELEASE/PRIVACY/README/CHANGELOG. Commits use explicit paths and
   per-hunk staging.

## Verification

- **pytest:**
  - Policy table: install day, day 6, day 7, same day, clock moved back, `can_ask` false, each
    `launch_kind`.
  - Session tests: the first `app_started` wins, the second is ignored; dismissal records the date and
    saves.
  - Quick Start: a direct launch with Quick Start on and no nag; a nag day replaces Quick Start.
  - Settings save doesn't overwrite the field; read-only save runs Save As; the bridge schema;
    `make test`.
- **Kotlin JVM:**
  - Launch-kind classification (MAIN, VIEW, history flag, saved state, null action).
  - `process(purchases)` against a fake: purchased and unacknowledged gets acknowledged; pending gets
    no grant; pending then purchased on the next start; a refund after an OK query; no change on
    SERVICE_UNAVAILABLE.
  - `LicencesTest` runs and doesn't skip, for both flavours.
- **Gradle:** `assembleFossDebug assemblePlayDebug`, the unit tests and lint for both flavours.
  `check_manifest.py --flavor` on the foss APK and on the playRelease APK. `aapt2 dump permissions`
  shows no INTERNET in either.
- **Emulator** (under the lock, `nice`, 2 GB):
  - Play debug with the debug date override: the nag on day 7, not again the same day, not on day 6.
    With no Play Store on the AVD there's no price, so there's no nag; checking that is part of the
    test.
  - Using DocumentsUI's "Open with" on a `.txt`: it opens, there's no nag, rotation doesn't reopen it,
    and a read-only grant leads Save to Save As.
  - FOSS: no nag, and the Ko-fi row is in About.
  - Screenshots checked visually.
  - `fdroid scanner` on the foss variant if it's available locally.
- **On Tibi's side (internal track, license tester):**
  - a purchase gives the badge and the thank-you;
  - kill the app during a pending purchase, finish it, relaunch, and check it's acknowledged;
  - a reinstall restores the badge;
  - a refund with entitlement removed clears it.
