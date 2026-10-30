============
Introduction
============

What is Chord Notepad?
----------------------

Chord Notepad is a text editor that recognizes chord symbols. You write your
lyrics with the chords on the line above them, the way you'd jot a song on the
back of an envelope or find it written online. As you type, the application
highlights the chords and can play them back using synthesized instruments.

.. platform-figure:: editor-main-window
   :alt: The Chord Notepad main window: a chord sheet with chord symbols
         highlighted in blue above the lyrics, directives in braces, and a
         toolbar across the top.
   :android-alt: Chord Notepad on a phone, in the Play tab: a song with blue
                 chords above the lyrics, the chord that is playing in yellow,
                 the chord sheet below the text and the player at the bottom.
   :align: center
   :width: 100%
   :android-caption: A song playing in Chord Notepad. Chord symbols are blue
      above the lyric lines, the chord that sounds right now is yellow, and
      ``{directives}`` and ``// comments`` are colored differently and never
      play. Below the text are the chord sheet and the player.

   A chord sheet open in Chord Notepad. Chord symbols are highlighted in blue
   above the lyric lines; ``{directives}`` and ``// comments`` are colored
   differently and never play.

.. only:: desktop

   It works like a regular text editor, but with chord detection and audio
   playback built in. You don't mark up your text or press a "detect" button:
   Chord Notepad reads each line and works out on its own which lines are chords
   and which are lyrics, so a word like *Am* in a sentence isn't mistaken for a
   chord. Click any highlighted chord to hear it, or press **Play** to run through
   the whole sheet in time.

.. only:: android

   It works like a regular text editor, but with chord detection and audio
   playback built in. You don't mark up your text or press a "detect" button:
   Chord Notepad reads each line and works out on its own which lines are chords
   and which are lyrics, so a word like *Am* in a sentence isn't mistaken for a
   chord. In the Play tab, tap any highlighted chord to hear it, or press **▶** to
   run through the whole sheet in time.

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
blue with an underline; a word that looks like a chord but isn't one turns gray,
and lyrics stay in the normal text colour. Detection works line by
line, so a chord line like ``C  Am  F  G`` lights up while the lyric under it
is left alone even when it contains chord-like words (an *Am* in a sentence, a
*La* or a *Si*). See :doc:`writing_chords` for what counts as a valid chord.

Multiple Notation Systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the notation you're comfortable with:

* **American notation**: C, D, E, F, G, A, B
* **European notation** (solfège): Do, Re, Mi, Fa, Sol, La, Si
* **Roman numerals**: I, IV, V, vi -- played relative to the current key

.. only:: desktop

   The toolbar toggle (labelled **AB / Do**) switches the editor between American
   and European note names:

.. only:: android

   The **AB / Do** switch in the Edit ribbon sets the notation the text is read
   in: American or European note names. **Convert**, right next to it, rewrites
   the chords themselves from one notation to the other.

.. platform-figure:: notation-toggle
   :alt: The AB / Do notation toggle at the left of the toolbar, with AB
         (American) selected.
   :android-alt: The AB / Do switch and the Convert button in the Edit ribbon,
                 with AB (American) selected.
   :align: center
   :android-caption: The notation switch and Convert. **AB** is American, **Do**
      is European.

   The notation toggle. **AB** is American, **Do** is European.

.. only:: desktop

   Roman numerals are **not** part of this toggle -- they are always recognized,
   in either mode, and are resolved against the current ``{key: ...}``. Switching
   the toggle only changes how the editor reads and shows note names; it does not
   rewrite text you have already typed (use :menuselection:`Tools --> Convert to
   ...` for that). All three notations are covered in :doc:`writing_chords`.

.. only:: android

   Roman numerals are **not** part of this toggle -- they are always recognized,
   in either mode, and are resolved against the current ``{key: ...}``. Switching
   the toggle only changes how the editor reads and shows note names; it does not
   rewrite text you have already typed (use **Convert** in the Edit ribbon for
   that). All three notations are covered in :doc:`writing_chords`.

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
* Write melodies or rhythms in standard notation (not sheet music software)
* Edit guitar tablature by hand (not a tab editor)

For those features, you would need different software.

The chord sheet strip does show your chords on a staff, as fret diagrams, or as
tab (see :doc:`chord_sheet`), but those views are drawn from the chords you
type and the voicing that plays them. You can't place individual notes or
frets yourself.

System Requirements
-------------------

.. only:: desktop

   Chord Notepad runs on:

   * **Linux** (requires libfluidsynth)
   * **Windows**
   * **macOS**

   Audio playback requires a working sound system. The application uses FluidSynth
   for instrument synthesis.

.. only:: android

   The Android app needs Android 7.0 or newer on a 64-bit phone or tablet. It
   works offline: the instruments, this guide and everything else are built in,
   and the app doesn't ask for internet access.

   This edition of the guide describes the Android app. Chord Notepad also runs
   on Linux, Windows and macOS. Songs are plain text files, and the chord
   notation is the same on every platform, so a song written on your phone
   plays the same on your computer.

Getting Chord Notepad
---------------------

.. only:: desktop

   Chord Notepad is free and open source. Downloads for every platform are on the
   `GitHub releases page <https://github.com/chibicitiberiu/chord-notepad/releases>`_.

   It is also available from:

   * **Snap Store** (Linux): https://snapcraft.io/chord-notepad, or run
     ``sudo snap install chord-notepad``
   * **Microsoft Store** (Windows): https://apps.microsoft.com/detail/9nb07qdfwjf4.
     This is a paid supporter edition. It is the same app as the free download and
     updates automatically. Buying it helps support development.

.. only:: android

   Chord Notepad is free and open source. The source code, and the downloads
   for every platform, are on
   `GitHub <https://github.com/chibicitiberiu/chord-notepad/releases>`_.

   Every feature is free, wherever you got the app. The version from Google
   Play offers an optional one-time purchase that supports development: from
   a week after you install it, the app asks about it at most once a day, when
   you open the app itself (never when you open a song from another app). Tap
   **Not now** to carry on. After you buy it, the app stops asking and
   **☰ → Settings** shows a supporter badge. The purchase is tied to your
   Google account, so it comes back when you reinstall or change phones.
