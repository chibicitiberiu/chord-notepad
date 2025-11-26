"""Standalone help viewer using pywebview.

This module runs as a separate process from the main application,
providing complete isolation between the Tkinter GUI and the webview.

Usage:
    python help_viewer.py <docs_path>
"""

import os
import sys

# Disable hardware acceleration and force software rendering
# This avoids GBM buffer issues on Linux
if sys.platform.startswith('linux'):
    os.environ['WEBKIT_DISABLE_COMPOSITING_MODE'] = '1'
    os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'


def main() -> None:
    """Launch the help viewer window."""
    if len(sys.argv) < 2:
        print("Usage: python help_viewer.py <docs_path>", file=sys.stderr)
        sys.exit(1)

    docs_path = sys.argv[1]
    index_path = os.path.join(docs_path, 'index.html')

    if not os.path.exists(index_path):
        print(f"Documentation not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import webview
    except ImportError:
        print("pywebview not installed. Run: pipenv install pywebview", file=sys.stderr)
        sys.exit(1)

    url = f'file://{index_path}'

    webview.create_window(
        title='Chord Notepad Help',
        url=url,
        width=1000,
        height=700,
        resizable=True,
        text_select=True,
    )

    # Use GTK backend explicitly on Linux
    gui = 'gtk' if sys.platform.startswith('linux') else None
    webview.start(gui=gui)


if __name__ == '__main__':
    main()
