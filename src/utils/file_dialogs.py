"""Native file dialogs: XDG Desktop Portal on Linux, Tk everywhere else.

Inside a Flatpak with no ``--filesystem`` permission the app can only reach
files the user picks through ``org.freedesktop.portal.FileChooser``. Tk's own
dialogs browse the sandbox's private filesystem, so on Linux we ask the portal
over D-Bus (via ``jeepney``, imported lazily) and fall back to
``tkinter.filedialog`` whenever the portal can't be used.

The public functions mirror ``tkinter.filedialog.askopenfilename`` /
``asksaveasfilename`` and return ``''`` when the user cancels.

Backend selection:

* ``CHORD_NOTEPAD_FILE_DIALOG=tk`` forces the Tk dialog.
* ``CHORD_NOTEPAD_FILE_DIALOG=portal`` skips the platform check and goes
  straight to the portal (still falls back to Tk if the portal fails).
* Otherwise the portal is tried on Linux only; it is skipped for the rest of
  the session once it has been found missing.

Any failure before the portal dialog appears (no session bus, no portal, no
FileChooser interface, D-Bus error on the call) falls back to Tk. A portal
response of 1 means "cancelled" and returns ``''``; a response of 2 ("ended
some other way") also falls back to Tk.
"""

import logging
import os
import secrets
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, TypeVar, Union
from urllib.parse import unquote, urlparse

# Moved to utils.paths (Tk-free); re-exported for existing importers.
from utils.paths import display_path, is_document_portal_path  # noqa: F401

logger = logging.getLogger(__name__)

ENV_OVERRIDE = "CHORD_NOTEPAD_FILE_DIALOG"
BACKEND_TK = "tk"
BACKEND_PORTAL = "portal"

_PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
_FILE_CHOOSER_IFACE = "org.freedesktop.portal.FileChooser"
_REQUEST_IFACE = "org.freedesktop.portal.Request"
_REQUEST_PATH_PREFIX = "/org/freedesktop/portal/desktop/request"

# Seconds to wait for D-Bus method replies (not for the user). The first call
# may D-Bus-activate xdg-desktop-portal, which can take a moment.
_DBUS_CALL_TIMEOUT = 10.0
# How often the Tk main thread checks whether the worker has finished.
_POLL_INTERVAL_MS = 50

# Portal Response codes
_RESPONSE_SUCCESS = 0
_RESPONSE_CANCELLED = 1

# Glob filter entry type in the portal's a(sa(us)) filter format (1 = MIME type)
_FILTER_GLOB = 0

PortalFilter = Tuple[str, List[Tuple[int, str]]]
FileTypes = Iterable[Sequence[Any]]
_T = TypeVar("_T")


class PortalUnavailableError(Exception):
    """The portal could not show a dialog; the caller should use Tk instead."""


# Set once the portal has been found missing, so later dialogs go straight to Tk.
_portal_known_missing = False
# True while a portal dialog is up. The main thread keeps pumping Tk events then,
# so a second request (e.g. Ctrl+O again via the menu) is possible; it is
# answered with '' instead of opening a second dialog.
_portal_dialog_open = False


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def ask_open_filename(
    parent: Optional[tk.Misc] = None,
    title: str = "",
    filetypes: FileTypes = (),
    initialdir: Optional[str] = None,
) -> str:
    """Ask the user to pick an existing file to open.

    Args:
        parent: Widget the dialog belongs to (its toplevel becomes the
            dialog's parent window). Defaults to Tk's default root.
        title: Dialog title.
        filetypes: Tk-style filetypes, e.g. ``[("Text", "*.txt"), ("All", "*.*")]``.
        initialdir: Folder to start in.

    Returns:
        Absolute path of the chosen file, or ``''`` if the user cancelled.
    """
    if _portal_dialog_open:
        logger.debug("Portal file dialog already open; ignoring nested request")
        return ""
    if _choose_backend() == BACKEND_PORTAL:
        options: Dict[str, Tuple[str, Any]] = {
            "modal": ("b", True),
            "multiple": ("b", False),
        }
        options.update(_filter_options(filetypes))
        if initialdir:
            options["current_folder"] = ("ay", _path_to_portal_bytes(initialdir))
        try:
            uris = _show_portal_dialog(parent, "OpenFile", title, options)
        except PortalUnavailableError as exc:
            logger.warning("File portal unavailable, using Tk dialog: %s", exc)
        else:
            return _first_path(uris)

    kwargs = _tk_kwargs(parent, title=title, filetypes=filetypes, initialdir=initialdir)
    return _normalise_tk_result(filedialog.askopenfilename(**kwargs))


