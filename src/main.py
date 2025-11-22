#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application.
"""

import sys
import tkinter as tk
from ui.main_window import MainWindow

# Import build info for logging
try:
    from build_info import VERSION, BUILD_TYPE, COMMIT_HASH, BUILD_DATE
except ImportError:
    VERSION = "dev-local"
    BUILD_TYPE = "development"
    COMMIT_HASH = "unknown"
    BUILD_DATE = "unknown"


def main():
    """Main entry point"""
    # Log version information at startup
    print("=" * 60)
    print("Chord Notepad")
    print("=" * 60)
    print(f"Version:    {VERSION}")
    print(f"Build Type: {BUILD_TYPE}")
    print(f"Commit:     {COMMIT_HASH}")
    print(f"Build Date: {BUILD_DATE}")
    print("=" * 60)
    print()

    root = MainWindow()
    root.mainloop()


if __name__ == "__main__":
    main()
