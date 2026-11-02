# Release History

Append-only log of published releases. Newer releases at the top.
Entries are added automatically by the release pipeline.

## v0.5.1 — 2026-11-02

- Android: available on Chromebooks and other devices without a touchscreen (Google Play no longer requires one).
- Android: the Quick Start's example songs follow dark mode instead of staying black on white.
- Linux: ARM64 builds (a standalone `ChordNotepad-linux-arm64`, a Flatpak and a snap) next to the x64 ones.
- macOS: a proper app in a disk image (`.dmg`): drag it to Applications and open it like any other Mac app, instead of running a bare program from Terminal.
- macOS: a build for Intel Macs (`ChordNotepad-macos-x64.dmg`), next to the Apple silicon one.
- macOS: FluidSynth is built into the app, so installing it from Homebrew is no longer needed.

## v0.5.0 — 2026-11-01

### Added

- **Chord Notepad for Android.** It runs on Android phones and tablets
  (Android 7.0 or newer, 64-bit) and is the same app as on the desktop:
  chord detection with highlighting, playback with the same sound font,
  transpose, capo suggestions, the chord sheet (piano roll, staff, chord
  boxes and tab), custom voicings, the Chord Identifier, MIDI export and the
  built-in user guide. Songs are opened and saved through Android's file
  picker, and `.txt` files open from a file manager or another app with
  "Open with". It needs no permissions and works offline. The APK
  (`ChordNotepad-android.apk`) and its full source code are attached to this
  release; a Google Play version will follow. Both are free with every
  feature. The Play version asks for support once a day, starting a week
  after install, and offers an optional one-time supporter purchase that
  adds a badge in Settings; the GitHub version has a donation link in About
  instead. The two are signed differently, so one can't update the other.
- **Directives are checked as you type.** A directive that can't work is
  shown in red and skipped during playback: an out-of-range or badly
  formatted value, a missing parameter, an unknown key, or a loop placed
  above its label. While the cursor is in a directive, the status bar (on
  Android, a strip above the keyboard) shows its correct syntax; hover over
  a red one (on Android, long-press it) to see what's wrong. A `{capo}`,
  `{bpm}`, `{time}` or `{key}` that another of the same kind overrides
  before any chord plays is shown faded, with a "has no effect" hint.
- **Chord Identifier.** The keys a chord actually sounds light up in amber
  for a few seconds when you play it, and a note off either end of the piano
  is named beside it. A new **Play** button plays the selected keys as they
  are; long-press a chord or Play (on the desktop, Shift+click, or
  right-click Play) to hear the notes rolled, one at a time from the lowest.
  It also offers added-tone readings, trying each note as the root: E G# B C
  gives `Eaddb6` (E major with an added flat 6th) before `Caugmaj7/E`, and
  C E G F# gives `Cadd#11`.
- **More chords.** Sharp and flat added notes, written after `add`
  (`Eaddb6`, `Eaddb13`, `Cadd#11`, `Cmaddb9`, or in brackets like
  `E(addb6)`), in American and European notation and with roman numerals.
  Also `C6/9` (and with a bass, `C6/9/E`), `Cmmaj9`, `Cdim(maj7)` and
  `Csus2sus4` (or `Csus24`). Roman numerals accept `iim7` and Berklee-style
  `IIm7` as minor chords.
- **Open-source licences and source code.** On the desktop,
  **Help → Open Source Licences** (also a button in About) lists every
  component the app is built from, with its version, licence and full
  licence text, including the additional terms of Chord Notepad's own
  licence, the logo's terms, the user guide's CC BY-SA 4.0 licence and the
  guide's fonts and scripts. Each release now also carries the source code
  of Chord Notepad (`ChordNotepad-<version>-source.tar.gz`) and of the
  bundled LGPL, GPL and MPL libraries
  (`ChordNotepad-<version>-third-party-sources.tar`); for the Linux binary
  and the snap, whose libraries come from Ubuntu, that's the Ubuntu source
  packages of the GPL and LGPL ones, and a list of the others. To use your
  own FluidSynth build, set `CHORD_NOTEPAD_LIBFLUIDSYNTH` to its path (not
  in the snap).
