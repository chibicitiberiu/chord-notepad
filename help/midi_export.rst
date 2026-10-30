===========
MIDI export
===========

Chord Notepad can save your song as a standard MIDI file, so you can open it
in a DAW, a notation program, or any other tool that reads ``.mid`` files.


Exporting a Song
================

.. only:: desktop

   1. Go to :menuselection:`File --> Export MIDI...`
   2. The save dialog suggests the song's name with ``.mid`` (``Untitled.mid``
      for a song you haven't saved yet). Choose a folder, change the name if
      you like, and save.
   3. Chord Notepad renders the song and writes the file. The status bar says
      "Exporting MIDI: …" while it works and "Exported MIDI: …" when it's done.

.. only:: android

   1. Tap **☰** at the top left and choose **Export MIDI…**.
   2. Android's file picker opens, with the song's name and ``.mid`` filled
      in (``Untitled.mid`` for a song you haven't saved yet). Pick a folder,
      on the phone or in any storage app such as Google Drive, change the
      name if you like, and tap **Save**.
   3. Chord Notepad renders the song and writes the file. The status says
      "Exporting MIDI: …" while it works and "Exported MIDI: …" when the file
      is written: on the player's status line in the Play tab, or at the
      bottom of the screen in the Edit tab.

.. platform-figure:: drawer
   :platforms: android
   :alt: The open drawer: New song, Open, the recent songs, Save as, Export
         MIDI, Settings, User guide, Quick start and About.

   **Export MIDI…** is in the ☰ drawer, under Save as….

.. only:: android

   The exported file is a copy: the song you're editing stays open as it was,
   and the ``.mid`` file doesn't join the recent songs. If the export fails
   (a song without chords, or a folder the app can't write to), a message
   says why.

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

   * The starting tempo is the toolbar BPM, unless a ``{bpm}`` before the
     first chord sets it. Every ``{bpm}`` change in the song is written at the
     point it occurs, so the file speeds up and slows down exactly where the
     song does.

.. only:: android

   * The starting tempo is the one in the player's song pill: set by a
     ``{bpm}`` before the song's first chord, or the Tempo in Song defaults
     when there's none (see :doc:`playback`). Every ``{bpm}`` change in the
     song is written at the point it occurs, so the file speeds up and slows
     down exactly where the song does.

* The starting time signature, and each ``{time: beats/unit}``, becomes a MIDI
  time-signature event. A unit MIDI can't store (``{time: 4/3}``, say) is left
  out; the timing is still right.
* The starting key, and each ``{key: note}``, becomes a MIDI key-signature
  event, placed at the first chord in that key. Only keys in American notation
  (``G``, ``Bb``, ``F#m``) are written: with European keys such as ``Sol`` the
  file has no key signature.

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

   On the phone, open the file from the folder you saved it to with any app
   that plays or edits MIDI files. To work on it on a computer, save it to a
   cloud folder (or copy it over USB) and open it there.


A Couple of Gotchas
====================

* **Loops make the file longer than the text.** A short song with a
  ``{loop: chorus 8}`` produces a MIDI file with eight full passes of the
  chorus, because there's nowhere else for the repeats to live once loops
  are gone. If the file plays longer than you expect, check for loop
  directives.

.. only:: desktop

   * **The speed multiplier doesn't affect the file.** The toolbar's speed
     percentage (see :doc:`playback`) is a practice control for live playback
     only. Export always uses the song's real tempo -- the BPM from
     the toolbar and any ``{bpm}`` directives, with the multiplier ignored.

.. only:: android

   * **The speed multiplier doesn't affect the file.** The player's Speed
     setting (see :doc:`playback`) is a practice control for live playback
     only. Export always uses the song's real tempo -- the song's BPM and any
     ``{bpm}`` directives, with the multiplier ignored.