def ask_save_as_filename(
    parent: Optional[tk.Misc] = None,
    title: str = "",
    filetypes: FileTypes = (),
    defaultextension: str = "",
    initialfile: Optional[str] = None,
    initialdir: Optional[str] = None,
) -> str:
    """Ask the user where to save a file.

    Args:
        parent: Widget the dialog belongs to. Defaults to Tk's default root.
        title: Dialog title.
        filetypes: Tk-style filetypes, e.g. ``[("Text", "*.txt"), ("All", "*.*")]``.
        defaultextension: Appended when the chosen name has no extension
            (``".txt"`` or ``"txt"``), like Tk does.
        initialfile: Name pre-filled in the dialog.
        initialdir: Folder to start in.

    Returns:
        Absolute path to save to, or ``''`` if the user cancelled.
    """
    if _portal_dialog_open:
        logger.debug("Portal file dialog already open; ignoring nested request")
        return ""
    if _choose_backend() == BACKEND_PORTAL:
        options: Dict[str, Tuple[str, Any]] = {"modal": ("b", True)}
        options.update(_filter_options(filetypes))
        if initialfile:
            options["current_name"] = ("s", initialfile)
        if initialdir:
            options["current_folder"] = ("ay", _path_to_portal_bytes(initialdir))
        try:
            uris = _show_portal_dialog(parent, "SaveFile", title, options)
        except PortalUnavailableError as exc:
            logger.warning("File portal unavailable, using Tk dialog: %s", exc)
        else:
            path = _first_path(uris)
            if path:
                path = _finish_portal_save_path(parent, path, defaultextension)
            return path

    kwargs = _tk_kwargs(
        parent,
        title=title,
        filetypes=filetypes,
        defaultextension=defaultextension,
        initialfile=initialfile,
        initialdir=initialdir,
    )
    return _normalise_tk_result(filedialog.asksaveasfilename(**kwargs))


def tk_filetypes_to_portal_filters(filetypes: FileTypes) -> List[PortalFilter]:
    """Convert Tk filetypes into the portal's ``a(sa(us))`` filter list.

    Each Tk entry is ``(label, patterns)`` where patterns is a space-separated
    string or a sequence of strings. ``"*.*"`` and ``"*"`` become ``"*"`` (Tk
    on X11 treats ``*.*`` as "everything", including names without a dot), and
    a bare extension such as ``".txt"`` becomes ``"*.txt"``.

    Args:
        filetypes: Tk-style filetypes.

    Returns:
        List of ``(label, [(0, glob), ...])`` tuples; entries with no usable
        pattern are dropped.
    """
    filters: List[PortalFilter] = []
    for entry in filetypes or ():
        if len(entry) < 2:
            continue
        label, patterns = str(entry[0]), entry[1]
        if isinstance(patterns, str):
            pattern_list = patterns.split()
        else:
            pattern_list = [str(p) for p in patterns]

        globs: List[Tuple[int, str]] = []
        for pattern in pattern_list:
            glob = _tk_pattern_to_glob(pattern)
            if glob and (_FILTER_GLOB, glob) not in globs:
                globs.append((_FILTER_GLOB, glob))
        if globs:
            filters.append((label, globs))
    return filters


