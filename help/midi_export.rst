================
Exporting a song
================

Chord Notepad can export a song in three ways:

* **MIDI** (``.mid``): the notes themselves, with the tempo and the key, to
  open in a DAW, a notation program, or any other tool that reads MIDI files.
* **Audio** (``.wav``): a recording of the song as Play sounds it, to listen
  to anywhere, send to the band, or practise along with. See
  `Exporting Audio`_ below.
* **PDF** (``.pdf``): the song's text on paper-sized pages, to print or send
  to someone who doesn't have Chord Notepad. See `Exporting a PDF`_ below.


Exporting MIDI
==============

.. only:: desktop

   1. Go to :menuselection:`File --> Export MIDI...`
   2. The save dialog suggests the song's name with ``.mid``. A song you
      haven't saved yet gets its first line of lyrics
      (``Twinkle, twinkle, little star.mid``), or ``Untitled.mid`` if it has
      none. Choose a folder, change the name if you like, and save.
   3. Chord Notepad renders the song and writes the file. The status bar says
      "Exporting MIDI: …" while it works and "Exported MIDI: …" when it's done.

.. only:: android

   .. only:: not ios

      1. Tap **☰** at the top left and choose **Export MIDI…**.
      2. Android's file picker opens, with the song's name and ``.mid`` filled
         in (for a song you haven't saved yet, its first line of lyrics, or
         ``Untitled.mid`` without lyrics). Pick a folder, on the phone or in any
         storage app such as Google Drive, change the name if you like, and tap
         **Save**.
      3. Chord Notepad renders the song and writes the file. The status says
         "Exporting MIDI: …" while it works and "Exported MIDI: …" when the file
         is written: on the player's status line in the Play tab, or at the
         bottom of the screen in the Edit tab.

   .. only:: ios

      1. Tap **☰** at the top left and choose **Export MIDI…**.
      2. "Preparing export…" shows while Chord Notepad renders the song and makes
         the file. **Cancel** stops it.
      3. iOS's save sheet opens with the song's name and ``.mid`` (for a song you
         haven't saved yet, its first line of lyrics, or ``Untitled.mid`` without
         lyrics). Choose a folder in Files, iCloud Drive or another provider, change
         the name in the **Save as** field if you like, and confirm. The status then
         says "Exported MIDI: …" with the folder: on the player's status line in the
         Play tab, or at the bottom of the screen in the Edit tab. If you cancel the
         sheet, nothing is saved.

.. platform-figure:: drawer
   :platforms: android
   :alt: The open drawer: New song, Open, the recent songs, Save as, Export
         MIDI, Export audio, Export PDF, Settings, Examples, User guide, Quick start and About.
   :ios-alt: The open menu: New song, Open, the recent songs, Save as, Export
             MIDI, Export audio, Export PDF, Settings, Examples, User guide,
             Quick start, About and Diagnostics.
   :ios-caption: **Export MIDI…**, **Export audio…** and **Export PDF…** are in
      the ☰ menu, under Save as….

   **Export MIDI…**, **Export audio…** and **Export PDF…** are in the ☰
   drawer, under Save as….