- A line that starts with `.` is always plain text, for lyric lines such as
  "la la la" that would otherwise be read as chords.
- Desktop: **Tools → Insert → Capo**.
- An empty song shows "Type or paste a song here" in grey until you type or
  paste; it isn't part of the text.

### Changed

- **Transpose spells chords for the key they land in.** A song moved into B
  now gets `F#`, `C#` and `G#m` instead of `Gb`, `Db` and `Abm`, and one
  moved into Db gets `Gb` and `Ab7`. The key comes from the song's `{key}`,
  or from its chords when there is none. A diminished chord leading up a
  semitone gets a sharp (`D#dim7 Em7`). Transposed keys take the spelling
  with fewer sharps or flats, so C up a semitone is `Db` and Am down one is
  `G#m`, in the `{key}` and the toolbar key alike.
- **Notation is per song.** The AB / Do toggle switches only the song you
  have open; it no longer changes your default. A new song starts in the
  notation set in Settings. Opening a song, or pasting one into an empty
  document, picks the notation its chords are written in, so a song in
  `Sol Re Mim Do` opens in European even when American is the default (on
  Android, also a song restored after the system closed the app in the
  background). Changing the default in Settings also switches a song you
  haven't switched by hand and whose chords didn't decide it.
- **Songs no longer change your defaults.** Opening a song leaves your
  Settings alone. Values the song sets itself are shown as set by the song;
  a change you make that the song doesn't set lasts until you close the
  song. Only Settings changes the defaults.
- The Chord Identifier names chords and notes in the notation of the song
  you have open: in a European song the keys, the notes and the results
  read `Do Mi Sol`, `Lam7`, `Domaj7/Mi`, and an inserted chord goes in that
  way. Typed notes can be in either notation (`Do Mi Sol` or `C E G`).
- Settings shows the Default key list and the voicing editor's note names
  (strings, voice ranges, hand ranges) in the notation chosen in Settings,
  so `Mi2 La2 Re3` with European, switching as soon as you change it, and
  accepts either spelling when you type a note.
- A lowercase root is always minor: `cmaj7`, `cM7` and `cΔ` are now C
  minor-major 7 (they played C major 7), as `c7` is `Cm7`. Roman numerals
  follow the same rule: `iimaj7` in C is D F A C#.
- Converting between American and European notation keeps the song as you
  wrote it: lowercase minors stay lowercase and minor (`c c# f#` becomes
  `do do# fa#` and back), `DoM7` becomes `CM7` and `♯` stays `♯`, so
  converting there and back gives the same text. `{key}` directives are
  converted too (`{key: G}` becomes `{key: Sol}`), and a lyric line that
  would read as chords in the other notation gets a `.` in front, so
  `la la la` stays a lyric.
- Tempo can be 20 to 400 BPM everywhere, including a typed `{bpm}`. A
  relative change such as `{bpm: +50}` that would leave that range is
  clamped, with a warning in the status bar.
- Suggest Capo replaces a `{capo}` that comes before the first chord instead
  of adding a second one, and on a selection it changes only that part.
- The Windows, macOS and Linux downloads are smaller: they no longer bundle
  numpy, matplotlib, chardet and other packages the app never used, and on
  Windows two unused FluidSynth libraries (libinstpatch and libgobject). The
  Flatpak and snap no longer include chardet either.
- The help and README say where to get Chord Notepad: the GitHub releases,
  the Snap Store, and the Microsoft Store (a paid supporter edition of the
  same app). The help's "Limitations" section no longer claims there is no
  staff or tab view.
- The About dialog and the Windows executable's file properties now state
  the correct licence (GNU AGPL-3.0) and copyright holder. They wrongly said
  MIT.
- Dropped "ChordPro" from the Linux desktop entry and AppStream search
  keywords.

### Fixed

