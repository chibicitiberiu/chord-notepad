==================
The User Interface
==================

:plat:`This section covers all the menus, toolbars, and special tools in Chord Notepad.|This section covers every part of the screen, the drawer, and the special tools in Chord Notepad.|This section covers every part of the screen, the menu, and the special tools in Chord Notepad.`


.. only:: desktop

   The Window
   ==========

   The window has two workspaces, **Edit** and **Play**, chosen with the two
   tabs at the top left (**Ctrl+1** and **Ctrl+2**). The song's name is at
   the right of the same strip, with a • after it while there are unsaved
   changes, and the **☰** button next to it opens the menu. The window
   remembers its size and position; it always starts in Edit.

   .. platform-figure:: main-window-labeled
      :platforms: desktop
      :alt: The Edit workspace with numbered callouts: 1 the Edit and Play
            tabs, 2 the ☰ menu, 3 the rail, 4 the toolbar, 5 the text, 6
            the status bar.

      The Edit workspace. 1 Edit and Play tabs, 2 the ☰ menu, 3 the rail,
      4 the toolbar, 5 the text, 6 the status bar.

   **Edit** is for writing. Along the top is a toolbar, along the left edge a
   narrow **rail** of icons that open the sidebars, and in the middle the
   text. The toolbar's **Play** and **Stop** buttons start and stop the song
   without leaving Edit (the text is read-only until it stops), and **F9**
   shows the chord sheet under the text.

   **Play** is for listening. The **player bar** replaces the toolbar, the
   text is frozen so a stray key can't change it, and the chord sheet is
   always under it:

   .. platform-figure:: play-window-labeled
      :platforms: desktop
      :alt: The Play workspace while a song plays, with numbered callouts on
            the player bar: 1 the song's values, 2 back to the start,
            3 play and pause, 4 stop, 5 the timeline, 6 the position, 7 the
            voicing, 8 the instrument, 9 the speed, 10 the metronome, 11 the
            volume, and 12 the chord sheet's views.

      The Play workspace while a song plays.

   The pencil in the corner of the text, or **Ctrl+1**, goes back to Edit.

   The Edit Toolbar
   ================

   From the left:

   * **Undo** and **Redo** (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z). They are greyed
     out when there is nothing to undo or redo.
   * **Transpose** (Ctrl+T) opens the Transpose dialog; see :doc:`transpose`.
   * **Capo** opens Suggest Capo, which lists the capo positions with the
     chord shapes they give, the easiest first; the same as
     :menuselection:`Tools --> Suggest capo...` (see :doc:`chord_sheet`).
   * **Convert** converts the song between American and European chord
     names; see :doc:`transpose`.
   * The **AB | Do** switch, described below.
   * At the right, **Chord sheet** shows or hides the chord sheet under the
     text (F9; see :doc:`chord_sheet`), and **Play** and **Stop** work as
     they do in the player bar.

   Notation Switch (AB | Do)
   -------------------------

   .. platform-figure:: notation-toggle
      :platforms: desktop
      :alt: The AB and Do buttons, AB selected.

      The notation switch.

   Two buttons let you switch notation systems:

   * **AB** - American notation (C, D, E, F, G, A, B)
   * **Do** - European notation (Do, Re, Mi, Fa, Sol, La, Si)

   Clicking one switches the notation the song you have open is *read* in,
   without changing a letter of your text (to rewrite the chords, use
   **Convert**). A new song starts in the notation set in Settings. An opened
   song, or one you paste into an empty document, starts in the notation its
   chords are written in (see :ref:`notation-autodetect`). The status bar
   shows the notation at its right end.

   The Player Bar
   ==============

   The player bar is the top of the Play workspace. Left to right, it holds
   the transport, the song's own values with the timeline under them, and
   the sound.

   .. _desktop-song-values:

   Tempo, Key and Time Signature
   -----------------------------

   In the middle, above the timeline, are the song's tempo, time signature
   and key, for example **90 bpm · 3/4 · G**. They are what the song starts with.

   * When the song sets one with a directive before its first chord, such as
     ``{bpm: 90}``, ``{key: D}`` or ``{time: 6/8}``, the value is the song's
     and clicking it takes you to that directive in the text. Rest the
     pointer on it to see which directive sets it ("Set by {bpm: 90} in the
     song"); edit that directive to change it. A later change, like a second
     ``{bpm}`` halfway through, doesn't show here: the bar keeps the
     starting value.
   * A value the song doesn't set comes from the defaults in |settings|, and
     you can change it here. The change is for the current song only: it
     isn't saved with the file or in Settings, and **New** and **Open** start
     again from the defaults. Only Settings changes the defaults; opening a
     song doesn't.

   **Tempo** is in beats per minute (20-400):

   * **Drag left or right** to change it
   * **Click** to type an exact value, then Enter
   * **Middle-click** to reset it to the default (120 BPM)
   * **Scroll** with the mouse wheel to step by 1

   .. platform-figure:: key-picker
      :platforms: desktop
      :alt: The song's values with the key picker open under the key: the
            twelve notes from C to B, with C selected.

      The key picker.

   **Key** and **Time signature** open a small picker when you click them
   (or, with the keyboard, Tab to the value and press Enter or Space): a
   grid of keys, or the common time signatures and a beats box over a beat
   unit. The keys shown match the song's notation
   (C-D-E-F-G-A-B or Do-Re-Mi-Fa-Sol-La-Si), and the key also gives the key
   signature in the Staff view. Beats go from 1 to 16 and the beat unit is 1,
   2, 4, 8 or 16: 4/4 is standard time, 3/4 a waltz, 6/8 compound duple. The
   key tells Chord Notepad how to read roman numerals such as ``V`` or
   ``vi``.

   While a song plays, the tempo is read-only and shows the **effective
   tempo**: what is playing right now, including changes from ``{bpm}``
   directives in the song. The key and time signature are locked. When you
   pause or stop, they go back to the song's starting values and can be
   changed again unless the song sets them. A value you change while paused
   is heard when you resume: playback starts again from the chord where you
   paused.

   Transport
   ---------

   **⏮** goes back to the start of the song, and keeps playing if the song was
   playing. **▶** plays from the **playhead**, the small marker in the text
   (see below); it shows ⏸ while playing, and then pauses. **Shift+click**
   on ▶ plays from the text cursor instead. **⏹** stops playback, puts the
   playhead back on the first chord and silences any notes still ringing.
   The keyboard has **F5** for play and pause and **Shift+F5** for stop and
   rewind.

   The **position**, for example ``5:2``, is the bar and beat of the song,
   counted from the top.

   The **timeline** is a slim bar with one segment for each labelled section
   of the song, and a gap between sections. Rest the pointer on a segment to
   see its name and the bar the pointer is over; **click** or **drag** to
   move there. While a song plays, playback jumps to the spot.

   The Playhead
   ------------

   In the text, a small marker (a bar with a diamond on top) shows where
   playback starts. **Click a chord** to hear it: the marker moves there
   and the chord sounds, and the next **▶** starts from that chord.
   **Shift+click** it to hear it rolled, one note at a time from the lowest
   up. If the song is already playing, clicking a chord jumps playback to
   it. Dragging
   on the timeline or pressing ⏮ moves the marker too.

   A chord in the text works like a link: every click plays it, however fast
   you click, and clicking never selects it. The text cursor still goes where
   you clicked, so you can type right there. To select a chord's text, hold
   **Alt**: Alt+click puts the cursor in it, Alt+double-click selects the
   chord, and Alt+drag selects from there. Nothing plays while Alt is held,
   and the pointer over a chord turns back into the text cursor. A
   Shift+click on a chord leaves the selection as it was.

   Some Linux desktops move the whole window when you Alt+drag in it (Xfce
   and MATE do out of the box; KDE Plasma 6 and GNOME use the Meta or Super
   key instead). There, either pick another key for moving windows in the
   desktop's settings, or start the drag just outside the chord: a drag that
   starts on other text selects across chords as usual.

   Voicing and Instrument
   ----------------------

   .. platform-figure:: voicing-menu
      :platforms: desktop
      :alt: The Voicing menu under the player bar: Piano checked, five
            guitar and ukulele tunings, four ensembles, and Edit voicings.

      The Voicing menu.

   The **Voicing** button (with a note icon and its name, such as *Piano*)
   chooses *how* each chord's notes are picked: which notes sound, in which
   octaves, and on a fretted instrument, which shape you play. The
   **Instrument** button beside it chooses the sound you hear. In Edit, both
   are also in the chord sheet's header, since you usually change them
   together. The voicings:

   * **Piano** - Keyboard-style voicing (default)
   * **Guitar (Standard - EADGBE)** - standard tuning
   * **Guitar (Drop D)** - DADGBE tuning
   * **Guitar (DADGAD)** - Celtic tuning
   * **Guitar (Open G)** - Blues/slide tuning
   * **Ukulele** - standard G C E A (re-entrant) tuning
   * **Choir (SATB)** - four-part mixed choir
   * **Male Choir (TTBB)** - four-part male choir
   * **Treble Choir (SSA)** - three-part treble choir
   * **String Quartet** - two violins, viola, cello
   * Any custom voicings you've added in Settings -- a fretted instrument,
     a piano or an ensemble

   **Edit voicings...** at the bottom opens Settings on the Voicings page. The
   voicing can't change while a song plays; the button is greyed out and its
   tooltip says why. See :doc:`fretted` for how the fretted-instrument
   voicings (guitar and beyond) work and how to define your own, and
   :doc:`ensembles` for the same on ensembles.

   .. platform-figure:: instrument-menu
      :platforms: desktop
      :alt: The Instrument menu under the player bar, with the Guitar family
            open to its eight instruments.

      The Instrument menu, with the Guitar family open.

   The **Instrument** button (a guitar icon, or its name when there is room)
   opens a menu organized by General MIDI family: Piano, Chromatic
   Percussion, Organ, Guitar, Bass, Strings, Ensemble, Brass, Reed, Pipe,
   Synth Lead, Synth Pad, Synth Effects, Ethnic, Percussive and Sound
   Effects. Each family opens to its eight instruments. A dot marks the
   family of the instrument in use.

   Speed, Metronome and Volume
   ---------------------------

   .. platform-figure:: speed-controls
      :platforms: desktop
      :alt: The speed popup: a number box reading 100, a slider, the presets
            50, 75, 90, 100, 125 and 150 percent, and a Reset button.

      The speed popup.

   The **speed** button (``100%`` by default) is a multiplier that scales the
   playback speed on top of the tempo, whether you set that by hand or with a
   directive. Use it as a "practice slowdown" knob. Click it to open a popup
   with a slider (12.5% to 400%, with 100% in the middle), a box to type a
   value, six presets and **Reset**. In the box you can write ``150``,
   ``150%``, ``87.5`` or ``1.5x``. On the button itself, the mouse wheel steps
   by 5% and a middle-click goes back to ``100%``. **Ctrl+]** and **Ctrl+[**
   step the speed up and down, and **Ctrl+Backslash** resets it.
   At any speed other than 100%, the tempo above the timeline is followed by
   the tempo you actually hear, in grey: ``95 bpm → 143 bpm (150%)``.

   Unlike the tempo, the speed **stays editable during playback** and takes
   effect immediately on the next chord. For example, set it to ``50%`` to
   play a song at half speed without changing its tempo.

   The **metronome** button (**Ctrl+M**) arms a click track that sounds
   *during song playback*.

   * High wood-block on the downbeat, low one on offbeats
   * The click is scheduled by the playback engine itself, so it always lines
     up with the song's beats — including changes made by ``{time: X/Y}`` and
     ``{bpm: ...}`` directives mid-song
   * Toggle it on, then press Play. Turning it off does not pause playback,
     it just silences the click
   * Always starts off when you open the app
   * Too quiet or too loud? Set its level with the **Metronome** slider
     under the volume button

   The **volume** button opens two sliders and a mute button. The **Music**
   slider sets how loud the chords are, and the **Metronome** slider under
   it sets how loud the click is, each from 0% to 100% (the default). Each
   leaves the other alone, so you can turn the music down and keep the
   click loud. Both work while a song plays and are remembered. **Mute**
   silences both, and isn't remembered. The mouse wheel over the volume
   button steps the music by 5%.

   When the window is narrow, the bar gives up space in a fixed order: the
   timeline shrinks first, then the voicing and instrument buttons show only
   their icons, then the timeline shrinks further. The song's values always
   stay.

   The Menus
   =========

   The **☰** button at the top right opens the main menu:

   .. platform-figure:: app-menu
      :platforms: desktop
      :alt: The ☰ menu: New, Open, Open recent, Backups, Save, Save as, a
            zoom control, Export MIDI, Export audio, Export PDF, Show menu
            bar, Dark theme, Settings, Help and Quit.

      The ☰ menu.

   **New**, **Open...**, **Open recent**, **Backups**, **Save**, **Save as...**
      The file commands, described below.

   **Zoom**
      The − and + buttons scale the whole window in steps (Ctrl+Alt+=,
      Ctrl+Alt+Minus; Ctrl+Alt+0 for 100%), and the corner button switches
      to full screen (F11). This is separate from the text size.

   **Export MIDI...**, **Export audio...**, **Export PDF...**
      Described under File Menu.

   **Show menu bar**
      Shows a classic menu bar (below). It's off by default.

   **Dark theme** (Ctrl+Shift+L)
      Switches between the light and the dark look. The same setting is
      **Theme** in Settings, which can also follow the system.

   **Settings...** (Ctrl+,)
      Opens the Settings window; see :doc:`settings`.

   **Help**
      The User Guide, Quick Start, Keyboard shortcuts, Open Source Licences and
      About, described under Help Menu.

   **Quit** (Ctrl+Q)
      Closes Chord Notepad. You'll be asked about unsaved changes.

   The Menu Bar
   ------------

   Everything the ☰ menu does, and everything else, is also in a classic menu
   bar with File, Edit, View, Playback, Tools and Help. It stays hidden to
   leave the room to the song. Show it for good with **☰ → Show menu bar**,
   or just reach into it: tap **Alt** to show it until you are done, press
   **F10** to open its first menu, or **Alt+F**, **Alt+E**, **Alt+V**,
   **Alt+P**, **Alt+T** and **Alt+H** to open one directly. On macOS the menus
   are in the system menu bar and always shown.

   .. platform-figure:: menu-bar
      :platforms: desktop
      :alt: The menu bar with the View menu open.

      The menu bar, with View open.

   The rest of this guide writes a command as *Menu → Item*, for example
   **Playback → Voicing**. Each one is in the menu bar under that name, and
   most are also somewhere in the window.

   File Menu
   ---------

   **New** (Ctrl+N)
      Create a new, empty document. If you have unsaved changes, you'll be asked
      to save them first.

   **Open...** (Ctrl+O)
      Open an existing chord sheet file. Browse to find your file and click Open.

   **Open recent**
      A submenu showing the files you opened or saved lately (10 by default;
      see :doc:`settings`). Two files with the same name show their folders.

   **Backups**
      The copies of unsaved songs that a crash or a shutdown left behind,
      newest first, and **Clear backups** at the bottom. It's greyed out
      when there are none. See :doc:`getting_started`.

   **Save** (Ctrl+S)
      Save the current document. If it's a new file, you'll be asked where to
      save it.

   **Save as...** (Ctrl+Shift+S)
      Save the current document with a new name or location.

   **Export MIDI...**
      Save the song as a standard MIDI file. Opens a save dialog for a ``.mid``
      file containing the same voicings, timing, tempo, and instrument as
      playback, with loops unrolled into their repeats. See
      :doc:`midi_export` for details.

   **Export audio...**
      Save the song as a ``.wav`` file that sounds the way Play does: the
      same voicing, instrument, volume and speed, with the metronome if it's
      on. See :doc:`midi_export`.

   **Export PDF...**
      Save the song's text as a ``.pdf`` file to print or share, with the
      directives written out in grey and the page numbers at the bottom. See
      :doc:`midi_export`.

   **Quit** (Ctrl+Q)
      Close Chord Notepad. You'll be asked to save any unsaved changes.

   Edit Menu
   ---------

   **Undo** (Ctrl+Z)
      Undo your last action. You can undo multiple times to go back through your
      edit history.

   **Redo** (Ctrl+Y or Ctrl+Shift+Z)
      Redo an action you just undid.

   **Cut** (Ctrl+X), **Copy** (Ctrl+C), **Paste** (Ctrl+V)
      The usual clipboard commands, also in the right-click menu of the text.

   **Select All** (Ctrl+A)
      Select all text in the document. The cursor goes to the end, so End or
      Shift+Up carry on from there.

   **Select line** (Ctrl+L)
      Select the line the cursor is on, whole. Press it again to take in the
      next line too.

   **Find...**, **Replace...**, **Find next**, **Find previous**, **Go to line...**
      Ctrl+F, Ctrl+H, F3, Shift+F3 and Ctrl+G: the find bar under the text;
      see :ref:`find-and-replace`.

   **Duplicate line or selection** (Ctrl+D)
      Without a selection, repeats the cursor's line under it. With one,
      puts a copy of the selected text right after it and selects the copy.

   **Delete line** (Ctrl+Shift+K)
      Deletes the line the cursor is on, or every line the selection touches.

   **Move line up**, **Move line down** (Ctrl+Shift+Up, Ctrl+Shift+Down)
      Moves the cursor's line, or the selected lines, past the line above or
      below. Handy for swapping two verses' lines or reordering sections.

   **Toggle comment** (Ctrl+/)
      Puts ``//`` in front of the cursor's line or the selected lines, or
      takes it off again when they are all comments already. Commented lines
      are notes for you: they aren't played. See :doc:`writing_chords`.

   **Indent lines** (Tab), **Unindent lines** (Shift+Tab)
      With a selection over several lines, Tab adds a tab in front of each;
      in a single line it types a tab as usual. Shift+Tab takes one step of
      indentation off the selected lines, or off the cursor's line: a tab, or
      the same number of spaces from every line, so chords stay over the
      words they belong to.

   **Change value...** (Alt+Down)
      Opens the picker of the directive value the cursor is in, as the
      **▾** next to it does (see :ref:`desktop-pickers`). It's greyed out
      when the cursor isn't in a value that has a picker.

   **Overwrite mode** (Insert)
      Typing replaces the character after the cursor instead of pushing it
      along. The status bar shows **OVR** while it is on, and the cursor turns
      into a block. Press Insert again to go back.

   Each of these edits is one step for Undo. While a song plays, the ones
   that change the text are greyed out and the keys show the "Stop playback
   to edit the song" badge, as typing does; Find, Select line and Go to line
   still work.

   The right-click menu of the text has Undo, Redo, Cut, Copy, Paste and
   Select all, then Find, Replace and Go to line, then Toggle comment,
   Duplicate and Delete line.

   .. _find-and-replace:

   Find and Replace
   ----------------

   **Ctrl+F** opens a bar along the bottom of the text, with the cursor in
   its field. If you had selected a word or a few on one line, they are
   already in it. As you type, the next match is selected and every other
   match in the song gets a light green tint; the selected one is a stronger
   green. Next to the field the bar counts them ("3 of 7"), or says **No
   matches** in red.

   * **Enter**, **F3** or the down arrow go to the next match;
     **Shift+Enter**, **Shift+F3** or the up arrow to the previous one. At
     the end of the song the search starts again from the top, and the bar
     says so for a moment ("Continued from the top").
   * **Aa** matches upper and lower case exactly (off, "am" also finds "Am").
   * **W** finds whole words only: with it on, "Am" doesn't find the start of
     "Am7".
   * **Escape**, or the × at the right, closes the bar and puts you back in
     the text, where the match stays selected.

   F3 and Shift+F3 also work with the bar closed: they look for the last
   thing you searched for.

   **Ctrl+H**, or the arrow at the left of the bar, adds a second row for the
   replacement. **Replace** (or Enter in that field) replaces the selected
   match and moves on to the next one; if nothing is selected yet, the first
   press only finds. **Replace all** replaces every match at once, and the
   status bar says how many. Either way, one Undo puts it back. While a song
   plays you can still search, but Replace waits until playback stops. In
   the Play workspace the bar has no Replace row.

   **Ctrl+G** turns the bar into **Go to line**: type a line number and press
   Enter, and the cursor goes to the start of that line.

   When you select a word yourself, say by Alt+double-clicking a chord, the
   same word elsewhere in the song gets a faint grey tint, so you can see at
   a glance where else that chord is. It only counts whole words with the
   same case: selecting "Am" doesn't light up "Am7" or "am".

   View Menu
   ---------

   **Edit** and **Play** (Ctrl+1, Ctrl+2)
      Switch workspace.

   **Directives** (Ctrl+Shift+D) and **Chord identifier** (Ctrl+Shift+I)
      Open the sidebar of that name, or close it when it is already open (see
      below). From the Play workspace they go to Edit first.

   **Chord sheet under the text** (F9)
      Shows or hides the chord sheet under the text in the Edit workspace. In
      Play the sheet is always there. See :doc:`chord_sheet`.

   **Chord sheet view**
      Piano roll, Staff, Fret cards or Tab (Alt+1 to Alt+4), then **Zoom
      in**, **Zoom out** and **Reset zoom (100%)** for the chord sheet's
      drawing, as its **−** / **+** buttons. They have no keys of their own:
      Ctrl+Mouse Wheel over the sheet zooms it too.

   **Word wrap**
      Off (the default), a line longer than the window runs on past its
      right edge, with a scrollbar under the text to reach the rest, so each
      chord line stays over its lyric line. On, long lines wrap at the edge
      of the window, and a chord line that wraps no longer lines up with the
      words under it. Saved for next time; the same setting as **Word wrap**
      in |settings|.

   **Larger text** (Ctrl+Plus), **Smaller text** (Ctrl+Minus), **Reset text size** (Ctrl+0)
      Change the size of the text by 10% steps of the 11-point default. The
      **100%** box in the corner of the text does the same with its − and +
      buttons, and you can also zoom with **Ctrl+Mouse Wheel**. The size
      you pick is remembered, and Settings → General has the font and the
      exact size.

   **Zoom in, Zoom out, Reset zoom (whole window)** and **Full screen**
      As in the ☰ menu.

   **Show menu bar** and **Dark theme**
      As in the ☰ menu.

   Playback Menu
   -------------

   **Play / Pause** (F5), **Stop and rewind** (Shift+F5), **Metronome** (Ctrl+M)
      The player bar's controls, usable from the Edit workspace too.

   **Faster**, **Slower** and **Normal speed (100%)**
      Step the speed by 5% (Ctrl+], Ctrl+[) or put it back to 100%
      (Ctrl+Backslash).

   **Voicing** and **Instrument**
      The two menus described under Voicing and Instrument.

   Tools Menu
   ----------

   **Transpose...** (Ctrl+T)
      Shifts the chords up or down by a number of semitones. See
      :doc:`transpose`.

   **Suggest capo...**
      Lists the capo positions for a fretboard voicing, the easiest first, and
      inserts the ``{capo}`` directive for the one you pick. See
      :doc:`directives`.

   **Convert to American notation**
      Converts all European notation chords (Do, Re, Mi...) in your document to
      American notation (C, D, E...), keeping each chord over its syllable
      (see :doc:`transpose`).

   **Convert to European notation**
      Converts all American notation chords (C, D, E...) in your document to
      European notation (Do, Re, Mi...), keeping each chord over its syllable
      (see :doc:`transpose`).

   **Settings...** (Ctrl+,)
      Opens the Settings window: general preferences, playback and audio
      defaults, and the full voicing editor, on three pages. **Save** at the
      bottom keeps the changes and **Discard** drops them. See
      :doc:`settings`.

   Directives and the chord identifier have no entry here: they live in the
   sidebars, which are in the View menu and on the rail.

   Help Menu
   ---------

   **User guide** (F1)
      Opens this user guide.

   **Quick start**
      Opens the short tour the app shows the first time. It lives under
      **☰ → Help** too.

   **Keyboard shortcuts**
      Opens the shortcuts page of this guide.

   **Open source licences**
      Lists everything this copy of Chord Notepad is built from: the app
      itself, Python, Qt, FluidSynth and the other libraries, the Python packages,
      the sound font, the icons and the user guide's fonts and scripts.
      Select one to see its version, its licence and the full licence text.
      The list matches your build, so the Windows, macOS, Flatpak and snap
      versions each show their own parts; on Linux it also lists the system
      libraries that came with the app.

      Select **Source code** at the top to find out where to get the source
      of each part. Every release on GitHub has, next to the downloads, the
      source of Chord Notepad and of the bundled libraries whose licences
      ask for it (the LGPL, GPL and MPL ones). The Linux download and the
      snap use libraries from Ubuntu: for those, the release has the source
      of the GPL and LGPL ones and lists the others with their versions.

      To run Chord Notepad with your own build of FluidSynth, set the
      environment variable ``CHORD_NOTEPAD_LIBFLUIDSYNTH`` to the full path of
      your FluidSynth library before you start the app. This doesn't work in
      the snap, which sets the variable itself; **Source code** has the
      details. The same page explains how to run with your own Qt.

   **About Chord Notepad**
      Shows information about Chord Notepad:

      * Version number
      * Build information
      * Description of the application
      * Copyright, licence, source code link, and the no-warranty notice

      Its **Open Source Licences** button opens the same list.

   The Rail and the Sidebars
   =========================

   The rail at the left of the Edit workspace has an icon for each sidebar
   and, at the bottom, one for **Settings**. Click an icon to open its
   sidebar next to the text, click it again to close it. Drag the edge
   between a sidebar and the text to resize it; its width is remembered.
   While a song plays or is paused the sidebars can't change the text, and
   their buttons are greyed out.

   The Directives Sidebar
   ----------------------

   .. platform-figure:: directives-palette
      :platforms: desktop
      :alt: The Directives sidebar: tiles for tempo changes, time, key and
            capo, sections, and rest and comment.

      The Directives sidebar (Ctrl+Shift+D).

   The tiles write directives for you, so you don't have to remember the
   exact syntax. Click a tile (or move to it with the arrow keys and press
   Enter or Space) and its directive is inserted at the text cursor as one
   undo step, with its value already selected: type to replace it. Rest the
   pointer on a tile for a tooltip that says what it does.

   * **Tempo:** ``{bpm: 120}``, faster (``+10``) and slower (``-10``), a
     percentage (``50%``), a multiplier (``2x``) and ``reset``
   * **Time, key, capo:** ``{time}``, a major key, a minor key, ``{capo}``
   * **Sections:** ``{label}``, ``{loop}``, a loop with a count of 3, and a
     loop back to the start
   * **Text:** a rest (``NC``) and a ``//`` comment

   A tile fills in something that works where you are: a key in the song's
   notation, a label that isn't used yet, a loop to a label above the
   cursor. See :doc:`directives` for what each one does.

   .. _desktop-pickers:

   Value Pickers
   -------------

   Right after you insert a directive, and whenever you put the cursor in
   one, a small **▾** appears next to its value. Click it (or press
   **Alt+Down**) to change the value without typing: a picker opens with
   the choices that fit that directive, such as the keys, or a number box.
   Enter or a click applies one as a single undo step; Escape closes the
   picker.

   The tempo picker also has a **Tap** button for finding a song's tempo:
   tap it along with the beat (play a recording, or count the song in your
   head) and from the second tap on the box shows the tempo of your last
   taps. Stop for a few seconds and the next tap starts a new count. Nothing
   changes in the song until you press **Apply** or Enter.

   Directive Hints
   ---------------

   While the text cursor is inside a directive, the status bar at the bottom
   of the window shows how that directive is written, for example
   ``{bpm: 120} · {bpm: +10} · {bpm: 50%} · {bpm: 2x} · {bpm: reset}``. It
   works for one you're still typing too: after ``{lo`` it shows the ``{loop}``
   forms, and after a lone ``{`` it lists every directive. If the directive is
   red or faded, the reason comes first, for example "Tempo must be 20-400 —
   {bpm: 120} · …". When the cursor leaves the directive, the status bar shows
   what it showed before. While a song plays, the status bar keeps showing
   playback.

   Rest the mouse pointer on any directive for a moment, and a small card
   under it shows how that directive is written; for a red or faded one, the
   reason comes first.

   The Status Bar
   --------------

   The strip along the bottom shows, on the left, messages ("Opened: ...",
   "Saved: ...", why something was refused) and the song's tempo, time
   signature and key. On the right it shows the line and column of the cursor,
   **OVR** while overwrite mode is on (the Insert key), and the song's
   notation. Thin vertical lines separate the values, and
   each keeps its place and width as the numbers change.

   While a song plays, the left side shows "Playing" and the chord that is
   sounding, with a coloured dot, then the bar ("Bar 2 / 125"), the tempo, the
   time signature and the key in force at that chord, so a key or tempo
   change in the middle of the song shows up as it plays. When the tempo was
   clamped by a relative change, the tempo is tinted and its tooltip says
   where. Paused, the same shows without the dot. The text can't be edited
   until playback stops; if you try, a small red badge at the right says
   "Stop playback to edit the song · Shift+F5 stops".

.. only:: android

   .. _android-app-bar:

   The App Bar
   ===========

   The bar across the top of the screen holds, from left to right:

   * **☰** opens the :plat:`|drawer|menu` (see :ref:`android-drawer` below).
   * **The song title.** A • after the name means there are unsaved changes.
     An untitled song shows "Untitled" until you save it or give it a name.
   * **The Edit and Play tabs.**
   * **Save** (the disk icon). It is greyed out while there are no unsaved
     changes.

   .. only:: not ios

      Tap the title to **Rename** the song. The dialog shows the file's full name
      ("Saved as …"); type the new name without the ``.txt``, which is kept. Some
      storage places (a cloud drive, for example) don't allow renaming. Then the
      app offers to save a copy under the new name instead. That includes songs
      opened from **Downloads** in the file picker: open the same file through
      the device's storage (its Download folder) and it renames in place.

   .. only:: ios

      Tap the title to **Rename** the song. The dialog shows the file's full name
      ("Saved as …"); type the new name without the ``.txt``, which is kept. Songs
      the app keeps itself, such as the examples, and songs saved in the Chord
      Notepad folder in Files, rename in place. A song you picked from another folder
      or a cloud provider may refuse, because the app has no access to that folder.
      Then the app offers to save a copy under the new name instead.

   .. platform-figure:: rename
      :platforms: android
      :alt: The Rename dialog: a text field with Amazing Grace selected, the
            note Saved as "Amazing Grace.txt", and Cancel and Rename buttons.
      :ios-alt: The Rename dialog: a text field holding Amazing Grace with the
                cursor after the name, the note Saved as "Amazing Grace.txt",
                and Cancel and Rename buttons.

      Renaming a song.

   On a phone held sideways, the Edit tab puts a shortened title, the tabs and
   the Edit ribbon on one line, so more of the song fits on the screen. The
   title still shows the • and still opens Rename when you tap it:

   .. platform-figure:: landscape-edit
      :platforms: android
      :alt: A phone held sideways in the Edit tab: one bar with the menu
            button, the song's title, the Edit and Play tabs, a greyed-out Save and the
            Edit ribbon, and the song below it.

      The Edit tab on a phone held sideways.

   The colours follow the system's light or dark theme.

   .. _android-edit-play:

   Edit and Play
   =============

   The two tabs are two modes of the same song. Edit is for writing, Play is for
   listening and practising.

   .. list-table::
      :header-rows: 1
      :widths: 24 38 38

      * -
        - Edit
        - Play
      * - Text
        - Editable. A tap places the cursor and opens the keyboard.
        - Frozen: read-only, and the keyboard stays hidden.
      * - Tap a chord
        - Moves the cursor only. Nothing plays.
        - Moves the playhead there and plays the chord.
      * - Tap elsewhere
        - Moves the cursor.
        - Moves the playhead to the nearest chord. While a song plays, it
          does nothing.
      * - Drag
        - Selects or scrolls, as usual.
        - Scrolls. A drag that starts on the playhead marker moves it chord by
          chord.
      * - Long lines
        - Run on past the screen's edge (unless Word wrap is on): swipe
          sideways for the rest. Typing past the edge brings the cursor into
          view.
        - Run on past the screen's edge (unless Word wrap is on): swipe
          sideways for the rest. The playing chord is kept in view.
      * - Pinch
        - Changes the text size.
        - Changes the text size.
      * - Controls
        - The Edit ribbon under the app bar.
        - The player at the bottom of the screen.
      * - Messages
        - Shown briefly at the bottom of the screen.
        - Shown in the player's status line.
      * - Chord sheet
        - Never shown.
        - Shown (the **▭** button hides it).

   Long lines don't wrap, so each chord line stays over its lyric line however
   narrow the screen. To have them wrap at the screen's edge instead, turn on
   **Word wrap** in ☰ → Settings → General (a chord still never splits across
   two lines, but a wrapped chord line no longer lines up with its lyric).

   Songs you open start in the Play tab, and new songs start in Edit.
   Switching to Edit while a song plays or is paused stops playback. Both tabs keep the same
   scroll position, so you don't lose your place when you switch.

   .. only:: not ios

      Held sideways, the Play tab puts the text on the left and the chord sheet,
      with the player under it, on the right. Drag the handle between the two
      halves to give either side more room (from 30% to 70% of the width); the
      app remembers it. A tablet does the same in landscape. With the chord sheet
      hidden, the text takes the whole width and the player sits at the bottom.

   .. only:: ios

      Held sideways, the Play tab puts the text on the left and the chord sheet,
      with the player under it, on the right. Drag the handle between the two
      halves to give either side more room (from 30% to 70% of the width); the
      app remembers it. An iPad does the same in landscape. With the chord sheet
      hidden, the text takes the whole width and the player sits at the bottom.

   .. platform-figure:: landscape-play
      :platforms: android
      :alt: A phone held sideways in the Play tab while a song plays: the text
            on the left with Em highlighted, and on the right the chord sheet
            with the player below it, a narrow handle between the two halves.

      The Play tab on a phone held sideways.

   .. only:: not ios

      While a song plays, the screen stays on. Playback pauses by itself when you
      leave the app, when another app starts playing sound or a call comes in, and
      when you unplug your headphones.

   .. only:: ios

      While a song plays, the screen stays on. Playback pauses by itself when you
      leave the app.

   .. _android-edit-ribbon:

   The Edit Ribbon
   ===============

   A single row of buttons under the app bar, in the Edit tab:

   .. platform-figure:: edit-ribbon
      :platforms: android
      :alt: The Edit ribbon: Undo, Redo, Insert, Transpose, Capo, Identify, the AB
            and Do switch, Convert, and a chevron at the right edge.
      :ios-alt: The Edit ribbon on an iPhone: Undo, Redo, Find, Insert,
                Transpose, Capo, Identify, and a chevron at the right edge (the
                AB and Do switch and Convert are further right).

      The Edit ribbon.

   * **Undo** and **Redo**. They're greyed out when there is nothing to undo
     or redo.
   * **＋ Insert**, which opens a sheet of directives (see *Insert
     Directive Dialogs* below)
   * **Transpose**, which opens the dialog described in :doc:`transpose`
   * **Capo**, which opens Suggest Capo (see :doc:`chord_sheet`). It looks at
     the selected text, or the whole song when nothing is selected, and puts
     the ``{capo}`` directive at the top or at the start of the selection.
     **＋ Insert → Capo** instead inserts at the cursor, and has a **Suggest**
     button for the same dialog
   * **Identify**, which opens the Chord Identifier (see below)
   * **AB / Do**, the notation the text is read in, for this song only (a new
     song starts in the one set in Settings, an opened one in the one its
     chords are written in)
   * **Convert**, which rewrites every chord and ``{key}`` directive in the
     document into the other notation, keeping each chord over its syllable
     (see :doc:`transpose`), and switches AB / Do to match

   When the buttons don't all fit, drag the ribbon sideways. A **›** at its
   right edge means there are more buttons off screen; tapping it scrolls them
   into view.

   The notation switch and Convert do different jobs. Switching AB / Do changes
   how the editor reads what you type and leaves the text alone, so a ``C`` on
   the page stops being recognized after you switch to **Do**. Convert changes
   the text itself, starting from the notation the switch shows: with **AB**
   on it turns American chords into European ones, with **Do** on the other
   way round. So to convert a song written in solfège, switch to **Do** first
   (its chords turn blue), then tap Convert.

   Cut, copy, paste and select all are in the text's own menu: long-press or
   select some text to see it. Messages from the app, such as the one that
   confirms a save, appear briefly at the bottom of the screen.

   .. only:: not ios

      When the soft keyboard leaves little room for the text, as on a phone held
      sideways, the app bar and the ribbon hide so the text gets the space. A
      small floating **Undo / Redo** chip sits above the keyboard until it closes,
      and the bars come back.

   .. only:: ios

      Held sideways, the app bar and the ribbon share one line above the
      keyboard. When the keyboard would leave the text less than about 170
      points (a smaller iPhone, or the keyboard's suggestions bar), they hide
      so the text gets the space, and a small floating **Undo / Redo** chip sits
      above the keyboard until it closes.

   .. platform-figure:: edit-keyboard-collapsed
      :platforms: android
      :alt: A phone held sideways with the keyboard open. Only a few lines of
            the song show above the keyboard, the bars are hidden, and a small
            Undo and Redo chip floats at the right.
      :ios-alt: An iPhone held sideways with the keyboard open: the app bar and
                the ribbon on one line, a few lines of the song, the keyboard.
      :ios-caption: Typing on an iPhone held sideways: on this one the text
         still has room, so the bars stay.

      Typing on a phone held sideways: only the text and the Undo / Redo chip
      are left.

   .. _android-player:

   The Player
   ==========

   In the Play tab the player sits at the bottom of the screen. From top to
   bottom it has the song pill, a row of buttons and a status line.

   .. platform-figure:: player-labeled
      :platforms: android
      :alt: The player while a song plays, with numbered callouts: 1 the song
            pill reading 90, 3/4, G; 2 Voicing, greyed out; 3 Instrument; 4 back
            to the start; 5 pause; 6 the metronome, switched on; 7 speed, with a
            1.25x badge; 8 the chord sheet button, switched on; 9 the status
            line reading Bar 6/66, Playing Em.

      The player while a song plays, with the metronome on and the speed at
      125%.

   #. **The song pill** reads something like "𝄞 90 · 3/4 · G ⌄": the tempo,
      time signature and key the song starts with. Tap it to open **Playback
      settings** (below).
   #. **Voicing** opens a sheet with the voicings grouped as Piano, Fretted,
      Ensembles and Your voicings. **Edit voicings…** at the bottom opens
      Settings › Voicings. See :doc:`playback`, :doc:`fretted` and
      :doc:`ensembles`. While a song plays the button is greyed out, because
      the whole song is voiced before it starts: pause to change it.
      (Tap the greyed button and it tells you so.)
   #. **Instrument** opens a sheet with the 16 General MIDI families. Tap a
      family to see its eight instruments with their program numbers, and tap
      one to select it. The ← button goes back to the families.
   #. **⏮** stops playback and returns the playhead to the first chord.
   #. **▶ / ❚❚**, the big button, plays from the playhead, pauses, and resumes.
      Pause keeps the playhead where it is. When you press ▶, a ring spins
      around the button for a moment while the song is prepared.
   #. **Metronome** turns on a click track that sounds during playback. It is
      tinted while it's on.
   #. **Speed** opens the Speed sheet (below). The button shows a badge such
      as "1.25×" when the speed isn't 100%.
   #. **▭** shows or hides the chord sheet (see :doc:`chord_sheet`). It is
      tinted while the chord sheet is shown.
   #. **The status line** shows the position and what is happening, for
      example "Bar 6/24 · Playing Em" or "Bar 6/24 · Paused", and any message
      from the app.

   There is no Stop button: **❚❚** pauses, and **⏮** stops and rewinds. When a
   song reaches its end, the playhead goes back to the first chord.

   .. _song-defaults:

   Playback Settings
   -----------------

   Tap the song pill to see the **Tempo**, **Time signature** and **Key** the
   song starts with. Each row says what it does: the tempo is the speed of
   playback, the time signature the beats per bar (bar lines and the
   metronome), and the key gives the Staff view's key signature and the key
   of relative chords (I, V, vi).

   .. platform-figure:: song-defaults
      :platforms: android
      :alt: The Playback settings sheet. Tempo shows 90 bpm, set by {bpm: 90}
            in the song, with an Edit link. Time signature 3/4 and Key G can
            be changed because the song has no time or key directive. A note
            says these aren't saved in the song. Write into song and Done at
            the bottom.

      Playback settings for a song that sets its tempo but not its time
      signature or key.

   * A value the song sets with a directive is read-only. It shows "Set by
     ``{bpm: 90}`` in the song · Edit". **Edit** switches to the Edit tab with
     the cursor on that directive.
   * A value the song doesn't set comes from the defaults in :doc:`settings`,
     and you can tap it to change it. The change is for this song only: it
     isn't saved with the file or in Settings, and a new song or one you open
     starts again from the defaults. The note at the bottom of the sheet says
     so.
   * **Write into song** inserts the missing directives at the top of the
     song, so the values travel with the file.

   While a song plays, the values and **Write into song** are greyed out; tap
   one to see why. Pause (**❚❚**) to change them: the next **▶** starts again
   from the paused chord with the new values.

   The Speed Sheet
   ---------------

   The Speed button opens a sheet with the speed in large type and a slider
   from 12.5% to 400%. **Reset** puts it back to 100%, and **Manual…** opens a
   small dialog where you type a value from 12.5 to 400. Speed multiplies the
   tempo, and unlike the tempo it can change while a song plays.

   .. platform-figure:: speed-manual
      :platforms: android
      :alt: The Manual speed dialog: a field holding 125 with a percent sign,
            the hint 12.5 to 400, and Cancel and OK buttons.

      Typing an exact speed.

   .. _android-playhead:

   The Playhead
   ============

   The playhead is a small marker, a bar with a triangle on top, drawn just
   before the chord where playback starts. It exists only in the Play tab.

   .. platform-figure:: playhead
      :platforms: android
      :alt: A few lines of a song in the Play tab. A blue bar with a small
            triangle on top stands just before the Em chord.

      The playhead before the Em chord.

   * **Tap a chord** to move the playhead there and hear the chord.
   * **Tap anywhere else** in the text to move the playhead to the nearest
     chord, without a sound.
   * **Drag the marker** to move it chord by chord. Start the drag on the marker
     itself; a drag that starts anywhere else scrolls the text.

   **▶** plays from the playhead, and while a song plays the playhead follows
   the music. Tapping a chord then makes playback jump to it, and the marker
   can't be dragged. The same chord gets an edge mark in the chord sheet.
   **⏮** brings the playhead back to the first chord.

   .. _android-drawer:

   The :plat:`Drawer|Drawer|Menu`
   ==================================

   .. only:: not ios

      The ☰ button opens the drawer. Everything that isn't on the main screen is
      here. To close it without picking anything, tap outside it or press Back.

   .. only:: ios

      The ☰ button opens the menu. Everything that isn't on the main screen is
      here. To close it without picking anything, tap outside it. There is no edge
      swipe: the menu opens with ☰ only.

   .. platform-figure:: drawer
      :platforms: android
      :ios-alt: The menu: New song, Open, the recent songs, Save
                as, Export MIDI, Export audio, Export PDF, Settings, Examples,
                User guide, Quick start, About and Diagnostics.
      :ios-caption: The menu.
      :alt: The drawer: New song, Open, a Recent list with three songs, Save
            as, Export MIDI, Export audio, Export PDF, Settings, Examples, User guide, Quick start and
            About.

      The drawer.

   .. only:: not ios

      **New song**
         Start a new, empty song. It opens in the Edit tab. If the current song
         has unsaved changes, you're asked whether to save them first.

      **Open…**
         Pick a song with the system file picker (the device's storage,
         Downloads, Drive or any other place it offers). It opens in the Play
         tab.

      **Recent**
         The songs you opened recently, listed right in the drawer. Tap one to open
         it. The app keeps access to the songs you picked, and a song that has
         been deleted or moved drops off the list. How many it remembers is a
         setting (see :doc:`settings`).

      **Save as…**
         Save the song under a new name or in a new place. (Plain Save is the disk
         icon in the app bar.)

      **Export MIDI…**
         Write the song as a ``.mid`` file. See :doc:`midi_export`.

      **Export audio…**
         Write the song as a ``.wav`` file that sounds the way Play does. See
         :doc:`midi_export`.

      **Export PDF…**
         Write the song's text as a ``.pdf`` file to print or share. See
         :doc:`midi_export`.

      Below those, the app's own entries:

      **Settings**
         The settings screens, including the Voicings editor. See :doc:`settings`.

      **Examples**
         The example songs that come with Chord Notepad. A sheet lists them by
         file name (``01_quick_start.txt`` and so on); tap one to open it in the
         Play tab. You get a copy that is stored inside the app, so you can edit
         and save it. Tap the same example again and the unchanged copy reopens;
         if you changed it (or it is open with unsaved edits), a new copy is made
         with a number in the name, such as ``01_quick_start (2).txt``. The copies
         show up in **Recent** as "name.txt (Examples)" and can be renamed. They
         live only in the app's own storage: file managers don't see them, they
         aren't backed up, and uninstalling the app deletes them. Use **Save
         as…** to keep your own copy somewhere else.

      **User guide**
         This guide. It works offline, and F1 on a hardware keyboard opens it too.
         Back goes to the page you read before, then back to your song.

      **Quick start**
         The short tour that opens the first time you start the app.

      **About**
         The version and build, the copyright, the licence (GNU AGPL-3.0 with
         additional terms), a link to the source code, the no-warranty notice,
         and **Open source licences**: the licences of everything the app is
         built from. Copies from outside Google Play also have a **Support
         development** link.

      There is no Exit entry. Press Back on the main screen to leave the app; if
      the song has unsaved changes, it asks whether to save them first.

   .. only:: ios

      **New song**
         Start a new, empty song. It opens in the Edit tab. If the current song
         has unsaved changes, you're asked whether to save them first.

      **Open…**
         Pick a song in the Files picker (On My iPhone, iCloud Drive or any other
         place Files offers). It opens in the Play tab.

      **Recent**
         The songs you opened recently, listed right in the menu. Tap one to open
         it. The app keeps access to the songs you picked, and a song that has
         been deleted or moved drops off the list. How many it remembers is a
         setting (see :doc:`settings`).

      **Save as…**
         Save the song under a new name or in a new place. (Plain Save is the disk
         icon in the app bar.)

      **Export MIDI…**
         Write the song as a ``.mid`` file. See :doc:`midi_export`.

      **Export audio…**
         Write the song as a ``.wav`` file that sounds the way Play does. See
         :doc:`midi_export`.

      **Export PDF…**
         Write the song's text as a ``.pdf`` file to print or share. See
         :doc:`midi_export`.

      Below those, the app's own entries:

      **Settings**
         The settings screens, including the Voicings editor. See :doc:`settings`.

      **Examples**
         The example songs that come with Chord Notepad. A sheet lists them by
         file name (``01_quick_start.txt`` and so on); tap one to open it in the
         Play tab. You get a copy that is stored inside the app, so you can edit
         and save it. Tap the same example again and the unchanged copy reopens;
         if you changed it (or it is open with unsaved edits), a new copy is made
         with a number in the name, such as ``01_quick_start (2).txt``. The copies
         show up in **Recent** as "name.txt (Examples)" and can be renamed. They
         live only in the app's own storage: the Files app doesn't show them, and
         deleting the app deletes them. Use **Save as…** to keep your own copy
         somewhere else.

      **User guide**
         This guide. It works offline, and Command+? on a hardware keyboard opens
         it too. Links to web sites open in Safari. Swipe from the left edge to go
         back through the guide's pages; ← returns to your song.

      **Quick start**
         The short tour that opens the first time you start the app.

      **About**
         The version and build, the copyright, the licence (GNU AGPL-3.0 with
         additional terms), a link to the source code, the no-warranty notice,
         and **Open source licences**: the licences of everything the app is
         built from.

      **Diagnostics**
         A page with what the app's audio and Python engine report, and an **Export
         diagnostics** button for when you report a problem.

      There is no Exit entry. Leave the app as you leave any other iOS app.


.. _chord-identifier:

The Chord Identifier
====================

.. only:: desktop

   The Chord Identifier helps you figure out what chord you're hearing or playing.
   It is a sidebar of the Edit workspace: click the piano icon on the rail,
   press **Ctrl+Shift+I**, or use **View → Chord identifier**.

   .. platform-figure:: chord-identifier
      :platforms: desktop
      :alt: The Chord identifier sidebar: a two-octave piano with C, E and G
            selected, the notes field reading C E G, and the candidate C
            marked best.

      The Chord identifier with C, E and G selected.

.. only:: android

   .. only:: not ios

      The Chord Identifier helps you figure out what chord you're hearing or playing.
      Open it with **Identify** (the piano icon) in the Edit ribbon. On a phone it
      fills the screen, and the ← at the top left closes it; held sideways, the
      piano is on the left and the Notes field and the chords on the right. On a
      tablet it opens as a dialog.

   .. only:: ios

      The Chord Identifier helps you figure out what chord you're hearing or playing.
      Open it with **Identify** (the piano icon) in the Edit ribbon. On an iPhone it
      fills the screen, and the ← at the top left closes it; held sideways, the
      piano is on the left and the Notes field and the chords on the right. On an
      iPad it opens as a card over the screen.

   .. platform-figure:: identify
      :platforms: android
      :alt: The Identify Chord screen: a two-octave piano with C, E, G and B
            selected, the Notes field showing C E G B, a Clear button, and
            Cmaj7 picked under Possible Chords. An Insert button at the bottom.

      C, E, G and B make a Cmaj7.

The Piano Keyboard
------------------

.. only:: desktop

   A visual two-octave piano keyboard appears at the top of the sidebar.

   **Left-click a key:**

   * Toggles that note's selection (on/off)
   * Plays the note when it becomes selected, so you can hear it
   * Selected keys appear highlighted

   **Right-click or Shift+click a key:**

   * Plays the note without selecting it
   * Useful for testing notes before adding them

.. only:: android

   A visual two-octave piano keyboard appears at the top of the screen.

   **Tap a key:**

   * Toggles that note's selection (on/off)
   * Plays the note when it becomes selected, so you can hear it
   * Selected keys appear highlighted

   **Long-press a key:**

   * Plays the note without selecting it
   * Useful for testing notes before adding them

The Notes Input Field
---------------------

Below the piano, you can type note names directly:

* Type notes separated by spaces: ``C E G``
* Or with commas: ``C, E, G``
* Include sharps and flats: ``C Eb G``
* Add an octave to place a note: ``E3 G#3 B3 C4``. A note without one goes
  just above the note before it, so the first note you type is the lowest:
  ``E G# B C`` is read with E in the bass

The chords are named with the accidentals you typed: ``Bb D F`` gives ``Bb``,
``A# D F`` gives ``Bb`` as well (it can't be spelled as a chord with A#), and
``F# A# C#`` gives ``F#``. Notes picked on the keyboard get the usual names:
``Bb``, ``Eb``, ``Ab`` and ``Db`` major, ``F#`` major, ``Eb`` minor.

You can type the notes in either notation, whatever the song uses: ``Do Mi
Sol``, ``Sib Re Fa`` and ``Do4 Mi4 Sol4`` work as well as ``C E G``.

Song Notation
-------------

The identifier names notes and chords in the notation of the song you have
open (**AB / Do**). In a European song the keys are labelled ``Do Re Mi``,
the Notes field shows ``Do Mi Sol``, and the results read ``Do``, ``Lam7``,
``Miaddb6`` or ``Domaj7/Mi``. A chord you insert goes into the song spelled
that way.

.. only:: desktop

   Switching **AB / Do** while the identifier is open renames everything at
   once; the chords found and their order stay the same.

The Results List
----------------

As you select notes, Chord Notepad analyzes them and shows matching chords:

* The list updates automatically as you add or remove notes
* Several chords may match the same notes, for example ``Am`` and ``Am/C``
  when C is the lowest note
* Each note is also tried as the root, with any extra notes named as added
  notes: E G# B C gives ``Eaddb6`` (E major with an added flat 6th) as well
  as ``Caugmaj7/E``
* Notes that no root names in full can still be a chord with its 5th or
  3rd left out: C E Bb gives ``C7(no5)``, C G Bb gives ``C7(no3)``. So
  can notes that every root names only with two added notes: C E Bb D A
  gives ``C13(no5)`` as well as ``Amaddb9add11/C``. Two
  notes a fifth apart are a power chord (C G gives ``C5``); other pairs of
  notes, and clusters such as C C# D, aren't named
* The likeliest chords come first. A chord built on the lowest note leads,
  then inversions (the lowest note is the chord's 3rd, 5th or 7th), and
  last the readings that would put an added note in the bass. Common
  chords come before rare ones, and each added note counts against a
  reading. A reading built on another note comes as a slash chord first
  (``Caugmaj7/E``), then without the bass (``Caugmaj7``)

.. only:: desktop

   The first result is marked **best**.

   **Click a result:**
      Plays that chord so you can hear it. **Shift+click** plays it rolled.

   **Double-click a result:**
      Inserts that chord into your document at the text cursor, and puts the
      cursor back in the text so you can carry on typing.

   **Drag a result into the text:**
      Drops the chord where you let go.

   **The ▶ next to a result:**
      Plays that chord so you can hear it. **Shift+click** it to play the
      chord rolled: one note at a time from the lowest, like a quick strum.

.. only:: android

   **Tap a result:**
      Picks that chord and plays it so you can hear it.

   **Long-press a result:**
      Picks it and plays it rolled: one note at a time from the lowest, like
      a quick strum.

   **Double-tap a result:**
      Inserts that chord into your document at the cursor position.

While a chord plays, the keys it actually sounds light up in amber for a few
seconds (a key that is also selected keeps its blue and gets an amber dot),
so you can see when what you hear isn't what you picked. The chord plays on
the piano's two octaves, starting on your lowest key when the chord starts
there. A note that falls off either end of the keyboard is named beside it,
for example ``◂ E3``.

The Insert Button
-----------------

.. only:: desktop

   There is no Insert button: double-click a result in the list (or drag it
   into the text) to add that chord to your document. From the keyboard, Up
   and Down move through the results, **Space** plays the current one and
   **Enter** inserts it.

.. only:: android

   Tap **Insert** to put the picked chord, followed by a space, at the cursor
   in your document (with a space before it too, right after a chord or a
   word). The identifier stays open, so you can work out and insert
   the next chord too; the line at the bottom confirms each insert.

The Clear Button
----------------

.. only:: desktop

   Click the **✕** at the right of the notes field to reset all selections and
   start over.

.. only:: android

   Tap **Clear** to reset all selections and start over.

The Play Button
---------------

**Play** sounds exactly the keys you selected, in their octaves, and lights
them up like a played chord. It is greyed out until a key is selected.

.. only:: desktop

   Click the **▶** next to the notes field to hear the selected keys
   together. Shift+click or right-click it to hear them rolled, one at a
   time from the lowest.

.. only:: android

   Tap **Play** to hear the selected keys together. Long-press it to hear
   them rolled, one at a time from the lowest.

Using the Chord Identifier
--------------------------

**Example: "What chord am I playing?"**

.. only:: desktop

   1. Open the Chord Identifier (the piano icon on the rail, or Ctrl+Shift+I)
   2. Play the chord on your instrument
   3. Click the notes on the piano keyboard (or type them)
   4. Look at the results list
   5. Click a result (or the ▶ next to it) to hear which one sounds right
   6. Double-click the result to add it to your document

.. only:: android

   1. Open the Chord Identifier (Edit tab → Identify)
   2. Play the chord on your instrument
   3. Tap the notes on the piano keyboard (or type them)
   4. Look at the results list
   5. Tap results to hear which one sounds right
   6. Double-tap it (or tap Insert) to add it to your document


Visual Guide
============

Chord Notepad uses colors to help you understand your document at a glance.

Color Coding
------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Color
     - Style
     - Meaning
   * - Blue
     - Underlined
     - Valid chord (will play)
   * - Gray
     - Underlined
     - Invalid/unrecognized chord
   * - Gray
     - Normal
     - Comment (after ``//``)
   * - Purple
     - Normal
     - Valid directive
   * - Red
     - Underlined
     - Invalid directive
   * - Faded purple
     - Normal
     - Directive with no effect (another of its kind replaces it before any
       chord plays)
   * - Yellow
     - Background
     - Currently playing chord

.. only:: android

   .. platform-figure:: editor-colours
      :platforms: android
      :alt: A short song in the Edit tab: purple directives on the first line,
            a red underlined {tempo: fast} below it, a grey comment, a purple
            label, blue underlined chords, a grey underlined Gsus5, and black
            lyrics.

      Every colour in one place but one. ``{tempo: fast}`` is red because
      ``fast`` isn't a tempo value (``{tempo: 100}`` would be purple), and
      ``Gsus5`` is grey because it isn't a chord. Not shown: a faded purple
      directive, one that another of its kind replaces before any chord plays.

   In the dark theme the same colours are a little lighter, and the playing
   chord is a dark yellow, so everything stays readable on the dark
   background.

Valid Chords (Blue, Underlined)
-------------------------------

When you type a chord that Chord Notepad recognizes, it turns blue with an
underline. This means:

* The chord is valid
* It will play during playback

.. only:: desktop

   * You can click it to play it

.. only:: android

   * In the Play tab you can tap it to play it

Invalid Chords (Gray, Underlined)
---------------------------------

If something looks like a chord but isn't valid, it appears gray with an
underline. This might mean:

* A typo (``Cmm7`` instead of ``Cm7``)
* An unsupported chord type
* Something that looks like a chord but isn't

Check the spelling or simplify the chord.

Comments (Gray)
---------------

Everything after ``//`` on a line appears in gray without an underline. Comments
are completely ignored during playback.

Directives (Purple or Red)
--------------------------

Valid directives appear in purple: ``{bpm: 120}``

Invalid directives appear in red: ``{invalid: something}``

A directive that has no effect appears in faded purple: one that another
directive of the same kind replaces before any chord plays, such as the first
of ``{capo: 2}`` and ``{capo: 3}`` written one after the other. It does no harm;
you can delete it.

.. _directive-hints:

Directive Hints
---------------

You don't have to remember how a directive is written: :plat:`the app shows its
syntax while you write one, and a red or faded directive tells you what's
wrong with it|a red or faded directive tells you what's wrong with it`.

.. only:: desktop

   While the text cursor is inside a directive, the status bar at the bottom
   of the window shows how that directive is written, for example
   ``{bpm: 120} · {bpm: +10} · {bpm: 50%} · {bpm: 2x} · {bpm: reset}``. It
   works for one you're still typing too: after ``{lo`` it shows the ``{loop}``
   forms, and after a lone ``{`` it lists every directive. If the directive is
   red or faded, the reason comes first, for example "Tempo must be 20-400 —
   {bpm: 120} · …". When the cursor leaves the directive, the status bar shows
   what it showed before. While a song plays, the status bar keeps showing
   playback.

   Rest the mouse pointer on any directive for a moment, and a small card
   under it shows the same; for a red or faded one, the reason and the
   correct syntax.

.. only:: android

   In the Play tab, touch and hold a red or faded directive. A small card
   under it shows the reason and the correct syntax. It goes away after a few seconds, or when
   you touch the screen again. Holding a directive doesn't move the playhead.

   .. platform-figure:: directive-explain
      :platforms: android
      :alt: The Play tab after touching and holding a red {bpm: 500}: a card
            under it says "Tempo must be 20-400" in red, then the {bpm} forms.

      Holding an invalid directive in the Play tab.

Currently Playing (Yellow Highlight)
------------------------------------

During playback, the chord that's currently sounding has a yellow background.
This helps you follow along with the music.

.. only:: desktop

   Mouse Cursor Changes
   --------------------

   * Over normal text: Standard text cursor
   * Over a valid chord: Hand pointer (indicating you can click to play)

   Window Title
   ------------

   The window title shows:

   * **filename - Chord Notepad** for saved files
   * **filename* - Chord Notepad** if there are unsaved changes (note the asterisk)
   * **Untitled - Chord Notepad** for new, unsaved documents

.. only:: android

   Playhead Marker
   ---------------

   In the Play tab, a small coloured marker (a bar with a triangle) sits before
   the chord where playback starts. Tapping a chord or the text moves it, and
   dragging the marker steps it chord by chord. See :ref:`android-playhead`
   above.

   The Song Title
   --------------

   The title in the app bar shows the file name without its extension. A •
   after it means there are unsaved changes. Tap the title to rename the song.


Insert Directive Dialogs
========================

.. only:: desktop

   The tiles of the Directives sidebar (see above) insert directives without
   your having to remember the exact syntax. They don't open dialogs: the
   directive goes in at the cursor with its value selected, and you type
   over the value or change it with its **▾**. The sections below describe
   the values each directive takes.

.. only:: android

   The **＋ Insert** button in the Edit ribbon opens a sheet with **Tempo**
   ``{bpm}``, **Time signature** ``{time}``, **Key** ``{key}``, **Capo**
   ``{capo}``, **Label** ``{label}`` and **Loop** ``{loop}``. Put the cursor
   where the directive should go first. Each entry opens a small dialog where
   you fill in the value; the directive is then inserted at the cursor (with a
   space before it, right after a chord or a word).

   .. platform-figure:: insert-sheet
      :platforms: android
      :alt: The Insert sheet: Tempo, Time signature, Key, Capo, Label (section)
            and Loop, each with its directive on the right, and Cancel.

      The Insert sheet.

   The dialogs check what you type as you go. If a value isn't valid, the
   reason shows in red under the field and **Insert** stays greyed out until
   you fix it. The dialogs are described below.

Insert Tempo (BPM) Dialog
-------------------------

Enter a tempo value:

* **Absolute:** Just a number from 20 to 400, like ``120``
* **Relative:** ``+20`` or ``-10``
* **Percentage:** ``50%``
* **Multiplier:** ``2x`` or ``0.5x``
* **Reset:** Type ``reset`` or ``original``

.. only:: desktop

   The tempo tiles add ``{bpm: 120}``, ``{bpm: +10}``, ``{bpm: -10}``,
   ``{bpm: 50%}``, ``{bpm: 2x}`` and ``{bpm: reset}`` at your cursor; type any
   of the forms above over the selected value.
   Its **▾** picks a form and a number, or finds the tempo by tapping
   along (**Tap**, see :ref:`desktop-pickers`).

.. only:: android

   Tap Insert to add ``{bpm: value}`` at your cursor.

   .. platform-figure:: insert-tempo
      :platforms: android
      :alt: The Insert BPM/Tempo Change dialog: a list of the valid formats and
            an empty BPM field, with Cancel and a greyed-out Insert.

      The Tempo dialog.

Insert Time Signature Dialog
----------------------------

.. only:: desktop

   The time tile adds ``{time: 3/4}`` at your cursor with the value
   selected. Its **▾** offers the common time signatures (2/4 to 12/8), or
   set your own:

   * Beats (1-16)
   * Unit (1, 2, 4, 8, or 16)

.. only:: android

   Two pickers let you set:

   * Beats (1-16)
   * Unit (1, 2, 4, 8, or 16)

   Tap Insert to add ``{time: beats/unit}`` at your cursor.

   .. platform-figure:: insert-time
      :platforms: android
      :alt: The Insert Time Signature Change dialog: Beats 4 over Unit 4, each
            a drop-down, with Cancel and Insert.

      The Time signature dialog.

Insert Key Dialog
-----------------

.. only:: desktop

   The major key and minor key tiles add ``{key: G}`` or ``{key: Am}`` at
   your cursor, in the song's notation, with the key selected. The keys
   with a key signature are the ones to use (Eb rather than D#, and Am, Bbm
   and the other minors too); the **▾** picks another.

.. only:: android

   A dropdown shows the 15 major and 15 minor keys that have a key
   signature (so Eb rather than D#, and Am, Bbm and the other minors too), in
   your current notation. Select one and tap Insert to add ``{key: ...}`` at
   your cursor.

   .. platform-figure:: insert-key
      :platforms: android
      :alt: The Insert Key Change dialog with the Key drop-down set to C, and
            Cancel and Insert.

      The Key dialog.

Insert Label Dialog
-------------------

Type a name for your label. The name should:

* Contain only letters, numbers, and underscores
* Be unique (not already used in the document)

.. only:: desktop

   The label tile adds ``{label: verse}`` at your cursor, or the next name
   not used yet, with the name selected for you to type over.

.. only:: android

   Tap Insert to add ``{label: name}`` at your cursor.

   .. platform-figure:: insert-label
      :platforms: android
      :alt: The Insert Label dialog: an empty Label field, with Cancel and a
            greyed-out Insert.

      The Label dialog.

Insert Loop Dialog
------------------

Two controls:

* **Label dropdown:** Shows ``@start`` plus all labels in your document

.. only:: desktop

   * **Count:** How many times to repeat (the **▾** offers 2 to 16; you can
     type a bigger number)

   The loop tile adds a loop to the nearest label above the cursor, the
   **×3** tile the same with a count of 3, and the **start** tile a loop to
   ``@start``. Type over the label or the count, or use the **▾**.

.. only:: android

   * **Count:** How many times to repeat (2-100), set with − and +

   Tap Insert to add ``{loop: label count}`` at your cursor.

   .. platform-figure:: insert-loop
      :platforms: android
      :alt: The Insert Loop dialog: the Label drop-down set to @start, Count 2
            between minus and plus buttons, and Cancel and Insert.

      The Loop dialog.

Insert Capo Dialog
------------------

.. only:: desktop

   The capo tile adds ``{capo: 3}`` at your cursor; type the fret the capo
   sits on over the 3 (0 to 12, where 0 means no capo). To see the capo
   positions ranked for a fretboard voicing, the easiest first, and insert
   the one you pick, use :menuselection:`Tools --> Suggest capo...`; see
   :doc:`chord_sheet`.

.. only:: android

   Enter the fret the capo sits on (0 to 12, where 0 means no capo), then tap
   Insert to add ``{capo: N}`` at your cursor. Tap **Suggest** instead to see
   the capo positions ranked for a fretboard voicing, the easiest first, and
   insert the one you pick; see :doc:`chord_sheet`.

   .. platform-figure:: insert-capo
      :platforms: android
      :alt: The Insert Capo dialog: an explanation, an empty Fret field, and
            the Suggest, Cancel and Insert buttons.

      The Capo dialog. The key stays the same; a fretboard voicing plays the
      capo shapes.
