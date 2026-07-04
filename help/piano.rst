==============
Piano Voicing
==============

Piano is the default instrument, and the *piano model* is the engine behind
it: a two-hand keyboard voicer that treats voicing as an optimization rather
than a fixed template. A *voicing* is a named configuration -- a model (the
engine that renders it) plus that model's parameters. The other two models
are covered elsewhere: fretted instruments like guitar in :doc:`fretted`, and
groups of independent singers or players in :doc:`ensembles`.


How the Two Hands Are Voiced
================================

The left hand plays the bass -- a single note or an octave-doubled one, down
in the low register -- and the right hand plays a voicing of the chord's core
tones (root, third, fifth, seventh where present), tried in root position and
every inversion, at a few different octave placements. Any extensions a
chord carries -- a 9th, an 11th, a 13th -- always stack on top of that core
voicing rather than displacing it, so a dense jazz chord still reads as the
plain triad or seventh underneath with color added above.

Not every voicing that's built this way is playable, so the picker throws
out anything that breaks the physical model first: too many notes for one
hand, too wide a stretch, or the right hand crossing below the left. What
survives is scored on two things -- how good the voicing is on its own
(register, spacing, whether a close interval is sitting low enough to sound
muddy) and how smoothly it follows from the previous chord (common tones
held, small movements preferred) -- and the whole song is optimized together,
not chord by chord, so the hands settle into a stable register instead of
drifting up or down over a long song or a repeated section.


The Built-in Voicing
=========================

Chord Notepad ships with one built-in piano voicing, **Grand Piano**, and it's
the default instrument for a new song. Its parameters reproduce the piano
engine's original, hand-tuned behavior exactly, so if you've never touched
the Voicings page, this is what you've been hearing all along.


Defining a Custom Piano Voicing
=====================================

If you want the piano to sit in a different register, spread the hands
further apart, or trade completeness for a sparser texture, add a custom
piano voicing from :menuselection:`Tools --> Settings...` --> Voicings:
load **Grand Piano** as a starting point, change what's different (ranges,
span, weights), and save. See :doc:`settings` for the page itself.

Power users can also edit the configuration file directly -- the same
mechanism used for custom fretted instruments and ensembles. The file lives
at ``~/.config/chord-notepad/settings.json`` on Linux, or the equivalent
per-user application-data folder on Windows and macOS.

Add a ``voicings`` object at the top level, keyed by a short slug you'll use
internally; each entry needs a ``"model": "piano"`` and describes one
keyboard configuration. Here's a voicing that keeps both hands lower and
closer together, suited to a slow, intimate ballad:

.. code-block:: json

   {
     "voicings": {
       "close_low": {
         "model": "piano",
         "label": "Close & Low",
         "rh_range": ["C3", "C6"],
         "rh_center": 55,
         "hand_gap_floor": 4,
         "weights": {
           "rh_wide_gap_penalty": -1.2
         }
       }
     }
   }

* ``model`` is required and must be ``"piano"`` for a voicing defined this
  way (a fretted instrument uses ``"model": "fretboard"``, and an ensemble
  uses ``"model": "ensemble"`` -- see :doc:`fretted` and :doc:`ensembles`).
* ``label`` is what shows up in the Voicing menu (defaults to the slug if
  omitted).
* ``lh_range``, ``rh_range``, ``bass_range``, and ``rh_low_anchor`` are all
  optional ``[low, high]`` pairs. Give each endpoint as a note name
  (``"C3"``, ``"E4"``) or a raw MIDI number; middle C is ``C4``.
* ``rh_center``, ``rh_low_interval_floor``, ``hand_span``,
  ``max_notes_per_hand``, ``max_total_notes``, ``hand_gap_floor``, and
  ``add_bass`` are all optional -- see the parameter reference below for
  what each controls and its default.
* ``weights`` is optional and partial -- give only the settings you want to
  change, and everything else keeps its default. See the parameter
  reference below for the full list of keys.

Custom piano voicings appear in :menuselection:`Playback --> Voicing`
automatically the next time Chord Notepad starts, sorted alongside every
other voicing -- built-in or custom, piano, fretted, or ensemble -- by model
and then name.


How to Change Voicing
=========================

1. Open the **Playback** menu.
2. Click **Voicing**.
3. Select **Grand Piano**, or any custom piano voicing you've defined (see
   above).
4. Play your chords to hear the difference.

A checkmark shows the current voicing, the same as for :doc:`playback`.


Voicing Parameters
=======================

Every piano voicing, built-in or custom, is steered by the same physical
hand limits, the same scoring anchors, and the same set of numeric weights.
These are the controls the Voicings page of :menuselection:`Options -->
Settings...` exposes, one control per row -- see :doc:`settings` for the
page itself; they can also be set directly in a voicing's entry in
``settings.json``.

