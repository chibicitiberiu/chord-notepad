# Draft: AGPL-3.0 section 7 additional permissions for app stores

Status: draft for Tibi to approve or edit. Nothing in LICENSE, README or the app
has been changed.

## Why it's needed

Two separate problems come up when the app ships through an app store.

1. **Non-free store libraries.** The play flavour links the Google Play Billing
   Library (billing-ktx 9.1.0) and, through it, Google Play services
   (play-services-base, -basement, -tasks, -location, -places-placereport) and
   Google's datatransport/Firebase encoder libraries. They're under the Android
   Software Development Kit License Agreement, not a free licence, so their
   source can't be part of the play APK's Corresponding Source. Plain AGPL-3.0
   doesn't allow conveying that combination. An iOS build would use StoreKit
   and the Microsoft Store build could use the Windows.Services.Store APIs; both
   are probably covered by the GPL's System Libraries rule already, but naming
   them removes the doubt.
2. **Store terms.** Section 10 forbids imposing "any further restrictions" on
   recipients. Apple's App Store terms (FairPlay DRM, device limits, usage
   rules) clearly do; the Microsoft Store's standard licence terms and Google
   Play's terms of service are less clear-cut. This is the issue that pushed VLC
   off the App Store in 2011 and that Bulwark Mail is collecting contributor
   consent for (github.com/orgs/bulwarkmail/discussions/1113).

Tibi is the only copyright holder today, so neither problem stops Tibi's own
builds. The permissions matter for contributed code (it arrives under whatever
terms are in the repo when it's contributed) and for forks.

## Proposed text

> **Additional permissions under GNU AGPL version 3 section 7**
>
> Copyright (C) 2025-2026 Tiberiu Chibici
>
> These permissions are granted in addition to the GNU Affero General Public
> License version 3 ("the License") for Chord Notepad ("the Program").
>
> **Definitions.**
>
> "App Store" means each of the following, including its successors run by the
> same company: Google Play, operated by Google LLC; the Microsoft Store,
> operated by Microsoft Corporation; and the App Store, operated by Apple Inc.,
> in its iOS, iPadOS and macOS editions.
>
> "Store Library" means a library, framework or software development kit
> published by the operator of an App Store for in-app purchases, licensing or
> other integration with that App Store, together with the libraries it depends
> on as published by the same operator. Examples are the Google Play Billing
> Library with Google Play services, Google Data Transport and the Firebase
> encoders it depends on; Apple StoreKit; and the Microsoft Store APIs
> (Windows.Services.Store).
>
> **1. Linking Store Libraries.** If you modify this Program, or any covered
> work, by linking or combining it with a Store Library (or a modified version
> of that library), containing parts covered by the terms of that library's
> licence, the licensors of this Program grant you additional permission to
> convey the resulting work. Corresponding Source for a non-source form of such
> a combination need not include the source code for the parts of the Store
> Library used; it shall include the source of the covered work.
>
> **2. Distribution through an App Store.** The licensors of this Program grant
> you additional permission to convey the Program, or any covered work, in
> object code form through an App Store, even where that App Store's terms of
> service, licence terms or technical measures (such as digital rights
> management or limits on the number of devices) place restrictions on
> recipients that section 10 of the License would otherwise forbid, provided
> that:
>
> (a) you make the Corresponding Source of the work you convey available to
> everyone, at no charge, under the terms of the License, from a publicly
> accessible network server, for as long as you offer that work through the
> App Store; and
>
> (b) you say where that Corresponding Source can be obtained, in the App Store
> listing or in the work's user interface.
>
> The App Store's restrictions apply only to the copy obtained through the App
> Store. They do not apply to the Corresponding Source or to any copy obtained
> another way.
>
> **Scope.** These permissions do not permit linking with any non-free library
> other than a Store Library, and they do not relax any other term of the
> License for the covered work. You may remove these additional permissions
> from your copy, or from any part of it, as section 7 of the License allows; a
> version without them is plain AGPL-3.0.

Section 1 follows the shape of the FSF's template for GPL linking exceptions,
with the Corresponding Source sentence turned around because the store
libraries' source isn't available. Section 2's conditions match what section
6(d) already asks for (source from a network server at no extra charge), so
anyone shipping through a store is no worse off than under the plain licence.

Tibi meets 2(a) and 2(b) today: the source is on GitHub, the Play listing
gives the URL, and both the Android and desktop About screens show it (the
desktop one at `src/ui/main_window.py:1306`, which covers the Microsoft Store
build).

### Option: store permission for official builds only

As drafted, anyone may ship a fork through a store. To keep that to Tibi's own
releases (for example, to avoid a clone of the paid Microsoft Store edition),
change the opening of section 2 to:

> The licensors of this Program grant Tiberiu Chibici, and anyone Tiberiu
> Chibici authorises in writing, additional permission to convey ...

Forks could then still be distributed anywhere else under the AGPL, but not
through a store unless they remove the store's restrictions. This version is
more protective and less generous; some contributors may see it as one-sided,
as they would a CLA.

## Where it would go

- **A new file, `LICENSE.ADDITIONAL`**, with the text above. Keeping `LICENSE`
  verbatim matters: `android/tools/gather_licenses.py` copies it byte for byte
  into the app as `AGPL-3.0.txt`, and GitHub's licence detection reads it.
- **README.md**, "License" section: one sentence after "Licensed under GNU
  Affero General Public License v3.0", e.g. "with additional permissions for
  distribution through app stores (see `LICENSE.ADDITIONAL`)."
- **A short CONTRIBUTING.md** (there isn't one yet) saying contributions are
  accepted under the AGPL with the permissions in `LICENSE.ADDITIONAL`. This
  makes sure contributed code comes in under both.
- **The app's licence screen**: the `chord-notepad` entry in
  `android/app/src/main/assets/licenses/components.json` gets the new file as
  a second text (`"texts": ["AGPL-3.0", "AGPL-additional-permissions"]`), with
  the file added to gather_licenses.py's table. Shown in both flavours. The
  desktop About/licence view should show it too.

## Open points for Tibi

1. Store permission for anyone (as drafted) or for official builds only (the
   option above).
2. The defined "Store Library" covers future store SDKs automatically but is
   broader than naming each Maven artifact. The CI manifest check still flags
   new Google components, so a change is noticed either way.
3. Copyright years and holder line as they should read.
4. Whether to add other stores later (Amazon Appstore, Samsung Galaxy Store,
   Snap Store). The Snap Store and Flathub don't restrict recipients, so they
   don't need it.
