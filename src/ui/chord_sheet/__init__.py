"""Chord sheet strip: a bottom-docked panel of voiced-chord cards.

This package holds the headless-testable pieces of the chord sheet feature:

- :mod:`ops` -- a draw-op recorder so renderers never touch Tk directly.
- :mod:`renderer_interface` -- the frozen plugin contract for strip renderers.
- :mod:`name_card` -- a placeholder renderer drawing chord-symbol cards.
- :mod:`panel` -- the Tk panel shell that hosts the scrolling canvas.

The four "real" renderers (keyboard diagram, grand staff, guitar fret box, and
tab view) plug in later via :class:`renderer_interface.StripRenderer` without
touching this contract.
"""