Hands and Range
------------------

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Left-hand range
     - The lowest and highest key the left hand will ever play.
     - ``lh_range``
     - C1 - C3
   * - Right-hand range
     - The lowest and highest key the right hand will ever play.
     - ``rh_range``
     - C3 - C6
   * - Preferred bass range
     - Where the bass note should ideally sit. It isn't a hard limit --
       sitting outside this window costs the below/above-bass weights per
       semitone, so the left hand can still stray from it when the chord
       demands.
     - ``bass_range``
     - C2 - B2
   * - Right-hand low anchor
     - The window the right hand's *lowest* note is anchored within when the
       optimizer places a voicing at a given octave.
     - ``rh_low_anchor``
     - C3 - E4
   * - Right-hand center
     - The ideal mean pitch of the right hand. Drifting away from this costs
       the center-penalty weight per semitone.
     - ``rh_center``
     - 63 (Eb4)
   * - Low-interval floor
     - Below this pitch, a close right-hand interval (a third or narrower)
       starts to sound muddy rather than rich. Costs the low-interval-penalty
       weight per such interval.
     - ``rh_low_interval_floor``
     - 52 (E3)
   * - Hand span
     - The widest reach of a single hand, in semitones -- a ninth by default.
     - ``hand_span``
     - 14
   * - Max notes per hand
     - The most notes one hand may hold at once -- five fingers, five notes.
     - ``max_notes_per_hand``
     - 5
   * - Max total notes
     - The most notes both hands may play together for one chord.
     - ``max_total_notes``
     - 10
   * - Hand gap floor
     - The right hand should clear the bass note by more than this many
       semitones. Closer than that costs the muddy-gap weight per semitone
       of shortfall.
     - ``hand_gap_floor``
     - 2
   * - Add bass
     - Whether the left hand plays a bass note at all. Turn this off for a
       right-hand-only texture, e.g. when something else is already covering
       the bass.
     - ``add_bass``
     - true

Weights steer the picker when it scores a candidate voicing. Every weight is
a signed number added to the voicing's score. Positive values make that
trait more likely, negative values less likely, and higher is always more
preferred. A trait you want the picker to chase gets a positive weight; one
you want it to steer clear of gets a negative one; zero leaves it neutral.

.. list-table::
   :header-rows: 1
   :widths: 28 40 20 12

   * - Control
     - What it does
     - Config key
     - Default
   * - Right-hand note
     - Added per note kept in the right hand. More positive favors fuller
       voicings; less positive lets the picker thin them out.
     - ``rh_note_bonus``
     - +0.6
   * - Right-hand centering
     - Subtracted per semitone the right hand's mean pitch strays from
       "Right-hand center".
     - ``rh_center_penalty``
     - -1.4
   * - Bass below range
     - Subtracted per semitone the bass sits below "Preferred bass range".
     - ``lh_below_bass_penalty``
     - -1.5
   * - Bass above range
     - Subtracted per semitone the bass sits above "Preferred bass range".
     - ``lh_above_bass_penalty``
     - -1.5
   * - Doubled bass
     - Subtracted once when the bass note is octave-doubled in the left
       hand.
     - ``lh_double_penalty``
     - -1.0
   * - Doubled bass, low
     - An extra cost per semitone an octave-doubled bass sits below
       "Preferred bass range", on top of "Doubled bass".
     - ``lh_double_low_penalty``
     - -1.0
   * - Muddy interval
     - Subtracted per close right-hand interval (a third or narrower)
       sounding below "Low-interval floor".
     - ``rh_low_interval_penalty``
     - -2.0
   * - Wide right-hand gap
     - Subtracted per interior right-hand gap wider than an octave.
     - ``rh_wide_gap_penalty``
     - -0.6
   * - Muddy hand gap
     - Subtracted per semitone the hands clear each other by less than
       "Hand gap floor".
     - ``muddy_gap_penalty``
     - -1.5
   * - Common tone held
     - Added per common tone held across a chord change (voice leading).
     - ``common_tone_bonus``
     - +1.5
   * - Movement
     - Subtracted per semitone of nearest-neighbour movement across a chord
       change (voice leading). More negative keeps both hands stiller from
       one chord to the next.
     - ``movement_penalty``
     - -0.35
   * - Omission (by tone role)
     - Added to the score for dropping a chord tone entirely when the hand
       and note limits don't leave room for everything. The values are
       negative, so a more negative one keeps that tone more insistently.
       Same role taxonomy as the ensemble model's omission weights (see
       :doc:`ensembles`): ``root`` (-4.0), ``third`` (-40.0), ``fifth``
       (-8.0), ``seventh`` (-40.0), ``color`` (-30.0), ``extension`` (-7.0).
     - ``omit.root`` / ``.third`` / ``.fifth`` / ``.seventh`` / ``.color`` /
       ``.extension``
     - see left

.. note::
   These weights apply per piano voicing. A custom piano voicing that omits
   ``weights`` entirely uses the defaults above; one that sets ``weights``
   only needs to list the keys it wants to change; anything else falls back
   to the same defaults.
