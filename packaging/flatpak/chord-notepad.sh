#!/bin/sh
app=/app/share/chord-notepad/
export PYTHONPATH="${app}core:${app}desktop${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m chordnotepad_desktop "$@"
