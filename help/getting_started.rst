===============
Getting Started
===============

This guide will walk you through your first few minutes with Chord Notepad.
By the end, you'll know how to write chords, play them back, and save your work.

Opening the Application
-----------------------

.. only:: desktop

   Launch Chord Notepad like any other application. The first time, a short
   **Quick Start** tour opens: seven pages with the main ideas and a small
   example on each. Clear **Don't show this again on startup** if you don't
   want it to come back; you can always reopen it from **☰ → Help → Quick
   start**.

   .. platform-figure:: quick-start
      :platforms: desktop
      :alt: The Quick Start tour on page 1 of 7: a welcome text, a short song
            with blue chords over the lyrics, the Don't show this again box,
            and the Previous, Next and Close buttons.

      The first page of the Quick Start tour.

   After the tour you get an empty document in the **Edit** workspace, with a
   toolbar across the top, a narrow rail of icons and the Directives sidebar
   on the left, a large text area in the middle, and a status bar along the
   bottom -- see the next section for a labelled tour.

.. only:: android

   Open Chord Notepad like any other app. The first time, a short **Quick
   Start** tour opens: seven pages with the main ideas and a small example on
   each. Tap **✕** at the top to close it from any page. Clear **Show at
   startup** at the bottom if you don't want it to come back; you can always
   reopen it from **☰ → Quick start**. The tour doesn't
   open when you start the app by opening a song from another app.

   .. platform-figure:: quick-start
      :platforms: android
      :alt: The Quick Start tour on page 1 of 7: a welcome text, a short song
            with blue chords over the lyrics, the Show at startup box, and the
            Previous and Next buttons.

      The first page of the Quick Start tour.

   After the tour you get a new, empty song in the **Edit** tab, ready for
   typing. Songs you open later start in the **Play** tab instead. Everything
   that isn't on the screen is in the menu behind the **☰** button at the top
   left.

The Main :plat:`Window|Screen`
------------------------------

.. only:: desktop

   .. platform-figure:: main-window-labeled
      :platforms: desktop
      :alt: The Chord Notepad window with numbered callouts on the menu bar,
            toolbar controls, text editor, and status bar.
      :align: center
      :width: 100%

      The main window at a glance.

   #. **Edit and Play tabs** -- switch between writing and listening
      (Ctrl+1, Ctrl+2). Play shows the player bar and the chord sheet.
   #. **☰** -- the main menu: New, Open, Save, Export MIDI, Settings, Help and
      more. **☰ → Show menu bar** adds a classic File, Edit, View, Playback,
      Tools and Help menu bar, which holds every command.
   #. **Rail** -- opens the Directives sidebar, the Chord identifier and
      Settings.
   #. **Toolbar** (Edit only) -- Undo and Redo, Transpose, Convert, the
      **AB / Do** switch (American or European note names; roman numerals
      work in either; see :doc:`writing_chords`), the chord sheet button, and
      **Play** and **Stop**.
   #. **Text editor** -- your workspace. Type here as in any text editor; Chord
      Notepad colours what you write:

      * **Blue, underlined** = valid chord (plays, and is clickable)
      * **Gray, underlined** = something that looks like a chord but isn't
      * **Gray** = a ``//`` comment (never plays)
      * **Purple** = a valid ``{directive}``; **red** = an invalid one

   #. **Status bar** -- messages, playback state, the cursor position and the
      song's notation.

   The tempo, key, time signature, speed, voicing and instrument controls are
   in the player bar of the Play workspace, described in :doc:`interface`.

