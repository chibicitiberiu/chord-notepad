"""The Licences window: every component of this build, its licence and full text.

A thin view over :class:`services.licence_catalog.LicenceCatalog`: the list,
the details and the texts all come from there.
"""

import logging
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Dict, Optional

from services.licence_catalog import LicenceCatalog, LicenceEntry

logger = logging.getLogger(__name__)

_SOURCE_ITEM = "__source__"
# Same blue as the scrubber values (ui/scrubber.py).
LINK_COLOR = "#1565c0"


class LicencesDialog(tk.Toplevel):
    """Lists the components on the left, the selected one's licence on the right."""

    def __init__(self, parent: tk.Misc, catalog: LicenceCatalog):
        """Build the window.

        Args:
            parent: The window it opens over (the main window or About).
            catalog: What to show (see ``services.licence_catalog.load_for_this_app``).
        """
        super().__init__(parent)
        self.title("Open Source Licences")
        self.transient(parent)
        self.geometry("900x580")
        self.minsize(640, 400)
        self._catalog = catalog
        self._previous_grab = parent.grab_current()
        self._items: Dict[str, LicenceEntry] = {}
        self._url: Optional[str] = None

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        intro = ("Chord Notepad is built from these components. Select one to read its licence; "
                 "\"Source code\" says where to get the source of each.")
        ttk.Label(outer, text=intro, wraplength=860, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 8))

        panes = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes)
        self._tree = ttk.Treeview(left, columns=("license",), show="tree headings", selectmode="browse")
        self._tree.heading("#0", text="Component")
        self._tree.heading("license", text="Licence")
        self._tree.column("#0", width=230, stretch=True)
        self._tree.column("license", width=150, stretch=True)
        tree_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        panes.add(left, weight=2)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        self._title = ttk.Label(right, font=("TkDefaultFont", 11, "bold"))
        self._title.pack(anchor=tk.W)
        self._details = ttk.Label(right, justify=tk.LEFT, wraplength=480)
        self._details.pack(anchor=tk.W, fill=tk.X, pady=(2, 2))
        self._link = ttk.Label(right, foreground=LINK_COLOR, cursor="hand2")
        self._link.pack(anchor=tk.W, pady=(0, 6))
        self._link.bind("<Button-1>", lambda _e: self._open_url())
        text_frame = ttk.Frame(right)
        text_frame.pack(fill=tk.BOTH, expand=True)
        self._text = tk.Text(text_frame, wrap=tk.WORD, font="TkFixedFont", padx=8, pady=6,
                             relief=tk.FLAT, borderwidth=1, highlightthickness=1)
        text_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=text_scroll.set, state=tk.DISABLED)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        panes.add(right, weight=3)

        buttons = ttk.Frame(outer)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Close", command=self._close).pack(side=tk.RIGHT)

        self._fill_tree()
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self._show_selected())
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._tree.selection_set(_SOURCE_ITEM)
        self._tree.focus(_SOURCE_ITEM)
        self._tree.focus_set()
        self.grab_set()

    def _fill_tree(self) -> None:
        self._tree.insert("", tk.END, iid=_SOURCE_ITEM, text="Source code", values=("",))
        for key, heading, entries in self._catalog.groups():
            group = self._tree.insert("", tk.END, iid=f"group:{key}", text=heading, open=True, values=("",))
            for entry in entries:
                label = f"{entry.name} {entry.version}" if entry.version else entry.name
                self._items[entry.id] = entry
                self._tree.insert(group, tk.END, iid=entry.id, text=label, values=(entry.license,))

    def _show_selected(self) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid == _SOURCE_ITEM:
            self._show("Source code", "", None, self._catalog.source_offer)
            return
        entry = self._items.get(iid)
        if entry is None:  # a group heading
            return
        lines = [f"Licence: {entry.license}"]
        if entry.copyright:
            lines.append(f"Copyright: {entry.copyright}")
        if entry.note:
            lines.append(entry.note)
        if entry.source_url and entry.source_url != entry.url:
            lines.append(f"Source: {entry.source_url}")
        title = f"{entry.name} {entry.version}" if entry.version else entry.name
        self._show(title, "\n".join(lines), entry.url, self._catalog.text_of(entry))

    def _show(self, title: str, details: str, url: Optional[str], text: str) -> None:
        self._title.configure(text=title)
        self._details.configure(text=details)
        self._url = url
        self._link.configure(text=url or "")
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.configure(state=tk.DISABLED)
        self._text.yview_moveto(0)

    def _open_url(self) -> None:
        if self._url:
            try:
                webbrowser.open(self._url)
            except Exception as exc:  # noqa: BLE001 - no browser is not an error worth a dialog
                logger.warning("Could not open %s: %s", self._url, exc)

    def _close(self) -> None:
        self.grab_release()
        self.destroy()
        if self._previous_grab is not None:
            try:
                self._previous_grab.grab_set()
            except tk.TclError:
                pass
