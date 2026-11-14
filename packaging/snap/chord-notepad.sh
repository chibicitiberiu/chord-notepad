#!/bin/sh
# Inside the snap, XDG_RUNTIME_DIR points at a per-snap folder, so libpulse
# can't find the user's PulseAudio/PipeWire socket on its own.
if [ -z "$PULSE_SERVER" ]; then
    export PULSE_SERVER="unix:/run/user/$(id -u)/pulse/native"
fi
app="$SNAP/share/chord-notepad/"
export PYTHONPATH="${app}core:${app}desktop${PYTHONPATH:+:$PYTHONPATH}"
exec "$SNAP/bin/python3" -m chordnotepad_tk.main "$@"
