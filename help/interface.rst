==================
The User Interface
==================

This section covers all the menus, toolbars, and special tools in Chord Notepad.


.. only:: desktop

   The Toolbar
   ===========

   The toolbar at the top of the window gives you quick access to the most common
   controls.

   Notation Toggle (AB/Do)
   -----------------------

   Two buttons on the left let you switch notation systems:

   * **AB** - American notation (C, D, E, F, G, A, B)
   * **Do** - European notation (Do, Re, Mi, Fa, Sol, La, Si)

   The selected button appears highlighted. Clicking switches your notation and
   updates the key selector to match.

   BPM Control
   -----------

   The BPM value is shown as underlined text in the toolbar.

   * **Drag left/right** to change the value (range 20-400 BPM)
   * **Click** to type a precise value
   * **Middle-click** to reset to the default (120 BPM)
   * **Scroll** with the mouse wheel to step by 1

   During playback the BPM control becomes read-only and shows the **effective
   BPM** — what's actually playing right now, including any changes from
   ``{bpm}`` directives in the song. When playback stops, it goes back to
   showing your base BPM and is editable again.

   Speed Multiplier
   ----------------

   Next to the BPM is the speed multiplier (``100%`` by default), which scales
   the playback speed on top of the BPM (whether you set it manually or via a
   directive). Use it as a "practice slowdown" knob.

   * **Drag left/right** to change the value (range 12.5% - 400%, snapping every 12.5%)
   * **Click** to type a precise value — accepts ``150``, ``150%``, or ``1.5x``
   * **Middle-click** to reset to ``100%``

   Unlike the BPM control, the multiplier **stays editable during playback** and
   takes effect immediately on the next chord. For example, set the multiplier
   to ``50%`` to play a song at half speed without changing its underlying BPM.

   Key Selector
   ------------

   A dropdown menu lets you choose the musical key:

   * Click to open the list of keys
   * Select the key for your song
   * This affects how roman numerals are interpreted

   The keys shown match your notation choice (C-D-E-F-G-A-B for American,
   Do-Re-Mi-Fa-Sol-La-Si for European).

   Time Signature Controls
   -----------------------

   Two spinboxes let you set the time signature:

   * **First box** - Beats per measure (1-16)
   * **Second box** - Beat unit (1, 2, 4, 8, or 16)

   Common settings:

   * 4/4 - Standard time (four quarter-note beats)
   * 3/4 - Waltz time (three quarter-note beats)
   * 6/8 - Compound duple (six eighth-note beats)

   Metronome
   ---------

   The metronome toggle (next to the time signature) arms a click track that
   sounds *during song playback*.

   * High wood-block on the downbeat, low one on offbeats
   * The click is scheduled by the playback engine itself, so it always lines
     up with the song's beats — including changes made by ``{time: X/Y}`` and
     ``{bpm: ...}`` directives mid-song
   * Toggle it on, then press Play. Turning it off does not pause playback,
     it just silences the click
   * Always starts off when you open the app

   Playback Buttons
   ----------------

   **Play/Pause Button (▶/⏸)**

   * Shows ▶ when stopped or paused
   * Click to start playing from the beginning
   * **Shift+Click** to play from the cursor position
   * Shows ⏸ when playing - click to pause

   **Stop Button (⏹)**

   * Stops playback completely
   * Clears the yellow highlight
   * Resets the playback position


   The Menus
   =========

   File Menu
   ---------

   **New** (Ctrl+N)
      Create a new, empty document. If you have unsaved changes, you'll be asked
      to save them first.

   **Open...** (Ctrl+O)
      Open an existing chord sheet file. Browse to find your file and click Open.

   **Save** (Ctrl+S)
      Save the current document. If it's a new file, you'll be asked where to
      save it.

   **Save As...** (Ctrl+Shift+S)
      Save the current document with a new name or location.

   **Export MIDI...**
      Save the song as a standard MIDI file. Opens a save dialog for a ``.mid``
      file containing the same voicings, timing, tempo, and instrument as
      playback, with loops unrolled into their repeats. See
      :doc:`midi_export` for details.

   **Recent Files**
      A submenu showing up to 10 recently opened files. Click any file to open it
      quickly.

   **Exit** (Ctrl+Q)
      Close Chord Notepad. You'll be asked to save any unsaved changes.

   Edit Menu
   ---------

   **Undo** (Ctrl+Z)
      Undo your last action. You can undo multiple times to go back through your
      edit history.

   **Redo** (Ctrl+Y)
      Redo an action you just undid.

   **Cut** (Ctrl+X)
      Cut the selected text to the clipboard.

   **Copy** (Ctrl+C)
      Copy the selected text to the clipboard.

   **Paste** (Ctrl+V)
      Paste text from the clipboard at the cursor position.

   **Select All** (Ctrl+A)
      Select all text in the document.

   View Menu
   ---------

   **Font...**
      Opens a dialog to change the font:

      * **Font family** - Choose from any font installed on your system
      * **Font size** - Choose from 6 to 72 points

      Your choice is saved and remembered for next time.

   **Chord Sheet**
      Shows or hides the chord sheet strip docked under the editor, with the
      song's voiced chords laid out left to right as they'll actually play.
      See :doc:`chord_sheet`.

   **Increase Font Size** (Ctrl+Plus)
      Make the text one size larger.

   **Decrease Font Size** (Ctrl+Minus)
      Make the text one size smaller.

   **Reset Font Size** (Ctrl+0)
      Return to the default font size (11 points).

   You can also zoom using **Ctrl+Mouse Wheel** (scroll up to zoom in, down to
   zoom out).

   Playback Menu
   -------------

   **Voicing**
      A submenu to select the chord voicing style:

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
      * Any custom voicings you've added to the config file -- a fretted
        instrument or an ensemble

      A checkmark shows the current selection. See :doc:`fretted` for how the
      fretted-instrument voicings (guitar and beyond) work and how to define
      your own, and :doc:`ensembles` for the same on ensembles.

   **Instrument**
      A submenu organized by instrument category:

      * Piano, Chromatic Percussion, Organ, Guitar, Bass, Strings, Ensemble,
        Brass, Reed, Pipe, Synth Lead, Synth Pad, Synth Effects, Ethnic,
        Percussive, Sound Effects

      Browse categories to find instruments. A checkmark shows the current
      selection.

   Tools Menu
   ----------

   **Identify Chord...**
      Opens the Chord Identifier tool (see below).

   **Insert**
      A submenu with shortcuts to insert directives:

      * **BPM/Tempo Change...** - Insert a ``{bpm}`` directive
      * **Time Signature Change...** - Insert a ``{time}`` directive
      * **Key Change...** - Insert a ``{key}`` directive
      * **Label...** - Insert a ``{label}`` directive
      * **Loop...** - Insert a ``{loop}`` directive

      Each option opens a dialog where you fill in the value, then the directive
      is inserted at your cursor position.

   **Convert to American Notation**
      Converts all European notation chords (Do, Re, Mi...) in your document to
      American notation (C, D, E...).

   **Convert to European Notation**
      Converts all American notation chords (C, D, E...) in your document to
      European notation (Do, Re, Mi...).

   Options Menu
   ------------

   **Settings...**
      Opens the Settings window: general preferences, playback and audio
      defaults, and the full voicing editor, across three pages with
      Save/Cancel. See :doc:`settings`.

   Help Menu
   ---------

   **User Guide** (F1)
      Opens this user guide.

   **Quick Start**
      Opens a short quick-start reference.

   **About**
      Shows information about Chord Notepad:

      * Version number
      * Build information
      * Description of the application


