# Draft: AGPL-3.0 section 7 additional permissions for app stores

Status: draft for Tibi to approve or edit, revised after two independent
reviews (2026-10-30). Nothing in LICENSE, README or the app has been changed.

## Why it's needed

Three separate problems come up when the app ships through an app store.

1. **Non-free store libraries.** The play flavour links the Google Play Billing
   Library (billing-ktx 9.1.0) and, through it, Google Play services
   (play-services-base, -basement, -tasks, -location, -places-placereport) and
   Google's datatransport/Firebase encoder libraries. They're under the Android
   Software Development Kit License Agreement, not a free licence, so their
   source can't be part of the play APK's Corresponding Source. Plain AGPL-3.0
   doesn't allow conveying that combination. StoreKit (iOS) and
   Windows.Services.Store are probably System Libraries already; naming them
   removes the doubt.
2. **Store terms restrict users.** Section 10 forbids imposing "any further
   restrictions" on recipients. Apple's terms (FairPlay DRM, the device limits
   in its usage rules) clearly do; the FSF objected to GNU Go on the App Store
   in 2010 for this reason, and VLC was pulled in 2011.
3. **Store terms bind the developer.** Section 12 says that conditions imposed
   on you "by court order, agreement or otherwise" don't excuse you; if you
   can't meet both, you may not convey at all. The developer agreement you sign
   with a store is such an agreement, so excusing section 10 alone isn't enough.