def file_uri_to_path(uri: str) -> str:
    """Convert a ``file://`` URI from the portal into a local path.

    Args:
        uri: URI such as ``file:///home/me/My%20Song.txt``.

    Returns:
        The percent-decoded local path.

    Raises:
        ValueError: If the URI is not a local ``file:`` URI.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Not a file URI: {uri!r}")
    if parsed.netloc not in ("", "localhost"):
        raise ValueError(f"Not a local file URI: {uri!r}")
    # surrogateescape round-trips non-UTF-8 bytes the same way os.fsdecode does
    return unquote(parsed.path, errors="surrogateescape")


def apply_default_extension(path: str, defaultextension: str) -> str:
    """Append ``defaultextension`` when ``path`` has no extension, like Tk.

    Args:
        path: Chosen file path.
        defaultextension: Extension with or without the leading dot; empty
            means "leave the path alone".

    Returns:
        The path, with the extension appended if it had none.
    """
    if not path or not defaultextension:
        return path
    if os.path.splitext(path)[1]:
        return path
    ext = defaultextension if defaultextension.startswith(".") else "." + defaultextension
    return path + ext


# ----------------------------------------------------------------------
# Backend selection
# ----------------------------------------------------------------------

def _choose_backend() -> str:
    """Decide which dialog implementation to use for the next call."""
    override = os.environ.get(ENV_OVERRIDE, "").strip().lower()
    if override == BACKEND_TK:
        return BACKEND_TK
    if override == BACKEND_PORTAL:
        return BACKEND_PORTAL
    if override:
        logger.warning("Ignoring unknown %s=%r (expected 'tk' or 'portal')", ENV_OVERRIDE, override)

    if not sys.platform.startswith("linux"):
        return BACKEND_TK
    if _portal_known_missing:
        return BACKEND_TK
    return BACKEND_PORTAL


def _mark_portal_missing(reason: str) -> None:
    """Remember that the portal isn't there, so later dialogs skip it."""
    global _portal_known_missing
    _portal_known_missing = True
    logger.debug("File chooser portal not available: %s", reason)


# ----------------------------------------------------------------------
# Portal plumbing
# ----------------------------------------------------------------------

def _show_portal_dialog(
    parent: Optional[tk.Misc],
    method: str,
    title: str,
    options: Dict[str, Tuple[str, Any]],
) -> Optional[List[str]]:
    """Show a portal dialog without blocking Tk's event loop.

    Returns:
        The chosen URIs, or None if the user cancelled.

    Raises:
        PortalUnavailableError: If the dialog couldn't be shown.
    """
    global _portal_dialog_open
    parent_window = _parent_window_handle(parent)
    _portal_dialog_open = True
    try:
        return _run_in_worker(
            parent, lambda: _portal_request(method, parent_window, title, options)
        )
    finally:
        _portal_dialog_open = False


