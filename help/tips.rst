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

**Repeat sections in place with loops:**

A loop repeats the span between its label and the loop directive, so put the
label at the start of a section and the loop at its end:

.. code-block:: chord

   {label: verse}
   G  D  Em  C
   {loop: verse 2}      // play the verse twice, then carry on

   {label: chorus}
   C  D  G
   {loop: chorus 2}     // play the chorus twice

Write the sections in the order they should play. A loop repeats a section on
the spot; it can't jump around to rearrange them. See :doc:`directives` for the
full behavior.

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

Chord Notepad reads one notation at a time (the AB/Do toggle), so chords in the
other notation aren't recognized. A line that mixes the two may not count as a
chord line at all:

.. code-block:: chord

   // Don't do this
   C  Am  Fa  Sol    // Mixed notation: not detected in either mode

   // Do this instead
   C  Am  F  G       // All American
   // or
   Do  Lam  Fa  Sol  // All European

.. only:: desktop

   Use the **Convert to American/European** options in the Tools menu to switch
   an entire document at once.

.. only:: android

   Use **Convert** in the Edit ribbon to switch an entire document at once.


Workflow Tips
=============

.. only:: android

   .. rubric:: On a Phone or Tablet

   * **Write in Edit, listen in Play.** Edit is for typing; Play freezes the
     text so a tap plays a chord instead of opening the keyboard. Songs you
     open start in Play, so you can't change them by accident while you
     practise. Switch to Edit when you want to change something.
   * **Turn the phone sideways for the chord sheet.** In landscape the sheet
     sits beside the text instead of under it, so you see more of both.
     Drag the handle between them to give the sheet more or less room (see
     :doc:`chord_sheet`). On a tablet the same layout shows a lot more of
     the song.
   * **Pinch the text** with two fingers to make it bigger or smaller, in
     either tab. On a music stand, a bigger font is easier to read.
   * **Use a hardware keyboard** for longer songs. Ctrl+S saves, Ctrl+Z
     undoes, and the other shortcuts are listed in :doc:`reference`.
   * **Typing in landscape** leaves little room above the keyboard, so the
     app bar and the Edit ribbon step aside and a small Undo / Redo chip
     floats above the keyboard. They come back when the keyboard closes.
   * **The screen stays on while a song plays**, so you can play along
     without touching the phone. Pausing lets it time out again.
   * **Practise with the speed button** rather than editing ``{bpm}``: slow
     the song down, then bring it back to 100% with Reset (see
     :doc:`playback`).

.. platform-figure:: tablet-play
   :platforms: android
   :alt: A tablet held sideways in the Play tab while a song plays: the whole
         song text on the left, a tall piano roll and the player on the right.

   A tablet in landscape: the whole song on the left, the chord sheet and the
   player on the right.

Practice Mode
-------------

Turn any progression into a practice exercise by looping it:

.. code-block:: chord

   {bpm: 60}              // Start slow
   {label: practice}
   Dm7  G7  Cmaj7  Am7
   {loop: practice 20}    // Repeat 20 times

To speed up as you go, write the tempo steps out inline rather than looping. A
loop restores the tempo it had *at the label* every time around (see
:doc:`directives`), so a ``{bpm}`` bump placed before the loop is undone on each
repeat. Written out, it climbs as intended:

.. code-block:: chord

   {bpm: 60}
   Dm7  G7  Cmaj7  Am7
   {bpm: 70}
   Dm7  G7  Cmaj7  Am7
   {bpm: 80}
   Dm7  G7  Cmaj7  Am7

Comparing Options
-----------------

.. only:: desktop

   Write multiple versions and click to compare:

.. only:: android

   Write multiple versions and, in the Play tab, tap to compare:

.. code-block:: chord

   // Option A - minor feel
   Am  F  C  G

   // Option B - major feel
   C  G  Am  F

   // Option C - jazzy
   Am7  Fmaj7  Cmaj7  G7

