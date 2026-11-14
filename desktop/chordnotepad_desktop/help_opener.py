"""Help opens in the system browser (parity checklist §7, "Help").

The Qt port of ``chordnotepad_tk/help_window.py`` (Tk goes after the
switch, so the Qt package can't use it): the built help's ``index.html``
as a file URL, or, under Flatpak and Snap, where the browser outside the
sandbox can't read the app's files, from a local HTTP server on 127.0.0.1
with a random port (one per run, started on first use). The URL is opened
with ``QDesktopServices`` (the OpenURI portal in a sandbox). The messages
are Tk's; the window shows them as "Help Unavailable".
"""

import http.server
import logging
import os
import socketserver
import threading
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from chordnotepad.exceptions import ChordNotepadError

logger = logging.getLogger(__name__)

#: The dialog's title (Tk's ``messagebox.showwarning`` title).
HELP_UNAVAILABLE_TITLE = "Help Unavailable"


def is_sandboxed() -> bool:
    """Whether the app runs inside Flatpak or Snap."""
    return bool(os.environ.get("FLATPAK_ID") or os.environ.get("SNAP"))


class HelpServer:
    """Serves the help folder on 127.0.0.1 (a random free port) from a daemon thread."""

    def __init__(self, docs_path: str) -> None:
        self.docs_path = docs_path
        self.server: Optional[socketserver.TCPServer] = None
        self.port: Optional[int] = None

    def start(self) -> int:
        def handler(*args, **kwargs):
            return http.server.SimpleHTTPRequestHandler(*args, directory=self.docs_path, **kwargs)

        self.server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        logger.info("Help server started on port %s", self.port)
        return self.port

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            logger.info("Help server stopped")


class HelpOpener:
    """Opens the help; keeps the sandbox's server running between calls.

    Args:
        docs_path: The built help (``AppPaths.help_html``), or None.
        open_url: Opens a URL, True if it could (``QDesktopServices.openUrl``).
        sandboxed: Whether to serve over HTTP (:func:`is_sandboxed` by default).
    """

    def __init__(self, docs_path: Optional[Path],
                 open_url: Optional[Callable[[str], bool]] = None,
                 sandboxed: Optional[bool] = None) -> None:
        self._docs_path = str(docs_path) if docs_path is not None else ""
        self._open_url = open_url or (lambda url: QDesktopServices.openUrl(QUrl(url)))
        self._sandboxed = is_sandboxed() if sandboxed is None else sandboxed
        self._server: Optional[HelpServer] = None

    def open(self) -> str:
        """Open the help in the browser and return its URL.

        Raises:
            ChordNotepadError: The help isn't there or no browser opened it;
                the message says what to do.
        """
        index = os.path.join(self._docs_path, "index.html") if self._docs_path else ""
        if not index or not os.path.exists(index):
            logger.error("Documentation not found: %s", index or "(no help folder)")
            raise ChordNotepadError(
                "Could not find the help documentation.\n\n"
                f"Looked in: {self._docs_path}\n\n"
                "If you run from source, build it first with:\n"
                "  make docs-html")
        url = None
        try:
            if self._sandboxed:
                if self._server is None or self._server.server is None:
                    self._server = HelpServer(self._docs_path)
                    self._server.start()
                url = f"http://127.0.0.1:{self._server.port}/index.html"
            else:
                url = QUrl.fromLocalFile(os.path.abspath(index)).toString()
            logger.info("Opening help: %s", url)
            opened = self._open_url(url)
        except Exception as e:
            logger.error("Failed to open help: %s", e, exc_info=True)
            message = f"Could not open the help.\n\n{e}"
            if url:
                message += f"\n\nYou can open it yourself at:\n{url}"
            raise ChordNotepadError(message) from e
        if not opened:
            logger.error("No web browser could open %s", url)
            raise ChordNotepadError(
                "Could not open a web browser to show the help.\n\n"
                f"You can open it yourself at:\n{url}")
        return url

    def stop(self) -> None:
        """Stop the help server, if one runs."""
        if self._server is not None:
            self._server.stop()
            self._server = None
