"""The small dialogs and the Settings window (plan steps G1, G2): the Python side.

:class:`DialogsModel` is what ``qml/app/AppDialogs.qml`` works with, beside
the session's store:

* :attr:`DialogsModel.settings`: the Settings window's
  :class:`~chordnotepad_desktop.settings_window.SettingsModel`;
* :attr:`DialogsModel.about`: About's lines (version and build, from the
  build info the entry point hands over, or the dev-local values);
* :meth:`DialogsModel.licences` / :meth:`DialogsModel.licenceDetail`: the
  Licences window from the session's ``licence_catalog`` (a direct call);
* :meth:`DialogsModel.openHelp`: the help in the browser, "Help
  Unavailable" through the error presenter when it can't open;
* :meth:`DialogsModel.paintSnippet`: Quick Start's examples, highlighted
  with the editor's colours from the spans the session sent;
* :meth:`DialogsModel.resourceUrl`, :meth:`DialogsModel.openUrl`.

The texts are Tk's (``chordnotepad_tk/main_window.py`` About and
show_licences, ``dialogs/licences_dialog.py``); the Qt package can't import
the Tk one.
"""

import html
import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple

from PySide6.QtCore import Property, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QTextDocument
from PySide6.QtQuick import QQuickTextDocument

from chordnotepad.app_paths import AppPaths
from chordnotepad.exceptions import ChordNotepadError
from chordnotepad_desktop.editor_bridge import SpanHighlighter, char_formats
from chordnotepad_desktop.help_opener import HELP_UNAVAILABLE_TITLE, HelpOpener
from chordnotepad_desktop.offsets import OffsetMapper
from chordnotepad_desktop.settings_window import SettingsModel

logger = logging.getLogger(__name__)

#: The build info fields About shows (``chordnotepad_tk/build_info.py``,
#: which CI writes), in order, with their labels.
BUILD_FIELDS = (("VERSION", "Version:"), ("BUILD_TYPE", "Build Type:"),
                ("BUILD_NUMBER", "Build Number:"), ("COMMIT_SHORT", "Commit:"),
                ("BUILD_DATE", "Build Date:"))

#: About's texts (Tk's show_about).
ABOUT_DESCRIPTION = "A simple text editor for musicians with\nchord detection and playback"
ABOUT_COPYRIGHT = ("© 2025–2026 Tiberiu Chibici\nGNU AGPL-3.0 · github.com/chibicitiberiu/chord-notepad\n"
                   "Free software with ABSOLUTELY NO WARRANTY. You may share and change it\n"
                   "under the GNU AGPL-3.0 with the additional terms in Open Source Licences.")
#: The project's page, the link in About's copyright.
ABOUT_REPO = "github.com/chibicitiberiu/chord-notepad"
ABOUT_REPO_URL = "https://" + ABOUT_REPO
#: The same text for a rich-text label: line breaks, and the repository as a link.
ABOUT_COPYRIGHT_HTML = (html.escape(ABOUT_COPYRIGHT).replace("\n", "<br>")
                        .replace(ABOUT_REPO, f'<a href="{ABOUT_REPO_URL}">{ABOUT_REPO}</a>'))
#: The Licences window's intro and its error (Tk's).
LICENCES_INTRO = ("Chord Notepad is built from these components. Select one to read its licence; "
                  "\"Source code\" says where to get the source of each.")
LICENCES_UNAVAILABLE_TITLE = "Licences Unavailable"
#: The tree's first row.
SOURCE_ITEM = "__source__"
SOURCE_LABEL = "Source code"


def dev_build_info(paths: AppPaths) -> Dict[str, str]:
    """What a build without CI's build_info shows (Tk's dev-local values)."""
    return {"VERSION": f"v{paths.read_version()} (dev-local)", "BUILD_TYPE": "development",
            "BUILD_NUMBER": "0", "COMMIT_SHORT": "unknown", "BUILD_DATE": "unknown"}


