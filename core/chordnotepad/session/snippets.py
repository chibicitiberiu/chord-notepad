"""The Directives palette (the Qt Edit sidebar), as plain data.

Every tile inserts a snippet: a directive's usual form with its value
selected, so typing replaces it (or the ▾ picker after it changes it), or a
bit of text (a rest, a comment). ``AppSession.insert_snippet`` inserts one
as a single undo step; :func:`fill_snippet` makes the template valid where
it goes first (a key in the song's notation, a label not taken yet, a loop
to a label above it), and :func:`select_range` is what gets selected.

The texts are the approved mockup's (``DirectivePalette.qml``). The
duration tiles come after the switch (plan step B4, "after the switch").
"""

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

from chordnotepad.models.notation import (
    AMERICAN_DIRECTIVE_KEYS, EUROPEAN_DIRECTIVE_KEYS, Notation, directive_key_names,
)
from chordnotepad.session.directives import LOOP_START
from chordnotepad.session.pickers import loop_parts

#: One directive on its own: ``{keyword: value}`` (no braces or newline inside).
_DIRECTIVE = re.compile(r"^\{([^{}\n:]*)(:\s*)([^{}\n]*?)\s*\}$")
_COMMENT_PREFIX = "// "


@dataclass(frozen=True)
class Snippet:
    """A palette tile.

    Attributes:
        id: Stable name, for tests and object names (``tempo``, ``key-minor``).
        icon: The tile's icon (``pal-<icon>`` in the Qt icon set).
        caption: The tiny caption under the icon ("" for none).
        text: What a click inserts (before :func:`fill_snippet`).
        name: The tooltip's title.
        hint: The tooltip's explanation.
    """

    id: str
    icon: str
    caption: str
    text: str
    name: str
    hint: str


@dataclass(frozen=True)
class SnippetGroup:
    """A palette group: its caption and tiles."""

    title: str
    snippets: Tuple[Snippet, ...]


PALETTE: Tuple[SnippetGroup, ...] = (
    SnippetGroup("Tempo", (
        Snippet("tempo", "tempo", "120", "{bpm: 120}", "Tempo", "Beats per minute from here on."),
        Snippet("tempo-faster", "tempo", "+10", "{bpm: +10}", "Faster",
                "Raises the tempo by this many bpm."),
        Snippet("tempo-slower", "tempo", "−10", "{bpm: -10}", "Slower",
                "Lowers the tempo by this many bpm."),
        Snippet("tempo-percent", "tempo", "%", "{bpm: 50%}", "Tempo percent",
                "Changes the tempo by a percentage."),
        Snippet("tempo-multiplier", "tempo", "×2", "{bpm: 2x}", "Tempo multiplier",
                "Multiplies the tempo."),
        Snippet("tempo-reset", "tempo-reset", "reset", "{bpm: reset}", "Reset tempo",
                "Back to the song's starting tempo."),
    )),
    SnippetGroup("Time · key · capo", (
        Snippet("time", "time", "", "{time: 3/4}", "Time signature",
                "Beats per bar, and the beat's note value, from here on."),
        Snippet("key-major", "key-major", "", "{key: G}", "Major key",
                "For roman numerals and the staff's key signature."),
        Snippet("key-minor", "key-minor", "", "{key: Am}", "Minor key",
                "For roman numerals and the staff's key signature."),
        Snippet("capo", "capo", "", "{capo: 3}", "Capo", "Capo fret for the fretted views."),
    )),
    SnippetGroup("Sections", (
        Snippet("label", "label", "", "{label: verse}", "Label",
                "Names this point, so a loop can repeat from it."),
        Snippet("loop", "loop", "", "{loop: verse}", "Repeat", "Plays the labelled section again."),
        Snippet("loop-3", "loop", "×3", "{loop: verse 3}", "Repeat ×3",
                "Plays the labelled section this many times."),
        Snippet("loop-start", "loop-start", "start", "{loop: @start 2}", "Repeat from the start",
                "Plays from the top of the song again, this many times."),
    )),
    SnippetGroup("Text", (
        Snippet("rest", "rest", "NC", "NC", "Rest (no chord)",
                "No chord: silence on a chord line, as long as a chord would last."),
        Snippet("comment", "comment", "", "// comment", "Comment", "Text that isn't played."),
    )),
)


def snippet(snippet_id: str) -> Snippet:
    """The palette tile ``snippet_id``.

    Raises:
        KeyError: If there is none.
    """
    for group in PALETTE:
        for tile in group.snippets:
            if tile.id == snippet_id:
                return tile
    raise KeyError(snippet_id)


def split_directive(text: str) -> Optional[Tuple[str, int, int]]:
    """For a text that is exactly one ``{keyword: value}``: its keyword (as
    typed, stripped) and where its value starts and ends; else None."""
    match = _DIRECTIVE.match(text)
    if match is None:
        return None
    return match.group(1).strip(), match.start(3), match.end(3)


def select_range(text: str) -> Optional[Tuple[int, int]]:
    """What to select after inserting ``text``, as offsets into it: a
    directive's value, a comment's words; None for anything else (the
    caret goes after it)."""
    directive = split_directive(text)
    if directive is not None:
        _, start, end = directive
        return (start, end) if start < end else None
    if text.startswith(_COMMENT_PREFIX) and len(text) > len(_COMMENT_PREFIX):
        return len(_COMMENT_PREFIX), len(text)
    return None


def _respell_key(key: str, notation: str) -> str:
    for names in (AMERICAN_DIRECTIVE_KEYS, EUROPEAN_DIRECTIVE_KEYS):
        if key in names:
            return directive_key_names(notation)[names.index(key)]
    return key


def _free_label(label: str, taken: Iterable[str]) -> str:
    taken = set(taken)
    if label not in taken:
        return label
    n = 2
    while f"{label}{n}" in taken:
        n += 1
    return f"{label}{n}"


def fill_snippet(text: str, *, notation: str = Notation.AMERICAN.value,
                 labels: Sequence[str] = (), labels_above: Sequence[str] = ()) -> str:
    """``text`` made valid where it goes; anything but a directive is kept.

    - ``{key}``: the key in ``notation`` (``{key: Sol}`` in a European song).
    - ``{label}``: a name the song doesn't have yet (``verse2``, ``verse3``).
    - ``{loop}``: a label above it, the nearest one if the one named isn't
      (``labels_above`` is in song order), else ``@start``; the count stays.

    Args:
        text: A palette snippet (or any text).
        notation: The song's notation.
        labels: Every label in the song.
        labels_above: The labels above the place it goes, in song order.
    """
    directive = split_directive(text)
    if directive is None:
        return text
    keyword, start, end = directive
    value = text[start:end]
    kind = keyword.lower()
    if kind == "key":
        value = _respell_key(value, notation)
    elif kind == "label":
        value = _free_label(value, labels)
    elif kind == "loop":
        label, count = loop_parts(value)
        explicit = value.strip() != label
        if label != LOOP_START and label not in labels_above:
            label = labels_above[-1] if labels_above else LOOP_START
        value = f"{label} {count}" if explicit else label
    else:
        return text
    return text[:start] + value + text[end:]
