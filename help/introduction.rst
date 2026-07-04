============
Introduction
============

What is Chord Notepad?
----------------------

Chord Notepad is a text editor that recognizes chord symbols. You write your
lyrics with the chords on the line above them, the way you'd jot a song on the
back of an envelope or find it written online. As you type, the application
highlights the chords and can play them back using synthesized instruments.

.. figure:: /images/editor-main-window.png
   :alt: The Chord Notepad main window: a chord sheet with chord symbols
         highlighted in blue above the lyrics, directives in braces, and a
         toolbar across the top.
   :align: center
   :width: 100%

   A chord sheet open in Chord Notepad. Chord symbols are highlighted in blue
   above the lyric lines; ``{directives}`` and ``// comments`` are colored
   differently and never play.

It works like a regular text editor, but with chord detection and audio
playback built in. You don't mark up your text or press a "detect" button:
Chord Notepad reads each line and works out on its own which lines are chords
and which are lyrics, so a word like *Am* in a sentence isn't mistaken for a
chord. Click any highlighted chord to hear it, or press **Play** to run through
the whole sheet in time.

See :doc:`getting_started` to make your first chord sheet, and
:doc:`writing_chords` for the full notation.

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Chord Notepad recognizes chord symbols as you write. Valid chords appear in
blue with an underline; unrecognized text stays gray. Detection works line by
line, so a chord line like ``C  Am  F  G`` lights up while the lyric under it
is left alone even when it contains chord-like words (an *Am* in a sentence, a
*La* or a *Si*). See :doc:`writing_chords` for what counts as a valid chord.

Multiple Notation Systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the notation you're comfortable with:

* **American notation**: C, D, E, F, G, A, B
* **European notation** (solfège): Do, Re, Mi, Fa, Sol, La, Si
* **Roman numerals**: I, IV, V, vi -- played relative to the current key

The toolbar toggle (labelled **AB / Do**) switches the editor between American
and European note names:

.. figure:: /images/notation-toggle.png
   :alt: The AB / Do notation toggle at the left of the toolbar, with AB
         (American) selected.
   :align: center

   The notation toggle. **AB** is American, **Do** is European.

Roman numerals are **not** part of this toggle -- they are always recognized,
in either mode, and are resolved against the current ``{key: ...}``. Switching
the toggle only changes how the editor reads and shows note names; it does not
rewrite text you have already typed (use :menuselection:`Tools --> Convert to
...` for that). All three notations are covered in :doc:`writing_chords`.

Playback
~~~~~~~~

The application plays chords using:

* **Piano voicing** - keyboard-style chord arrangements
* **Guitar voicing** - fingerings for various tunings (standard, drop D, etc.)
* **128 instruments** - the full General MIDI instrument set

The playback engine applies *voice leading* -- it moves as little as possible
from one chord to the next instead of jumping around the keyboard -- which is
explained in :doc:`playback`.

Song Control
~~~~~~~~~~~~

Build complete songs with directives (see :doc:`directives`):

* **Tempo control** - set the BPM, and change it mid-song
* **Time signatures** - 4/4, 3/4, 6/8, and more
* **Labels and loops** - mark sections and repeat them
* **Chord duration** - hold some chords longer than others

Add Comments
~~~~~~~~~~~~

Use ``//`` to add section markers, reminders, or performance notes that are
shown but never played:

.. code-block:: chord

   C    Am   F    G    // Verse - play softly
   F    G    C         // Chorus - build up here

Lyrics do **not** need comment markers -- write them on their own line below
the chords and Chord Notepad keeps them out of playback automatically.

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
