# Draft: AGPL-3.0 section 7 additional permission for Play Billing

Status: draft for Tibi to approve or edit. Nothing in LICENSE, README or the app
has been changed.

## Why it's needed

The play flavour links the Google Play Billing Library (billing-ktx 9.1.0) and,
through it, Google Play services (play-services-base, -basement, -tasks,
-location, -places-placereport) and Google's datatransport/Firebase encoder
libraries. Billing and Play services are distributed under the Android Software
Development Kit License Agreement, not a free licence, so their source can't be
part of the play APK's Corresponding Source. Plain AGPL-3.0 doesn't allow
conveying that combination. Section 7 lets the copyright holders add a
permission that removes the obstacle for these specific libraries only.

Only the copyright holders can grant it. If any part of the code has an outside
contributor, that person has to agree too (or their part has to be covered by
their own grant).

## Proposed text

> **Additional permission under GNU AGPL version 3 section 7**
>
> If you modify this Program, or any covered work, by linking or combining it
> with the Google Play Billing Library (Maven artifacts
> `com.android.billingclient:billing` and `com.android.billingclient:billing-ktx`)
> and the libraries it depends on as published by Google (Google Play services,
> `com.google.android.gms:*`; Google Data Transport,
> `com.google.android.datatransport:*`; Firebase encoders,
> `com.google.firebase:firebase-encoders*`), or modified versions of those
> libraries, containing parts covered by the terms of the Android Software
> Development Kit License Agreement or other Google licence terms, the
> licensors of this Program grant you additional permission to convey the
> resulting work. Corresponding Source for a non-source form of such a
> combination need not include the source code for the parts of those
> libraries used; it shall include the source of the covered work.
>
> This permission applies only to the libraries named above. It does not
> permit linking with any other non-free library, and it does not relax any
> other term of the license for the covered work itself. You may remove this
> additional permission from your copy, or from any part of it, as section 7
> allows; a version without it is plain AGPL-3.0.

This follows the shape of the FSF's template for GPL linking exceptions ("If you
modify this Program, or any covered work, by linking or combining it with ...
the licensors of this Program grant you additional permission to convey the
resulting work"), with the Corresponding Source sentence turned around because
the Google libraries' source isn't available.

## Where it would go

- **README.md**, "License" section: one sentence after "Licensed under GNU
  Affero General Public License v3.0", e.g. "with an additional permission to
  link the Google Play Billing Library in the Google Play build (see
  `LICENSE.ADDITIONAL`)."
- **A new file** (suggested `LICENSE.ADDITIONAL`, or a "NOTICE" file) with the
  text above and the copyright line ("Copyright (C) 2025-2026 Tiberiu
  Chibici"). Keeping `LICENSE` verbatim matters: `android/tools/gather_licenses.py`
  copies it byte for byte into the app as `AGPL-3.0.txt`, and GitHub's licence
  detection reads it.
- **The app's licence screen**: the `chord-notepad` entry in
  `android/app/src/main/assets/licenses/components.json` could list the new
  file as a second text, so both flavours show it (it is harmless in foss).
  That entry's `texts` would become `["AGPL-3.0", "AGPL-additional-permission"]`,
  with the file added to gather_licenses.py's table.

## Open points for Tibi

1. Name of the file and whether the permission also appears in the source
   headers (the repo's .py/.kt files don't carry licence headers today, so a
   repo-level notice is consistent).
2. Whether to name the dependency families (as drafted) or only "the Google
   Play Billing Library and its dependencies as published by Google". Naming
   them is narrower; a future billing release that adds a new Google artifact
   would then need the list extended (CI's check_manifest.py already fails on
   new manifest entries, which is a natural moment to revisit this).
3. Copyright years and holder line as they should read.
