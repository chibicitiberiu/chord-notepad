"""The Quick Start tour's pages, per platform.

A page is a title plus a list of blocks. A block is one of

* ``("text", paragraph)``
* ``("snippet", song_text, notation)``: an example shown like the editor
  shows it (the chords highlighted by the real detection);
* ``("image", resource_path)``: a bundled picture.

The desktop pages are the ones the Tk dialog always showed; the Android ones
differ only where the desktop names a gesture or a menu (and leave out the
desktop screenshot).
"""

from typing import Any, Dict, List

from session.platform import ANDROID, DESKTOP, check_platform

#: The picture of the chord sheet (desktop only).
CHORD_SHEET_IMAGE = "resources/quickstart/chord_sheet.png"


def pages(platform: str = DESKTOP) -> List[Dict[str, Any]]:
    """The tour's pages for ``platform`` (a new list each call).

    Raises:
        ValueError: For an unknown platform.
    """
    android = check_platform(platform) == ANDROID

    def variant(desktop: str, mobile: str) -> str:
        return mobile if android else desktop

    chord_sheet_blocks: List[tuple] = [
        ("text",
         "The panel under the editor draws the song's chords as you write: "
         "as a piano roll, on a music staff, as guitar chord diagrams (Fret "
         "cards), or as tab. It follows along while the song plays."),
    ]
    if not android:
        chord_sheet_blocks.append(("image", CHORD_SHEET_IMAGE))
    chord_sheet_blocks.append(
        ("text", variant(
            "Fret cards and Tab need a fretted instrument, picked in Playback "
            "→ Voicing (for example Guitar). Show or hide the panel with "
            "View → Chord Sheet.",
            "Fret cards and Tab need a fretted instrument, picked in ⋮ → "
            "Playback → Voicing (for example Guitar). Show or hide the panel "
            "with ⋮ → View → Chord Sheet.")))

    return [
        {
            "title": "Welcome to Chord Notepad",
            "blocks": [
                ("text",
                 "Chord Notepad is a text editor for musicians. Write a song the way "
                 "a chord sheet looks: chords on their own line, right above the "
                 "lyrics they go with."),
                ("snippet",
                 "C        C/E      F      C\n"
                 "Twinkle, twinkle, little star,\n"
                 "Dm    Am     G        C\n"
                 "How I wonder what you are!",
                 "american"),
                ("text", variant(
                    "The app recognizes chord lines on its own and highlights their "
                    "chords; lyric lines are left alone. Click any chord in the editor "
                    "to hear it, or press ▶ in the toolbar to play the whole song.",
                    "The app recognizes chord lines on its own and highlights their "
                    "chords; lyric lines are left alone. Tap any chord in the editor "
                    "to hear it, or press ▶ in the toolbar to play the whole song.")),
            ],
        },
        {
            "title": "How Chord Lines Are Detected",
            "blocks": [
                ("text",
                 "There is nothing to mark up. A line counts as a chord line when "
                 "most of its words are chords, so a lyric that happens to contain "
                 "a word like “A” stays plain text."),
                ("snippet",
                 "G              D/F#        Em          C\n"
                 "A song for you, a melody I made\n"
                 "Am7   Dsus4   Cmaj7   G/B   F#m7b5   E7#9",
                 "american"),
                ("text",
                 "Chords can be as rich as you need: sevenths, suspended and added "
                 "notes, extensions, altered notes, and slash chords for a specific "
                 "bass note."),
            ],
        },
        {
            "title": "Do-Re-Mi and Roman Numerals",
            "blocks": [
                ("text",
                 "Prefer solfège? Switch to European notation with the Do button "
                 "in the toolbar and write chords as Do, Re, Mi… with a lowercase "
                 "m for minor."),
                ("snippet",
                 "Do        Lam       Rem7      Sol7\n"
                 "Somewhere a melody is calling\n"
                 "Fa        Do/Mi     Rem       Sol\n"
                 "Every note is coming home",
                 "european"),
                ("text",
                 "Roman numerals write chords relative to the key, set with "
                 "{key: …} or the Key box. Change the key and the same song plays "
                 "in the new key."),
                ("snippet",
                 "{key: G}\n"
                 "I         vi        IV        V7\n"
                 "Here's a tune in any key you like\n"
                 "ii7       V7        I\n"
                 "Play it high or play it low",
                 "american"),
            ],
        },
        {
            "title": "Tempo, Meter and Timing",
            "blocks": [
                ("text",
                 "Directives in {braces} set the tempo, time signature and key. They "
                 "can go anywhere, so a song can speed up or change key halfway "
                 "through."),
                ("snippet",
                 "{bpm: 90} {time: 3/4}\n"
                 "G         G7        C*6\n"
                 "Walking slow in waltz time,\n"
                 "D7*1.5   C*1.5    G     NC\n"
                 "step and turn and home",
                 "american"),
                ("text",
                 "Each chord lasts one bar unless you add *beats after it: C*6 holds "
                 "for two bars of 3/4, D7*1.5 for a beat and a half. NC is a bar of "
                 "silence. The toolbar's Speed, Key and Time controls set the "
                 "defaults for the whole song."),
            ],
        },
        {
            "title": "Song Structure",
            "blocks": [
                ("text",
                 "Name a section with {label: …} and repeat it with {loop: name "
                 "times}. Lines starting with // are comments: they're notes for you "
                 "and are never played."),
                ("snippet",
                 "{label: chorus}\n"
                 "F         C         G         Am\n"
                 "Sing it loud and sing it clear,\n"
                 "F         C         G\n"
                 "everybody gather near\n"
                 "// Chorus twice at the end\n"
                 "{loop: chorus 2}",
                 "american"),
                ("text", variant(
                    "Tools → Insert has small dialogs for adding labels, loops and "
                    "other directives if you'd rather not type them.",
                    "⋮ → Tools → Insert has small dialogs for adding labels, loops and "
                    "other directives if you'd rather not type them.")),
            ],
        },
        {
            "title": "The Chord Sheet",
            "blocks": chord_sheet_blocks,
        },
        {
            "title": "You're Ready!",
            "blocks": [
                ("text", "That's all you need to get started."),
                ("text", variant(
                    "Press F1 any time for the full User Guide (also in the Help menu). "
                    "Tools → Identify Chord names a chord from the notes you pick, "
                    "and Help → Quick Start brings this tour back.",
                    "The full User Guide is in ⋮ → Help → User Guide. ⋮ → Tools → "
                    "Identify Chord names a chord from the notes you pick, and "
                    "⋮ → Help → Quick Start brings this tour back.")),
                ("text", "Have fun making music!"),
            ],
        },
    ]