def _portal_request(
    method: str,
    parent_window: str,
    title: str,
    options: Dict[str, Tuple[str, Any]],
) -> Optional[List[str]]:
    """Call ``FileChooser.<method>`` and block until the portal responds.

    Runs on a worker thread. It subscribes to the ``Request.Response`` signal
    on the predicted request path before making the call, so a fast response
    can't be missed.

    Returns:
        The chosen URIs, or None if the user cancelled (or the connection
        broke after the dialog was shown).

    Raises:
        PortalUnavailableError: If anything failed before the dialog appeared,
            or the portal answered with response code 2.
    """
    try:
        from jeepney import DBusAddress, HeaderFields, MatchRule, Properties, message_bus, new_method_call
        from jeepney.io.blocking import open_dbus_connection
        from jeepney.wrappers import DBusErrorResponse, unwrap_msg
    except ImportError as exc:
        _mark_portal_missing(f"jeepney not importable ({exc})")
        raise PortalUnavailableError(f"jeepney not importable: {exc}") from exc

    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception as exc:  # KeyError (no address), OSError, auth errors...
        _mark_portal_missing(f"no session bus ({exc!r})")
        raise PortalUnavailableError(f"cannot connect to the session bus: {exc!r}") from exc

    with conn:
        portal = DBusAddress(_PORTAL_OBJECT_PATH, bus_name=_PORTAL_BUS_NAME, interface=_FILE_CHOOSER_IFACE)

        # 1. Is FileChooser there at all? Reading its version property fails with
        #    ServiceUnknown / UnknownInterface / UnknownProperty if not.
        try:
            version = unwrap_msg(
                conn.send_and_get_reply(Properties(portal).get("version"), timeout=_DBUS_CALL_TIMEOUT)
            )[0][1]
        except DBusErrorResponse as exc:
            _mark_portal_missing(str(exc))
            raise PortalUnavailableError(f"FileChooser portal not found: {exc}") from exc
        except Exception as exc:
            raise PortalUnavailableError(f"probing the FileChooser portal failed: {exc!r}") from exc
        logger.debug("Using FileChooser portal version %s for %s", version, method)

        # 2. Subscribe to the Response signal on the request path we expect.
        token = "chord_notepad_" + secrets.token_hex(8)
        request_path = _predict_request_path(conn.unique_name, token)
        response_rule = MatchRule(
            type="signal", interface=_REQUEST_IFACE, member="Response", path=request_path
        )
        # Local filter catches Response on any path; we pick ours out below,
        # which also covers old portals that return a different handle.
        local_rule = MatchRule(type="signal", interface=_REQUEST_IFACE, member="Response")

        with conn.filter(local_rule, bufsize=16) as responses:
            try:
                unwrap_msg(conn.send_and_get_reply(message_bus.AddMatch(response_rule), timeout=_DBUS_CALL_TIMEOUT))

                # 3. Make the call. The reply is just the request handle.
                call_options = dict(options)
                call_options["handle_token"] = ("s", token)
                call = new_method_call(portal, method, "ssa{sv}", (parent_window, title, call_options))
                handle = unwrap_msg(conn.send_and_get_reply(call, timeout=_DBUS_CALL_TIMEOUT))[0]

                if handle != request_path:
                    logger.debug("Portal returned request %s, expected %s", handle, request_path)
                    unwrap_msg(conn.send_and_get_reply(
                        message_bus.AddMatch(MatchRule(
                            type="signal", interface=_REQUEST_IFACE, member="Response", path=handle
                        )),
                        timeout=_DBUS_CALL_TIMEOUT,
                    ))
            except Exception as exc:
                raise PortalUnavailableError(f"FileChooser.{method} call failed: {exc!r}") from exc

            # 4. The dialog is up. Wait (as long as the user likes) for the answer.
            try:
                while True:
                    signal = conn.recv_until_filtered(responses)
                    if signal.header.fields.get(HeaderFields.path) == handle:
                        break
            except Exception:
                logger.exception("Lost the D-Bus connection while the file dialog was open")
                return None

    code, results = signal.body
    return _interpret_response(code, results)


def _interpret_response(code: int, results: Dict[str, Tuple[str, Any]]) -> Optional[List[str]]:
    """Turn a portal ``Response`` signal body into URIs / None / fallback.

    Raises:
        PortalUnavailableError: For response code 2 (or anything unexpected).
    """
    if code == _RESPONSE_SUCCESS:
        uris_variant = results.get("uris")
        return list(uris_variant[1]) if uris_variant else []
    if code == _RESPONSE_CANCELLED:
        return None
    raise PortalUnavailableError(f"portal ended the dialog with response code {code}")


def _predict_request_path(unique_name: str, token: str) -> str:
    """Build the Request object path the portal will use for ``token``.

    ``:1.42`` becomes ``1_42``, per the portal's request-path convention.
    """
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{_REQUEST_PATH_PREFIX}/{sender}/{token}"


def _parent_window_handle(parent: Optional[tk.Misc]) -> str:
    """Return ``x11:<hex XID>`` of the parent's WM frame, or ``''`` if unknown."""
    widget = parent if parent is not None else getattr(tk, "_default_root", None)
    if widget is None:
        return ""
    try:
        if widget.tk.call("tk", "windowingsystem") != "x11":
            return ""
        frame = widget.winfo_toplevel().wm_frame()
        return f"x11:{int(str(frame), 16):x}"
    except (tk.TclError, ValueError, TypeError) as exc:
        logger.debug("Could not determine parent window for portal dialog: %s", exc)
        return ""