.. only:: android

   The screen has two tabs at the top. **Edit** is for writing:

   .. platform-figure:: main-edit-labeled
      :platforms: android
      :alt: The Edit tab with numbered callouts: 1 the menu button, 2 the song
            title, 3 the Edit and Play tabs, 4 Save, 5 the Edit ribbon, 6 the
            song text.

      The Edit tab.

   **Play** is for listening. Here the same song is playing:

   .. platform-figure:: main-play-labeled
      :platforms: android
      :alt: The Play tab while a song plays, with numbered callouts: 1 the menu
            button, 2 the song title, 3 the tabs, 4 Save, 6 the song text with
            the chord that's playing in yellow, 7 the player, 8 the chord sheet.

      The Play tab, while a song plays.

   #. **☰** -- opens the drawer: New song, Open…, your recent songs, Save as…,
      Export MIDI…, and below them Settings, Examples, User guide, Quick start
      and About.
   #. **Song title** -- shows a • when there are unsaved changes. Tap it to
      rename the song.
   #. **Edit and Play tabs** -- switch between writing and listening. Switching
      to Edit stops playback.
   #. **Save** -- the disk icon at the right end of the bar.
   #. **Edit ribbon** (Edit tab only) -- Undo and Redo, ＋ Insert, Transpose,
      Identify, the **AB / Do** notation switch and **Convert**. Drag it
      sideways when it doesn't fit on the screen.
   #. **Text** -- your song. In Edit, tap to place the cursor and type as in
      any text editor. In Play the text is frozen, and a small marker, the
      **playhead**, shows where playback starts. Chord Notepad colours what you
      write:

      * **Blue, underlined** = valid chord (plays when you tap it in the Play tab)
      * **Gray, underlined** = something that looks like a chord but isn't
      * **Gray** = a ``//`` comment (never plays)
      * **Purple** = a valid ``{directive}``; **red** = an invalid one

   #. **Player** (Play tab only) -- the song's tempo, time signature and key,
      the Voicing and Instrument buttons, ⏮, the big ▶/❚❚, the metronome, the
      speed and the chord sheet button. The status line at the bottom shows the
      bar and the chord that's playing.
   #. **Chord sheet** (Play tab only) -- the song's chords drawn as a piano
      roll, on a staff, as chord diagrams or as tab. The ▭ button in the player
      shows or hides it. See :doc:`chord_sheet`.

Every control is described in full in :doc:`interface`.

Your First Chord Sheet
----------------------

Let's create a simple chord progression:

.. only:: desktop

   1. Click in the text area (the **Edit** workspace; a new document opens
      there)
   2. Type: ``C  Am  F  G``
   3. Each chord turns blue when recognized

.. only:: android

   1. Make sure you are in the **Edit** tab (a new song already is), then tap in
      the text area. The keyboard opens.
   2. Type: ``C  Am  F  G``
   3. Each chord turns blue when recognized

   .. platform-figure:: edit-keyboard
      :platforms: android
      :alt: A new, untitled song in the Edit tab with the keyboard open. The
            text reads C Am F G, each chord blue and underlined.

      A new song after typing four chords. The • after "Untitled" means it
      isn't saved yet.

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

   1. Click the **Play** button (▶) in the toolbar (callout **4** above), or
      press **F5**. Playback starts at the **playhead**, the small marker
      before the first chord.
   2. Listen as each chord plays in sequence
   3. Watch the **yellow highlight** move through your chords
   4. Click **Stop** (⏹) when you're done

   Switch to the **Play** workspace to see the player bar and the chord
   sheet while it plays:

   .. platform-figure:: play-window-labeled
      :platforms: desktop
      :alt: The Play workspace while a song plays, with numbered callouts on
            the player bar and the chord sheet.

      The Play workspace. 1 the song's values, 2 back to the start, 3 play and
      pause, 4 stop, 5 the timeline, 6 the position, 7 voicing, 8 instrument,
      9 speed, 10 metronome, 11 volume, 12 the chord sheet's views.

.. only:: android

   1. Switch to the **Play** tab. The keyboard closes and the player appears at
      the bottom.
   2. Tap the big **▶** button. Playback starts at the playhead, the small
      marker before the first chord. (A ring spins around the button for a
      moment while the song is prepared.)
   3. Listen as each chord plays in sequence
   4. Watch the **yellow highlight** move through your chords
   5. Tap **❚❚** to pause, or **⏮** to stop and go back to the first chord

   .. platform-figure:: player-labeled
      :platforms: android
      :alt: The player while a song plays, with numbered callouts: 1 the song
            pill reading 90, 3/4, G; 2 Voicing, greyed out; 3 Instrument; 4 back
            to the start; 5 pause; 6 the metronome, switched on; 7 speed, with a
            1.25x badge; 8 the chord sheet button, switched on; 9 the status
            line reading Bar 6/66, Playing Em.

      The player. 1 song pill, 2 Voicing, 3 Instrument, 4 back to the start,
      5 play / pause, 6 metronome, 7 speed, 8 chord sheet, 9 status line.

.. only:: desktop

   You can also click any single chord to hear it on its own, even while a song is
   playing: the playhead moves there, and the next ▶ starts from that chord.
   :doc:`playback` covers playing from the cursor, looping sections, and
   the metronome.

