===========
MIDI export
===========

Chord Notepad can save your song as a standard MIDI file, so you can open it
in a DAW, a notation program, or any other tool that reads ``.mid`` files.


Exporting a Song
================

1. Go to :menuselection:`File --> Export MIDI...`
2. Choose a location and filename, and save with a ``.mid`` extension.
3. Chord Notepad writes the file.

There's no dialog to configure -- the export uses whatever is currently set
for voicing, instrument, and tempo, described below.


What Ends Up in the File
=========================

The exported file contains exactly what playback would play:

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

Tempo, meter, and key come from the same directives that drive playback:

* The starting tempo is the toolbar BPM. Every ``{bpm}`` change in the song
  is written at the point it occurs, so the file speeds up and slows down
  exactly where the song does.
* Each ``{time: beats/unit}`` becomes a MIDI time-signature event.
* Each ``{key: note}`` becomes a MIDI key-signature event.

The **Instrument** selected under :menuselection:`Playback --> Instrument` is
written as the track's MIDI program, so a General MIDI player or synth picks
a matching sound automatically. The metronome click is never written to the
file, even if it's turned on and audible during playback.

The file has two tracks: a conductor track carrying tempo, time signature,
and key, and a chord track carrying the notes. This is the standard layout
most software expects.


Working with the Exported File
===============================

Any MIDI-aware program can open the file: a DAW like Reaper or Ableton, a
notation program like MuseScore, or GarageBand. The chords all sit on one
track, and the tempo and meter changes come along with them, so a program
that reads MIDI tempo maps will follow the song's tempo changes rather than
playing everything at a single flat speed.


A Couple of Gotchas
====================

* **Loops make the file longer than the text.** A short song with a
  ``{loop: chorus 8}`` produces a MIDI file with eight full passes of the
  chorus, because there's nowhere else for the repeats to live once loops
  are gone. If the file plays longer than you expect, check for loop
  directives.
* **The speed multiplier doesn't affect the file.** The toolbar's ``x0.5``
  / ``x2`` multiplier (see :doc:`playback`) is a practice control for live
  playback only. Export always uses the song's real tempo -- the BPM from
  the toolbar and any ``{bpm}`` directives, with the multiplier ignored.
