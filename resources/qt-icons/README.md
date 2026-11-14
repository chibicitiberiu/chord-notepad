# Qt window icons

The SVG icons of the Qt Quick window (`desktop/chordnotepad_desktop`). QML
draws them with `PixelIcon` through the icon provider
(`chordnotepad_desktop/icons.py`), which tints each to one colour. They are
drawn on a 24x24 grid, black on transparent. The Tk window's PNGs are in
`resources/icons/`.

## `mdi/`: Material Design Icons

From the Pictogrammers [`@mdi/svg`](https://github.com/Templarian/MaterialDesign-SVG)
package, version 7.4.47, the set the Android app uses too
(`android/tools/mdi_icons.py`). The icons are under the Apache License 2.0;
the Licences window shows it (`resources/licenses/texts/Apache-2.0.txt`,
`mdi-Pictogrammers-Free-License.txt`).

Most are the upstream path under the upstream name. These differ:

| File | From |
|---|---|
| `braces.svg` | `code-braces`, renamed |
| `pal-label.svg` | `label`, renamed (the palette's Label tile) |
| `pal-tempo.svg` | `metronome`, renamed (the palette's Tempo tile) |
| `pal-tempo-reset.svg` | `metronome`, shrunk, with our reset arrow |
| `transpose.svg` | `swap-vertical` and `music-note` side by side, on a 32x24 grid |
| `volume.svg` | `volume-high`, its parts reordered and retouched |
| `volume-off.svg` | the speaker of `volume-high`, with our cross |

Each changed file says so in a comment.

## `own/`: drawn for Chord Notepad

Ours, in the same style, under the app's licence: the capo, the 3/4 time
signature, the palette tiles (`pal-*`), the panel layouts (`dock-none`,
`dock-right`, `panel-left`), the rounded `stop` and `theme`.

A name must be unique across both folders (`tests/qt/test_qt_icons.py`).
