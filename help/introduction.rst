============
Introduction
============

What is Chord Notepad?
----------------------

Chord Notepad is a text editor that recognizes chord symbols. As you type,
it highlights valid chords and can play them back using synthesized instrument
sounds.

It works like a regular text editor, but with chord detection and audio
playback built in.

Who is it for?
--------------

Chord Notepad is useful for:

* **Songwriters** sketching out chord progressions
* **Musicians** practicing chord changes with audio feedback
* **Teachers** creating chord sheets for students
* **Band members** sharing chord charts

No music theory knowledge is required. If you can write ``C  F  G``, you can
use the application.

Key Features
------------

Automatic Chord Detection
~~~~~~~~~~~~~~~~~~~~~~~~~

Chord Notepad recognizes chord symbols as you write. Valid chords appear in
blue with an underline. Unrecognized text appears in gray.

Multiple Notation Systems
~~~~~~~~~~~~~~~~~~~~~~~~~

Use the notation you're comfortable with:

* **American notation**: C, D, E, F, G, A, B
* **European notation**: Do, Re, Mi, Fa, Sol, La, Si
* **Roman numerals**: I, IV, V, vi (relative to the key)

You can switch between notations using the toolbar toggle.

Playback
~~~~~~~~

The application plays chords using:

* **Piano voicing** - Keyboard-style chord arrangements
* **Guitar voicing** - Fingerings for various tunings (standard, drop D, etc.)
* **128 instruments** - General MIDI instrument set

The playback engine applies voice leading between chords.

Song Control
~~~~~~~~~~~~

Build complete songs with:

* **Tempo control** - Set the BPM for your progression
* **Time signatures** - 4/4, 3/4, 6/8, and more
* **Labels and loops** - Mark sections and repeat them
* **Chord duration** - Hold some chords longer than others

Add Comments
~~~~~~~~~~~~

Use ``//`` to add notes, lyrics, or reminders that won't affect playback:

.. code-block:: chord

   C    Am   F    G    // Verse - play softly
   F    G    C         // Chorus - build up here

Limitations
-----------

Chord Notepad is a chord editor, not a full music production tool. It does not:

* Record audio or add effects (not a DAW)
* Display standard musical notation (not sheet music software)
* Show guitar tablature (not a tab editor)

For those features, you would need different software.

System Requirements
-------------------

Chord Notepad runs on:

* **Linux** (requires libfluidsynth)
* **Windows**
* **macOS**

Audio playback requires a working sound system. The application uses FluidSynth
for instrument synthesis.
