"""The standard set of chord-sheet strip renderers, in view-picker order."""

from typing import List

from chord_sheet.fret_card import FretCardRenderer
from chord_sheet.piano_roll import PianoRollRenderer
from chord_sheet.renderer_interface import StripRenderer
from chord_sheet.staff_card import StaffCardRenderer
from chord_sheet.tab_strip import TabStripRenderer


def default_renderers() -> List[StripRenderer]:
    """Build the standard renderer set, in view-picker order.

    Piano roll, Staff, Chord box, then Tab. The two fretted views declare
    ``requires_fingering`` so the viewmodel gates them out for songs voiced
    without fingering data (e.g. piano/ensemble).
    """
    return [
        PianoRollRenderer(),
        StaffCardRenderer(),
        FretCardRenderer(),
        TabStripRenderer(),
    ]