.. only:: android

   The App Bar
   ===========

   The bar across the top of the screen holds, from left to right:

   * **☰** opens the drawer (see *The Drawer* below).
   * **The song title.** A • after the name means there are unsaved changes. Tap
     the title to **Rename** the song. The dialog shows "Saved as name.txt". If
     the storage the file lives in can't rename it, the app offers **Save as…**
     instead. A new, untitled song gets its name when you first save it.
   * **The Edit and Play tabs.**
   * **Save** (the disk icon).

   On a phone held sideways the tabs and the Edit ribbon share one line, and the
   title is hidden. The colours follow the system's light or dark theme.

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
        - Moves the playhead to the nearest chord.
      * - Drag
        - Selects or scrolls, as usual.
        - Scrolls. A drag that starts on the playhead marker moves it chord by
          chord.
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

   Songs you saved before open in the Play tab, and new songs open in Edit.
   Switching to Edit while a song plays stops playback.

   The Edit Ribbon
   ===============

   A single row of buttons under the app bar, in the Edit tab:

   * **Undo** and **Redo**
   * **＋ Insert**, which opens a sheet of directives (see *Insert Directive
     Dialogs* below)
   * **Transpose**, which opens the dialog described in :doc:`transpose`
   * **Identify**, which opens the Chord Identifier (see below)
   * **AB / Do**, the notation the text is read in
   * **Convert**, which rewrites every chord in the document into the other
     notation and switches AB / Do to match

   The ribbon scrolls sideways. A **›** at its right edge means there are more
   buttons off screen.

   The notation switch and Convert do different jobs. Switching AB / Do changes
   how the editor reads what you type and leaves the text alone, so a ``C`` on
   the page stops being recognized after you switch to **Do**. Convert changes
   the text itself.

   Cut, copy and paste are in the text's own selection menu. Status messages
   appear briefly at the bottom of the screen.

   When the soft keyboard leaves little room for the text, the app bar and the
   ribbon hide so the text gets the space. A small floating **Undo / Redo** chip
   sits above the keyboard until it closes, and the bars come back.

   The Player
   ==========

   In the Play tab the player sits at the bottom of the screen. From top to
   bottom it has the song pill, a row of buttons and a status line.

   **The song pill** reads something like "𝄞 90 · 3/4 · G ⌄": the tempo, time
   signature and key the song starts with. Tap it to open **Song defaults**:

   * A value the song sets with a directive is read-only. It shows "Set by
     ``{bpm: 90}`` in the song · Edit". **Edit** switches to the Edit tab with the
     cursor on that directive.
   * A value the song doesn't set is an editable default. It is not saved with
     the file.
   * **Write into song** inserts the missing directives at the top of the song.

   **The buttons**, left to right:

   * **Voicing** opens a sheet with the voicings grouped as Piano, Fretted,
     Ensembles and Your voicings. **Edit voicings…** at the bottom opens
     Settings › Voicings. See :doc:`fretted` and :doc:`ensembles`.
   * **Instrument** opens a sheet with the 16 General MIDI families. Tap a family
     to see its eight instruments with their program numbers, and tap one to
     select it. The ← button goes back to the families.
   * **⏮** stops playback and returns the playhead to the first chord.
   * **▶ / ⏸**, the big button, plays from the playhead. Pause keeps the playhead
     where it is.
   * **Metronome** toggles a click track that sounds during playback.
   * **Speed** opens a sheet with a slider from 25% to 400%, **Reset** and
     **Manual…**, which lets you type a value. The button shows a badge such as
     "1.25×" when the speed isn't 100%. Speed stays adjustable during playback.
   * **▭** shows or hides the chord sheet (see :doc:`chord_sheet`).

   There is no Stop button: **⏸** pauses, and **⏮** stops and rewinds.

   **The status line** under the buttons shows the position and what is
   happening, for example "Bar 6/24 · Playing Em" or "Bar 6/24 · Paused".

   **The playhead** is a small coloured bar with a triangle, drawn before the
   chord where playback starts. It follows the music while a song plays, and the
   same chord gets an edge mark in the chord sheet. While a song plays, tapping
   a chord jumps playback there.

   The Drawer
   ==========

   The ☰ button opens the drawer. There is no ⋮ menu; everything lives here.

   **New song**
      Start a new, empty song. It opens in the Edit tab.

   **Open…**
      Pick a song with the system file picker (Downloads, Drive or any document
      provider).

   **Recent**
      The songs you opened recently, listed right in the drawer. Tap one to open
      it. The app keeps access to the documents you picked, and a document that
      has disappeared drops off the list.

   **Save as…**
      Save the song under a new name or in a new place. (Plain Save is the disk
      icon in the app bar.)

   **Export MIDI…**
      Write the song as a ``.mid`` file. See :doc:`midi_export`.

   Below those, the app's own entries:

   **Settings**
      The settings screens, including the Voicings editor. See :doc:`settings`.

   **User guide**
      This guide. It works offline, and F1 on a hardware keyboard opens it too.

   **Quick start**
      A short tour of the main ideas.

   **About**
      The version, a description of the app and the open source licences.

   There is no Exit entry; leave the app the usual Android way.