Tibi is the only copyright holder today, so none of this stops Tibi's own
builds. The permissions matter for contributed code (it arrives under whatever
terms are in the repo when it's contributed) and for forks. Widening them
later would need every contributor's consent, so the definitions are general on
purpose (Tibi, 2026-10-30: no lock-in to today's stores).

## Proposed text

> **Additional permissions and terms under GNU AGPL version 3 section 7**
>
> Copyright (C) 2025-2026 Tiberiu Chibici
>
> These permissions and terms are added to the GNU Affero General Public
> License version 3 ("the License") for Chord Notepad ("this Program"). Terms
> defined in the License have the same meaning here.
>
> **Definitions.**
>
> "App Store" means an online service through which many developers who are
> not affiliated with its operator distribute software, to the public or to a
> group of users the developer chooses (such as testers or the members of an
> organisation), and which is operated by someone other than you or any entity
> that controls, is controlled by, or is under common control with you.
> Examples are Google Play, the Microsoft Store, Apple's App Store (iOS, iPadOS
> and macOS) and TestFlight, the Amazon Appstore, the Samsung Galaxy Store,
> Huawei AppGallery and Steam.
>
> "Store Library" means an unmodified library, framework or software
> development kit, as published by the operator of an App Store, used only to
> integrate a work with that App Store: selling the work or features of it,
> verifying or restoring purchases, updates delivered by the App Store, and
> review prompts. It includes the libraries it requires in order to work, as
> published by the same operator. Examples are the Google Play Billing Library
> (with the Google Play services, Google Data Transport and Firebase encoder
> libraries it requires), Apple StoreKit, and the Microsoft Store APIs
> (Windows.Services.Store). This definition does not cover the work's own use
> of any library for advertising, analytics, crash reporting, user tracking, or
> preventing the copying or modification of the work, even if that library is
> also part of a Store Library.
>
> **1. Linking Store Libraries.** If you modify this Program, or any covered
> work, by linking or combining it with a Store Library, the licensors of this
> Program grant you additional permission to convey the resulting work. For all
> purposes of the License, including sections 6 and 13, the Corresponding
> Source of such a combination need not include the source code of the Store
> Library; it shall include the source code of the covered work.
>
> **2. App Stores and platform requirements.** The licensors of this Program
> grant you additional permission to convey this Program, or any covered work,
> in object code form through an App Store, or in a form that a platform's
> operator requires before the work can be installed or run on that platform
> (such as code signing, notarisation or developer verification), and to accept
> that operator's terms for doing so, even where those terms or the operator's
> technical measures (such as digital rights management, limits on the number
> of devices, or trial periods) restrict recipients in a way that section 10 or
> section 12 of the License would otherwise forbid. This permission applies
> only if you comply with every other condition of the License, including
> sections 4 to 6, and:
>
> (a) you make the Corresponding Source of each version you convey this way
> available to everyone, at no charge, under the terms of the License, from a
> publicly accessible network server, for as long as you offer that version;
>
> (b) you state, in the App Store listing for the work (where there is one)
> and in its Appropriate Legal Notices, that it is licensed under the License
> and where its Corresponding Source can be obtained;
>
> (c) the restrictions are set by the operator, including through features of
> the App Store you choose to use; where the operator lets you supply your own
> licence terms for the work, any terms you supply add no restriction beyond
> the License; and
>
> (d) you do not assert those restrictions against anyone in respect of the
> Corresponding Source, or of copies obtained in any other way.
>
> This permission does not limit any right the License gives to any recipient,
> including one who obtained the work through an App Store. Section 3 of the
> License continues to apply to you.
>
> **3. Names.** Under sections 7(c) and 7(e) of the License: this License
> grants no right to use the name "Chord Notepad" or its icon as trade names
> or trademarks. A modified version conveyed through an App Store must be
> marked as modified and must be presented to users under a name and icon
> other than Chord Notepad's. This does not apply to a version changed only as
> needed to build, package or install it for a particular operating system,
> distribution or App Store, without changing what it does for its users.
>
> **Scope.** Permissions 1 and 2 extend to no non-free library other than a
> Store Library, and they neither add to nor take away from what the License
> itself allows, for example for System Libraries. When you convey a copy of a
> covered work, you may remove permissions 1 and 2 from that copy, or from any
> part of it, as section 7 of the License allows; a version without them is
> governed by the License and term 3 alone. If you remove permission 1, you may
> no longer convey a combination with a Store Library.

Notes on the text:
- Permission 1 follows the FSF's template for linking exceptions
  (gnu.org/licenses/gpl-faq.html#GPLIncompatibleLibs). The template drops its
  source sentence when the library's source can't be distributed; this version
  says it outright. "Unmodified" closes a gap: otherwise a fork could hide its
  own closed code inside a "modified" store library.
- The Store Library exclusion targets what the *work* uses a library for, so
  billing's own use of Google's datatransport stays covered while an app
  calling Firebase Analytics or AdMob isn't. Google's License Verification
  Library (a copy-protection scheme) is deliberately not covered.
- The "not affiliated" and "many developers" wording stops a friend's or a
  shell company's one-app "store" from counting, and keeps GitHub Releases
  and ordinary download sites out.
- "A form that a platform's operator requires" covers Apple notarisation and
  web distribution, EU alternative marketplaces, and Google's developer
  verification for sideloaded APKs (from 2026), so the FOSS APK and F-Droid
  builds are covered too.
- 2(c) blocks a fork from uploading its own restrictive EULA as "store
  terms" (App Store Connect and Partner Center both allow a custom EULA). The
  store's standard EULA is fine.
- Term 3 is a restriction section 7 allows, not a permission, so it stays even
  where 1 and 2 are removed. It's the clone protection: a fork can't
  re-publish the paid Microsoft Store edition under the same name and icon.
  Store impersonation policies back it up. It doesn't stop a fork from
  existing, or from being sold under its own name. It's limited to App Stores,
  and packaging changes are exempt, so Linux distributions and F-Droid can
  patch the build to package it without renaming (the Firefox/Iceweasel
  problem).

### Fallback option: store permission for official builds only

If term 3 isn't protection enough, permission 2 can be narrowed to Tibi's own
releases by changing its opening to:

> The licensors of this Program grant Tiberiu Chibici, and anyone Tiberiu
> Chibici authorises in writing, additional permission to convey ...

Forks could still be distributed anywhere except through a store. This is
more protective and less generous; some contributors may see it as one-sided,
as they would a CLA.

## What Tibi would have to do to comply

- **Play:** already compliant. The listing gives the repo URL, both flavours'
  About screens show it, and all play-flavour sources and build scripts are in
  the repo (CI attaches a source tarball with submodules).
- **Microsoft Store:** add the repo URL and "licensed under the GNU AGPL-3.0"
  to every listing language (the Romanian listing says "disponibilă gratuit pe
  GitHub" with no URL; the English one is only in Partner Center). The desktop
  About dialog (`src/ui/main_window.py:1306`) already shows both. Keep the
  store's standard licence terms; don't add a custom EULA.
- **Apple, later:** the same in App Store Connect; leave the custom licence
  agreement field empty, or set it to the AGPL.

## Known problems outside this text

1. **The desktop build ships no third-party licence notices (affects
   releases already out).** CI downloads the upstream
   `fluidsynth-2.3.4-win10-x64.zip` (`.github/workflows/build.yml:155`) and
   `chord-notepad.spec` bundles every DLL in it. That includes FluidSynth
   and, typically, glib, libintl and libsndfile, all LGPL. No licence text or
   notice is bundled (`datas` in `chord-notepad.spec`, `packaging/msix/`),
   and there's no source offer for those DLLs. CPython, Tcl/Tk, Pillow,
   music21 and the others need their notices too. Android solves this with
   `components.json`, a licences screen and `make_source_tarball.py`; the
   desktop needs the same: a licences view, and a source/notice bundle
   attached to each release (including the exact FluidSynth zip and its
   sources). This is independent of the AGPL permissions and should be fixed
   in the next desktop release.
2. **LGPL components and the App Store.** Permissions 1 and 2 only cover
   Tibi's code. FluidSynth, libsndfile, pyFluidSynth and chardet are
   LGPL-2.1, which has its own "no further restrictions" clause; only their
   own copyright holders can waive it. Relinking (LGPL-2.1 section 6) can be
   met, since the whole app builds from public source. The usage-rules
   conflict on Apple's store can't be fixed from here. Before any iOS work,
   choose: accept the risk, ask upstream, or replace the components. A small
   step: requests, chardet and urllib3 may be droppable from the Android/iOS
   bundle (no network access), if music21 allows it.
3. **Console stores** (Nintendo, Sony) ship SDKs under NDA. Their source can't
   be published and they aren't Store Libraries, so the AGPL rules them out
   whatever this text says.

## Where it would go

- **A new file, `LICENSE.ADDITIONAL`**, with the text above. Keeping `LICENSE`
  verbatim matters: `android/tools/gather_licenses.py` copies it byte for byte
  into the app as `AGPL-3.0.txt`, and GitHub's licence detection reads it.
- **README.md**, "License" section: "Licensed under GNU Affero General Public
  License v3.0, with additional permissions for app stores and terms about the
  project's name (see `LICENSE.ADDITIONAL`)." The README's "Contributing"
  section points to CONTRIBUTING.md.
- **A new CONTRIBUTING.md:** "By submitting a contribution you license it
  under the GNU AGPL-3.0-only together with the additional permissions and
  terms in LICENSE.ADDITIONAL, and you certify the Developer Certificate of
  Origin 1.1 (sign off your commits with `git commit -s`)." Optionally a CI
  check that commits from others carry a sign-off.
- **SPDX id:** the `chord-notepad` entry in
  `android/app/src/main/assets/licenses/components.json` becomes
  `AGPL-3.0-only WITH LicenseRef-ChordNotepad-Store-Permissions`, and its
  `texts` gets the new file as a second text, added to gather_licenses.py's
  table. Shown in both flavours, and in the desktop licences view once it
  exists.

## Open points for Tibi

1. **Term 3 (names):** keep it, or drop it. It's the recommended answer to the
   clone question instead of the official-builds-only fallback.
2. **CLA or DCO:** the draft assumes a DCO (contributors certify they may
   contribute; no relicensing right). If you'd ever want to relicense
   contributed code (for example to close future versions), you need a CLA,
   and the time to decide is now, while you're the only author.
3. **Copyright line** as it should read.
4. **Desktop notices:** whether to fix known problem 1 now or with the next
   desktop release.