- **Chords play the right notes.** Every chord quality is now tested
  against music theory in every key. Fixed along the way:
  - `C13b9`, `C13#9` and `C13b5` played the natural 11th, which clashes with
    the 3rd (a 13th chord leaves it out, as `C13` always did);
  - `C11b9` played a natural 9th instead of its flat 9th;
  - piano playback dropped a chord's root over a slash bass that isn't the
    root, so `Ab5/C` could come out as just C and Eb;
  - ensembles left out the root when a chord had more notes than voices, so
    a 3-voice G7 was rootless;
  - `bVI` in C played G# major instead of Ab, and roman numerals with `ø`
    (`viiø`, `iiø7`) didn't play;
  - the staff wrote some notes with the wrong letter: the flat 9th of
    `C7b9b13` is D♭, not C♯, and the third of `C#13` is E♯, not F.
- **Chords that weren't read.** Lowercase minors with a flat root (`bb`,
  `eb`, `ab`, and `sib`, `mib` in European) weren't chords, so transposing
  `A b c` down a tone gave an unusable `G a bb`. Chords with `♯` or `♭`
  after a lowercase root or in a slash bass (`c♯`, `C/G♭`) didn't play or
  transpose right. European notation now also takes `-` for minor, so
  converting `C-` no longer gives an unread `Do-`. Symbols such as `C77`,
  `C79` and `Cadd4` are no longer accepted as chords.
- **Playback.**
  - It keeps time more accurately: notes, the metronome and speed changes
    stay on the beat even while Chord Notepad is busy (for example redrawing
    the chord sheet), and long songs no longer slowly fall behind.
  - Opening another song or starting a new one while a song plays or is
    paused now stops it. Before, Play went on with the old song and lit up
    its chords in the new text.
  - Pressing Pause right after Play, while the song is still being prepared,
    now pauses it. Before, the song started playing anyway while the Play
    button showed it as paused.
  - Clicking a chord to hear it while the song is playing no longer
    interferes with playback, and clicked chords keep their smooth voice
    leading from one click to the next.
  - The **Audio driver** setting is now used: Chord Notepad tries that driver
    first. If it can't start, the next one is tried, and you're told when
    there's no working audio output at all, instead of silence.
- **Song text.**
  - Unusual text can no longer freeze Chord Notepad. A chord with a long run
    of digits, many unclosed `{`, or a very large file with many directives
    and comments used to take seconds to minutes to read; it's now instant.
    A directive has to fit on one line.
  - `{bpm: 0}`, a negative tempo or `{time: 0/4}` no longer crash or hang
    playback, and two loops that point at each other no longer render
    forever.
  - `{bpm: reset}` returns to the song's first tempo in a typed song too,
    not only in one opened from a file.
  - `{loop: my verse 2}` finds `{label: my verse}`: labels can contain
    spaces.
  - MIDI export includes songs written with European keys (Do, Lam).
- The Chord Identifier names chords with flats correctly ("Bb D F" is Bb,
  not D) and no longer offers a name that means other notes: E Ab B C was
  `Abaugmaj7` (now `Caugmaj7`), D F# A C E G# was `D13` (now `D9#11`).
- Custom voicings:
  - a mistyped string in a tuning (for example `E2 A2 X9 G3`) reports the
    actual bad note (`X9`) instead of a confusing message about the letter
    `E` or "20 strings";
  - if the selected custom voicing can no longer be built (for example after
    editing settings.json by hand), Chord Notepad starts with piano voicing
    instead of failing to start;
  - the help texts of some voicing fields now match what the voicing engine
    does.
- The speed control shows the speed the song actually plays at after
  snapping (112.5%, not the 110% you dragged to).
- The Insert Capo dialog no longer claims a capo never changes the sound:
  with a fretted voicing it does.
- Desktop on Linux: the Edit menu shows the Redo shortcut that actually
  works (Ctrl+Shift+Z).

## v0.4.1 — 2026-10-28

### Added

- **Linux packages.** Chord Notepad is now built as a Flatpak (a
  `.flatpak` file attached to each release) and as a snap for the Snap Store.
  Both run sandboxed, with settings and logs kept in the sandbox's own folder.
- **Native file dialogs on Linux.** Open, Save As, Export MIDI and the
  soundfont picker use your desktop's own file dialog (GNOME, KDE and others)
  when it is available, instead of Tk's dated one.

### Changed

