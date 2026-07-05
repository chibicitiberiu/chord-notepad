"""Chord sheet strip: a bottom-docked panel of voiced-chord cards.

This package holds the headless-testable pieces of the chord sheet feature:

- :mod:`ops` -- a draw-op recorder so renderers never touch Tk directly.
- :mod:`renderer_interface` -- the frozen plugin contract for strip renderers.
- :mod:`piano_roll`, :mod:`staff_card`, :mod:`fret_card`, :mod:`tab_strip`
  -- the four strip renderers (piano roll, grand staff, guitar fret box,
  and tab view), each a :class:`renderer_interface.StripRenderer`.
- :mod:`marker_lane` -- the pure geometry for the timeline marker lane the
  panel draws above every view.
- :mod:`clef_assets` -- embedded clef images + placement math for the staff view.
- :mod:`panel` -- the Tk panel shell that hosts the scrolling canvas.
"""