.. only:: desktop

   Click individual chords or play each section to hear the differences.

.. only:: android

   Tap individual chords or play each section to hear the differences.

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

.. only:: desktop

   Click chords in the scratch pad to test them, then copy the ones you like
   into your song.

.. only:: android

   In the Play tab, tap chords in the scratch pad to test them, then copy the ones you like
   into your song.


Troubleshooting
===============

No Sound?
---------

.. only:: desktop

   **Check your system volume:**
   Make sure your computer's volume is turned up and not muted.

.. only:: android

   **Check your device volume:**
   Make sure the media volume is turned up and not muted.

.. only:: desktop

   **Check the instrument:**
   Some instruments are quieter than others. Try switching to **Grand Piano**
   (in the Piano family, the default) to test.

.. only:: android

   **Check the instrument:**
   Some instruments are quieter than others. Try switching to **Grand Piano**
   (in the Piano family, the default) to test.

.. only:: desktop

   **Verify FluidSynth is working:**
   Chord Notepad needs FluidSynth for audio. On Linux, make sure ``libfluidsynth``
   is installed.

.. only:: android

   **Check where the sound goes:**
   If headphones or a Bluetooth speaker are connected, the sound plays there.

   **Check whether playback was paused:**
   Playback pauses when you leave the app, when a call comes in or another
   app starts playing, and when headphones are unplugged or a Bluetooth
   device disconnects. The status line then says "Paused". Tap **▶** to
   resume.

.. only:: desktop

   **Try restarting the application:**
   Sometimes audio systems need a fresh start.

.. only:: android

   **Try restarting the application:**
   Sometimes audio systems need a fresh start. Close Chord Notepad from the
   recent apps screen and open it again.

Chords Not Detected?
--------------------

**Check your spelling:**
Misspelled qualities aren't recognized:

* ``Cmaaj7`` → should be ``Cmaj7``
* ``Cmajor`` → should be ``C`` (or ``Cmaj7`` for the seventh)
* ``Cminor`` → should be ``Cm``

**Check for extra characters:**
Chords must be separated by spaces. ``C-Am-F-G`` won't work; use ``C Am F G``.

**Check the notation:**
If you're using European notation, make sure the toggle is set to "Do", not
"AB". Note that ``Csus``, ``c#``, and other shorthands *are* valid -- they just
may not mean what you expect (``c#`` is C-sharp *minor*; see the case note under
:ref:`playback-sounds-wrong`).

**A lyric line read as chords:**
A lyric line in European notation such as ``la la la`` (or ``do re mi``) can be
read as chords: it turns blue, plays, and Transpose changes it. Start the line
with a dot (``.la la la``) to keep it as text (see :ref:`forcing-text`).

**Check for unsupported chords:**
Chord Notepad recognizes a wide range of chords, including dense jazz voicings
like ``Cmaj13#11``, but a few unusual spellings still slip through. If a name
stays gray no matter what, fall back to a simpler one (``Cmaj7`` in place of
something the parser doesn't know).

.. _playback-sounds-wrong:

Playback Sounds Wrong?
----------------------

**Check the chord case:**
Case is meaningful. A capital letter is a major chord and a lowercase letter is
a minor one, so ``C`` is C major but ``c`` is C minor, and ``c#`` is C-sharp
minor rather than C-sharp major. If a chord sounds unexpectedly minor (or major),
check whether you capitalized the root. In roman numerals the same rule sets the
quality: ``V`` is major, ``v`` is minor.

.. only:: desktop

   **Check the key for roman numerals:**
   If you're using roman numerals (I, IV, V, etc.), make sure the key is set
   correctly in the toolbar or with a ``{key}`` directive.

.. only:: android

   **Check the key for roman numerals:**
   If you're using roman numerals (I, IV, V, etc.), make sure the key is set
   correctly in the song pill's Song defaults or with a ``{key}`` directive.

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
Chord Notepad reads UTF-8 text files. A file in another encoding (an older
Windows file with accented letters, say) won't open; save it as UTF-8 in
another editor first.

.. only:: desktop

   **Check the file extension:**
   While Chord Notepad can open any text file, if the file has a strange extension,
   you might need to select "All Files" in the Open dialog.

.. only:: android

   **Check the file type:**
   The file picker in **☰ → Open…** lists every file, so a song with an
   unusual extension still shows up and opens as text. A file that isn't
   plain text (a PDF or a word-processor document, say) won't open as a
   song: copy its text into a new song instead.

.. only:: desktop

   **Open/Save dialog looks different on Linux:**
   On Linux, Chord Notepad uses your desktop's own file dialog (through the
   XDG Desktop Portal) when one is available, and its built-in dialog
   otherwise. The Flatpak version always goes through the portal, since that's
   the only way it can reach your files. If the desktop dialog misbehaves, you
   can force the built-in one by starting the app with the environment variable
   ``CHORD_NOTEPAD_FILE_DIALOG=tk`` (or ``CHORD_NOTEPAD_FILE_DIALOG=portal`` to
   force the desktop one).