- **Errors are always shown.** When something goes wrong, the app now says so
  in a dialog with the reason (and where the log file is), instead of failing
  silently. This covers opening, saving and exporting files, playback and
  audio problems, the help window, and settings. If audio can't start, Play
  explains why instead of playing silence.
- On Linux, settings and logs follow the XDG base directories
  (`$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`) when they are set. The defaults
  (`~/.config` and `~/.local/share`) are unchanged.

### Fixed

- Choosing "Yes" to save unsaved changes no longer discards your edits when
  the save fails; the New/Open/Close you started is stopped instead.
- Saving to an existing file that can't be written no longer silently opens
  Save As; it tells you why the save failed.
- The Transpose dialog no longer closes silently on input that isn't a number.
- Linux desktops show Chord Notepad's own icon and name for its window.
- The app icon on macOS and Linux showed a black notepad instead of the pink
  one; the build now renders it correctly.
- The status bar no longer disappears when the window is shorter than its
  content.
- Linux menus have a soft one-pixel outline, and the highlighted item is no
  longer drawn with a raised bevel on older Tk.
- On Linux with older Tk (8.6), the app follows the desktop's display scaling
  and its checkboxes are no longer tiny.


## v0.4.0 — 2026-10-27

### Changed

- **Refreshed look.** Windows now uses its modern native theme (the app was
  using the classic Windows 95-style one); Linux gets a lighter, flat style.
  The toolbar is tidier, with hover feedback on its buttons and the BPM and
  speed values shown as chips; scrollbars are slim, menus have more breathing
  room, and the status bar is flat.
- **Chord sheet tabs.** The chord sheet's views (Piano roll, Staff, Fret cards,
  Tab) are now tabs. Hovering a greyed-out tab explains how to enable it.
- **New Quick Start tour.** Examples are shown exactly as they appear in the
  editor, with chords highlighted: chords over lyrics, how chord lines are
  detected, Do-Re-Mi and Roman numerals, timing, song sections, and a picture
  of the chord sheet.

### Fixed

