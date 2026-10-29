# Android UI: Edit / Play redesign

Status: agreed with Tibi on 2026-10-29; built on Android the same day (see
"Implementation notes" at the end). The interactive mockup is
`docs/design/android-modes-mockup.html`. Open it in a browser; it has a device
picker and a portrait/landscape switch.

The first Android build (M4/M5) copied the desktop layout: a toolbar, a ⋮ menu
and an always-editable text field. On a phone, the soft keyboard came up on
every tap, and the menu felt like a PC. This redesign keeps every feature and
remaps the controls to a touch screen. Porting includes making the app fit the
platform, so these are deliberate Android/desktop differences, not new features.

## Modes

The app bar has two tabs, **Edit** and **Play**: Material tabs with an
underline indicator.

| | Edit | Play |
|---|---|---|
| Text | editable; a tap places the cursor and opens the keyboard | frozen: read-only, keyboard hidden |
| Tap a chord | moves the cursor only (silent) | moves the playhead there and plays the chord |
| Tap elsewhere | moves the cursor | moves the playhead to the nearest chord |
| Drag | selects or scrolls as usual | scrolls; a drag that **starts on the playhead marker** scrubs it chord by chord |
| Pinch | text size | text size |
| Toolbar | editing ribbon | none (the player is at the bottom) |
| Status | snackbars only | inside the player |
| Chord sheet | never shown | shown (▭ hides it) |

- Existing songs open in Play; new ones open in Edit.
- Switching to Edit while playing stops playback.

## App bar (48 dp)

The app bar holds, from left to right:
- **☰** opens the drawer.
- **The song title.** It shows a • while there are unsaved changes. Tapping it opens **Rename**:
  - The dialog shows "Saved as name.txt".
  - If the storage provider can't rename, the app offers Save As instead with a short explanation.
  - An untitled song takes the name when it's first saved.
- **The tabs.**
- **Save.**

Phone landscape: the tabs and the Edit ribbon share one line, and the title is hidden.

## Edit ribbon (48 dp, one row)

- Undo
- Redo
- ＋ Insert: opens a sheet with Tempo `{bpm}`, Time signature `{time}`, Key `{key}`, Capo `{capo}`, Label `{label}` and Loop `{loop}`.
- Transpose: a `swap-vertical` + `music-note` composite icon.
- Identify: `piano`.
- AB | Do: notation segmented control.
- Convert: blue **C** at top-left with ↘, orange **↖ Do** at bottom-right. The arrows are the `arrow_right_alt` glyph rotated, the same arrow `swap_horiz` uses. The letters are Roboto Bold.

**Scrolling:** the ribbon scrolls sideways by dragging. A fade and a **›** chevron show there's more to the right, and a fade appears on the left once scrolled.

**Keyboard:** if the keyboard leaves less than about 170 dp for the text, the header collapses and only the text shows. A floating **undo / redo** chip then sits above the keyboard. The header comes back when the keyboard closes.

## Player (Play mode, bottom of the screen, toolbar background)

```
              𝄞 90 · 3/4 · G ⌄                    (song pill: muted purple text, no background)
 ♫ voicing · 🎸 instrument · ⏮ · ( ▶/⏸ ) · ⏱ metronome · ◔ speed · ▭ chord sheet
                Bar 6/24 · Playing Em              (status: position and activity only)
```

- The side icons are monochrome. They get a soft primary tint when active: metronome on, speed ≠ 100%, chord sheet shown.
- **There's no Stop button.**
  - ⏸ keeps the playhead where it is.
  - **⏮** stops playback and returns the playhead to the first chord.
  - At the end of the song, the playhead returns to the start.
- Speed shows a "1.25×" badge when it isn't 100%.
- **The playhead** is a primary-coloured marker before the chord where playback starts. ▶ plays from it and it follows the playback. The same chord gets an edge mark in the chord sheet.

## Sheets (all pickers are bottom sheets)

Every sheet has a drag handle, a title, a scrollable body and actions at the bottom.

- **Song pill → "Song defaults".** It lists Tempo, Time signature and Key.
  - A value the song sets with a directive is read-only and shows "Set by `{bpm: 90}` in the song · Edit". **Edit** switches to Edit mode and puts the cursor on that directive.
  - A value the song doesn't set is an editable default (not saved with the file).
  - **Write into song** inserts the missing directives at the top.
- **Voicing:** grouped as Piano, Fretted, Ensembles and Your voicings, with radio buttons. **Edit voicings…** opens Settings › Voicings.
- **Instrument:** two levels.
  - The first level lists the 16 General MIDI families, with a marker on the current family and its current instrument shown on the right.
  - Tapping a family opens its 8 instruments with program numbers. ← goes back.
