"""Menu outline for the restyled (clam) look on X11.

Tk draws X11 menu borders in shades derived from the menu background (the
dark one is 60% of it), so a raised or ridged border comes out as a heavy
grey line, and there is no option for its color. Instead, the menu's own
background becomes the outline color, behind a flat one-pixel border, and
every entry is painted in the normal menu color, so only the border shows
the menu background.

Separators stay Tk's own: Tk draws them in shades of the menu background
too, with no option for their color.

Entries added later (menus rebuilt at runtime) are painted each time the
menu opens. Windows and macOS menus are native and keep their own look.
"""

import tkinter as tk
from tkinter import ttk
from typing import Iterator

from constants import UI_BG, UI_BORDER


def style_menu(menu: tk.Menu) -> None:
    """Give an X11 menu a soft one-pixel outline.

    Only applies with the restyled clam theme on X11; elsewhere it does
    nothing.

    Args:
        menu: Dropdown or popup menu (not a menubar)
    """
    if menu.tk.call('tk', 'windowingsystem') != 'x11':
        return
    if ttk.Style(menu).theme_use() != 'clam':
        return

    def paint_entries() -> None:
        last = menu.index('end')
        if last is None:
            return
        for index in range(last + 1):
            if menu.type(index) == 'tearoff':
                continue
            if not str(menu.entrycget(index, 'background')):
                menu.entryconfigure(index, background=UI_BG)

    previous_postcommand = menu.cget('postcommand')

    def refresh() -> None:
        if previous_postcommand:
            menu.tk.eval(previous_postcommand)
        paint_entries()

    menu.configure(background=UI_BORDER, relief=tk.FLAT, borderwidth=1)
    paint_entries()
    menu.configure(postcommand=refresh)


def iter_menus(widget: tk.Misc) -> Iterator[tk.Menu]:
    """Yield every menu below a widget, depth first."""
    for child in widget.winfo_children():
        if isinstance(child, tk.Menu):
            yield child
        yield from iter_menus(child)
