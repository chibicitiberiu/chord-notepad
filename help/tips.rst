========================
Tips and Troubleshooting
========================

This section contains usage tips and solutions to common problems.


Best Practices
==============

Organizing Chord Sheets
-----------------------

**Use comments to section your work:**

.. code-block:: chord

   // ========== MY SONG ==========
   // Key: G | Tempo: 120 | Time: 4/4

   // --- INTRO ---
   G*4  D*4

   // --- VERSE 1 ---
   G  D  Em  C

   // --- CHORUS ---
   C  D  G  Em

Comments make it easy to navigate long documents and remember what's what.

**Keep one song per file:**

It's tempting to put multiple songs in one file, but separate files are easier
to manage, share, and find later.

**Use descriptive filenames:**

Instead of ``chords.txt``, try ``amazing_grace_key_of_G.txt`` or
``blues_practice_12bar.txt``.

Using Labels Effectively
------------------------

**Name labels clearly:**

.. code-block:: chord

   // Good
   {label: verse1}
   {label: chorus}
   {label: bridge}

   // Not as good
   {label: a}
   {label: b}
   {label: c}

**Build a master arrangement at the end:**

.. code-block:: chord

   // Define all your sections first
   {label: intro}
   G*4

   {label: verse}
   G  D  Em  C

   {label: chorus}
   C  D  G

   // Then arrange the song with loops
   {loop: intro 1}
   {loop: verse 2}
   {loop: chorus 1}
   {loop: verse 2}
   {loop: chorus 2}

This keeps your sections clean and your arrangement flexible.

Tempo Changes for Dynamic Songs
-------------------------------

**Gradual acceleration:**

.. code-block:: chord

   {bpm: 100}
   C  Am  F  G
   {bpm: +5}
   C  Am  F  G
   {bpm: +5}
   C  Am  F  G
   // Now at 110 BPM

**Slow sections:**

.. code-block:: chord

   // Normal tempo
   C  Am  F  G

   // Slower section
   {bpm: 80}
   Am*4  G*4

   // Back to normal
   {bpm: reset}
   C  Am  F  G

**Percentage changes:**

.. code-block:: chord

   {bpm: 120}
   C  Am  F  G

   {bpm: 50%}       // Half speed
   Am*8

   {bpm: 200%}      // Back to original (50% × 2 = 100%)

Notation Consistency
--------------------

**Stick to one notation system:**

Mixing American and European notation in the same file is confusing:

.. code-block:: chord

   // Don't do this
   C  Am  Fa  Sol    // Mixed notation - confusing!

   // Do this instead
   C  Am  F  G       // All American
   // or
   Do  Lam  Fa  Sol  // All European

Use the **Convert to American/European** options in the Tools menu to switch
an entire document at once.


Workflow Tips
=============

Practice Mode
-------------

Turn any progression into a practice exercise:

.. code-block:: chord

   {bpm: 60}         // Start slow
   {label: practice}
   Dm7  G7  Cmaj7  Am7

   {loop: practice 20}    // Repeat 20 times

   // Or gradually speed up
   {bpm: +5}
   {loop: practice 5}
   {bpm: +5}
   {loop: practice 5}
   // etc.

Comparing Options
-----------------

Write multiple versions and click to compare:

.. code-block:: chord

   // Option A - minor feel
   Am  F  C  G

   // Option B - major feel
   C  G  Am  F

   // Option C - jazzy
   Am7  Fmaj7  Cmaj7  G7

Click individual chords or play each section to hear the differences.

Quick Chord Testing
-------------------

Keep a "scratch pad" area at the bottom of your file:

.. code-block:: chord

   // === MY SONG ===
   C  Am  F  G
   // ... rest of song ...

   // === SCRATCH PAD - delete later ===
   // Testing chord options:
   Dm7  Em7  Fmaj7  G7
   Dm9  Em9

Click chords in the scratch pad to test them, then copy the ones you like
into your song.


Troubleshooting
===============

No Sound?
---------

**Check your system volume:**
Make sure your computer's volume is turned up and not muted.

**Check the instrument:**
Some instruments are quieter than others. Try switching to Acoustic Grand
Piano (the default) to test.

**Verify FluidSynth is working:**
Chord Notepad needs FluidSynth for audio. On Linux, make sure ``libfluidsynth``
is installed.

**Try restarting the application:**
Sometimes audio systems need a fresh start.

Chords Not Detected?
--------------------

**Check your spelling:**
Common typos:

* ``Cmaaj7`` → should be ``Cmaj7``
* ``Csus`` → try ``Csus4``
* ``c#`` → should be ``C#`` (capital C)

**Check for extra characters:**
Chords must be separated by spaces. ``C-Am-F-G`` won't work; use ``C Am F G``.

**Check the notation:**
If you're using European notation, make sure the toggle is set to "Do", not "AB".

**Check for unsupported chords:**
Some very complex or unusual chord names might not be recognized. Try simplifying
(e.g., ``Cmaj13#11`` might become ``Cmaj13`` or ``Cmaj7``).

Playback Sounds Wrong?
----------------------

**Check the key for roman numerals:**
If you're using roman numerals (I, IV, V, etc.), make sure the key is set
correctly in the toolbar or with a ``{key}`` directive.

**Check your time signature:**
If rhythms feel off, verify the time signature matches your intention.

**Check chord durations:**
If some chords seem too short or long, check for ``*`` duration modifiers.

Directives Not Working?
-----------------------

**Check the syntax:**

.. code-block:: chord

   {bpm: 120}      // Correct - has space after colon
   {bpm:120}       // Also works
   {bpm 120}       // Wrong - missing colon
   [bpm: 120]      // Wrong - wrong brackets

**Check for typos in label names:**

.. code-block:: chord

   {label: verse}
   ...
   {loop: verse 2}    // Correct - matches

   {label: verse}
   ...
   {loop: Verse 2}    // Wrong - case doesn't match!

Labels are case-sensitive.

File Won't Open?
----------------

**Check the file encoding:**
Chord Notepad works with UTF-8 text files. Files in other encodings might
cause issues.

**Check the file extension:**
While Chord Notepad can open any text file, if the file has a strange extension,
you might need to select "All Files" in the Open dialog.


Common Mistakes
===============

Forgetting to Save
------------------

The asterisk (*) in the title bar indicates unsaved changes. Save regularly
with Ctrl+S.

Using Wrong Notation Toggle
---------------------------

If your chords aren't detected, check that the notation toggle (AB/Do) matches
what you're typing. European notation won't be detected if American is selected,
and vice versa.

Editing During Playback
-----------------------

You can't edit while playing - the editor is locked. Stop playback first
(click ⏹), then make your changes.

Copy-Pasting Without Checking
-----------------------------

When pasting chords from the web, watch out for:

* Fancy quote characters (`` ' `` instead of plain ``'``)
* Non-breaking spaces
* HTML formatting

If pasted chords aren't detected, try retyping them.

Loops That Never End
--------------------

If you loop to a label that contains another loop back to itself, you create
a circular reference. The application handles this, but the song structure
may not behave as intended.


Getting Help
============

**Check this guide first:**
Most questions are answered in :doc:`writing_chords`, :doc:`directives`, or
:doc:`playback`.

**Use the Chord Identifier:**
If you're not sure how to write a chord, use Tools → Identify Chord to build
it from notes.

**Try things out:**
Invalid input is handled safely. You can click chords and test different
options without risk.
