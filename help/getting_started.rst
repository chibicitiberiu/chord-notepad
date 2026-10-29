===============
Getting Started
===============

This guide will walk you through your first few minutes with Chord Notepad.
By the end, you'll know how to write chords, play them back, and save your work.

Opening the Application
-----------------------

.. only:: desktop

   Launch Chord Notepad like any other application. It opens to an empty document
   (or the last file you had open) with a toolbar across the top, a large text
   area in the middle, and a status bar along the bottom -- see the next section
   for a labelled tour.

.. only:: android

   Open Chord Notepad like any other app. A new song opens in the **Edit** tab,
   an empty text area under the app bar. Songs you saved before open in the
   **Play** tab. The menu is the ☰ button at the top left.

The Main Window
---------------

.. only:: desktop

   .. figure:: /images/main-window-labeled.png
      :alt: The Chord Notepad window with numbered callouts on the menu bar,
            toolbar controls, text editor, and status bar.
      :align: center
      :width: 100%

      The main window at a glance.

   #. **Menu bar** -- File, Edit, View, Playback, Tools, and Help. Everything the
      toolbar does (and more) lives here too.
   #. **Notation toggle (AB / Do)** -- switch the editor between American and
      European note names. Roman numerals work in either mode. See
      :doc:`writing_chords`.
   #. **Tempo controls** -- the base **BPM** and a **speed %** multiplier
      (covered under *Adjusting the Tempo* below).
   #. **Key selector** -- the current key, used to resolve roman numerals like
      ``V`` or ``vi``.
   #. **Time signature** -- beats per bar and the beat unit (4/4, 3/4, 6/8, ...).
   #. **Playback controls** -- the metronome toggle, **Play/Pause** (▶), and
      **Stop** (⏹).
   #. **Text editor** -- your workspace. Type here as in any text editor; Chord
      Notepad colours what you write:

      * **Blue, underlined** = valid chord (plays, and is clickable)
      * **Gray, underlined** = something that looks like a chord but isn't
      * **Gray** = a ``//`` comment (never plays)
      * **Purple** = a valid ``{directive}``; **red** = an invalid one

   #. **Status bar** -- the current file, playback state, and messages.

.. only:: android

   #. **☰ drawer** -- New song, Open…, Recent, Save as…, Export MIDI…, and
      below them Settings, User guide, Quick start and About.
   #. **Song title** -- shows a • when there are unsaved changes. Tap it to
      rename the song.
   #. **Edit and Play tabs** -- Edit is for writing, Play is for listening.
      Switching to Edit stops playback.
   #. **Save** -- the disk icon at the right end of the app bar.
   #. **Edit ribbon** (Edit tab) -- Undo and Redo, ＋ Insert, Transpose,
      Identify, the **AB / Do** notation switch and **Convert**. It scrolls
      sideways when it doesn't fit.
   #. **Text** -- your workspace. In Edit, tap to place the cursor and type as in
      any text editor. In Play, the text is frozen and a small marker, the
      **playhead**, shows where playback starts. Chord Notepad colours what you
      write:

      * **Blue, underlined** = valid chord (plays when you tap it in the Play tab)
      * **Gray, underlined** = something that looks like a chord but isn't
      * **Gray** = a ``//`` comment (never plays)
      * **Purple** = a valid ``{directive}``; **red** = an invalid one

   #. **Player** (Play tab) -- the song's tempo, time signature and key, the
      voicing and instrument pickers, ⏮, the big ▶/⏸, the metronome, the speed
      and the chord sheet button. A status line underneath tells you the bar and
      the chord that's playing.

Every control is described in full in :doc:`interface`.

Your First Chord Sheet
----------------------

Let's create a simple chord progression:

.. only:: desktop

   1. Click in the text area
   2. Type: ``C  Am  F  G``
   3. Each chord turns blue when recognized

.. only:: android

   1. Make sure you are in the **Edit** tab (a new song already is), then tap in
      the text area. The keyboard opens.
   2. Type: ``C  Am  F  G``
   3. Each chord turns blue when recognized

This is the "50s progression," a common chord sequence.

Try adding another line:

.. code-block:: chord

   C  Am  F  G
   C  Am  F  G
   F  G  C

Chord Notepad understands far more than plain triads -- sevenths, extensions,
slash chords, roman numerals, and more. See :doc:`writing_chords` for the full
notation.

Playing Your First Chord
------------------------

Now let's hear it:

.. only:: desktop

   1. Click the **Play** button (▶) in the toolbar (callout **6** above)
   2. Listen as each chord plays in sequence
   3. Watch the **yellow highlight** move through your chords
   4. Click **Stop** (⏹) when you're done

.. only:: android

   1. Switch to the **Play** tab
   2. Tap the big **▶** button in the player at the bottom. Playback starts at the
      playhead, the small marker before the first chord.
   3. Listen as each chord plays in sequence
   4. Watch the **yellow highlight** move through your chords
   5. Tap **⏸** to pause, or **⏮** to stop and go back to the first chord

.. only:: desktop

   You can also click any single chord to hear it on its own, even while a song is
   playing. :doc:`playback` covers playing from the cursor, looping sections, and
   the metronome.

.. only:: android

   In the Play tab you can also tap any single chord to hear it on its own: the
   playhead moves there and the chord plays. If a song is already playing, tapping
   a chord jumps playback to it. :doc:`playback` covers playing from the playhead,
   looping sections, and the metronome.

