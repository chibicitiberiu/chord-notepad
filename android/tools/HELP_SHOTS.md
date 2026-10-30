# User guide screenshots (Android)

The Android edition of the user guide uses the images in
`help/images/android/`: `<name>.png` (light theme) and, for a few hero shots,
`<name>.dark.png` (dark theme). They are produced by
`android/tools/help_screenshots.py` from the shot list in
`android/tools/help_shots.json`, on the emulator, so they can be redone
whenever the UI changes. Don't edit the PNGs by hand.

## Running it

```bash
source android/local.env
(cd android && nice -n 10 ./gradlew :app:assembleDebug)   # the debug APK has the scene hooks
python3 android/tools/help_screenshots.py --list           # the shots
python3 android/tools/help_screenshots.py                  # all of them (about 15 minutes)
python3 android/tools/help_screenshots.py --only drawer,player-labeled
python3 android/tools/help_screenshots.py --only drawer --keep-emulator --debug
python3 android/tools/help_screenshots.py --markdown       # the table below
```

- It takes the emulator lock (`$ANDROID_ROOT/emulator.lock`, an exclusive
  `flock`) for as long as it runs, so two agents never drive the emulator at
  once. Use the same lock in any other script that drives the emulator.
- It boots `cn_phone` / `cn_tablet` headless when needed (`nice`, 2 GB,
  2 cores, `-gpu swangle_indirect`, no audio), installs the debug APK when the
  device has a different build, and stops the emulators it started (unless
  `--keep-emulator`). It only ever talks to `emulator-*` serials, never to a
  phone plugged in over USB.
- Device setup: System UI demo mode (9:41, full battery and Wi-Fi, no
  notifications), font scale 1.0, default density, animations off, spell
  checker off, light or dark through `cmd uimode night`, rotation locked.
- `--debug` keeps the raw captures and the `uiautomator` node dumps in
  `$ANDROID_ROOT/helpshot-debug/` (handy for placing callouts).
- Output: PNG, quantized to 256 colours (libimagequant) and optimized; phone
  shots are scaled to 720 px wide (2/3 of the device), landscape and tablet
  shots to half size. A run that produces identical bytes leaves the file
  untouched.

## How a shot is set up

Each shot starts from a clean app: force-stop, a fresh `settings.json`
(the manifest's `config` merged with the shot's own `config`), no recent
list and no UI preferences. Then the debug-only `HelpShotActivity`
(`android/app/src/debug/.../helpshot/`, not in release builds) shows the
normal main screen with the Compose test tags exposed as resource ids and
applies the shot's `scene`, a list of actions run inside the app:

| Action | Does |
|---|---|
| `{"do": "song", "file": "...", "name": "Song.txt"}` | the text as the open document (`file` relative to the repo, or `text`); with a `name` it looks saved, without one it's Untitled |
| `{"do": "mode", "mode": "edit" \| "play"}` | the Edit or Play tab |
| `{"do": "sheet", "visible": true, "view": "staff"}` | the chord sheet |
| `{"do": "playhead", "chord": 5}` | the playhead on the 6th valid chord |
| `{"do": "freeze", "chord": 5, "state": "playing"}` | plays from that chord, pauses as soon as it sounds and shows the playing state again, silent and still (`"paused"` leaves it paused) |
| `{"do": "metronome", "on": true}` | the metronome |
| `{"do": "recent", "names": ["A.txt"]}` | the drawer's recent list (display only) |
| `{"do": "select", "text": "me\n", "cursor": true}` | selects that text in the editor, or puts the cursor after it |
| `{"do": "wait", "ms": 4500}` | waits (Edit scenes wait for the "Ready" snackbar to go) |

A `scene` can name one of the manifest's shared `scenes`; `scene_extra` adds
actions after it. Then the `steps` run from outside, through adb:

| Step | Does |
|---|---|
| `{"tap": {"tag": "player_speed"}}` | taps a node; selectors: `tag` (Compose test tag, see `ui/UiTags.kt`), `desc`, `desc_prefix`, `text`, `text_prefix`, `contains`, `index`; `"at": [fx, fy]` taps at a fraction of the node's bounds |
| `{"wait_for": {...}}` | waits for a node |
| `{"type": "C  Am  F  G"}` | types with the soft keyboard |
| `{"key": "BACK"}` | a key event |
| `{"swipe": {...}, "by": [0, -600]}` | drags from a node's centre |
| `{"actions": [...]}` | more in-app actions, through a broadcast |
| `{"sleep": 2}` | waits (every step is followed by 0.8 s unless it sets `sleep`) |

Then the screenshot:

- `crop`: `nodes` (selectors whose bounds are united; `{"window": true}` is
  the top window, i.e. a dialog or sheet), `pad_dp` or `pads_dp`
  `[left, top, right, bottom]`, `full_width`, `height_dp`, `top_dp`,
  `rect_dp`. Without `crop` the whole screen is kept.
- `callouts`: numbered circles in the app's primary colour, each
  `{"n": 1, "target": {selector, "at": [fx, fy]}, "offset": [dx, dy]}`; the
  circle sits `offset` output pixels from the anchor with a leader line to it.
  The legend stays in the RST: the numbers are listed per image below.
- `dark: true` also makes `<name>.dark.png`; `device` (`phone`, `tablet`),
  `orientation` (`portrait`, `landscape`), `scale`, `settle` (seconds before
  the capture).
- `page` and `what` are for this file (and `--markdown`).

The songs live in `android/tools/help_shot_songs/` (Amazing Grace is in the
public domain; the colour demo is our own text).

### Known limits

- The `recent` list and the document name are for display: the "document"
  isn't a real file, so Save, Rename or opening a recent entry in a scene
  doesn't work.
- `freeze` sets the chord sheet's playing column from the playback state:
  playback started from a playhead in the middle of a song reports the
  strip's chord one ahead (a bug to look at; playback from the start is
  right).

- `about.png` shows the debug build (build type, build number, commit), so
  it changes with every commit; retake it when the version changes.
- Text fields in the Insert dialogs are captured without the keyboard
  (the crop keeps only the dialog).

## The images

Callout numbers are listed in the "Shows" column; the RST writes the
legend. Pages are named `file: section`.