.. only:: android

   In the Play tab you can also tap any single chord to hear it on its own: the
   playhead moves there and the chord plays, and the next ▶ starts from there.
   If a song is already playing, tapping a chord jumps playback to it.
   :doc:`playback` covers playing from the playhead, looping sections, and the
   metronome.

Adjusting the Tempo
-------------------

.. only:: desktop

   There are two separate tempo controls, both in the Play workspace's player
   bar: the tempo, under the song's name, and the speed button:

   .. platform-figure:: speed-controls
      :platforms: desktop
      :alt: The speed popup: a number box reading 100, a slider, six presets
            and a Reset button.
      :align: center

      The speed popup.

.. only:: android

   There are two separate tempo controls, both in the Play tab's player:

.. only:: desktop

   #. **BPM** -- the song's *base* tempo in beats per minute. This is what a
      ``{bpm: ...}`` directive sets, and the number written on the page. Drag it,
      click to type an exact value, or scroll to nudge it (default 120).
   #. **Speed %** -- a *multiplier* applied on top of the BPM, a practice knob.
      Click the speed button for a slider, a box and presets. ``100%`` plays at
      the written tempo; ``50%`` plays it at half speed without
      changing the underlying BPM. Unlike the BPM, this one stays adjustable while
      a song is playing, so you can slow a tricky passage down on the fly.

.. only:: android

   #. **Tempo** -- the song's *base* tempo in beats per minute. This is what a
      ``{bpm: ...}`` directive sets, and the number written on the page. The
      song pill at the top of the player (it reads something like
      "𝄞 90 · 3/4 · G") shows it. Tap the pill to open **Playback
      settings**:

      .. platform-figure:: song-defaults
         :platforms: android
         :alt: The Playback settings sheet. Tempo shows 90 bpm, set by
               {bpm: 90} in the song, with an Edit link. Time signature 3/4
               and Key G can be changed because the song has no time or key
               directive. A note says these aren't saved in the song. Write
               into song and Done at the bottom.

         Playback settings for a song that sets its tempo but not its time
         signature or key.

      If the song has a ``{bpm}`` directive, the tempo is shown with "Set by
      ``{bpm: 90}`` in the song"; tap **Edit** to jump to that directive and
      change it. If it hasn't, the tempo is a default you can change right
      there (it starts at the Default BPM from Settings, 120 unless you changed
      it). A default isn't saved with the file unless you
      tap **Write into song**, which adds the missing directives at the top.
   #. **Speed** -- a *multiplier* applied on top of the tempo, a practice knob.
      Tap the **Speed** button in the player and drag the slider (12.5% to 400%),
      or tap **Manual…** to type a value. **Reset** goes back to 100%.
      ``100%`` plays at the written tempo; ``50%`` plays it at half speed
      without changing the underlying tempo. The button shows a badge such as
      "1.25×" while the speed isn't 100%. Unlike the tempo, this one stays
      adjustable while a song is playing, so you can slow a tricky passage down
      on the fly.

      .. platform-figure:: speed-sheet
         :platforms: android
         :alt: The Playback speed sheet at 125 percent: a slider from 25 to
               400 percent, and the Reset, Manual and Done buttons.

         The Speed sheet.

So the actual playback speed is *BPM × %*. See :doc:`directives` for changing
tempo mid-song, and :doc:`interface` for the full behaviour of each control.

Changing the Sound
------------------

.. only:: desktop

   Want a different instrument? In the Play workspace, click the
   **Instrument** button in the player bar (or open **Playback →
   Instrument**) and pick one from any category:

.. only:: android

   Want a different instrument? In the Play tab, tap **Instrument** in the player
   and pick one from any family.

.. only:: desktop

   .. platform-figure:: instrument-menu
      :platforms: desktop
      :alt: The Instrument menu open at the Guitar family, listing its eight
            instruments.
      :align: center
      :width: 90%

      Instruments are grouped by General MIDI category.

   1. Click the **Instrument** button in the player bar
   2. Browse the categories (Piano, Guitar, Strings, ...)
   3. Click an instrument to select it
   4. Play your chords to hear the new sound