- **Speed:** the value in large type, a slider (25–400%), then **Reset**, **Manual…** and **Done**. Manual… opens a small dialog with a number field (25–400, validated) and Cancel / OK.

## Drawer (☰)

The ⋮ menu is gone; the drawer holds everything it had.

- **Documents:** New song, Open…, Recent (inline list), Save as…, Export MIDI…
- **App:** Settings, User guide, Quick start, About.

## Chord sheet

- Pinch to zoom.
- The sheet's tabs, the − / + buttons and the disabled-tab reason stay as built.
- Show or hide it with the player's ▭ button.
- **Portrait:** below the text, with a horizontal drag handle for its height.
- **Edit mode:** never shown, on any device. The text gets the whole screen.
- **Landscape** (phones and tablets, Play mode): always side by side. The text is on the left. The right column holds the chord sheet, with the player at its bottom in Play mode. A vertical drag handle sets the column width (30–70%, default 50%). In the narrower column the player's buttons shrink so all seven fit.

## Colour and themes

The UI uses one Material 3-style tonal family: neutral surfaces with a hint of the indigo primary. Each surface has a fixed role, and the app follows the system light/dark setting.

| Token | Role | Light | Dark |
|---|---|---|---|
| surface | text, app bar | #fbfbff | #121318 |
| surface-low | chord sheet, bottom sheets, drawer | #f4f5fa | #191b21 |
| surface2 | Edit ribbon, player | #eceef5 | #202229 |
| surface-high | selected chips, dialogs | #e2e5ef | #2a2c34 |
| line | dividers | #d5d8e2 | #353842 |
| text / muted / icon | | #1a1b20 / #5c5f6b / #454852 | #e3e4eb / #a3a7b3 / #c8cbd5 |
| primary / on-primary / primary-soft | | #3f51b5 / #fff / #dde1ff | #b6c3ff / #1b2a6b / #2e3a72 |
| song pill text | | #6a5a99 | #c4b5f2 |

**Editor colours.** Light mode uses the desktop colours unchanged: chord #1565c0, directive #7b1fa2, comment #9e9e9e, playing #fff176. Dark mode needs readable variants of the same hues: #8ab4f8, #d39be0, #7f848f and a dark-yellow playing highlight #5a4f00. This is the one place the "don't change the editor colours" rule bends, and only for dark mode.

**Chord sheet.** The bars keep their blue and brown, slightly lighter in dark mode (#78a6d8 / #d09a6c). The playing column is translucent yellow in both themes.

## Icons

- **Library:** Pictogrammers Material Design Icons, 7.4.x, Apache-2.0. Add an entry to the licences screen.
  - Names used: `plus`, `undo`, `redo`, `swap-vertical`, `music-note`, `piano`, `metronome`, `music-clef-treble`, `music`, `guitar-acoustic`, `speedometer`, `skip-previous`, `play`, `pause`, `dock-bottom`, `label`, `repeat`, `pencil`, `play-circle`, `content-save`, `menu`, `file-plus`, `folder-open`, `file-music`, `content-save-edit`, `export`, `cog`, `book-open-variant`, `school`, `information`, `magnify-plus`, `magnify-minus`, `arrow-left`, `chevron-right`, `chevron-down`, `radiobox-marked`, `radiobox-blank`.
- **Our own, in MDI's style** (24-unit grid, one flat colour, rounded 2-unit strokes): the **capo** (still needs a better drawing) and the **3/4 time signature**.
- **Colour:** icons are tinted per function in the ribbon and sheets, and monochrome in the player.

## Desktop impact

None needed. The playhead (tap to position, ⏮ to rewind) would be a good desktop addition later.

## Implementation notes

Where the build differs from the text above, and why:

- **Light editor colours.** The light theme keeps the desktop's real colours
  (Tk `blue`, `#8B4789`, `gray`, `yellow` from `src/constants.py`), not the
  hex values listed under "Editor colours", which don't match the desktop.
  "Unchanged" won over the list. The dark variants are as listed.
- **Phone landscape in Play** shows the title: the one-line header exists to
  make room for the Edit ribbon, and Play has no ribbon.
- **Taps while playing** jump playback to the tapped chord (the session's
  rule); the marker can't be dragged while a song plays, since it follows
  playback.
- **Landscape column width** is kept on the device (`shared_prefs/ui.xml`),
  not in the session's settings: the desktop has no such value.
- **Icons.** `swap-vertical` and `music-note` only appear inside the
  Transpose composite drawable, so they have no drawables of their own. The
  Instrument sheet's family markers use MDI `circle` / `circle-outline`.