The Chord Identifier
====================

.. only:: desktop

   The Chord Identifier helps you figure out what chord you're hearing or playing.
   Access it through **Tools → Identify Chord...**.

.. only:: android

   The Chord Identifier helps you figure out what chord you're hearing or playing.
   Open it with **Identify** (the piano icon) in the Edit ribbon.

The Piano Keyboard
------------------

.. only:: desktop

   A visual two-octave piano keyboard appears at the top of the window.

   **Left-click a key:**

   * Toggles that note's selection (on/off)
   * Plays the note so you can hear it
   * Selected keys appear highlighted

   **Right-click a key:**

   * Plays the note without selecting it
   * Useful for testing notes before adding them

.. only:: android

   A visual two-octave piano keyboard appears at the top of the screen.

   **Tap a key:**

   * Toggles that note's selection (on/off)
   * Plays the note so you can hear it
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

The Results List
----------------

As you select notes, Chord Notepad analyzes them and shows matching chords:

* The list updates automatically as you add or remove notes
* Multiple chords may match the same notes (inversions, enharmonic names)
* More common chords appear first

.. only:: desktop

   **Single-click a result:**
      Plays that chord so you can hear it.

   **Double-click a result:**
      Inserts that chord into your document at the cursor position.

.. only:: android

   **Tap a result:**
      Plays that chord so you can hear it. Press **Insert** to put it in your
      document.

