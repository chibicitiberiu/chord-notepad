=========
Transpose
=========

Transpose shifts every chord in your song up or down by a fixed number of
semitones, so you can move a progression into a different key -- to fit a
singer's range, match another instrument, or just try how it sounds higher or
lower.


Transposing a Song
==================


.. only:: desktop

   1. Go to :menuselection:`Tools --> Transpose...`
   2. Choose the number of **semitones** to shift by. Positive numbers move the
      chords up, negative numbers move them down (a value of ``2`` raises
      everything by a whole step; ``-1`` lowers it by a half step).
   3. Click **OK**.

.. only:: android

   1. In the Edit tab, tap **Transpose** in the ribbon. (To transpose only part
      of the song, select that part first.)
   2. Choose the number of **semitones** to shift by with **−** and **+**, from
      -11 to +11. Positive numbers move the chords up, negative numbers move
      them down (a value of ``2`` raises everything by a whole step; ``-1``
      lowers it by a half step).
   3. Tap **OK**.

   .. platform-figure:: transpose
      :platforms: android
      :alt: The Transpose dialog: Transpose whole song, a short explanation,
            Semitones +2 between minus and plus buttons, and Cancel and OK.

      Transposing the whole song up a whole step.

If you have text selected, only the chords inside the selection are
transposed, and the dialog says *Transpose selection*. With nothing selected
the whole document is transposed, and the dialog says *Transpose whole song*.

.. only:: desktop

   The change is a single undo step -- one :kbd:`Ctrl+Z` puts everything back.

.. only:: android

   The change is a single undo step -- one **Undo** in the Edit ribbon puts
   everything back.


What Changes
============

* **Chords shift.** Both American (``C``, ``Am7``, ``F#m7b5``) and European
  (``Do``, ``Lam7``) chords move. The root and any slash-bass note both shift;
  the quality, extensions, parentheses, and any ``*duration`` suffix stay
  exactly as written (``Cmaj7/E`` up two becomes ``Dmaj7/F#``, ``Am*4`` becomes
  ``Bm*4``).
* **Notation is preserved.** European chords stay European -- ``Do`` up two
  becomes ``Re``, and the minor form is kept (``rem`` becomes ``mim``).

.. only:: desktop

   * **Key directives shift.** A ``{key: C}`` or ``{key: Am}`` inside the
     transposed range moves with the chords (and keeps its major or minor form).
     When you transpose the whole song, the toolbar **Key** shifts too, so
     roman-numeral chords keep sounding the same.

.. only:: android

   * **Key directives shift.** A ``{key: C}`` or ``{key: Am}`` inside the
     transposed range moves with the chords (and keeps its major or minor form).
     When you transpose the whole song, the song's key (the **Key** in the song
     pill and in Playback settings) shifts too, so roman-numeral chords keep
     sounding the same.

What stays put:

* **Roman numerals** (``I``, ``ii``, ``V7``) are relative to the key by
  definition, so they never move -- shifting the key is what re-pitches them.
* **Rests** (``NC``), **comments** (``// ...``), and **lyrics** are left
  untouched.


Spelling of Sharps and Flats
============================

Each transposed chord is spelled the way it's written in the key it lands in.
Move a song from G up to B and you get ``F#``, ``C#`` and ``G#m`` (B major is a
key of sharps), not ``Gb``, ``Db`` and ``Abm``. Move a song from F down to Db
and you get ``Gb`` and ``Ab7`` rather than ``F#`` and ``G#7``. Chords from
outside the key are spelled the usual way for that key: in D a borrowed chord a
tone below the tonic is ``C``, and up a semitone in Eb it becomes ``Db``, not
``C#``.

Chord Notepad works out the key like this:

* A ``{key}`` directive sets the key for the chords after it, up to the next
  ``{key}``. The directive moves with the song, so the chords follow its new
  key. This holds for a selection too, even when the ``{key}`` is outside it.
* For chords before the first ``{key}`` (or a song without one), it recognizes
  the key from those chords. If it can't tell, say for two or three chords that
  fit several keys, it falls back to the simple rule below.

.. only:: desktop

   * The toolbar **Key** isn't used for spelling. Add a ``{key}`` at the top of
     the song if a spelling comes out wrong.

.. only:: android

   * The song's key (in the song pill and Playback settings) isn't used for
     spelling. Add a ``{key}`` at the top of the song if a spelling comes out
     wrong.

A diminished chord that leads up a semitone to the next chord gets a sharp, as
it's usually written: ``C#dim7`` before ``Dm7`` (or before ``G7/D``), not
``Dbdim7``.

It never writes awkward names like ``E#``, ``B#``, ``Cb`` or ``Fb``, or double
sharps and flats. Where the key would need one, the plain note is written
instead (``F`` in F# major, ``B`` in Gb major).

The simple rule, used when the key isn't known: if the original chord had a
sharp it prefers a sharp result, and if it had a flat it prefers a flat;
otherwise it uses the common default (``C#``, ``Eb``, ``F#``, ``Ab``, ``Bb``).

Transposing up and then back down by the same amount gives the same notes.
Chords spelled for their key come back exactly as they were; a chord spelled
against its key may come back in the key's spelling (a ``Gb`` in a song in D
returns as ``F#``).

.. only:: desktop

   Key names (the toolbar key and ``{key}`` directives) take the key with fewer
   sharps or flats: C up a semitone is ``Db`` (five flats), not ``C#`` (seven
   sharps), and Am down a semitone is ``G#m``, not ``Abm``. Where both have as
   many (``F#`` and ``Gb``, ``D#m`` and ``Ebm``) the original's sharp or flat
   decides. A key that has no key signature is never written: a chord can be
   spelled ``D#`` freely, but there is no D# major key, so a key that would
   land there comes out ``Eb`` -- likewise ``Gbm`` becomes ``F#m``, ``Dbm``
   becomes ``C#m``, ``G#`` becomes ``Ab``, and ``A#`` becomes ``Bb``.

.. only:: android

   Key names (the song's key and ``{key}`` directives) take the key with fewer
   sharps or flats: C up a semitone is ``Db`` (five flats), not ``C#`` (seven
   sharps), and Am down a semitone is ``G#m``, not ``Abm``. Where both have as
   many (``F#`` and ``Gb``, ``D#m`` and ``Ebm``) the original's sharp or flat
   decides. A key that has no key signature is never written: a chord can be
   spelled ``D#`` freely, but there is no D# major key, so a key that would
   land there comes out ``Eb`` -- likewise ``Gbm`` becomes ``F#m``, ``Dbm``
   becomes ``C#m``, ``G#`` becomes ``Ab``, and ``A#`` becomes ``Bb``.


Keeping Chords Over the Lyrics
==================================

Chords sit above the lyric syllable where they're played. Transposing can make
a chord name longer or shorter (``Fa`` to ``Sol``, or ``C`` to ``C#``), which
would otherwise nudge the chords out of line with the words below.

Chord Notepad keeps each chord above its syllable:

* A chord that gets **shorter** is padded with a space so the following chords
  keep their positions.
* A chord that gets **longer** first tries to close up an extra space on the
  chord line. When there's no room, the lyric line just below is stretched
  instead -- a space is added at a word gap, or a ``-`` is slipped into a word
  (``singer`` becomes ``sin-ger``) -- so the chords and the words shift
  together and stay aligned.

This only applies when a chord line is directly followed by a lyric line. A
chord line on its own just keeps its chords spaced sensibly.
