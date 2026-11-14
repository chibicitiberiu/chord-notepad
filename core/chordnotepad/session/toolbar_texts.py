"""The tooltips of the song values and the transport (the Tk toolbar, the Qt
player bar).

Both desktop front ends show these; they were the Tk main window's
constants. :func:`set_by_tooltip` is the text of a value the song sets with a
directive. Where the Qt window works differently (its ▶ plays from the
playhead, its time signature is one value) :func:`play_pause_tooltip` and
:data:`TIME_TOOLTIP` have its wording.
"""

from chordnotepad.session import platform
from chordnotepad.session.state import PlayAction

BPM_TOOLTIP = ("Beats per minute for this song (the default is in Settings). Drag to change, "
               "click to type, middle-click to reset to 120. Pause to change it while a "
               "song plays.")
KEY_TOOLTIP = ("Key for roman numeral chords and the Staff view's key signature in this song "
               "(the default is in Settings). Pause to change it while a song plays.")
BEATS_TOOLTIP = "Beats per measure (pause to change it while a song plays)"
UNIT_TOOLTIP = "Beat unit, 4 = quarter note (pause to change it while a song plays)"
#: The Qt player's time signature, one value for Tk's two spinboxes.
TIME_TOOLTIP = ("Time signature for this song: beats per measure over the beat unit, "
                "4 = quarter note (the default is in Settings). Pause to change it while "
                "a song plays.")
MULTIPLIER_TOOLTIP = ("Speed multiplier applied on top of BPM. Middle-click to reset to 100%. "
                      "Adjustable during playback.")
METRONOME_TOOLTIP = "Click track during playback. Toggle this on, then press Play."
STOP_TOOLTIP = "Stop playback"
#: The notation toggle's two halves (Tk's AB | Do buttons, the Qt AB|Do).
AMERICAN_TOOLTIP = "American notation (C, D, E...)"
EUROPEAN_TOOLTIP = "European notation (Do, Re, Mi...)"
#: The notations by name, as the Qt status bar shows the song's.
NOTATION_NAMES = {"american": "American", "european": "European"}


def convert_tooltip(target: str) -> str:
    """The Qt toolbar's Convert button, which converts the song's chords to
    ``target`` (``american`` or ``european``), the notation it isn't in."""
    if target == "european":
        return "Convert the song's chords to European notation (Do, Re, Mi...)"
    return "Convert the song's chords to American notation (C, D, E...)"

_PLAY_PAUSE_TOOLTIPS = {
    platform.DESKTOP: {
        PlayAction.PLAY: "Play from start (Shift+Click to play from cursor)",
        PlayAction.PAUSE: "Pause playback",
        PlayAction.RESUME: "Resume playback",
    },
    # The Qt window has a playhead: ▶ starts there (resolution 7).
    platform.DESKTOP_QT: {
        PlayAction.PLAY: "Play from the playhead (Shift+Click to play from cursor)",
        PlayAction.PAUSE: "Pause playback",
        PlayAction.RESUME: "Resume playback",
    },
}


def set_by_tooltip(directive: str) -> str:
    """The tooltip of a song value the song sets with ``directive``."""
    return f"Set by {directive} in the song"


def play_pause_tooltip(action: PlayAction, platform_name: str = platform.DESKTOP) -> str:
    """What the Play/Pause button's tooltip says it does now."""
    return platform.pick(_PLAY_PAUSE_TOOLTIPS, platform_name)[PlayAction(action)]
