========
Settings
========

.. only:: desktop

   :menuselection:`Tools --> Settings...` opens the Settings window, where
   everything that used to mean hand-editing the config file now has a form.
   It has three pages -- **General**, **Playback & Audio**, and **Voicings** --
   plus **Save** and **Cancel** at the bottom. Save writes every page at once;
   Cancel discards whatever you changed and closes the window.

.. only:: android

   **☰ → Settings** opens the settings screens, where everything that used to
   mean hand-editing the config file now has a form. There are two pages,
   **General** and **Playback**, plus the **Voicings** editor. Each field has a
   line of help under it.

   .. platform-figure:: settings-pages
      :platforms: android
      :alt: The Settings screen listing three pages: General, Playback and
            Voicings, each with a one-line summary, and Save at the top right.

      Settings on a phone. Tap a page to open it.

   On a phone each page is a screen of its own, and the ← at the top goes back
   to the list. On a tablet, or a phone held sideways, the list stays on the
   left and the page opens beside it.

   Nothing changes until you tap **Save** at the top right; it saves every page
   at once and closes Settings. If you leave with ← or Back instead and have
   changed something, the app asks whether to discard your changes.

   The Voicing sheet in the Play tab has an **Edit voicings…** entry that opens
   the Voicings editor directly.

   In the version from Google Play, a card above the pages offers the optional
   supporter purchase, or shows your supporter badge once you've bought it.


General
=======

.. only:: desktop

   **Font family** and **Font size**
      The editor's font, the same setting as :menuselection:`View --> Font...`.

.. only:: android

   .. platform-figure:: settings-general
      :platforms: android
      :alt: The General page: Font family Monospace, Font size 11 with minus
            and plus buttons, Chord notation American or European, Default
            key C, a Show quick start at startup switch, and Number of recent
            files 10.

      The General page.

   **Font family** and **Font size**
      The editor's font: Monospace, Sans or Serif, from 6 to 72 points.
      Monospace keeps chords lined up over the lyrics. You can also change the
      size by pinching the text.

.. only:: desktop

   **Notation**
      American or European, the same toggle as the AB/Do buttons in the
      toolbar.

.. only:: android

   **Chord notation**
      American or European, the same switch as AB / Do in the Edit ribbon.

**Default key**
   The key a song starts in when it has no ``{key}`` directive before its
   first chord. Picking a key :plat:`in the toolbar|in the song pill's Song
   defaults` changes it for the song you're working on only, and opening a
   song with a ``{key}`` directive leaves this setting alone.

.. only:: desktop

   **Show quick start at startup**
      Whether the quick-start reference (also reachable from
      :menuselection:`Help --> Quick Start`) opens automatically when Chord
      Notepad launches.

   **Max recent files**
      How many entries :menuselection:`File --> Recent Files` remembers.

   **Log level**
      How much detail Chord Notepad writes to its log file. Takes effect the
      next time you start the application.

.. only:: android

   **Show quick start at startup**
      Whether the Quick Start tour (also in ☰ → Quick start) opens
      automatically when Chord Notepad starts. The **Show at startup** box at the
      bottom of the tour is the same setting.

   **Number of recent files**
      How many songs ☰ → Recent remembers, from 1 to 50.


:plat:`Playback & Audio|Playback`
==================================

**Default BPM**
   The tempo a song starts at when it has no ``{bpm}`` directive before its
   first chord.

**Default time signature**
   The time signature a song starts with when it has no ``{time}`` directive
   before its first chord.

Only Settings changes the defaults (the key, tempo and time signature). The
values :plat:`in the toolbar|in the song pill's Song defaults` belong to the
song you're working on: a change there isn't saved, and opening a song
doesn't touch the defaults either. A new song, and every song you open,
starts again from the defaults here, so a change on this page shows from the
next new or opened song.

.. only:: android

   .. platform-figure:: settings-playback
      :platforms: android
      :alt: The Playback page: Default BPM 120 with minus and plus buttons, and
            the default time signature as Beats 4 and Beat unit 4.

      The Playback page.

   A song's own ``{bpm}`` and ``{time}`` directives always win over them
   while it plays (see :doc:`interface`).

   The sound itself has no settings on Android: the app always uses its
   built-in instruments and the phone's normal audio output.

