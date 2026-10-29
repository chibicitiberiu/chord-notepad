"""Headless chord-sheet renderers, shared by the desktop and Android UIs.

- :mod:`ops` -- a draw-op recorder so renderers never touch a toolkit directly.
- :mod:`renderer_interface` -- the frozen plugin contract for strip renderers.
- :mod:`piano_roll`, :mod:`staff_card`, :mod:`fret_card`, :mod:`tab_strip`
  -- the four strip renderers (piano roll, grand staff, guitar fret box,
  and tab view), each a :class:`renderer_interface.StripRenderer`.
- :mod:`marker_lane` -- the pure geometry for the timeline marker lane drawn
  above every view.
- :mod:`clef_assets` -- embedded clef images + placement math for the staff view.

The Tk side (the panel and the canvas replay) lives in :mod:`ui.chord_sheet`.
"""
