#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application.
"""

import sys

from application import Application


def main():
    """Thin wrapper that delegates to Application.main()"""
    exit_code = Application.main()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