.. only:: desktop

   **Soundfont path**
      The ``.sf2`` file FluidSynth loads for playback. Leave it empty to use
      the soundfont bundled with Chord Notepad. Takes effect after restarting
      the application.

   **Audio driver**
      The FluidSynth audio driver to try first (for example ``alsa``,
      ``pulseaudio`` or ``jack``). If it can't start, Chord Notepad falls back to
      the usual drivers for your system, and tells you when none of them works.
      Leave it empty to use the usual drivers only. Takes effect after restarting
      the application.

.. only:: desktop

   .. note::
      Capo handling moved out of Settings: a capo is now a ``{capo: N}`` directive
      in the song, and :menuselection:`Tools --> Suggest Capo...` finds and inserts
      a good one. See :doc:`chord_sheet` and :doc:`directives`.

.. only:: android

   .. note::
      Capo handling moved out of Settings: a capo is now a ``{capo: N}`` directive
      in the song, and ＋ Insert → Capo → Suggest in the Edit ribbon finds and inserts a good
      one. See :doc:`chord_sheet` and :doc:`directives`.


Voicings
========

The Voicings page is the full voicing editor -- everything :doc:`fretted`,
:doc:`ensembles`, and :doc:`piano` describe as configuration-file entries,
with a form in front of it. A *voicing* is still a named configuration (a
model plus that model's parameters); a *model* is still the engine
underneath -- fretboard, ensemble, or piano. See those three pages for what
each parameter actually does; this page only covers the controls that get
you there.

.. only:: desktop

   The left side lists your custom voicings, grouped by model (Fretboard,
   Piano, Ensemble), with **+** and **-** buttons to add a new one or remove
   the selected one. Built-in voicings -- the four guitars, the ukulele, the
   four ensemble presets, the default piano -- aren't listed here since
   they're not yours to edit, but they are available as starting points (see
   below).

.. only:: android

   The list shows your custom voicings, grouped by model (Fretboard, Piano,
   Ensemble). **Add voicing** at the top of the list adds a new one and opens
   it; the **Remove voicing** button is in the voicing's own form, and asks
   before it removes anything. On a phone the list is a screen of its own:
   tap a voicing to open its form full screen, and ← or Back returns to the
   list. Built-in voicings -- the four guitars, the ukulele, the four
   ensemble presets, the default piano -- aren't listed here since they're
   not yours to edit, but they are available as starting points (see below).

   .. platform-figure:: settings-voicings
      :platforms: android
      :alt: The Voicings page on a phone: an Add voicing button, then the
            groups Fretboard with My 7-String, Piano with no voicings, and
            Ensemble with no voicings.

      The Voicings list on a phone, with one custom voicing.

   On a tablet held sideways, the pages, the list and the form all fit on one
   screen:

   .. platform-figure:: settings-voicings-tablet
      :platforms: android
      :alt: Settings on a tablet in landscape: the pages on the left, the
            Voicings list in the middle with My 7-String selected, and its
            form on the right with Name, Model, Load config, Remove voicing,
            Strings and the fret and span fields.

      Settings › Voicings on a tablet.

.. only:: desktop

   The right side edits whichever voicing is selected. Every control has a
   hover tooltip explaining what it does, so if a field's purpose isn't
   obvious, point at it before consulting :doc:`fretted` or :doc:`ensembles`.

.. only:: android

   The form edits the voicing you picked. Every field has a line of
   supporting text under it explaining what it does, so if a field's purpose
   isn't obvious, read that before consulting :doc:`fretted` or :doc:`ensembles`.
   Number fields have **−** and **+** buttons beside them, and you can also type
   the value.

   .. platform-figure:: settings-voicing-form
      :platforms: android
      :alt: The form for the voicing My 7-String on a phone: Name with a
            pencil button, Model Fretboard, Load config and Remove voicing
            buttons, Strings B1 E2 A2 D3 G3 B3 E4, then Max fret, Fingers and
            Max span with minus and plus buttons. Save at the top right.

      A fretboard voicing's form on a phone (the top of it; the weights are
      further down).

**Load config**
   Copies every parameter from an existing voicing -- any built-in preset
   or any other custom voicing -- into the one you're editing. This is the
   normal way to start a new voicing: load the closest preset, then change
   what's different. Since it overwrites everything currently in the
   editor, it asks you to confirm first.

