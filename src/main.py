#!/usr/bin/env python3
"""
Chord Notepad - A simple text editor with chord detection and playback

Entry point for the application.
"""

import sys
import tkinter as tk
from ui.main_window import MainWindow


def main():
    """Main entry point"""
    root = MainWindow()
    root.mainloop()


if __name__ == "__main__":
    main()