.. only:: android

   .. only:: not ios

      The exported file is a copy: the song you're editing stays open as it was,
      and the ``.mid`` file doesn't join the recent songs. If the export fails
      (a song without chords, or a folder the app can't write to), a message
      says why.

   .. only:: ios

      The exported file is a copy: the song you're editing stays open as it was,
      and the ``.mid`` file doesn't join the recent songs. If the export fails
      (a song without chords, say), a message says why.

There are no export options to set: the export uses whatever is currently set
for voicing, instrument, and tempo, described below.


What Ends Up in the File
=========================

The exported file contains exactly what playback would play:

.. only:: desktop

   * **The same chord voicings.** Piano voice leading or guitar fingerings,
     whichever :doc:`Voicing <playback>` is currently selected, note for note.
   * **The same timing.** Chord durations (``C*2``, ``Am*4.5``, and so on) carry
     over as MIDI note lengths.
   * **Loops unrolled.** A ``{loop: verse 4}`` doesn't come across as a MIDI
     loop -- there's no such thing. Each of the four passes is written out in
     full, one after another, just as it's heard during playback. See
     :doc:`directives` for how ``{label}`` and ``{loop}`` build up a song.
   * **Rests as silence.** ``NC`` sections play nothing, so they become gaps in
     the file rather than notes.
   * **The whole song, from the top.** Export always renders the entire
     document from the beginning, no matter where your cursor is or what you
     last clicked.

.. only:: android

   * **The same chord voicings.** Piano voice leading or guitar fingerings,
     whichever :doc:`Voicing <playback>` is currently selected, note for note.
   * **The same timing.** Chord durations (``C*2``, ``Am*4.5``, and so on) carry
     over as MIDI note lengths.
   * **Loops unrolled.** A ``{loop: verse 4}`` doesn't come across as a MIDI
     loop -- there's no such thing. Each of the four passes is written out in
     full, one after another, just as it's heard during playback. See
     :doc:`directives` for how ``{label}`` and ``{loop}`` build up a song.
   * **Rests as silence.** ``NC`` sections play nothing, so they become gaps in
     the file rather than notes.
   * **The whole song, from the top.** Export always renders the entire
     document from the beginning, no matter where the playhead or your cursor is.

Tempo, meter, and key come from the same directives that drive playback:

.. only:: desktop

   * The starting tempo is the player bar's tempo, unless a ``{bpm}`` before the
     first chord sets it. Every ``{bpm}`` change in the song is written at the
     point it occurs, so the file speeds up and slows down exactly where the
     song does.

.. only:: android

   * The starting tempo is the one in the player's song pill: set by a
     ``{bpm}`` before the song's first chord, or the Tempo in Playback settings
     when there's none (see :doc:`playback`). Every ``{bpm}`` change in the
     song is written at the point it occurs, so the file speeds up and slows
     down exactly where the song does.

* The starting time signature, and each ``{time: beats/unit}``, becomes a MIDI
  time-signature event.
* The starting key, and each ``{key: note}``, becomes a MIDI key-signature
  event, placed at the first chord in that key. European keys are written as
  their American equivalent (``Sol`` as G, ``Lam`` as A minor), and a key MIDI
  has no signature for is written as its enharmonic twin (``D#`` as Eb).

.. only:: desktop

   The **Instrument** selected under :menuselection:`Playback --> Instrument` is
   written as the track's MIDI program, so a General MIDI player or synth picks
   a matching sound automatically. The metronome click is never written to the
   file, even if it's turned on and audible during playback.

.. only:: android

   The **Instrument** picked in the Play tab's player is
   written as the track's MIDI program, so a General MIDI player or synth picks
   a matching sound automatically. The metronome click is never written to the
   file, even if it's turned on and audible during playback.

The file has two tracks: a conductor track carrying tempo, time signature,
and key, and a chord track carrying the notes. This is the standard layout
most software expects.

**Ensemble voicings export one track per voice.** If an :doc:`ensemble
voicing <ensembles>` (Choir, Male Choir, Treble Choir, String Quartet, or a
custom ensemble) is selected instead of piano or guitar, the single chord
track is replaced by one track per voice, named after it and top voice first:
Soprano, Alto, Tenor and Bass for the Choir, Violin I, Violin II, Viola and
Cello for the String Quartet. The file opens in a notation program as separate
parts rather than one stack of chords. Every voice track gets the same
instrument, the one selected for playback.


Working with the Exported File
===============================

Any MIDI-aware program can open the file: a DAW like Reaper or Ableton, a
notation program like MuseScore, or GarageBand. The chords sit on one track
(one per voice for an ensemble), and the tempo and meter changes come along
with them, so a program
that reads MIDI tempo maps will follow the song's tempo changes rather than
playing everything at a single flat speed.

.. only:: android

   .. only:: not ios

      On the phone, open the file from the folder you saved it to with any app
      that plays or edits MIDI files. To work on it on a computer, save it to a
      cloud folder (or copy it over USB) and open it there.

   .. only:: ios

      Open the file from the Files app with any app that plays or edits MIDI
      files. To work on it on a computer, save it to iCloud Drive or another cloud
      folder and open it there.


A Couple of Gotchas
====================

* **Loops make the file longer than the text.** A short song with a
  ``{loop: chorus 8}`` produces a MIDI file with eight full passes of the
  chorus, because there's nowhere else for the repeats to live once loops
  are gone. If the file plays longer than you expect, check for loop
  directives.

.. only:: desktop

   * **The speed multiplier doesn't affect the file.** The player bar's speed
     percentage (see :doc:`playback`) is a practice control for live playback
     only. A MIDI export always uses the song's real tempo -- the tempo from
     the player bar and any ``{bpm}`` directives, with the multiplier ignored.
     An audio export does follow it (below).

.. only:: android

   * **The speed multiplier doesn't affect the file.** The player's Speed
     setting (see :doc:`playback`) is a practice control for live playback
     only. A MIDI export always uses the song's real tempo -- the song's BPM
     and any ``{bpm}`` directives, with the multiplier ignored. An audio
     export does follow it (below).


Exporting Audio
===============

An audio export records the song the way you hear it when you press Play,
into a WAV file (16-bit stereo, 44.1 kHz) that any music player, phone or
audio editor can open.

.. only:: desktop

   1. Choose **Export audio...** in the ☰ menu, or
      :menuselection:`File --> Export audio...` on the menu bar.
   2. The save dialog suggests the song's name with ``.wav``, picked the same
      way as for MIDI. Choose a folder, change the name if you like, and save.
   3. Chord Notepad plays the song into the file, faster than real time: a
      four-minute song takes a few seconds. The status bar counts up while it
      works ("Exporting audio… 40%") and says "Exported audio: …" when the
      file is written. You can keep editing and playing meanwhile.

.. only:: android

   .. only:: not ios

      1. Tap **☰** at the top left and choose **Export audio…**.
      2. Android's file picker opens with the song's name and ``.wav`` filled
         in, picked the same way as for MIDI. Pick a folder, change the name if
         you like, and tap **Save**.
      3. Chord Notepad plays the song into the file, faster than real time. The
         status counts up while it works ("Exporting audio… 40%") and says
         "Exported audio: …" when the file is written: on the player's status
         line in the Play tab, or at the bottom of the screen in the Edit tab.

   .. only:: ios

      1. Tap **☰** at the top left and choose **Export audio…**.
      2. Chord Notepad plays the song into the file, faster than real time.
         "Preparing export…" counts up while it works (40%). **Cancel** stops it.
      3. iOS's save sheet opens with the song's name and ``.wav``, picked the same
         way as for MIDI. Choose a folder, change the name in the **Save as** field if
         you like, and confirm. The status then says "Exported audio: …" with the
         folder. If you cancel the sheet, nothing is saved.

There is no dialog with options. The file sounds like Play does at the moment
you choose the file name:

.. only:: desktop

   * **The voicing and the instrument** selected under
     :menuselection:`Playback`, note for note.
   * **The Music slider** under the volume button. Mute doesn't apply: the
     file is never silent.
   * **The metronome**, only if it's on, at the Metronome slider's level.
   * **The speed percentage** in the player bar: at 50% the file is twice as
     long, and every ``{bpm}`` change keeps its place.
   * **The soundfont** playback uses (see :doc:`settings`). A new soundfont
     chosen in Settings is used after a restart, for exports too.

.. only:: android

   * **The voicing and the instrument** picked in the Play tab's player, note
     for note.
   * **The metronome**, only if it's on.
   * **The speed** in the player: at 50% the file is twice as long, and every
     ``{bpm}`` change keeps its place.

Like a MIDI export, it's **the whole song, from the top**, with every loop
played out, whatever the cursor or the playhead is on. After the last chord
the file goes on while it rings out: two seconds at least, longer for a
sound that fades slowly such as a pad, and eight at most. The export is a copy: the song stays
open as it was, and the ``.wav`` file doesn't join the recent songs.

One audio export runs at a time. Choosing **Export audio** again before the
first one has finished says so and asks for no file; try again once the
status has stopped counting up.

A WAV file is large: about 10 MB per minute of music. If the export fails (a
song without chords, a full disk, or a folder the app can't write to), a
message says why.

.. only:: android

   .. only:: not ios

      Android makes the file as soon as you tap **Save** in the picker, so an
      export that fails after that leaves it behind, empty or cut short. The
      message names it; delete it in your files app if you don't need it.

   .. only:: ios

      Chord Notepad makes the file before the save sheet opens, so an export that
      fails leaves nothing behind. If you cancel the sheet, nothing is saved.

.. only:: desktop

   Quitting while an audio export is still running stops it, and no file is
   written.


Exporting a PDF
===============

A PDF export prints the song's text as you typed it, in a monospace font, so
the chords stay over the words they belong to. It's for sharing the song: the
chord sheet, the chord diagrams and the colours of the editor don't come
along.

.. only:: desktop

   1. Choose **Export PDF...** in the ☰ menu, or
      :menuselection:`File --> Export PDF...` on the menu bar.
   2. The save dialog suggests the song's name with ``.pdf``, picked the same
      way as for MIDI. Choose a folder, change the name if you like, and save.
   3. The status bar says "Exported PDF: …" when the file is written.

.. only:: android

   .. only:: not ios

      1. Tap **☰** at the top left and choose **Export PDF…**.
      2. Android's file picker opens with the song's name and ``.pdf`` filled
         in, picked the same way as for MIDI. Pick a folder, change the name if
         you like, and tap **Save**.
      3. The status says "Exported PDF: …" when the file is written: on the
         player's status line in the Play tab, or at the bottom of the screen in
         the Edit tab.

   .. only:: ios

      1. Tap **☰** at the top left and choose **Export PDF…**.
      2. iOS's save sheet opens with the song's name and ``.pdf``, picked the same
         way as for MIDI. Choose a folder, change the name in the **Save as** field if
         you like, and confirm.
      3. The status says "Exported PDF: …" with the folder: on the player's status
         line in the Play tab, or at the bottom of the screen in the Edit tab. If you
         cancel the save sheet, nothing is saved.

What the pages look like:

* **The text as it is.** Every line, blank lines, comments (``// ...``) and
  ``.`` text lines included, in the same columns as in the editor. A tab
  prints as spaces up to the next multiple of 8 columns, so text lined up
  with tabs may sit differently than on your screen; spaces line up exactly.
* **Directives as plain words, in grey.** ``{key: A} {time: 4/4} {bpm: 200}``
  prints as ``Key: A | Time: 4/4 | BPM: 200``. A ``{label: Chorus}`` prints
  as ``Chorus``, a ``{loop: Chorus 3}`` as ``Repeat Chorus ×3`` and
  ``{capo: 3}`` as ``Capo: 3``. A directive with a mistake in it prints the
  text between its braces. When the words are shorter than the directive,
  spaces fill the gap, so the chords after it keep their places. When
  they're longer, they take the room from the spaces after them, and push
  the rest of the line only when there aren't enough.
* **The song's name** at the top of every page, and the page number
  ("1 / 3") at the bottom.
* **A4 or Letter paper**, whichever your country uses (Letter in the US,
  Canada, Mexico and a few other countries, A4 elsewhere).
* **Long lines.** The text gets smaller, down to 7 points from 10, until
  the chords of the longest chord line fit across the page (a comment at its
  end doesn't count). A line that's still too long continues on the next
  line, indented by two more spaces. A chord line that doesn't fit even at 7
  points is cut at the same place as its lyric line, so each part of the
  chords stays over its part of the words.
* **Page breaks** never separate a chord line from the lyric line under it,
  and a comment or directive line, such as a section heading, moves to the
  next page with the line under it. A page never starts with blank lines.

A song with only lyrics, or with no text at all, exports too. The export is a
copy: the song stays open as it was, and the ``.pdf`` file doesn't join the
recent songs.

.. only:: android

   .. only:: not ios

      Android makes the file as soon as you tap **Save** in the picker, so an
      export that fails after that leaves it behind, empty. The message names
      it; delete it in your files app if you don't need it.

   .. only:: ios

      Chord Notepad makes the file before the save sheet opens, so an export that
      fails leaves nothing behind. If you cancel the sheet, nothing is saved.
