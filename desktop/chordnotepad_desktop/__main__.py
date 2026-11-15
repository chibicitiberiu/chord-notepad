"""``python -m chordnotepad_desktop`` (and the PyInstaller bundle's script).

All the start-up is in :mod:`chordnotepad_desktop.launcher`; this file only
calls it, with an absolute import, since PyInstaller runs it as a script.
"""

from chordnotepad_desktop.launcher import main

main()