.. only:: android

   The sheet lists the 16 General MIDI families (Piano, Guitar, Strings, ...).
   A dot marks the family of the instrument you have now, with its name on the
   right. Tap a family to see its eight instruments, tap one to select it, then
   play your chords to hear the new sound. The ← button goes back to the
   families, and **Done** closes the sheet.

   .. platform-figure:: instrument-programs
      :platforms: android
      :alt: The Instrument sheet open at the Guitar family: eight guitars with
            their program numbers 24 to 31, Steel Guitar selected, a back arrow
            next to the title and a Done button.

      Inside a family. The numbers are the General MIDI program numbers.

.. only:: desktop

   Separately, the **Voicing** button (or the **Playback → Voicing** menu) chooses *how* chords are laid
   out -- piano-style, or a guitar fingering in one of several tunings. Voicing
   and instrument are independent, and both are explained in :doc:`playback`.

.. only:: android

   Separately, the **Voicing** button in the player chooses *how* chords are laid
   out -- piano-style, or a guitar fingering in one of several tunings. Voicing
   and instrument are independent, and both are explained in :doc:`playback`.
   The voicing can't change while a song plays: pause first.

Saving Your Work
----------------

To save your chord sheet:

.. only:: desktop

   1. Press **Ctrl+S** (or go to **☰ → Save**)
   2. Choose where to save the file
   3. Enter a filename. For a new song the box already holds its first line
      of lyrics ("Twinkle, twinkle, little star.txt"), or the name you gave
      it with Rename; a song without lyrics starts as "Untitled.txt".
   4. Click Save

.. only:: android

   1. Tap the **Save** button (the disk icon) in the app bar (or press Ctrl+S on a
      hardware keyboard)
   2. For a new song, the system file picker opens: choose where to save it
      (the device's storage, Downloads, Drive, or any other place it offers) and
      enter a filename. The name starts as the song's first line of lyrics
      ("Twinkle, twinkle, little star.txt"), or the name you gave it, or
      "Untitled.txt" for a song without lyrics
   3. Confirm

   A song you saved before is saved in place, without asking. To save a copy
   under another name or in another place, use **☰ → Save as…**. To rename the
   song, tap its title in the app bar.

   If you leave the app with the Back button while there are unsaved changes,
   it asks whether to save them first.

Your chord sheet is saved as a plain text file. You can open it in any text
editor, but only Chord Notepad will play it back.

.. only:: desktop

   .. rubric:: Recovering unsaved work

   While a song has unsaved changes, Chord Notepad keeps a copy of it on
   the side, written a few seconds after you stop typing. If the app crashes
   or the computer shuts down before you save, the copy is still there next
   time: open **☰ → Backups** (also under **File** in the menu bar).
   Each entry shows the song's name and when the copy was written, newest
   first. A song that was never saved or renamed is listed by its first line
   of lyrics ("Twinkle, twinkle, little star, today at 14:32"). Choosing one
   opens the text with unsaved changes. For a song that had been saved
   before, **Save** writes it back to that file; a song that was never saved
   asks for a name, starting from that first line.

   The copy goes away when you save, or when you choose **Don't save** on
   quitting or opening another song. Copies older than 30 days are dropped,
   and only the 20 newest are kept. **Clear backups** at the bottom of the
   list removes them all, after asking (they can't be brought back). A copy that belongs to another Chord Notepad window
   that is still open isn't listed there.

Opening Existing Files
----------------------

To open a saved chord sheet:

.. only:: desktop

   1. Press **Ctrl+O** (or go to **☰ → Open**)
   2. Find your file
   3. Click Open

   Recent files appear in **☰ → Open recent** for quick access.

   You can also drag a song from your file manager and drop it anywhere on
   the Chord Notepad window. It opens just as if you had picked it with
   **Open**: if the current song has unsaved changes you're asked about them
   first, and the file joins **Open recent**. A window holds one song, so if
   you drop several files only the first one opens.

   To open a song as the app starts, give its path on the command line::

      chord-notepad path/to/song.txt

   (From a source checkout: ``python -m chordnotepad_desktop song.txt``.)
   To work on two songs side by side, start Chord Notepad twice.

.. only:: android

   1. Open **☰ → Open…** (or press Ctrl+O on a hardware keyboard)
   2. Pick your file in the system file picker

   Recent songs are listed right in the drawer, under **Recent**; tap one to
   open it.

   You can also open a ``.txt`` song from a file manager or another app: tap
   the file and choose Chord Notepad under **Open with**. Some apps only let
   Chord Notepad read the file; in that case **Save** asks where to save a
   copy, like **Save as…**.

   A song you open any of these ways starts in the Play tab, ready to play.

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
