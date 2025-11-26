"""Help window launcher.

Launches the help viewer as a separate process using pywebview.
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def show_help(docs_path: str) -> bool:
    """Launch the help viewer window.

    Args:
        docs_path: Path to the HTML documentation directory

    Returns:
        True if help was launched successfully, False otherwise
    """
    index_path = os.path.join(docs_path, 'index.html')

    if not os.path.exists(index_path):
        logger.error(f"Documentation not found: {index_path}")
        return False

    try:
        help_viewer_path = os.path.join(os.path.dirname(__file__), 'help_viewer.py')
        subprocess.Popen([sys.executable, help_viewer_path, docs_path])
        logger.info("Help viewer launched")
        return True
    except Exception as e:
        logger.error(f"Failed to launch help viewer: {e}")
        return False