Common Mistakes
===============

Forgetting to Save
------------------

.. only:: desktop

   The asterisk (*) in the title bar indicates unsaved changes. Save regularly
   with Ctrl+S.

.. only:: android

   A dot (•) after the song's title in the app bar means there are unsaved
   changes. Save regularly with the Save button (the disk icon) in the app
   bar, or Ctrl+S on a hardware keyboard.

   If Android closes Chord Notepad while it's in the background, your unsaved
   text is still there when you come back. That's a safety net, not a save:
   swiping the app away from the recent apps screen drops it.

Using Wrong Notation Toggle
---------------------------

If your chords aren't detected, check that the notation toggle (AB/Do) matches
what you're typing. European notation won't be detected if American is selected,
and vice versa.

Editing During Playback
-----------------------

.. only:: desktop

   You can't edit while playing - the editor is locked. Stop playback first
   (click ⏹), then make your changes.

.. only:: android

   The Play tab is read-only. Switch to the Edit tab (this stops playback) to
   make your changes.

Copy-Pasting Without Checking
-----------------------------

When you paste, Chord Notepad turns non-breaking spaces into plain spaces,
drops invisible zero-width characters and fixes Windows line endings, so chords
copied from a web page usually come through as they are. If pasted chords
aren't detected, check that they're separated by spaces rather than dashes or
other punctuation, and that the line isn't mostly lyrics or other words. If
that doesn't help, retype them.

Loops Shown in Red
------------------

A loop has to come after its label, because it repeats a section that has just
played. A ``{loop: b}`` above its ``{label: b}`` is shown in red and ignored, and
so is a loop to a label that doesn't exist (check the spelling and the case).
This also means two loops can't keep sending each other back forever. A label
name can be used once; a second ``{label}`` with the same name is red too.

A huge loop count is cut short: a song stops after 5,000 chords once its loops
are played out.

Getting Help
============

**Check this guide first:**
Most questions are answered in :doc:`writing_chords`, :doc:`directives`, or
:doc:`playback`.

.. only:: desktop

   **Use the Chord Identifier:**
   If you're not sure how to write a chord, use Tools → Identify Chord to build
   it from notes.

.. only:: android

   **Use the Chord Identifier:**
   If you're not sure how to write a chord, use **Identify** in the Edit ribbon to
   build it from notes.

.. only:: desktop

   **Try things out:**
   Invalid input is handled safely. You can click chords and test different
   options without risk.

.. only:: android

   **Try things out:**
   Invalid input is handled safely. You can tap chords and test different
   options without risk.

**Report a bug or ask a question:**
Chord Notepad is open source. If you hit a bug, have a chord that should be
recognized but isn't, or want to suggest a feature, open an issue on GitHub:
https://github.com/chibicitiberiu/chord-notepad/issues
