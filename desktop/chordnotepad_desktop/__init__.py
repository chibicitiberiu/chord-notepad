"""Chord Notepad's Qt Quick desktop front end (``--ui qt``), being built.

It replaces the Tk front end (``chordnotepad_tk``) at the 0.6.0 switch. It
talks to the core (``chordnotepad``) only, never to ``chordnotepad_tk``,
which is deleted the release after; the one exception is the shared entry
point (``chordnotepad_tk.main``), which starts it.

Keep this file free of imports: the entry point checks that PySide6 is
installed before it imports anything from here.
"""
