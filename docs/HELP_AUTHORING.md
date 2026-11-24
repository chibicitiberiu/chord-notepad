# Writing the User Guide

The guide in `help/*.rst` is one source with three editions:

| Edition | Build | Output | Shown in |
|---|---|---|---|
| Desktop | `make docs-html` (`-t desktop`), `make docs-pdf` | `help/build/html`, `help/build/rinoh` | the desktop app's Help, the PDF |
| Android | `make docs-html-android` (`-t android`) | `help/build/html-android` | the app's User Guide screen (Gradle `buildAndroidHelp` bundles it into the APK) |
| iOS | `make docs-html-ios` (`-t ios`) | `help/build/html-ios` | the iOS app's User Guide screen (`ios/tools/build_help.sh` in CI, copied in by the "User guide" build phase) |

**The iOS edition is the Android one** wherever the text doesn't say
otherwise. A `-t ios` build also has the `android` tag, so every
`.. only:: android` block shows in it, and `:plat:`, the `|terms|`,
`:platforms: android` and a figure's `:android-alt:`/`:android-caption:`
give iOS the Android text. Only where that text is wrong on an iPhone or
iPad (Back, the drawer, Android's file picker, Google Play, ...) does the
source add iOS text, with the tools below. Images never fall back: an iOS
figure needs its own image in `help/images/ios/`.

A plain `sphinx-build` with no tag builds the desktop edition. The extension
behind everything below is `help/_ext/editions.py`; `tests/test_help_editions.py`
covers it.

**The rule:** every edition must build with `-W` (warnings are errors). Run
`make docs-check` before committing; CI runs the same HTML checks in the
`test` job, the APK build fails on any Android-edition warning, and the iOS
app's CI build on any iOS-edition warning.

## Platform-specific text

Pick the smallest tool that fits.

**A word or two differs: `:plat:`.** The text before `|` is the desktop
edition's, the text after it Android's (and iOS's). A third side, after a
second `|`, is iOS's own text where Android's is wrong there. Any side may
be empty. Inline markup that doesn't need backquotes works (`**bold**`,
`*italic*`).

```rst
:plat:`Click|Tap` a chord to hear it. Open :plat:`**Tools → Settings**|**☰ → Settings**`.
The tempo is in the :plat:`toolbar|player`. :plat:`|It is saved with the song.`
Close it with :plat:`Esc|Back|←`.
```

You can't put roles or ``code`` inside `:plat:` (no nested backquotes). Use a
term or an `.. only::` block for those. Like any role, it needs a space (or
an opening bracket or quote) before it.

**Common words: `|terms|`.** Substitutions defined per platform in
`help/conf.py` (`help_terms`, as `name: (desktop, android)`, or
`(desktop, android, ios)` where iOS needs its own). Add a term when the same
swap appears on several pages.

| Term | Desktop | Android |
|---|---|---|
| `\|click\|`, `\|Click\|`, `\|clicks\|`, `\|clicked\|`, `\|clicking\|`, `\|Clicking\|` | click... | tap... |
| `\|settings\|` | **☰ → Settings...** | **☰ → Settings** |
| `\|voicings_settings\|` | **☰ → Settings... → Voicings** | **☰ → Settings → Voicings** |

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

Text that is right on Android but wrong on iOS goes in a nested block, with
the iOS text beside it (a nested `.. only::` leaves the Android HTML as it
was):

```rst
.. only:: android

   Tap **Open…** in the ☰ menu.

   .. only:: not ios

      Android's file picker opens: pick the song.

   .. only:: ios

      The Files picker opens: pick the song.
```

`.. only:: ios` alone is iOS text; `.. only:: android and not ios` is
Android's alone at the top level. Don't put a label or a section title in
one edition's block only: it changes the other editions' ids.
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
| `:platforms: desktop` | Only these editions show the figure (`desktop`, `android`, `ios`, separated by a space or comma; `android` includes iOS). The other editions don't need an image. To keep an Android figure out of iOS, put it in `.. only:: not ios`. |
| `:shared:` | One image for every edition, from `help/images/shared/`. For diagrams that don't show the UI. |
| `:desktop-alt:`, `:android-alt:`, `:ios-alt:` | Alt text for one edition; iOS falls back to Android's, then to `:alt:`. |
| `:desktop-caption:`, `:android-caption:`, `:ios-caption:` | Caption for one edition. When given, it replaces the body (caption and legend) for that edition; iOS falls back to Android's. Inline markup works; continue a long caption on indented lines. |

A missing image for the edition being built is an **error**, so
`make docs-check` (and the APK build) catch a figure that has a desktop
screenshot but no Android one. Either add the image or limit the figure with
`:platforms:`.

Where the images live:

```
help/images/desktop/   desktop screenshots (made by packaging/tools/qt_help_screenshots.py)
help/images/android/   Android screenshots (<name>.png, optional <name>.dark.png)
help/images/ios/       iOS screenshots (made by ios/tools/help_images.py from CI's artifacts)
help/images/shared/    diagrams used by every edition
```

The iOS screenshots come from the iOS workflow's artifacts: the preview
catalog (`ios-catalog`, the screens drawn from `ios/Fixtures`) and the
simulator's screenshots of the running app (`ios-screenshots`).
`ios/tools/help_shots.json` names, for each image, the PNG it comes from,
the part to keep in points and its numbered callouts:

```bash
gh run download <run> -n ios-catalog -D /tmp/run/catalog
gh run download <run> -n ios-screenshots -D /tmp/run/screenshots
python3 ios/tools/help_images.py --catalog /tmp/run/catalog --screenshots /tmp/run/screenshots
python3 ios/tools/help_images.py --list
```

A scene the guide needs and the catalog doesn't have is recorded in the
kit's `IntegrationHelpTests.swift` (`make ios-fixtures`) and drawn by a
`help_*` entry of `PreviewCatalog.screens`; a screen the catalog can't draw
(a web view, the keyboard, a UIKit card) is a `-CNScreen` hook that
`ios/tools/ci_screenshots.sh` screenshots.

The desktop screenshots come from the real Qt window, offscreen, so they can
be redone whenever the UI changes (don't edit the PNGs by hand):

```bash
pipenv run python packaging/tools/qt_help_screenshots.py --list
pipenv run python packaging/tools/qt_help_screenshots.py                 # every shot
pipenv run python packaging/tools/qt_help_screenshots.py --only main-window-labeled,transpose
```

It needs no display, and uses a throwaway profile and a silent player. The
shot list is in the script (each shot says which page it is for); it also
makes the Quick Start picture (`resources/quickstart/chord_sheet_qt.png`), the
store listing images (`packaging/store/screenshots/desktop/`) and the README's two (`docs/images/`). Every shot
is taken in the light and the dark theme: `<name>.png` and `<name>.dark.png`
(the store's and the README's dark ones are `<name>-dark.png`). `--theme light` or `--theme
dark` takes one, and `--only` also takes a single image (`--only
transpose.dark`).

On Android, `:width:` is ignored: images show at their natural size, never
wider than the screen and never taller than 70% of it, so a full-screen phone
screenshot shows as a smaller phone inside the page. Crop to the part of the
screen the text talks about when you can.

### Dark-mode screenshots

Both editions have a dark mode. The Android edition follows the app's
light/dark theme; the desktop edition follows the browser's or the system's
(`prefers-color-scheme`). For any image, an optional `<name>.dark.png` next
to it is shown instead when the page is dark:

```
help/images/android/play-tab.png        light theme (required)
help/images/android/play-tab.dark.png   dark theme (optional)
```

Nothing changes in the `.rst`. The HTML becomes a `<picture>` with a
`prefers-color-scheme: dark` source (and the image is no longer a link to its
full-size file). Without a dark variant the light image is shown in both
themes (no error), a little dimmed on a dark page; transparent diagrams get a
light backing in the Android edition so they stay readable. The PDF ignores
dark variants. `packaging/tools/qt_help_screenshots.py` makes the dark
variant of every desktop screenshot.

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
make docs-html-ios        # iOS HTML -> help/build/html-ios
make docs-pdf             # desktop PDF (rinohtype)
make docs-check           # the three HTML editions with -W, and the PDF if rinohtype is installed
```

To see the Android edition as the app shows it, open
`help/build/html-android/index.html` in a browser at phone width (about
412 px) and switch the browser or OS to dark mode to check the dark theme.
In the app, the User Guide's WebView takes light or dark from the app's theme
(`UserGuideScreen.kt`). The iOS edition uses the same stylesheet; its
WKWebView follows the app's light or dark look (`UserGuideView.swift`).

The Android edition's look is `help/_static/android.css` (the app's colour
tokens from `docs/design/android-ui-spec.md`, light and dark). The desktop
edition keeps `help/_static/custom.css` (the coral look; its dark mode uses the
Qt window's dark greys from `Theme.qml`); neither build loads the other's
stylesheet. To check the desktop dark mode, open `help/build/html/index.html`
and switch the browser or the system to dark.