- The editor's default font is monospace again on a fresh install. The default
  (Tk's fixed-width font) was being read as an unknown font name, so Tk fell
  back to a proportional font and chords drifted out of line above the lyrics.
- The chord sheet remembers the view you picked. Starting with an empty
  document used to replace a saved Fret cards or Tab choice with Piano roll;
  now it shows Piano roll only until chords load, then switches back.
- The instrument menu's marker for the current instrument family now lines up
  with the other family names.

## v0.3.2 — 2026-07-17

### Added

- **Windows:** Release builds are now code-signed with Azure Trusted Signing.
  This clears the SmartScreen "unknown publisher" warning and lets the app
  launch on machines that enforce Windows Application Control (WDAC / Smart App
  Control), which previously blocked the unsigned executable.

## v0.3.1 — 2026-07-09

### Fixed

- **Windows:** Fixed a startup failure where bundled runtime libraries such as
  `ucrtbase.dll` were rejected with a "Bad Image" error (status `0xc0e90002`).
  UPX executable compression was rewriting these DLLs and stripping their
  signatures; it is now disabled so the original signed libraries ship intact.

## v0.3.0 — 2026-07-07

### Added

- **Chord sheet** (View → Chord Sheet): a collapsible strip docked under the
  editor that lays out the song's voiced chords left to right, in playback
  order -- loops are unrolled, so a repeated section appears once per pass,
  and voice leading means the same chord symbol can be voiced differently
  from one pass to the next, exactly as it sounds. Four views, switched with
  toggle buttons: **Piano roll** (DAW-style, duration-proportional note bars,
  hands/voices color-coded) and **Staff** (one continuous engraved grand
  staff with key signatures, signature-relative accidentals, and per-voice
  colors) work for any voicing; **Fret cards** and **Tab** need fingering data
  and are only available for a fretboard-model voicing. A marker lane above
  the strip shows section labels, loop passes (``chorus (2/3)``), and
  tempo/meter changes. Roman-numeral chords are labeled with their resolution
  in the current key, e.g. ``V7 (G7)``. The strip follows playback with a
  highlight and auto-scroll, and clicking a chord plays that exact voicing.
  The piano roll's keyboard and the staff's clefs and key signature stay
  pinned at the left edge while the strip scrolls, and the Staff, Fret
  cards, and Tab views have per-view zoom buttons. The active view, zoom,
  and the panel's height are remembered between sessions. See the new
  Chord Sheet help page.

- **Transpose** (Tools → Transpose...): shift every chord in the selection
  (or the whole song, when nothing is selected) up or down by a number of
  semitones. Slash basses and ``{key}`` directives shift too, and a
  whole-song transpose also moves the toolbar key, so roman-numeral chords
  keep sounding the same. European chord names stay European. Chords keep
  their position above the right lyric syllable: the chord line absorbs
  small changes, and when a chord genuinely outgrows its slot the lyric
  line stretches with it (a space at a word gap, or a hyphen mid-word).
  One undo step reverses the whole operation.

- **Capo**: a new ``{capo: N}`` directive draws the Fret cards and Tab views
  relative to a capo -- the top of a fret diagram becomes the capo and the
  shapes read as the easy open chords you'd actually play, with a small
  ``Capo N`` marker. It changes only the shapes shown, not the pitch, and can
  change mid-song. **Tools → Suggest Capo...** finds a good capo for a voicing
  you pick (defaulting to the active one, or standard guitar) over the
  selection or whole song, and inserts the directive as one undo step. Applies
  to guitar and other fretboard voicings; ignored by piano and ensembles.


- **Configurable piano voicing** (Tools → Settings... → Voicings): the
  piano model is now fully editable, the same as the fretboard and ensemble
  models. Hand ranges (left hand, right hand, preferred bass), scoring
  anchors (right-hand low anchor and center, low-interval floor, hand span,
  note-count limits, hand gap floor), the add-bass toggle, and every signed
  weight -- including the per-role omission group -- can all be tuned per
  voicing or loaded from **Grand Piano** as a starting point. See the new
  Piano Voicing help page for the full parameter reference.

- **Settings window** (Tools → Settings...): a proper settings UI with
  three pages -- General (font, notation, default key, quick start at
  startup, recent-files count, log level), Playback & Audio (default BPM
  and time signature, soundfont path, audio driver), and Voicings -- and
  Save/Cancel. The Voicings page is a fully functional editor for custom
  voicings: load any built-in preset or existing custom voicing as a
  starting point, edit its name, model, and every parameter (strings,
  frets, weights for fretboard; voices, spacing, weights for ensemble),
  and save. Save validates everything and reports exactly which voicing
  and field is wrong. Renaming or deleting the voicing currently selected
  for playback is handled correctly, and new or changed voicings appear in
  Playback → Voicing as soon as you save, no restart needed. Editing the
  config file by hand still works. See the new Settings help page.

- **Ensemble voicings** (Playback → Voicing): four new presets voice every
  chord for a fixed group of singers or players instead of one instrument --
  **Choir (SATB)**, **Male Choir (TTBB)**, **Treble Choir (SSA)**, and
  **String Quartet**. Each voice moves the way a trained ensemble would:
  common tones held, small steps preferred, parallel fifths and octaves
  avoided, and the leading tone resolving to the tonic when a `{key:}` is
  set. Chords with more notes than voices drop the least characteristic
  tone first (the fifth before the third, a `sus4`'s suspended note never
  dropped); chords with fewer notes double tones, preferring the root; slash
  chords put the bass note in the lowest voice. Custom ensembles can be
  defined in the config file under the `voicings` registry
  (`"model": "ensemble"`), the same mechanism used for custom fretted
  instruments. Exporting MIDI with an ensemble voicing active writes
  one named track per voice instead of a single chord track. See the new
  Ensemble Voicings help page for the preset ranges and the full list of
  tunable voicing parameters.

- **Arbitrary fretted instruments** (Playback → Voicing): the guitar voicer
  is now a general "fretboard model" that can voice any fretted instrument
  with 3 to 12 strings, including re-entrant tunings (a string tuned higher
  than the one before it, like a ukulele's high G) -- the bass is always
  whichever string actually sounds lowest, not whichever is listed first. A
  new **Ukulele** preset (G4 C4 E4 A4) joins the four existing guitar
  tunings. Custom fretted instruments -- a baritone ukulele, a banjo, a
  seven-string guitar in a tuning of your own -- can be defined the same way
  custom guitar tunings always could. See the new Guitar and Fretted
  Instruments help page for the built-in voicings, a worked custom example,
  and the full parameter reference.

- **Unified `voicings` config registry**: custom guitar/fretted tunings and
  custom ensembles now live together under a single `voicings` key in the
  config file, each entry tagged `"model": "fretboard"` or
  `"model": "ensemble"`. They appear in Playback → Voicing automatically,
  sorted by model then name.

- **Export MIDI...** (File menu) saves the current song as a standard MIDI
  file. The file matches playback exactly: the selected piano or guitar
  voicing, the real timing, tempo changes from `{bpm}`, time and key
  signature events from `{time}`/`{key}`, and the currently selected
  instrument as the MIDI program. Loops are unrolled into their repeated
  passes, `NC` sections become silence, and the whole song is exported from
  the beginning regardless of cursor position. The playback speed
  multiplier is not applied -- the file always uses the song's real tempo.
  Written as two tracks (conductor + chords) for easy import into DAWs and
  notation software.

### Fixed

- The chord sheet's marker lane now flags key changes (from ``{key}``
  directives, including a loop restoring its section's key), alongside the
  existing section, loop, tempo, and meter markers. Markers that land on the
  same beat now share a single combined flag instead of overlapping, and
  nearby flags shift right so their labels never collide.

- Typing no longer stutters while the chord sheet re-renders: the strip's
  voicing work (and capo scoring) now runs on a background thread, is
  cancelled mid-search the moment you type again, and never runs at all
  while the panel is hidden. Dragging the panel divider repaints once per
  pause instead of once per pixel.

- Chord-sheet rendering is roughly 4x faster on songs with repeated chords
  (the voicing search no longer rescores the same shapes at every
  occurrence), and the capo suggestion -- by far the most expensive part,
  since it scores the whole song at eight capo positions -- is both 4x
  faster and remembered per song, so edits that don't change the chords
  reuse it instantly. Results are identical, just sooner.

- Transposing no longer produces impossible key names: a key that would land
  on D#, G#, A#, Dbm, or Gbm (spellings with no real key signature) now comes
  out as its enharmonic twin (Eb, Ab, Bb, C#m, F#m). The staff view also
  engraves such keys as their twin if one is typed directly, instead of
  drawing no signature at all, and note spellings with double flats (like the
  B-double-flat inside a Gbm chord) are respelled enharmonically instead of
  falling back to plain-text accidental marks.

- The staff view now spells notes to match the key signature: a song in F#
  whose chords are typed with flat names (Ebm, Db, Gb) engraves as D#m, C#,
  and F# with no accidentals, and the same song in Ebm engraves as Ebm, Db,
  and Cb. Chords outside the key keep the spelling you typed. Chord labels
  above the staff always stay as written.

- Pasting text with Windows-style line endings (CRLF) no longer leaves stray
  carriage-return characters in the editor (they showed up as junk glyphs at
  the ends of pasted lines). Pasted and opened text is also cleaned of
  non-breaking and zero-width spaces, which look right but silently break
  chord detection. Files on disk are never rewritten by this; the cleaned
  text only reaches the file when you save.

### Changed

- Guitar fingering selection now weighs a muted string buried inside a
  strummed shape much more heavily ("Muted inner string" weight, `-2.0` to
  `-4.0`). Progressions in flat keys (Ebm, Db, B) now come out as the barre
  and compact shapes a guitarist would actually play instead of contorted
  grips with a dead string in the middle; open-position songs keep their
  cowboy shapes. Saved voicings still on the old default are upgraded
  automatically; a hand-tuned value is left alone.

- Guitar fingering selection now penalizes wide fretting-hand stretches:
  compact shapes are preferred generally, and 4-fret shapes that would force
  a middle finger to make the far reach (rather than a lengthwise
  index-to-pinky stretch) effectively always lose to a playable alternative.
  Both penalties are editable weights in the fretboard voicing settings.


- Voicing weights now use one consistent convention. Every weight is a
  signed number added to a voicing's score: positive seeks the trait,
  negative avoids it, zero is neutral, and higher is always more preferred.
  The old mix of "penalty", "cost", and "bonus" labels with all-positive
  magnitudes is gone; controls now carry neutral trait names (for example
  "Wide stretch" at `-1.2`, "Correct bass note" at `+8.0`) whose sign tells
  you the direction. Existing config files are upgraded automatically the
  first time Chord Notepad starts after the change, with old positive
  penalty magnitudes negated on load, so custom voicings keep behaving the
  same. Config keys are unchanged (`span_penalty` and the rest); only their
  sign and display labels changed.

- The **Options...** menu item is now **Settings...**, reflecting what it
  actually opens.

- Config files using the old `custom_tunings` or `custom_ensembles` keys are
  migrated to the unified `voicings` registry automatically the first time
  Chord Notepad starts after upgrading, including whichever voicing was
  selected at the time. There's nothing to do by hand.

- Guitar voicings are now chosen for the whole song at once instead of chord by
  chord. The picker weighs each fingering's own quality against how smoothly it
  transitions to its neighbours across the entire progression, using lookahead
  to avoid locally-pretty shapes that force awkward jumps later. Repeated
  sections (such as looped verses) are voiced in the context they actually play
  in each time through.

- Piano voicings now follow a two-hand model: a left hand on the bass and a
  right hand on the chord, each limited to a real hand's reach (five notes, a
  ninth span). The voicer chooses among root position and inversions, keeps
  extensions (9ths/11ths/13ths) above the core triad, and optimizes the whole
  song at once. This keeps the right hand in a stable central register instead
  of drifting downward over long progressions and looped sections -- a repeated
  chord is now voiced the same way every time through.

- The Voicings settings page is easier to use correctly: every control has a
  hover tooltip, invalid fields turn red as soon as you type them instead of
  only on Save, and cross-field problems (a relaxed span smaller than the
  normal span, a voice's low note above its high note) show up as a message
  at the top of the editor. Load config now asks for confirmation, since it
  replaces every parameter of the voicing you're editing. The ensemble
  voices editor is a proper table (Name / Low / High columns, Add voice,
  per-row remove), the parameter forms use a tidier multi-column layout, and
  each Weights section explains the signed-weight rule up front.

## v0.2.0 — 2026-07-04

### Chord detection and voicing

- Extended chords are now voiced the way a player would: `C11` and `Cmaj11`
  drop the third that clashes with the eleventh, and `C13`/`Cm13`/`Cmaj13`
  drop the eleventh. Minor elevenths keep their flat third.
- Extension notes (9ths, 11ths, 13ths) now keep their proper octave during
  playback instead of collapsing into the root octave, so the colour of a
  chord is audible.
- Roman numerals: a lowercase numeral with a bare seventh is now minor, not
  dominant. `ii7` is Dm7; write `II7` for a secondary dominant (D7).
- `{loop: @start N}` now works. `@start` is a built-in label for the top of
  the document, so you can repeat a whole song without adding a `{label}`.
- The `Δ` (triangle) symbol now means a major *seventh*: `CΔ` is `Cmaj7`, and a
  number after it carries the extension (`CΔ9` is `Cmaj9`).
- Parenthesised major-seventh qualities resolve correctly: `Cm(maj7)` is a
  minor-major seventh, `C(maj7)` is `Cmaj7`.
- European chords that start with a solfège syllable (`Faug`, `Fadd9`, …) are
  no longer mangled during conversion.

### Fixes

- Released binaries no longer print `No module named 'PIL._tkinter_finder'`
  warnings while loading the toolbar icons.

### Documentation

- Rewrote the user guide with labelled screenshots and deeper explanations of
  how voice leading, voicings, loops, tempo, and chord notation actually work.
- Corrected the chord, directive, and reference tables against the code, and
  documented the notation shorthands (`# ♯`, `b ♭`, `°`, `ø`, `Δ`, `m(maj7)`).

## v0.1-build76 — 2026-05-30

- Initial release.
