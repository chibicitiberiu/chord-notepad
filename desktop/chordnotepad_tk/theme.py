"""The Tk UI's colours and the editor's text tags.

Desktop-only: the core and Android never read these. The Android editor
mirrors the editor colours as its own values (``EditorStyles.kt``), so a
change here is a change to both looks.
"""

# UI chrome palette (toolbar, borders, scrollbars, status bar). The editor's
# text and chord colors are deliberately not part of this. UI_BG is only
# applied on themes we restyle (clam); native themes keep their own surface.
UI_BG = "#f3f3f3"
UI_BORDER = "#cfcfcf"
UI_HOVER = "#e2e2e2"
UI_ACCENT = "#0078d4"
UI_ACCENT_ACTIVE = "#006cc1"
UI_TEXT_MUTED = "#5c5c5c"
UI_TEXT_DISABLED = "#a3a3a3"
# Unselected tab fill (the chord-sheet view tabs).
UI_TAB_IDLE = "#e7e7e7"
UI_SCROLL_THUMB = "#c4c4c4"
UI_SCROLL_THUMB_ACTIVE = "#a6a6a6"
# Tint behind draggable numeric values (BPM, speed %) in the toolbar.
UI_SCRUB_BG = "#e6effa"
UI_SCRUB_HOVER = "#d4e4f7"

# Text editor tags
TAG_CHORD_VALID = "chord"
TAG_CHORD_INVALID = "chord_invalid"
TAG_CHORD_PLAYING = "chord_playing"
TAG_DIRECTIVE_VALID = "directive_valid"
TAG_DIRECTIVE_INVALID = "directive_invalid"
TAG_DIRECTIVE_REDUNDANT = "directive_redundant"
TAG_COMMENT = "comment"

# Editor colours (Tk colour names)
COLOR_CHORD_VALID = "blue"
COLOR_CHORD_INVALID = "gray"
COLOR_COMMENT = "gray"
COLOR_CHORD_PLAYING_BG = "yellow"
COLOR_DIRECTIVE_VALID = "#8B4789"  # Purple for directives
COLOR_DIRECTIVE_INVALID = "red"
# A redundant directive (no effect) is the directive colour at this strength
# over the editor background (Tk text has no alpha).
DIRECTIVE_REDUNDANT_STRENGTH = 0.45
