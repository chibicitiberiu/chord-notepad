========
Settings
========

:menuselection:`Tools --> Settings...` opens the Settings window, where
everything that used to mean hand-editing the config file now has a form.
It has three pages -- **General**, **Playback & Audio**, and **Voicings** --
plus **Save** and **Cancel** at the bottom. Save writes every page at once;
Cancel discards whatever you changed and closes the window.


General
=======

**Font family** and **Font size**
   The editor's font, the same setting as :menuselection:`View --> Font...`.

**Chord notation**
   American or European, the same toggle as the AB/Do buttons in the
   toolbar.

**Default key**
   The key a new document starts in.

**Show quick start at startup**
   Whether the quick-start reference (also reachable from
   :menuselection:`Help --> Quick Start`) opens automatically when Chord
   Notepad launches.

**Number of recent files**
   How many entries :menuselection:`File --> Recent Files` remembers.

**Log level**
   How much detail Chord Notepad writes to its log file. Takes effect the
   next time you start the application.


Playback & Audio
=================

**Default BPM**
   The tempo a new document starts at.

**Default time signature**
   The time signature a new document starts at.

**Soundfont path**
   The ``.sf2`` file FluidSynth loads for playback. Leave it empty to use
   the soundfont bundled with Chord Notepad. Takes effect after restarting
   the application.

**Audio driver**
   The FluidSynth audio driver to use. Leave it empty to let FluidSynth
   pick one automatically. Takes effect after restarting the application.

**Allow capo** (under *Guitar*)
   When on, and a fretboard voicing is active, the chord sheet suggests the
   easiest capo position for the current song while a fret or tab view is
   shown (see :doc:`chord_sheet`). It is advice only -- nothing is re-voiced
   or transposed. Off by default; the change takes effect immediately.


Voicings
========

The Voicings page is the full voicing editor -- everything :doc:`fretted`,
:doc:`ensembles`, and :doc:`piano` describe as configuration-file entries,
with a form in front of it. A *voicing* is still a named configuration (a
model plus that model's parameters); a *model* is still the engine
underneath -- fretboard, ensemble, or piano. See those three pages for what
each parameter actually does; this page only covers the controls that get
you there.

The left side lists your custom voicings, grouped by model (Fretboard,
Piano, Ensemble), with **+** and **-** buttons to add a new one or remove
the selected one. Built-in voicings -- the four guitars, the ukulele, the
four ensemble presets, the default piano -- aren't listed here since
they're not yours to edit, but they are available as starting points (see
below).

The right side edits whichever voicing is selected. Every control has a
hover tooltip explaining what it does, so if a field's purpose isn't
obvious, point at it before consulting :doc:`fretted` or :doc:`ensembles`.

**Load config**
   Copies every parameter from an existing voicing -- any built-in preset
   or any other custom voicing -- into the one you're editing. This is the
   normal way to start a new voicing: load the closest preset, then change
   what's different. Since it overwrites everything currently in the
   editor, it asks you to confirm first.

**Name**
   The voicing's name. Editing it renames the voicing.

**Model**
   Fretboard, Ensemble, or Piano. Switching models changes which
   parameters appear below.

**Parameters**
   For a fretboard voicing: strings, frets, fingers, spans, and barres,
   plus all eleven weights (see :doc:`fretted`), laid out in a compact
   multi-column form. For an ensemble voicing: the voices table -- a row
   per voice with Name, Low, and High columns, an **Add voice** button,
   and a remove button on each row -- plus spacing, unisons, and all the
   weights, including the doubling, omission, and inversion groups (see
   :doc:`ensembles`). For a piano voicing: the left- and right-hand ranges,
   the preferred bass range, the right-hand low anchor and center, the
   low-interval floor, hand span, note-count limits, hand gap floor, the
   add-bass toggle, and all the weights, including the per-role omission
   group (see :doc:`piano`). Each Weights section opens with a one-line
   reminder of how weights work: every weight is a signed number added to
   the voicing's score, positive values make a trait more likely and
   negative ones less likely, higher is always more preferred, and the
   defaults suit most music, so leave them alone unless you have a specific
   reason not to.

Mistakes are flagged as you type, not just when you click Save: an
invalid field turns red immediately, and a problem that spans two fields
-- a relaxed span smaller than the normal span, a voice whose low note is
above its high note -- shows up as a message at the top of the editor.
Save stays blocked until every field on the page is valid. On top of
that, Save also validates every *other* voicing on the page, not just the
one you're currently editing, and if something's wrong there it names
exactly which voicing and which field. Renaming or deleting the voicing
you're currently playing with is handled: a rename follows the selection
so playback keeps using it, and a delete falls back to piano. Once you
save, any new or changed custom voicing shows up in
:menuselection:`Playback --> Voicing` immediately -- no restart needed.

Worked Example: A Seven-String Guitar
--------------------------------------

Say you want to add a seven-string guitar tuned like a standard six-string
with an extra low B string, the same instrument used as the custom-voicing
example in :doc:`fretted`. Here's how to build it from the Voicings page
instead of editing JSON by hand:

1. Open :menuselection:`Tools --> Settings...` and go to the
   **Voicings** page.
2. Click **+** to add a new voicing.
3. Click **Load config** and pick **Guitar (Standard - EADGBE)**. This
   fills in the standard tuning and all its defaults as a starting point.
4. In **Name**, type ``My 7-String``.
5. In the strings field, change the tuning from ``E2 A2 D3 G3 B3 E4`` to
   ``B1 E2 A2 D3 G3 B3 E4`` -- the same six strings with a low B added at
   the top.
6. Click **Save**.
7. Open :menuselection:`Playback --> Voicing` -- **My 7-String** is now in
   the list, under Fretboard. Select it and play some chords.