Adjusting the Tempo
-------------------

.. only:: desktop

   There are two separate tempo controls, side by side:

   .. figure:: /images/speed-controls-labeled.png
      :alt: The Speed controls: 190 bpm labelled 1, and 100% labelled 2.
      :align: center

      The two tempo controls.

.. only:: android

   There are two separate tempo controls:

.. only:: desktop

   #. **BPM** -- the song's *base* tempo in beats per minute. This is what a
      ``{bpm: ...}`` directive sets, and the number written on the page. Drag it,
      click to type an exact value, or scroll to nudge it (default 120).
   #. **Speed %** -- a *multiplier* applied on top of the BPM, a practice knob.
      ``100%`` plays at the written tempo; ``50%`` plays it at half speed without
      changing the underlying BPM. Unlike the BPM, this one stays adjustable while
      a song is playing, so you can slow a tricky passage down on the fly.

.. only:: android

   #. **Tempo** -- the song's *base* tempo in beats per minute. This is what a
      ``{bpm: ...}`` directive sets, and the number written on the page. If the
      song has no ``{bpm}`` directive, tap the song pill at the bottom of the Play
      tab (it reads something like "𝄞 90 · 3/4 · G") to open **Song defaults** and
      change the tempo there (the default is 120). It isn't saved with the file
      unless you tap **Write into song**.
   #. **Speed** -- a *multiplier* applied on top of the tempo, a practice knob.
      Tap the **Speed** button in the player and drag the slider (25% to 400%), or
      tap **Manual…** to type a value. ``100%`` plays at the written tempo; ``50%``
      plays it at half speed without changing the underlying tempo. The button
      shows a badge such as "1.25×" while the speed isn't 100%. Unlike the tempo,
      this one stays adjustable while a song is playing, so you can slow a tricky
      passage down on the fly.

So the actual playback speed is *BPM × %*. See :doc:`directives` for changing
tempo mid-song, and :doc:`interface` for the full behaviour of each control.

Changing the Sound
------------------

.. only:: desktop

   Want a different instrument? Open the **Playback → Instrument** menu and pick
   one from any category:

.. only:: android

   Want a different instrument? In the Play tab, tap **Instrument** in the player
   and pick one from any family.

.. only:: desktop

   .. figure:: /images/instrument-menu.png
      :alt: The Playback menu open at the Instrument submenu, listing categories
            such as Piano, Organ, Guitar, Bass, Strings, and more.
      :align: center
      :width: 90%

      Instruments are grouped by General MIDI category.

   1. Go to the **Playback** menu
   2. Open **Instrument** and browse the categories (Piano, Guitar, Strings, ...)
   3. Click an instrument to select it
   4. Play your chords to hear the new sound

.. only:: android

   The sheet lists the 16 General MIDI families (Piano, Guitar, Strings, ...).
   Tap a family to see its eight instruments, tap one to select it, then play your
   chords to hear the new sound. The ← button goes back to the families.

.. only:: desktop

   Separately, the **Playback → Voicing** submenu chooses *how* chords are laid
   out -- piano-style, or a guitar fingering in one of several tunings. Voicing
   and instrument are independent, and both are explained in :doc:`playback`.

.. only:: android

   Separately, the **Voicing** button in the player chooses *how* chords are laid
   out -- piano-style, or a guitar fingering in one of several tunings. Voicing
   and instrument are independent, and both are explained in :doc:`playback`.

Saving Your Work
----------------

To save your chord sheet:

.. only:: desktop

   1. Press **Ctrl+S** (or go to File → Save)
   2. Choose where to save the file
   3. Enter a filename
   4. Click Save

.. only:: android

   1. Tap the **Save** button (the disk icon) in the app bar (or press Ctrl+S on a
      hardware keyboard)
   2. For a new song, the system file picker opens: choose where to save it
      (Downloads, Drive, or any document provider) and enter a filename
   3. Confirm

   To save a copy under another name or location, use **☰ → Save as…**. To rename
   the song, tap its title in the app bar.

Your chord sheet is saved as a plain text file. You can open it in any text
editor, but only Chord Notepad will play it back.

Opening Existing Files
----------------------

To open a saved chord sheet:

.. only:: desktop

   1. Press **Ctrl+O** (or go to File → Open)
   2. Find your file
   3. Click Open

   Recent files appear in the **File → Recent Files** menu for quick access.

.. only:: android

   1. Open **☰ → Open…** (or press Ctrl+O on a hardware keyboard)
   2. Pick your file in the system file picker

   Recent songs are listed right in the drawer, under **☰ → Recent**. A song you
   open this way starts in the Play tab.

Next Steps
----------

For more details, see:

* :doc:`writing_chords` - Learn all the chord types you can write
* :doc:`directives` - Control tempo, time signature, and create song sections
* :doc:`playback` - Explore different voicings and instruments

.. only:: desktop

   * :doc:`shortcuts` - Speed up your workflow with keyboard shortcuts

.. only:: android

   * :doc:`shortcuts` - Keyboard shortcuts for an attached hardware keyboard

Practice Exercise
-----------------

Try writing this simple song structure:

.. code-block:: chord

   // Verse
   G  D  Em  C
   G  D  C

   // Chorus
   Em  C  G  D
   Em  C  G

Try playing it at different tempos, or with different instruments.
