===============
Getting Started
===============

This guide will walk you through your first few minutes with Chord Notepad.
By the end, you'll know how to write chords, play them back, and save your work.

Opening the Application
-----------------------

Launch Chord Notepad like any other application. On first launch, you'll see:

* A large **text editing area** in the center - this is where you write
* A **toolbar** at the top with playback controls
* A **menu bar** for additional features

The Main Window
---------------

Here's what you'll see:

**Toolbar (top)**
   The toolbar contains:

   * **Notation toggle** (AB/Do) - Switch between American and European notation
   * **BPM slider** - Control playback speed (60-240 beats per minute)
   * **Key selector** - Set the musical key
   * **Time signature** - Set beats per measure (like 4/4 or 3/4)
   * **Play/Pause button** - Start or pause playback
   * **Stop button** - Stop playback completely

**Text Editor (center)**
   This is your workspace. Type chords here just like you would in any text
   editor. Chord Notepad highlights what you type:

   * **Blue underlined text** = Valid chord (will play)
   * **Gray underlined text** = Invalid chord (won't play)
   * **Gray text** = Comment (ignored during playback)
   * **Purple text** = Directive (controls playback)

**Status Bar (bottom)**
   Shows the current state and playback information.

Your First Chord Sheet
----------------------

Let's create a simple chord progression:

1. Click in the text area
2. Type: ``C  Am  F  G``
3. Each chord turns blue when recognized

This is the "50s progression," a common chord sequence.

Try adding another line:

.. code-block:: chord

   C  Am  F  G
   C  Am  F  G
   F  G  C

Playing Your First Chord
------------------------

Now let's hear it:

1. Click the **Play button** (▶) in the toolbar
2. Listen as each chord plays in sequence
3. Watch the **yellow highlight** move through your chords
4. Click **Stop** (⏹) when you're done

You can also click any chord directly to hear it on its own.

Adjusting the Tempo
-------------------

Too fast? Too slow? Adjust the tempo:

1. Find the **BPM slider** in the toolbar
2. Drag it left to slow down, right to speed up
3. The number shows beats per minute (default is 120)

Try different tempos to find what feels right for your progression.

Changing the Sound
------------------

Want a different instrument?

1. Go to **Playback** menu in the menu bar
2. Click **Instrument**
3. Browse through categories (Piano, Guitar, Strings, etc.)
4. Click an instrument to select it
5. Play your chords to hear the new sound

Saving Your Work
----------------

To save your chord sheet:

1. Press **Ctrl+S** (or go to File → Save)
2. Choose where to save the file
3. Enter a filename
4. Click Save

Your chord sheet is saved as a plain text file. You can open it in any text
editor, but only Chord Notepad will play it back.

Opening Existing Files
----------------------

To open a saved chord sheet:

1. Press **Ctrl+O** (or go to File → Open)
2. Find your file
3. Click Open

Recent files appear in the **File → Recent Files** menu for quick access.

Next Steps
----------

For more details, see:

* :doc:`writing_chords` - Learn all the chord types you can write
* :doc:`directives` - Control tempo, time signature, and create song sections
* :doc:`playback` - Explore different voicings and instruments
* :doc:`shortcuts` - Speed up your workflow with keyboard shortcuts

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
