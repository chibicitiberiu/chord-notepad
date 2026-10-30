# Writing the User Guide

The guide in `help/*.rst` is one source with two editions:

| Edition | Build | Output | Shown in |
|---|---|---|---|
| Desktop | `make docs-html` (`-t desktop`), `make docs-pdf` | `help/build/html`, `help/build/rinoh` | the desktop app's Help, the PDF |
| Android | `make docs-html-android` (`-t android`) | `help/build/html-android` | the app's User Guide screen (Gradle `buildAndroidHelp` bundles it into the APK) |

A plain `sphinx-build` with no tag builds the desktop edition. The extension
behind everything below is `help/_ext/editions.py`; `tests/test_help_editions.py`
covers it.

**The rule:** both editions must build with `-W` (warnings are errors). Run
`make docs-check` before committing; CI runs the same HTML checks in the
`test` job, and the APK build fails on any Android-edition warning.

## Platform-specific text

Pick the smallest tool that fits.

**A word or two differs: `:plat:`.** The text before `|` is the desktop
edition's, the text after it Android's. Either side may be empty. Inline
markup that doesn't need backquotes works (`**bold**`, `*italic*`).

```rst
:plat:`Click|Tap` a chord to hear it. Open :plat:`**Tools → Settings**|**☰ → Settings**`.
The tempo is in the :plat:`toolbar|player`. :plat:`|It is saved with the song.`
```

You can't put roles or ``code`` inside `:plat:` (no nested backquotes). Use a
term or an `.. only::` block for those. Like any role, it needs a space (or
an opening bracket or quote) before it.

**Common words: `|terms|`.** Substitutions defined per platform in
`help/conf.py` (`help_terms`, as `name: (desktop, android)`). Add a term when
the same swap appears on several pages.

| Term | Desktop | Android |
|---|---|---|
| `\|click\|`, `\|Click\|`, `\|clicks\|`, `\|clicking\|`, `\|Clicking\|` | click... | tap... |
| `\|settings\|` | :menuselection:`Tools --> Settings...` | **☰ → Settings** |
| `\|voicings_settings\|` | :menuselection:`Tools --> Settings... --> Voicings` | **☰ → Settings → Voicings** |

```rst
|Click| any chord to play it. Voicings live under |settings|.
```

A substitution must stand alone as a word: `|click|s` doesn't work, which is
why `|clicks|` exists.

**Sentences or paragraphs differ: `.. only::`.**

```rst
.. only:: desktop

   Drag the BPM box, or scroll over it.

.. only:: android

   Tap the song pill at the bottom of the Play tab.
```

Content inside `.. only::` is still parsed in both builds (only the output is
dropped), so a reference that only exists in one edition still has to be
valid in both. `platform-figure` knows about this and doesn't look for an
image inside an `.. only::` block the current build drops.

**Symbols on Android.** The app's WebView draws ⏸ and ⏹ as orange emoji
(no text font on the device has them). In Android text write the pause
button as ❚❚; ▶ and ⏮ are fine.

## Figures

```rst
.. platform-figure:: main-window
   :alt: The main window with a chord sheet open.
   :android-alt: The Edit tab with a chord sheet open.
   :width: 100%

   The main window at a glance.
```

The argument is a name, not a path. The image is
`help/images/<edition>/<name>.png` for the edition being built
(`.svg`, `.jpg`, `.jpeg`, `.webp` are tried too, or give the extension in the
name). All the usual `figure` options work (`:alt:`, `:width:`, `:align:`,
`:name:`, ...), plus:

| Option | Meaning |
|---|---|
| `:platforms: desktop` | Only this edition shows the figure (`desktop`, `android`, or both separated by a space or comma). The other edition doesn't need an image. |
| `:shared:` | One image for both editions, from `help/images/shared/`. For diagrams that don't show the UI. |
| `:desktop-alt:`, `:android-alt:` | Alt text for one edition; falls back to `:alt:`. |
| `:desktop-caption:`, `:android-caption:` | Caption for one edition. When given, it replaces the body (caption and legend) for that edition. Inline markup works; continue a long caption on indented lines. |

A missing image for the edition being built is an **error**, so
`make docs-check` (and the APK build) catch a figure that has a desktop
screenshot but no Android one. Either add the image or limit the figure with
`:platforms:`.

Where the images live:

```
help/images/desktop/   desktop screenshots
help/images/android/   Android screenshots (<name>.png, optional <name>.dark.png)
help/images/shared/    diagrams used by both editions
```

On Android, `:width:` is ignored: images show at their natural size, never
wider than the screen and never taller than 70% of it, so a full-screen phone
screenshot shows as a smaller phone inside the page. Crop to the part of the
screen the text talks about when you can.

### Dark-mode screenshots

The Android edition follows the app's light/dark theme. For any Android or
shared image, an optional `<name>.dark.png` next to it is shown instead when
the page is dark:

```
help/images/android/play-tab.png        light theme (required)
help/images/android/play-tab.dark.png   dark theme (optional)
```

Nothing changes in the `.rst`. The HTML becomes a `<picture>` with a
`prefers-color-scheme: dark` source. Without a dark variant the light image is
shown in both themes (no error). Transparent diagrams get a light backing in
dark mode so they stay readable. The desktop edition and the PDF ignore dark
variants.

## Pages for one edition

Put a `:platforms:` field before the page title:

```rst
:platforms: desktop

==================
Keyboard Shortcuts
==================
```

The other edition leaves the page out entirely, and its toctree entry drops
out quietly, so `index.rst` keeps listing every page. Links to the page from
shared text (`:doc:\`shortcuts\``) would fail in the other edition: put them
in an `.. only::` block for that edition.

## Building and checking

```bash
make docs-html            # desktop HTML -> help/build/html
make docs-html-android    # Android HTML -> help/build/html-android
make docs-pdf             # desktop PDF (rinohtype)
make docs-check           # both HTML editions with -W, and the PDF if rinohtype is installed
```

To see the Android edition as the app shows it, open
`help/build/html-android/index.html` in a browser at phone width (about
412 px) and switch the browser or OS to dark mode to check the dark theme.
In the app, the User Guide's WebView takes light or dark from the app's theme
(`UserGuideScreen.kt`).

The Android edition's look is `help/_static/android.css` (the app's colour
tokens from `docs/design/android-ui-spec.md`, light and dark). The desktop
edition keeps `help/_static/custom.css`; neither build loads the other's
stylesheet.
