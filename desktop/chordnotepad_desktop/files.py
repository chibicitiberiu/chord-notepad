"""The File menu's documents: the recent list and the file pickers (plan step F3).

:class:`FilesModel` is the Qt side of the Tk window's
``_apply_recent_documents`` and ``_present_pick_document``
(removed in 0.6.0) plus Tk's ``file_dialogs`` rule for an added
extension:

* **Recent files** come from ``RecentDocumentsState`` (newest first, only
  those still there: the core prunes the list when it reads it). Same-named
  files are told apart by their folder (``formatting.recent_file_labels``,
  "song.txt — Band"); an empty list shows ``formatting.NO_RECENT_FILES``,
  disabled. Choosing one sends ``open_recent(ref)``.
* **The pickers** answer the session's ``PickDocumentRequest``: QML shows a
  Qt ``FileDialog`` with :attr:`FilesModel.pickRequested`'s title, filters
  and suggested name (Tk's, from ``formatting``), and hands the chosen URL to
  :meth:`FilesModel.accept` (or :meth:`FilesModel.cancel`). The answer is the
  core's ``DocumentRef`` for the path (``document_ref``, a direct call).
  The suggested name carries its extension: the Flatpak's portal only grants
  access to the exact name chosen, so ".txt" can't be added afterwards.
* **A typed name without an extension** gets the picker's (".txt",
  ".mid", ".wav"), as in Tk. The picker only asked about the name as typed, so if the
  name with the extension exists already, :attr:`FilesModel.confirmReplace`
  asks first ("Confirm Save As"); :meth:`FilesModel.replaceAnswered` gives
  the answer. A document-portal path is left as it is (the sandbox may write
  only that name).
* **One picker at a time:** a request that comes while one is open is
  answered "cancel" at once (Tk's portal dialog did the same).
* **A file dropped on the window** (Main.qml's DropArea) or named on the
  command line opens as File › Open's choice would: :meth:`FilesModel.openPath`
  sends ``open_document`` with its ref, so the session asks about unsaved
  changes, reports a file it can't read and adds the file to the recent
  list. Of several dropped files the first opens; :meth:`FilesModel.openDropped`
  returns the status bar's note about the others. Only local files count
  (:func:`dropped_paths`): a dropped web link stays text for the editor.

No initial folder is set, as in Tk: the dialog starts where the platform's
dialog starts.
"""

import logging
import os
from typing import Any, List, Optional

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from chordnotepad.session import formatting
from chordnotepad.session.bridge import to_json_value
from chordnotepad.session.documents import DocumentRef
from chordnotepad.session.events import PickMode
from chordnotepad.utils.paths import apply_default_extension, is_document_portal_path

logger = logging.getLogger(__name__)

#: The request this model answers.
PICK_REQUEST = "PickDocumentRequest"

#: (title, extension a bare name gets, filters) by PickMode value, Tk's.
PICKERS = {
    PickMode.OPEN.value: (formatting.OPEN_PICKER_TITLE, "", formatting.TEXT_FILE_TYPES),
    PickMode.SAVE.value: (formatting.SAVE_PICKER_TITLE, formatting.DEFAULT_EXTENSION,
                          formatting.TEXT_FILE_TYPES),
    PickMode.EXPORT_MIDI.value: (formatting.EXPORT_PICKER_TITLE, formatting.MIDI_EXTENSION,
                                 formatting.MIDI_FILE_TYPES),
    PickMode.EXPORT_AUDIO.value: (formatting.AUDIO_EXPORT_PICKER_TITLE, formatting.WAV_EXTENSION,
                                  formatting.WAV_FILE_TYPES),
}


def name_filters(file_types) -> List[str]:
    """Tk-style ``(label, pattern)`` pairs as Qt's name filters.

    ``"*.*"`` becomes ``"*"``: Tk on X11 reads it as "everything", Qt as
    "names with a dot" only.
    """
    filters = []
    for label, pattern in file_types:
        globs = ["*" if p in ("*", "*.*") else p for p in pattern.split()]
        filters.append(f"{label} ({' '.join(globs)})")
    return filters


def url_to_path(url: str) -> str:
    """A FileDialog's ``file://`` URL (or a plain path) as a local path; "" for none."""
    if not url:
        return ""
    qurl = QUrl(url)
    if qurl.isLocalFile():
        return qurl.toLocalFile()
    if not qurl.scheme():
        return url
    logger.warning("Ignoring a file that isn't local: %s", url)
    return ""