<!-- Generated with: python3 android/tools/help_screenshots.py --markdown -->
| Image | Shows | For (page: section) |
|---|---|---|
| `editor-main-window.png`<br>`editor-main-window.dark.png` | Play tab of a phone in portrait while a song plays (frozen on Em, bar 6): text with the playhead and yellow highlight, chord sheet (piano roll), player. No callouts (the Android counterpart of the desktop's hero shot). (phone) | introduction: What is Chord Notepad? |
| `main-play-labeled.png`<br>`main-play-labeled.dark.png` | Play tab of a phone in portrait while a song plays (frozen on Em, bar 6): app bar, text with the playhead and yellow highlight, chord sheet (piano roll), player. Callouts: 1 drawer, 2 title, 3 Edit/Play tabs, 4 Save, 6 text, 7 player, 8 chord sheet (5 is the ribbon, only in Edit). (phone) | getting_started: The Main Window; interface: Edit and Play |
| `main-edit-labeled.png`<br>`main-edit-labeled.dark.png` | Edit tab of a phone in portrait: app bar, Edit ribbon, editable text. Callouts: 1 drawer, 2 title, 3 Edit/Play tabs, 4 Save, 5 Edit ribbon, 6 text. (phone) | getting_started: The Main Window; interface: The Edit Ribbon |
| `player-labeled.png`<br>`player-labeled.dark.png` | The player alone while playing, metronome on and speed 125% (badge 1.25x). Callouts: 1 song pill, 2 Voicing (greyed while playing), 3 Instrument, 4 back to start, 5 play/pause, 6 metronome, 7 speed, 8 chord sheet button, 9 status line. (phone) | interface: The Player; getting_started: Playing Your First Chord / Adjusting the Tempo |
| `edit-ribbon.png` | The Edit ribbon on a phone: Undo, Redo, Insert, Transpose, Identify, AB/Do, Convert, and the › chevron (more to the right). (phone) | interface: The Edit Ribbon |
| `notation-toggle.png` | Close-up of the AB/Do notation switch and the Convert button in the Edit ribbon. (phone) | introduction: Multiple Notation Systems; writing_chords: Switching Notations |
| `editor-colours.png` | Edit tab text showing every colour: purple directives, a red invalid directive ({tempo: fast}), a grey comment, blue underlined chords and a grey underlined non-chord (Gsus5). (phone) | interface: Color Coding |
| `playhead.png` | Play tab text with the playhead (primary-coloured bar and triangle) before the Em chord. (phone) | interface: The Playhead; playback: Playing from the Cursor |
| `song-defaults.png` | Song defaults sheet (tap the song pill): Tempo set by {bpm: 90} in the song (read-only, with Edit), Time signature and Key as editable defaults, Write into song, Done. (phone) | interface: The Player; getting_started: Adjusting the Tempo; playback: The Status Bar |
| `voicing-sheet.png` | Voicing sheet: Piano, Fretted (four guitars, Ukulele), Ensembles (four presets) and Your voicings (My 7-String), with Edit voicings… and Done. (phone) | playback: Voicing Options; fretted, piano, ensembles: How to Change Voicing; settings: Voicings |
| `instrument-families.png` | Instrument sheet, first level: the 16 General MIDI families, the current one marked with its instrument on the right. (phone) | getting_started: Changing the Sound; playback: Changing Instruments |
| `instrument-programs.png` | Instrument sheet, second level: the Guitar family's eight instruments with program numbers, Steel Guitar selected, ← back. (phone) | getting_started: Changing the Sound; playback: How to Change Instruments |
| `speed-sheet.png` | Speed sheet at 125%: the value, the 25–400% slider, Reset, Manual… and Done. (phone) | getting_started: Adjusting the Tempo; interface: The Player |
| `speed-manual.png` | The Manual… speed dialog: a number field (25 to 400) with Cancel / OK. (phone) | getting_started: Adjusting the Tempo |
| `insert-sheet.png` | ＋ Insert sheet: Tempo, Time signature, Key, Capo, Label (section), Loop, each with its directive. (phone) | interface: Insert Directive Dialogs |
| `insert-tempo.png` | Insert BPM/Tempo Change dialog: the accepted formats and the BPM field. (phone) | interface: Insert Directive Dialogs |
| `insert-time.png` | Insert Time Signature Change dialog: Beats / Unit pickers. (phone) | interface: Insert Directive Dialogs |
| `insert-key.png` | Insert Key Change dialog: the key list. (phone) | interface: Insert Directive Dialogs |
| `insert-capo.png` | Insert Capo dialog: the Fret field (0–12) and Suggest. (phone) | interface: Insert Directive Dialogs; chord_sheet: Suggesting a Capo; directives: Capo |
| `insert-label.png` | Insert Label dialog: the label name field. (phone) | interface: Insert Directive Dialogs |
| `insert-loop.png` | Insert Loop dialog: label and count fields. (phone) | interface: Insert Directive Dialogs |
| `capo-suggest.png` | Suggest Capo dialog (＋ Insert → Capo → Suggest): pick the fretboard voicing to optimize for. (phone) | chord_sheet: Suggesting a Capo; directives: Finding the Best Capo |
| `transpose.png` | Transpose dialog (whole song): semitones with − / +, Cancel / OK. (phone) | transpose: Transposing a Song |
| `identify.png` | Chord Identifier (Edit ribbon → Identify): C, E, G and B selected on the keyboard, the Notes field, Possible Chords with Cmaj7 picked, Clear and Insert. (phone) | interface: The Chord Identifier |
| `drawer.png` | The ☰ drawer: New song, Open…, Recent (three songs), Save as…, Export MIDI…, Settings, User guide, Quick start, About. (phone) | interface: The Drawer; getting_started: Saving Your Work / Opening Existing Files; midi_export: Exporting a Song |
| `rename.png` | Rename dialog (tap the title): the name field and 'Saved as "Amazing Grace.txt"'. (phone) | interface: The App Bar; interface: The Song Title |
| `chord-sheet-piano-roll.png` | Piano roll view: the voiced notes on a keyboard grid, bass in brown, upper voices in blue, the label lane on top. (phone) | chord_sheet: The Four Views |
| `chord-sheet-staff.png` | Staff view: grand staff in the song's key; Fret cards and Tab are greyed out because the voicing is Piano. (phone) | chord_sheet: The Four Views |
| `chord-sheet-fret-cards.png` | Fret cards view (Guitar Standard voicing): a chord diagram per chord with zoom − / +. (phone) | chord_sheet: The Four Views |
| `chord-sheet-tab.png` | Tab view (Guitar Standard voicing): six-line tablature. (phone) | chord_sheet: The Four Views |
| `landscape-play.png`<br>`landscape-play.dark.png` | Phone in landscape, Play tab: text on the left, the chord sheet and the compact player in the right column, the vertical resize handle between them. (phone, landscape) | chord_sheet: Showing and Resizing the Strip; interface: Edit and Play |
| `landscape-edit.png` | Phone in landscape, Edit tab: the tabs and the Edit ribbon share one line, the title is hidden. (phone, landscape) | interface: The App Bar (phone held sideways) |
| `edit-keyboard.png` | A new song in the Edit tab with the keyboard open, after typing C Am F G (each chord blue). (phone) | getting_started: Your First Chord Sheet |
| `edit-keyboard-collapsed.png` | Phone in landscape typing in Edit: the keyboard leaves little room, so the app bar and ribbon hide and the floating Undo / Redo chip sits above the keyboard. (phone, landscape) | interface: The Edit Ribbon |
| `tablet-play.png` | Tablet in landscape, Play tab while playing: text on the left, chord sheet and player on the right. (tablet, landscape) | chord_sheet: Showing and Resizing the Strip; interface: Edit and Play |
| `settings-pages.png` | ☰ → Settings on a phone: the list of pages (General, Playback, Voicings). (phone) | settings: Settings |
| `settings-general.png` | Settings › General: font family and size, chord notation, default key, show quick start at startup, number of recent files. (phone) | settings: General |
| `settings-playback.png` | Settings › Playback: default BPM and time signature. (phone) | settings: Playback & Audio |
| `settings-voicings.png` | Settings › Voicings on a phone: Add voicing and the custom voicings grouped by model (My 7-String under Fretboard). (phone) | settings: Voicings |
| `settings-voicing-form.png` | The voicing form for My 7-String on a phone: Name, Model, Load config, Remove voicing, Strings (B1 E2 A2 D3 G3 B3 E4), Max fret, Fingers, spans…, Save in the top bar. (phone) | settings: Voicings; settings: Worked Example: A Seven-String Guitar |
| `settings-voicings-tablet.png` | Settings › Voicings on a tablet: the list on the left and My 7-String's form on the right. (tablet, landscape) | settings: Voicings |
| `quick-start.png` | Quick Start, page 1 of 7: Welcome, a highlighted snippet, Show at startup, Previous / Next. (phone) | getting_started: Opening the Application; interface: The Drawer |
| `about.png` | About: version, build, commit, licence, source link and Open source licences. (phone) | interface: The Drawer |
| `licences.png` | Open source licences: the components grouped (this app, Python runtime, audio libraries, …). (phone) | interface: The Drawer |
| `user-guide.png` | ☰ → User guide: this guide, offline, in the app. (phone) | shortcuts: Help; interface: The Drawer |
