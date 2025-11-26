==================
The User Interface
==================

This section covers all the menus, toolbars, and special tools in Chord Notepad.


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

BPM Slider
----------

The tempo slider controls playback speed:

* Drag left to slow down (minimum 60 BPM)
* Drag right to speed up (maximum 240 BPM)
* The current value displays next to the slider

The slider shows the *current* BPM, which may be different from what you set
if your song has ``{bpm}`` directives.

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

**Open** (Ctrl+O)
   Open an existing chord sheet file. Browse to find your file and click Open.

**Save** (Ctrl+S)
   Save the current document. If it's a new file, you'll be asked where to
   save it.

**Save As** (Ctrl+Shift+S)
   Save the current document with a new name or location.

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
   * **Guitar (Standard)** - EADGBE tuning
   * **Guitar (Drop D)** - DADGBE tuning
   * **Guitar (DADGAD)** - Celtic tuning
   * **Guitar (Open G)** - Blues/slide tuning

   A checkmark shows the current selection.

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

Help Menu
---------

**About**
   Shows information about Chord Notepad:

   * Version number
   * Build information
   * Description of the application


The Chord Identifier
====================

The Chord Identifier helps you figure out what chord you're hearing or playing.
Access it through **Tools → Identify Chord...**.

The Piano Keyboard
------------------

A visual two-octave piano keyboard appears at the top of the window.

**Left-click a key:**

* Toggles that note's selection (on/off)
* Plays the note so you can hear it
* Selected keys appear highlighted

**Right-click a key:**

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

**Single-click a result:**
   Plays that chord so you can hear it.

**Double-click a result:**
   Inserts that chord into your document at the cursor position.

The Insert Button
-----------------

Click **Insert into Editor** to add the selected chord to your document.

The Clear Button
----------------

Click **Clear** to reset all selections and start over.

Using the Chord Identifier
--------------------------

**Example: "What chord am I playing?"**

1. Open the Chord Identifier (Tools → Identify Chord...)
2. Play the chord on your instrument
3. Click the notes on the piano keyboard (or type them)
4. Look at the results list
5. Click results to hear which one sounds right
6. Double-click (or click Insert) to add it to your document

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
* You can click it to play it

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


Insert Directive Dialogs
========================

The Tools → Insert menu provides dialogs to help you insert directives without
remembering the exact syntax.

Insert BPM Dialog
-----------------

Enter a tempo value:

* **Absolute:** Just a number, like ``120``
* **Relative:** ``+20`` or ``-10``
* **Percentage:** ``50%``
* **Multiplier:** ``2x`` or ``0.5x``
* **Reset:** Type ``reset`` or ``original``

Click Insert to add ``{bpm: value}`` at your cursor.

Insert Time Signature Dialog
----------------------------

Two spinboxes let you set:

* Beats (1-16)
* Unit (1, 2, 4, 8, or 16)

Click Insert to add ``{time: beats/unit}`` at your cursor.

Insert Key Dialog
-----------------

A dropdown shows all valid keys in your current notation.
Select one and click Insert to add ``{key: note}`` at your cursor.

Insert Label Dialog
-------------------

Type a name for your label. The name should:

* Contain only letters, numbers, and underscores
* Be unique (not already used in the document)

Click Insert to add ``{label: name}`` at your cursor.

Insert Loop Dialog
------------------

Two controls:

* **Label dropdown:** Shows ``@start`` plus all labels in your document
* **Count spinbox:** How many times to repeat (1-100)

Click Insert to add ``{loop: label count}`` at your cursor.