The Insert Button
-----------------

.. only:: desktop

   Click **Insert into Editor** to add the selected chord to your document.

.. only:: android

   Tap **Insert** to put the selected chord, followed by a space, at the cursor
   in your document.

The Clear Button
----------------

.. only:: desktop

   Click **Clear** to reset all selections and start over.

.. only:: android

   Tap **Clear** to reset all selections and start over.

Using the Chord Identifier
--------------------------

**Example: "What chord am I playing?"**

.. only:: desktop

   1. Open the Chord Identifier (Tools → Identify Chord...)
   2. Play the chord on your instrument
   3. Click the notes on the piano keyboard (or type them)
   4. Look at the results list
   5. Click results to hear which one sounds right
   6. Double-click (or click Insert) to add it to your document

.. only:: android

   1. Open the Chord Identifier (Edit tab → Identify)
   2. Play the chord on your instrument
   3. Tap the notes on the piano keyboard (or type them)
   4. Look at the results list
   5. Tap results to hear which one sounds right
   6. Tap Insert to add it to your document

**Example: "What notes are in this chord?"**

1. Open the Chord Identifier
2. Type the chord in the results search, or
3. Build it from notes and see when it matches


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
   * - Yellow
     - Background
     - Currently playing chord

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

* A typo (``Cmaaj7`` instead of ``Cmaj7``)
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

   The Playhead
   ------------

   In the Play tab, a small coloured marker (a bar with a triangle) sits before
   the chord where playback starts. Tapping a chord or the text moves it, and
   dragging the marker steps it chord by chord. See *The Player* above.

   The Song Title
   --------------

   The title in the app bar shows the file name. A • after it means there are
   unsaved changes. Tap the title to rename the song.


Insert Directive Dialogs
========================

.. only:: desktop

   The Tools → Insert menu provides dialogs to help you insert directives without
   remembering the exact syntax.

.. only:: android

   The **＋ Insert** button in the Edit ribbon opens a sheet with **Tempo**
   ``{bpm}``, **Time signature** ``{time}``, **Key** ``{key}``, **Capo**
   ``{capo}``, **Label** ``{label}`` and **Loop** ``{loop}``. Each one opens a
   small dialog where you fill in the value; the directive is then inserted at
   the cursor. The dialogs are described below.

Insert BPM Dialog
-----------------

Enter a tempo value:

* **Absolute:** Just a number, like ``120``
* **Relative:** ``+20`` or ``-10``
* **Percentage:** ``50%``
* **Multiplier:** ``2x`` or ``0.5x``
* **Reset:** Type ``reset`` or ``original``

.. only:: desktop

   Click Insert to add ``{bpm: value}`` at your cursor.

.. only:: android

   Tap Insert to add ``{bpm: value}`` at your cursor.

Insert Time Signature Dialog
----------------------------

.. only:: desktop

   Two spinboxes let you set:

   * Beats (1-16)
   * Unit (1, 2, 4, 8, or 16)

   Click Insert to add ``{time: beats/unit}`` at your cursor.

.. only:: android

   Two pickers let you set:

   * Beats (1-16)
   * Unit (1, 2, 4, 8, or 16)

   Tap Insert to add ``{time: beats/unit}`` at your cursor.

Insert Key Dialog
-----------------

.. only:: desktop

   A dropdown shows all valid keys in your current notation.
   Select one and click Insert to add ``{key: note}`` at your cursor.

.. only:: android

   A dropdown shows all valid keys in your current notation.
   Select one and tap Insert to add ``{key: note}`` at your cursor.

Insert Label Dialog
-------------------

Type a name for your label. The name should:

* Contain only letters, numbers, and underscores
* Be unique (not already used in the document)

.. only:: desktop

   Click Insert to add ``{label: name}`` at your cursor.

.. only:: android

   Tap Insert to add ``{label: name}`` at your cursor.

Insert Loop Dialog
------------------

Two controls:

* **Label dropdown:** Shows ``@start`` plus all labels in your document

.. only:: desktop

   * **Count spinbox:** How many times to repeat (1-100)

   Click Insert to add ``{loop: label count}`` at your cursor.

.. only:: android

   * **Count:** How many times to repeat (1-100)

   Tap Insert to add ``{loop: label count}`` at your cursor.

.. only:: android

   Insert Capo Dialog
   ------------------

   Enter the fret the capo sits on (0 to 12), then tap Insert to add
   ``{capo: N}`` at your cursor. Tap **Suggest** instead to let Chord Notepad
   pick the easiest capo for a fretboard voicing; see :doc:`chord_sheet`.