def _run_in_worker(parent: Optional[tk.Misc], work: Callable[[], _T]) -> _T:
    """Run ``work`` on a thread while the Tk event loop keeps running.

    Looks synchronous to the caller: it returns ``work()``'s result (or
    re-raises its exception) once the worker is done. Meanwhile the main
    thread sits in ``wait_variable`` so Tk keeps redrawing.
    """
    outcome: Dict[str, Any] = {}
    done = threading.Event()

    def runner() -> None:
        try:
            outcome["result"] = work()
        except BaseException as exc:  # re-raised on the calling thread
            outcome["error"] = exc
        finally:
            done.set()

    worker = threading.Thread(target=runner, name="portal-file-dialog", daemon=True)
    worker.start()

    root = parent if parent is not None else getattr(tk, "_default_root", None)
    if root is None:
        done.wait()
    else:
        finished = tk.BooleanVar(master=root, value=False)

        def poll() -> None:
            if done.is_set():
                finished.set(True)
            else:
                root.after(_POLL_INTERVAL_MS, poll)

        root.after(_POLL_INTERVAL_MS, poll)
        root.wait_variable(finished)

    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


def _filter_options(filetypes: FileTypes) -> Dict[str, Tuple[str, Any]]:
    """Portal ``filters`` / ``current_filter`` options for Tk filetypes."""
    filters = tk_filetypes_to_portal_filters(filetypes)
    if not filters:
        return {}
    return {
        "filters": ("a(sa(us))", filters),
        "current_filter": ("(sa(us))", filters[0]),
    }


def _path_to_portal_bytes(path: str) -> bytes:
    """Encode a folder path as the portal's null-terminated byte string."""
    return os.fsencode(os.path.abspath(os.path.expanduser(path))) + b"\0"


def _first_path(uris: Optional[List[str]]) -> str:
    """Local path of the first URI, or ``''`` on cancel / unusable URI."""
    if not uris:
        return ""
    try:
        return file_uri_to_path(uris[0])
    except ValueError as exc:
        logger.warning("Ignoring file chosen through the portal: %s", exc)
        return ""


def _finish_portal_save_path(parent: Optional[tk.Misc], path: str, defaultextension: str) -> str:
    """Apply Tk's ``defaultextension`` rule to a path the portal returned.

    The portal confirmed overwriting ``path`` itself, not the name with the
    extension added, so ask again if that one already exists. Document-portal
    paths are left alone: the sandbox is only granted the exact name the user
    picked, so writing a different name there would fail.
    """
    if is_document_portal_path(path):
        return path
    with_ext = apply_default_extension(path, defaultextension)
    if with_ext != path and os.path.exists(with_ext):
        kwargs: Dict[str, Any] = {"icon": messagebox.WARNING}
        if parent is not None:
            kwargs["parent"] = parent
        replace = messagebox.askyesno(
            "Confirm Save As",
            f"{os.path.basename(with_ext)} already exists.\nDo you want to replace it?",
            **kwargs,
        )
        if not replace:
            return ""
    return with_ext


def _tk_pattern_to_glob(pattern: str) -> str:
    """Map one Tk filetype pattern onto a portal glob."""
    pattern = pattern.strip()
    if not pattern:
        return ""
    if pattern in ("*", "*.*"):
        return "*"
    if pattern.startswith("."):
        return "*" + pattern
    return pattern


def _tk_kwargs(parent: Optional[tk.Misc], **options: Any) -> Dict[str, Any]:
    """Keyword arguments for ``tkinter.filedialog``, skipping unset options."""
    kwargs = {key: value for key, value in options.items() if value not in (None, "", (), [])}
    if parent is not None:
        kwargs["parent"] = parent
    return kwargs


def _normalise_tk_result(result: Any) -> str:
    """Tk may return ``()`` instead of ``''`` on cancel; always return a str."""
    return result if isinstance(result, str) else ""