**Name**
   .. only:: desktop

      The voicing's name. Editing it renames the voicing.

   .. only:: android

      The voicing's name. Tap the field (or the pencil beside it) to rename
      the voicing in a dialog.

**Model**
   Fretboard, Ensemble, or Piano. Switching models asks first, then replaces
   the parameters with the new model's defaults.

**Parameters**
   For a fretboard voicing: strings, frets, fingers, spans, and barres,
   plus all thirteen weights :plat:`in a compact multi-column form|` (see
   :doc:`fretted`). For an ensemble voicing: the voices
   :plat:`table -- a row per voice with Name, Low, High and Staff columns|-- a
   card per voice with Name, Low, High and Staff`, an **Add voice** button,
   and a remove button on each :plat:`row|card` -- plus spacing, unisons, and all the
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

.. only:: desktop

   Mistakes are flagged as you type, not just when you click Save: an
   invalid field turns red immediately, and a problem that spans two fields
   -- a relaxed span smaller than the normal span, a voice whose low note is
   above its high note -- shows up as a message at the top of the editor.
   Save checks every voicing, not just the one you're editing: if one is
   invalid, it names the voicing and the problem, selects it, and saves
   nothing. Renaming or deleting the voicing
   you're currently playing with is handled: a rename follows the selection
   so playback keeps using it, and a delete falls back to piano. Once you
   save, any new or changed custom voicing shows up in
   :menuselection:`Playback --> Voicing` immediately -- no restart needed.

.. only:: android

   Mistakes are flagged as you type, not just when you save: an
   invalid field turns red immediately, and a problem that spans two fields
   -- a relaxed span smaller than the normal span, a voice whose low note is
   above its high note -- shows up as a message at the top of the editor.
   A voicing with a mistake is marked *Has errors* in the list. While any
   voicing is invalid, the **Save** button in the top bar looks greyed out,
   but tapping it still works as a check: it opens the first invalid
   voicing and names what's wrong with it. Renaming or deleting the voicing
   you're currently playing with is handled: a rename follows the selection
   so playback keeps using it, and a delete falls back to piano. Once you
   save, any new or changed custom voicing shows up in the Voicing sheet of
   the Play tab (under Your voicings) immediately -- no restart needed.

Worked Example: A Seven-String Guitar
--------------------------------------

Say you want to add a seven-string guitar tuned like a standard six-string
with an extra low B string, the same instrument used as the custom-voicing
example in :doc:`fretted`. Here's how to build it from the Voicings page
instead of editing JSON by hand:

.. only:: desktop

   1. Open :menuselection:`Tools --> Settings...` and go to the
      **Voicings** page.
   2. Click **+** to add a new voicing.
   3. Click **Load config** and pick **Guitar (Standard - EADGBE)**. This
      fills in the standard tuning and all its defaults as a starting point.
   4. In **Name**, type ``My 7-String``.
   5. In the strings field, change the tuning from ``E2 A2 D3 G3 B3 E4`` to
      ``B1 E2 A2 D3 G3 B3 E4`` -- the same six strings with a low B added in
      front (the list starts at the lowest string).
   6. Click **Save**.
   7. Open :menuselection:`Playback --> Voicing` -- **My 7-String** is now in
      the list, under Fretboard. Select it and play some chords.

.. only:: android

   1. Open |voicings_settings|.
   2. Tap **Add voicing**. The new voicing opens (full screen on a phone).
   3. Tap **Load config** and pick **Guitar (Standard - EADGBE)**. This
      fills in the standard tuning and all its defaults as a starting point.
   4. In **Name**, type ``My 7-String``.
   5. In the strings field, change the tuning from ``E2 A2 D3 G3 B3 E4`` to
      ``B1 E2 A2 D3 G3 B3 E4`` -- the same six strings with a low B added in
      front (the list starts at the lowest string).
   6. Tap **Save** in the top bar.
   7. Switch to the Play tab and tap **Voicing** in the player -- **My 7-String**
      is now in the list, under Your voicings. Select it and play some chords.

   .. platform-figure:: voicing-sheet
      :platforms: android
      :alt: The Voicing sheet: Piano; under Fretted, four guitar tunings and
            Ukulele; under Ensembles, four choir and string presets; under Your
            voicings, My 7-String. Edit voicings and Done at the bottom.

      The Voicing sheet, with the new voicing under Your voicings.
