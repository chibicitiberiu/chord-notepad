=========
Transpose
=========

Transpose shifts every chord in your song up or down by a fixed number of
semitones, so you can move a progression into a different key -- to fit a
singer's range, match another instrument, or just try how it sounds higher or
lower.


Transposing a Song
==================

1. Go to :menuselection:`Tools --> Transpose...`
2. Choose the number of **semitones** to shift by. Positive numbers move the
   chords up, negative numbers move them down (a value of ``2`` raises
   everything by a whole step; ``-1`` lowers it by a half step).
3. Click **OK**.

If you have text selected, only the chords inside the selection are
transposed, and the dialog says *Transpose selection*. With nothing selected
the whole document is transposed, and the dialog says *Transpose whole song*.

The change is a single undo step -- one :kbd:`Ctrl+Z` puts everything back.


What Changes
============

* **Chords shift.** Both American (``C``, ``Am7``, ``F#m7b5``) and European
  (``Do``, ``Lam7``) chords move. The root and any slash-bass note both shift;
  the quality, extensions, parentheses, and any ``*duration`` suffix stay
  exactly as written (``Cmaj7/E`` up two becomes ``Dmaj7/F#``, ``Am*4`` becomes
  ``Bm*4``).
* **Notation is preserved.** European chords stay European -- ``Do`` up two
  becomes ``Re``, and the minor form is kept (``rem`` becomes ``mim``).
* **Key directives shift.** A ``{key: C}`` or ``{key: Am}`` inside the
  transposed range moves with the chords (and keeps its major or minor form).
  When you transpose the whole song, the toolbar **Key** shifts too, so
  roman-numeral chords keep sounding the same.

What stays put:

* **Roman numerals** (``I``, ``ii``, ``V7``) are relative to the key by
  definition, so they never move -- shifting the key is what re-pitches them.
* **Rests** (``NC``), **comments** (``// ...``), and **lyrics** are left
  untouched.


Spelling of Sharps and Flats
============================

When a transposed chord lands on a black key, Chord Notepad picks a sensible
spelling. If the original chord had a sharp it prefers a sharp result, and if
it had a flat it prefers a flat; otherwise it uses the common default
(``C#``, ``Eb``, ``F#``, ``Ab``, ``Bb``). It never writes awkward names like
``E#`` or ``Cb`` or double accidentals.

Because of this, transposing up and then back down by the same amount returns
plain chords to exactly where they started, but a chord that was spelled with
an unusual accidental may come back with the more conventional spelling.


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