class _StaticSpans:
    """Fixed spans for a :class:`SpanHighlighter` (a Quick Start snippet)."""

    playing_range = None

    def __init__(self, spans: List[Tuple[int, int, str]]) -> None:
        self._spans = sorted(spans)

    def spans_between(self, first: int, last: int) -> List[Tuple[int, int, str]]:
        return [s for s in self._spans if s[1] > first and s[0] < last]


class DialogsModel(QObject):
    """The dialogs' data and actions (see the module docstring).

    Args:
        store: The window's :class:`~chordnotepad_desktop.session_store.SessionStore`.
        paths: Where the app's files are (licences, help, icons, Quick Start images).
        presenter: The error presenter (``show_message``), for "Help Unavailable".
        build_info: ``BUILD_FIELDS``' values as the entry point read them from
            ``build_info.py``; None for the dev-local values.
    """

    #: The desktop's colour scheme changed (systemDark).
    systemDarkChanged = Signal()

    def __init__(self, store: Any, paths: AppPaths, presenter: Any = None,
                 build_info: Optional[Mapping[str, str]] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._paths = paths
        self._presenter = presenter
        info = dev_build_info(paths)
        info.update({k: str(v) for k, v in (build_info or {}).items() if k in info})
        self._build = info
        self._settings = SettingsModel(store, parent=self)
        self._help = HelpOpener(paths.help_html)
        self._catalog: Any = None
        # Quick Start's snippet highlighters, by document (pitfall 8: keep the wrappers).
        self._snippets: Dict[int, Tuple[QQuickTextDocument, SpanHighlighter]] = {}
        hints = QGuiApplication.styleHints()
        hints.colorSchemeChanged.connect(lambda *_: self.systemDarkChanged.emit())

    def _get_settings(self) -> QObject:
        return self._settings

    #: The Settings window's model.
    settings = Property(QObject, _get_settings, constant=True)

    def _get_system_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    #: The desktop asks for dark colours (the theme setting "Follow the system").
    systemDark = Property(bool, _get_system_dark, notify=systemDarkChanged)

    # -- About --------------------------------------------------------------------------

    def _get_about(self) -> dict:
        icon = self._paths.resources / "icon-128.png" if self._paths.resources else None
        return {
            "name": "Chord Notepad",
            "lines": [{"label": label, "value": self._build[key]} for key, label in BUILD_FIELDS],
            "description": ABOUT_DESCRIPTION,
            "copyright": ABOUT_COPYRIGHT,
            "copyrightHtml": ABOUT_COPYRIGHT_HTML,
            "icon": QUrl.fromLocalFile(str(icon)).toString() if icon and icon.is_file() else "",
        }

    #: About's content: ``name``, ``lines`` (``{label, value}``),
    #: ``description``, ``copyright`` (plain) and ``copyrightHtml`` (with the
    #: repository as a link), ``icon`` (a file URL or "").
    about = Property("QVariantMap", _get_about, constant=True)

    # -- Licences -----------------------------------------------------------------------

    @Slot(result="QVariantMap")
    def licences(self) -> dict:
        """The Licences tree: ``{ok, intro, rows}``. Each row is ``{id,
        label, licence, group}`` (a group heading has ``group: true``);
        "Source code" comes first. When the licence list can't be read,
        ``{ok: false}``, and "Licences Unavailable" goes to the error
        presenter (Tk's message)."""
        try:
            self._catalog = self._store.direct("licence_catalog", self._paths.licenses)
        except (OSError, ValueError, TypeError) as e:
            logger.error("Could not load the licence list: %s", e, exc_info=True)
            if self._presenter is not None:
                self._presenter.show_message(LICENCES_UNAVAILABLE_TITLE,
                                             f"Could not read the licence list.\n\n{e}")
            return {"ok": False}
        rows = [{"id": SOURCE_ITEM, "label": SOURCE_LABEL, "licence": "", "group": False}]
        for key, heading, entries in self._catalog.groups():
            rows.append({"id": f"group:{key}", "label": heading, "licence": "", "group": True})
            for entry in entries:
                rows.append({"id": entry.id, "label": _entry_title(entry),
                             "licence": entry.license, "group": False})
        return {"ok": True, "intro": LICENCES_INTRO, "rows": rows}

    @Slot(str, result="QVariantMap")
    def licenceDetail(self, entry_id: str) -> dict:  # noqa: N802 (Qt)
        """One row's details: ``{title, details, url, text}`` (empty for a heading)."""
        catalog = self._catalog
        if catalog is None:
            return {}
        if entry_id == SOURCE_ITEM:
            return {"title": SOURCE_LABEL, "details": "", "url": "", "text": catalog.source_offer}
        entry = catalog.get(entry_id)
        if entry is None:
            return {}
        lines = [f"Licence: {entry.license}"]
        if entry.copyright:
            lines.append(f"Copyright: {entry.copyright}")
        if entry.note:
            lines.append(entry.note)
        if entry.source_url and entry.source_url != entry.url:
            lines.append(f"Source: {entry.source_url}")
        return {"title": _entry_title(entry), "details": "\n".join(lines),
                "url": entry.url or "", "text": catalog.text_of(entry)}

    @Slot(str)
    def openUrl(self, url: str) -> None:  # noqa: N802 (Qt)
        """Open ``url`` in the browser (a failure is only logged, as in Tk)."""
        if url and not QDesktopServices.openUrl(QUrl(url)):
            logger.warning("Could not open %s", url)

    # -- Help ---------------------------------------------------------------------------

    @Slot()
    def openHelp(self) -> None:  # noqa: N802 (Qt)
        """Open the help in the browser, or say why it can't ("Help Unavailable")."""
        self.openHelpPage("index.html")

    @Slot(str)
    def openHelpPage(self, page: str) -> None:  # noqa: N802 (Qt)
        """Open one page of the help (``shortcuts.html``: Help › Keyboard
        shortcuts), or say why it can't."""
        try:
            self._help.open(page)
        except ChordNotepadError as e:
            if self._presenter is not None:
                self._presenter.show_message(HELP_UNAVAILABLE_TITLE, str(e))

    @property
    def help_opener(self) -> HelpOpener:
        """The help opener (tests replace its browser)."""
        return self._help

    def stop(self) -> None:
        """The window is going away: stop the help server."""
        self._help.stop()

    # -- Quick Start --------------------------------------------------------------------

    @Slot(str, result=str)
    def resourceUrl(self, relative: str) -> str:  # noqa: N802 (Qt)
        """A bundled file (``resources/quickstart/...``, as Quick Start names
        images) as a file URL, or "" if it isn't there."""
        if not relative or self._paths.resources is None:
            return ""
        parts = relative.replace("\\", "/").split("/")
        if parts[0] == "resources":
            parts = parts[1:]
        path = self._paths.resources.joinpath(*parts)
        if not path.is_file():
            logger.warning("Quick Start image missing: %s", relative)
            return ""
        return QUrl.fromLocalFile(str(path)).toString()

    @Slot(QQuickTextDocument, "QVariantList", "QVariantMap")
    def paintSnippet(self, document: QQuickTextDocument, spans: Any,  # noqa: N802 (Qt)
                     palette: dict) -> None:
        """Highlight a Quick Start snippet like the editor: ``spans`` are the
        session's (code points), ``palette`` EditorPane's colours."""
        doc: QTextDocument = document.textDocument()
        mapper = OffsetMapper(doc.toPlainText())
        painted = []
        for span in _plain_list(spans):
            start, end = mapper.range_to_utf16(int(span["start"]), int(span["end"]))
            if end > start:
                painted.append((start, end, str(span["kind"])))
        key = id(doc)
        old = self._snippets.pop(key, None)
        if old is not None:
            old[1].setDocument(None)
        highlighter = SpanHighlighter(doc, _StaticSpans(painted))
        highlighter.formats = char_formats(
            {k: v.name(QColor.NameFormat.HexArgb) if isinstance(v, QColor) else str(v)
             for k, v in palette.items()})
        highlighter.rehighlight()
        self._snippets[key] = (document, highlighter)
        doc.destroyed.connect(lambda *_: self._snippets.pop(key, None))


def _entry_title(entry: Any) -> str:
    return f"{entry.name} {entry.version}" if entry.version else entry.name


def _plain_list(value: Any) -> list:
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    return list(value or [])
