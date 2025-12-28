"""Help window launcher.

Opens help documentation in the system browser. For sandboxed environments
(Flatpak/Snap), serves docs via a local HTTP server since the browser
cannot access container-internal file paths.
"""

import http.server
import logging
import os
import socketserver
import threading
import webbrowser
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level server instance to keep it alive
_help_server: Optional['HelpServer'] = None


def is_sandboxed() -> bool:
    """Check if running in a sandboxed environment (Flatpak or Snap)."""
    return bool(os.environ.get('FLATPAK_ID') or os.environ.get('SNAP'))


class HelpServer:
    """Local HTTP server for serving help documentation."""

    def __init__(self, docs_path: str):
        """Initialize the help server.

        Args:
            docs_path: Path to the HTML documentation directory
        """
        self.docs_path = docs_path
        self.server: Optional[socketserver.TCPServer] = None
        self.port: Optional[int] = None

    def start(self) -> int:
        """Start the HTTP server on a random available port.

        Returns:
            The port number the server is listening on
        """
        # Create handler that serves from docs_path
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=self.docs_path, **kwargs
        )

        # Bind to random available port
        self.server = socketserver.TCPServer(('127.0.0.1', 0), handler)
        self.port = self.server.server_address[1]

        # Start server in daemon thread
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        logger.info(f"Help server started on port {self.port}")
        return self.port

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server = None
            logger.info("Help server stopped")


def show_help(docs_path: str) -> bool:
    """Open the help documentation in the system browser.

    Args:
        docs_path: Path to the HTML documentation directory

    Returns:
        True if help was opened successfully, False otherwise
    """
    global _help_server

    index_path = os.path.join(docs_path, 'index.html')

    if not os.path.exists(index_path):
        logger.error(f"Documentation not found: {index_path}")
        return False

    try:
        if is_sandboxed():
            # In sandboxed environment, serve via HTTP
            # Reuse existing server if still running
            if _help_server is None or _help_server.server is None:
                _help_server = HelpServer(docs_path)
                _help_server.start()

            url = f'http://127.0.0.1:{_help_server.port}/index.html'
            logger.info(f"Opening help via HTTP server: {url}")
        else:
            # Direct file URL for non-sandboxed environments
            url = f'file://{os.path.abspath(index_path)}'
            logger.info(f"Opening help via file URL: {url}")

        webbrowser.open(url)
        return True

    except Exception as e:
        logger.error(f"Failed to open help: {e}")
        return False