def dropped_paths(urls: Any) -> List[str]:
    """The local files (not folders) among dropped URLs, in order."""
    paths = []
    for url in urls or []:
        qurl = url if isinstance(url, QUrl) else QUrl(str(url))
        if qurl.isLocalFile():
            path = qurl.toLocalFile()
            if path and not os.path.isdir(path):
                paths.append(path)
    return paths


def only_one_note(dropped: int) -> str:
    """The status bar's note when ``dropped`` (2 or more) files were dropped."""
    others = dropped - 1
    left = "the other file was" if others == 1 else f"the other {others} files were"
    return f"Only one file opens at a time; {left} left out."


class FilesModel(QObject):
    """The recent list and the file pickers for the menus and FileDialogs.qml.

    Args:
        store: The window's SessionStore.
    """

    #: The recent list changed.
    recentChanged = Signal()
    #: Show a picker: ``{requestId, mode, title, nameFilters, suggestedName, save}``.
    pickRequested = Signal("QVariant")
    #: Ask before replacing (request id, title, message).
    confirmReplace = Signal(int, str, str)
    #: Whether a picker (or its replace question) is up.
    pickerOpenChanged = Signal()

    def __init__(self, store: Any, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._store = store
        self._refs: List[DocumentRef] = []
        self._pending: Optional[int] = None
        self._replace_path: Optional[str] = None
        self._mode = PickMode.OPEN.value
        store.stateChanged.connect(self._on_state)
        store.request.connect(self._on_request)
        self._take_recent()

    # -- the recent list --------------------------------------------------------------

    def _get_labels(self) -> list:
        return list(formatting.recent_file_labels(self._refs))

    #: One label per recent file, newest first ("song.txt — Band" when two share a name).
    recentLabels = Property("QVariantList", _get_labels, notify=recentChanged)

    def _get_locations(self) -> list:
        return [ref.location for ref in self._refs]

    #: Where each recent file is (for a tooltip).
    recentLocations = Property("QVariantList", _get_locations, notify=recentChanged)

    def _get_none(self) -> str:
        return formatting.NO_RECENT_FILES

    #: The disabled entry of an empty list.
    noRecentText = Property(str, _get_none, constant=True)

    @Slot(int)
    def openRecent(self, index: int) -> None:  # noqa: N802 (Qt)
        """Open the recent file at ``index`` (the session asks about unsaved changes)."""
        if 0 <= index < len(self._refs):
            self._store.submit("open_recent", {"ref": to_json_value(self._refs[index])})

    def _on_state(self, type_name: str) -> None:
        if type_name == "RecentDocumentsState":
            self._take_recent()

    def _take_recent(self) -> None:
        items = self._store.state("RecentDocumentsState").value("items") or []
        refs = [DocumentRef(str(i["id"]), str(i["display_name"]), str(i["location"]))
                for i in items]
        if refs != self._refs:
            self._refs = refs
            self.recentChanged.emit()

    # -- a file dropped on the window, or named on the command line ----------------------

    @Slot("QVariantList", result=bool)
    def hasFiles(self, urls: Any) -> bool:  # noqa: N802 (Qt)
        """Whether dropped ``urls`` hold a local file to open."""
        return bool(dropped_paths(urls))

    @Slot("QVariantList", result=str)
    def openDropped(self, urls: Any) -> str:  # noqa: N802 (Qt)
        """Open the first local file of dropped ``urls``; the status bar's
        note if there were others ("" if not, or if there was no file)."""
        paths = dropped_paths(urls)
        if not paths:
            return ""
        self.openPath(paths[0])
        return only_one_note(len(paths)) if len(paths) > 1 else ""

    @Slot(str)
    def openPath(self, path: str) -> None:  # noqa: N802 (Qt)
        """Open the file at ``path`` as Open does with a picked one."""
        ref = self._store.direct("document_ref", os.path.abspath(path))
        self._store.submit("open_document", {"ref": to_json_value(ref), "read_only": False})

    # -- the pickers --------------------------------------------------------------------

    @Slot("QVariant", str, result=QUrl)
    def fileUrl(self, folder: Any, name: str) -> QUrl:  # noqa: N802 (Qt)
        """The URL of ``name`` in ``folder`` (the dialog's current folder,
        else the working directory): a picker pre-filled with a name needs a
        whole path, and the portal takes its file name as ``current_name``."""
        base = url_to_path(folder.toString() if isinstance(folder, QUrl) else str(folder or ""))
        return QUrl.fromLocalFile(os.path.join(base or os.getcwd(), name))

    @Slot(QObject, str)
    def prefillQuickDialog(self, window: QObject, name: str) -> None:  # noqa: N802 (Qt)
        """Show ``name`` in Qt Quick's own file dialog (the one used without a
        platform dialog, e.g. Linux outside a sandbox with no portal).

        It takes ``selectedFile`` but leaves its name field empty (Qt 6.12),
        so Save would look as if it had no name. The native dialogs and the
        portal take the name from ``selectedFile`` and have no such item.
        """
        if window is None or not name:
            return
        for impl in window.findChildren(QObject):
            if not impl.inherits("QQuickFileDialogImpl"):
                continue
            impl.setProperty("fileName", name)
            field = impl.findChild(QObject, "fileNameTextField")
            if field is not None:
                field.setProperty("text", name)

    @Slot("QVariantMap")
    def useColours(self, colours: dict) -> None:  # noqa: N802 (Qt)
        """Give Qt Quick's own file dialog the window's colours.

        It paints with the application palette (its header, list, breadcrumb
        bar and side bar), which our style otherwise never uses, so it came
        out in whatever the platform theme guessed, half dark and half
        light. ``colours`` maps QPalette role names (``window``, ``text``,
        ...) to colours; FileDialogs.qml sends Theme's, again when the
        theme turns dark or light. The platform's own dialogs don't use it.
        """
        palette = QGuiApplication.palette()
        for name, colour in colours.items():
            role = getattr(QPalette.ColorRole, name[:1].upper() + name[1:], None)
            if role is None:
                logger.warning("No palette role %r", name)
                continue
            palette.setColor(role, QColor(colour))
        QGuiApplication.setPalette(palette)

    def _get_picker_open(self) -> bool:
        return self._pending is not None

    pickerOpen = Property(bool, _get_picker_open, notify=pickerOpenChanged)

    def _on_request(self, type_name: str, data: Any) -> None:
        if type_name != PICK_REQUEST:
            return
        request_id = int(data["request_id"])
        if self._pending is not None:
            logger.debug("A file picker is open already; request %s cancelled", request_id)
            self._respond(request_id, None)
            return
        mode = str(data["mode"])
        title, extension, file_types = PICKERS[mode]
        self._set_pending(request_id)
        self._mode = mode
        self.pickRequested.emit({
            "requestId": request_id,
            "mode": mode,
            "title": title,
            "nameFilters": name_filters(file_types),
            "suggestedName": str(data.get("suggested_name") or ""),
            "save": mode != PickMode.OPEN.value,
        })

    @Slot(int, str)
    def accept(self, request_id: int, url: str) -> None:
        """The picker chose ``url``: answer with its document (after asking,
        if an added extension names a file that exists)."""
        if request_id != self._pending:
            return
        path = url_to_path(url)
        if not path:
            self.cancel(request_id)
            return
        _title, extension, _types = PICKERS[self._mode]
        if extension and not is_document_portal_path(path):
            with_ext = apply_default_extension(path, extension)
            if with_ext != path and os.path.exists(with_ext):
                self._replace_path = with_ext
                self.confirmReplace.emit(request_id, formatting.CONFIRM_REPLACE_TITLE,
                                         formatting.confirm_replace_message(
                                             os.path.basename(with_ext)))
                return
            path = with_ext
        self._finish(request_id, path)

    @Slot(int, bool)
    def replaceAnswered(self, request_id: int, replace: bool) -> None:  # noqa: N802 (Qt)
        """The answer to :attr:`confirmReplace`: replace the file, or cancel."""
        if request_id != self._pending or self._replace_path is None:
            return
        path, self._replace_path = self._replace_path, None
        if replace:
            self._finish(request_id, path)
        else:
            self.cancel(request_id)

    @Slot(int)
    def cancel(self, request_id: int) -> None:
        """The picker was closed without a choice."""
        if request_id != self._pending:
            return
        self._replace_path = None
        self._set_pending(None)
        self._respond(request_id, None)

    def _finish(self, request_id: int, path: str) -> None:
        ref = self._store.direct("document_ref", path)
        self._set_pending(None)
        self._respond(request_id, to_json_value(ref))

    def _respond(self, request_id: int, value: Any) -> None:
        self._store.submit("respond", {"request_id": request_id, "value": value})

    def _set_pending(self, request_id: Optional[int]) -> None:
        if request_id != self._pending:
            self._pending = request_id
            self.pickerOpenChanged.emit()
