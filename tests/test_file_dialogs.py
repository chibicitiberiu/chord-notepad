"""Tests for utils.file_dialogs (portal file chooser with Tk fallback).

No real D-Bus or dialogs: the portal round-trip is exercised against a fake
jeepney connection, and the public functions are tested with the portal call
and the Tk dialogs mocked out. One test pumps a hidden Tk root, skipped when
there is no display (same pattern as test_tooltip.py).
"""

import os
import threading
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from utils import file_dialogs as fd


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Reset module-level state and the env override for every test."""
    monkeypatch.delenv(fd.ENV_OVERRIDE, raising=False)
    monkeypatch.setattr(fd, "_portal_known_missing", False)
    monkeypatch.setattr(fd, "_portal_dialog_open", False)


@pytest.fixture
def on_linux(monkeypatch):
    monkeypatch.setattr(fd.sys, "platform", "linux")


@pytest.fixture
def portal(monkeypatch, on_linux):
    """Run the portal path synchronously with a mocked _portal_request."""
    monkeypatch.setattr(fd, "_run_in_worker", lambda parent, work: work())
    monkeypatch.setattr(fd, "_parent_window_handle", lambda parent: "x11:1c00009")
    request = mock.Mock(name="_portal_request")
    monkeypatch.setattr(fd, "_portal_request", request)
    return request


@pytest.fixture
def tk_dialogs(monkeypatch):
    """Replace tkinter.filedialog's functions as used by the module."""
    open_dialog = mock.Mock(name="askopenfilename", return_value="/tk/picked.txt")
    save_dialog = mock.Mock(name="asksaveasfilename", return_value="/tk/saved.txt")
    monkeypatch.setattr(fd.filedialog, "askopenfilename", open_dialog)
    monkeypatch.setattr(fd.filedialog, "asksaveasfilename", save_dialog)
    return mock.Mock(open=open_dialog, save=save_dialog)


# ----------------------------------------------------------------------
# Filter conversion
# ----------------------------------------------------------------------

class TestFilterConversion:
    def test_space_separated_patterns(self):
        filters = fd.tk_filetypes_to_portal_filters(
            [("Chord files", "*.txt *.cho"), ("All files", "*.*")]
        )
        assert filters == [
            ("Chord files", [(0, "*.txt"), (0, "*.cho")]),
            ("All files", [(0, "*")]),
        ]

    def test_sequence_patterns_and_bare_extensions(self):
        filters = fd.tk_filetypes_to_portal_filters([("Songs", (".txt", "*.cho")), ("Any", "*")])
        assert filters == [("Songs", [(0, "*.txt"), (0, "*.cho")]), ("Any", [(0, "*")])]

    def test_empty_and_duplicate_patterns_dropped(self):
        filters = fd.tk_filetypes_to_portal_filters(
            [("Nothing", ""), ("Text", "*.txt *.txt"), ("Bad",)]
        )
        assert filters == [("Text", [(0, "*.txt")])]

    def test_no_filetypes(self):
        assert fd.tk_filetypes_to_portal_filters(()) == []
        assert fd.tk_filetypes_to_portal_filters(None) == []
        assert fd._filter_options(()) == {}

    def test_current_filter_is_first(self):
        options = fd._filter_options([("MIDI files", "*.mid"), ("All files", "*.*")])
        assert options["filters"][0] == "a(sa(us))"
        assert options["current_filter"] == ("(sa(us))", ("MIDI files", [(0, "*.mid")]))


# ----------------------------------------------------------------------
# URIs and paths
# ----------------------------------------------------------------------

class TestUriDecoding:
    def test_percent_decoding(self):
        assert fd.file_uri_to_path("file:///home/me/My%20Song%20%231.txt") == "/home/me/My Song #1.txt"

    def test_utf8(self):
        assert fd.file_uri_to_path("file:///home/me/Caf%C3%A9.cho") == "/home/me/Café.cho"

    def test_localhost_authority(self):
        assert fd.file_uri_to_path("file://localhost/tmp/a.txt") == "/tmp/a.txt"

    def test_non_utf8_bytes_round_trip(self):
        path = fd.file_uri_to_path("file:///tmp/bad%FFname.txt")
        assert os.fsencode(path) == b"/tmp/bad\xffname.txt"

    def test_doc_portal_uri(self):
        assert fd.file_uri_to_path("file:///run/user/1000/doc/3f2a91bc/song.txt") == (
            "/run/user/1000/doc/3f2a91bc/song.txt"
        )

    @pytest.mark.parametrize("uri", ["https://example.com/a.txt", "file://otherhost/a.txt", "/plain/path"])
    def test_rejects_non_local(self, uri):
        with pytest.raises(ValueError):
            fd.file_uri_to_path(uri)

    def test_first_path_ignores_bad_uri(self):
        assert fd._first_path(["sftp://host/x"]) == ""
        assert fd._first_path([]) == ""
        assert fd._first_path(None) == ""


class TestDefaultExtension:
    @pytest.mark.parametrize(
        "path, ext, expected",
        [
            ("/home/me/song", ".txt", "/home/me/song.txt"),
            ("/home/me/song", "txt", "/home/me/song.txt"),
            ("/home/me/song.cho", ".txt", "/home/me/song.cho"),
            ("/home/me/song.mid", ".mid", "/home/me/song.mid"),
            ("/home/my.dir/song", ".txt", "/home/my.dir/song.txt"),
            ("/home/me/song", "", "/home/me/song"),
            ("", ".txt", ""),
        ],
    )
    def test_apply_default_extension(self, path, ext, expected):
        assert fd.apply_default_extension(path, ext) == expected


class TestDisplayPath:
    @pytest.mark.parametrize(
        "path",
        [
            "/run/user/1000/doc/3f2a91bc/My Song.txt",
            "/run/flatpak/doc/3f2a91bc/My Song.txt",
            Path("/run/user/1000/doc/3f2a91bc/My Song.txt"),
        ],
    )
    def test_doc_portal_paths_show_basename(self, path):
        assert fd.is_document_portal_path(path)
        assert fd.display_path(path) == "My Song.txt"

    @pytest.mark.parametrize("path", ["/home/me/My Song.txt", "relative/song.txt", "/run/user/1000/other/x.txt"])
    def test_normal_paths_unchanged(self, path):
        assert not fd.is_document_portal_path(path)
        assert fd.display_path(path) == path
        assert fd.display_path(Path(path)) == str(Path(path))


# ----------------------------------------------------------------------
# Backend selection
# ----------------------------------------------------------------------

class TestChooseBackend:
    @pytest.mark.parametrize("platform", ["win32", "darwin"])
    def test_tk_off_linux(self, monkeypatch, platform):
        monkeypatch.setattr(fd.sys, "platform", platform)
        assert fd._choose_backend() == fd.BACKEND_TK

    def test_portal_on_linux(self, on_linux):
        assert fd._choose_backend() == fd.BACKEND_PORTAL

    def test_tk_once_portal_known_missing(self, on_linux, monkeypatch):
        monkeypatch.setattr(fd, "_portal_known_missing", True)
        assert fd._choose_backend() == fd.BACKEND_TK

    def test_env_forces_tk(self, on_linux, monkeypatch):
        monkeypatch.setenv(fd.ENV_OVERRIDE, "tk")
        assert fd._choose_backend() == fd.BACKEND_TK

    def test_env_forces_portal(self, monkeypatch):
        monkeypatch.setattr(fd.sys, "platform", "win32")
        monkeypatch.setattr(fd, "_portal_known_missing", True)
        monkeypatch.setenv(fd.ENV_OVERRIDE, " Portal ")
        assert fd._choose_backend() == fd.BACKEND_PORTAL

    def test_unknown_env_value_ignored(self, monkeypatch):
        monkeypatch.setattr(fd.sys, "platform", "darwin")
        monkeypatch.setenv(fd.ENV_OVERRIDE, "gtk")
        assert fd._choose_backend() == fd.BACKEND_TK


# ----------------------------------------------------------------------
# Public functions: portal vs Tk fallback
# ----------------------------------------------------------------------

class TestAskOpenFilename:
    def test_portal_success(self, portal, tk_dialogs):
        portal.return_value = ["file:///home/me/My%20Song.txt"]
        result = fd.ask_open_filename(
            None, title="Open File", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir="/home/me",
        )
        assert result == "/home/me/My Song.txt"
        tk_dialogs.open.assert_not_called()

        method, parent_window, title, options = portal.call_args.args
        assert (method, parent_window, title) == ("OpenFile", "x11:1c00009", "Open File")
        assert options["modal"] == ("b", True)
        assert options["multiple"] == ("b", False)
        assert options["current_filter"] == ("(sa(us))", ("Text Files", [(0, "*.txt")]))
        assert options["current_folder"] == ("ay", b"/home/me\0")

    def test_portal_cancel_returns_empty(self, portal, tk_dialogs):
        portal.return_value = None
        assert fd.ask_open_filename(None, title="Open File") == ""
        tk_dialogs.open.assert_not_called()

    def test_portal_unavailable_falls_back_to_tk(self, portal, tk_dialogs):
        portal.side_effect = fd.PortalUnavailableError("no portal")
        filetypes = [("Text Files", "*.txt")]
        assert fd.ask_open_filename(None, title="Open File", filetypes=filetypes) == "/tk/picked.txt"
        tk_dialogs.open.assert_called_once_with(title="Open File", filetypes=filetypes)

    def test_env_tk_skips_portal(self, portal, tk_dialogs, monkeypatch):
        monkeypatch.setenv(fd.ENV_OVERRIDE, "tk")
        parent = object()
        assert fd.ask_open_filename(parent, title="Pick", initialdir="/x") == "/tk/picked.txt"
        portal.assert_not_called()
        tk_dialogs.open.assert_called_once_with(parent=parent, title="Pick", initialdir="/x")

    def test_non_linux_uses_tk(self, portal, tk_dialogs, monkeypatch):
        monkeypatch.setattr(fd.sys, "platform", "win32")
        assert fd.ask_open_filename(None) == "/tk/picked.txt"
        portal.assert_not_called()

    def test_tk_empty_tuple_normalised(self, tk_dialogs, monkeypatch):
        monkeypatch.setenv(fd.ENV_OVERRIDE, "tk")
        tk_dialogs.open.return_value = ()
        assert fd.ask_open_filename(None) == ""

    def test_nested_request_while_portal_open(self, portal, tk_dialogs, monkeypatch):
        monkeypatch.setattr(fd, "_portal_dialog_open", True)
        assert fd.ask_open_filename(None) == ""
        portal.assert_not_called()
        tk_dialogs.open.assert_not_called()

    def test_busy_flag_cleared_after_dialog(self, portal, tk_dialogs):
        seen = []
        portal.side_effect = lambda *a: seen.append(fd._portal_dialog_open) or None
        fd.ask_open_filename(None)
        assert seen == [True]
        assert fd._portal_dialog_open is False


class TestAskSaveAsFilename:
    def test_portal_options(self, portal, tk_dialogs):
        portal.return_value = ["file:///home/me/out.mid"]
        result = fd.ask_save_as_filename(
            None, title="Export MIDI", defaultextension=".mid",
            filetypes=[("MIDI files", "*.mid"), ("All files", "*.*")],
            initialfile="Song.mid", initialdir="/home/me/Music",
        )
        assert result == "/home/me/out.mid"
        method, _, title, options = portal.call_args.args
        assert (method, title) == ("SaveFile", "Export MIDI")
        assert options["current_name"] == ("s", "Song.mid")
        assert options["current_folder"] == ("ay", b"/home/me/Music\0")
        assert options["current_filter"][1][0] == "MIDI files"
        assert "multiple" not in options
        tk_dialogs.save.assert_not_called()

    def test_no_initialdir_means_no_current_folder(self, portal, tk_dialogs):
        portal.return_value = None
        assert fd.ask_save_as_filename(None, title="Save") == ""
        options = portal.call_args.args[3]
        assert "current_folder" not in options
        assert "current_name" not in options

    def test_default_extension_appended(self, portal, tk_dialogs, tmp_path):
        portal.return_value = [(tmp_path / "song").as_uri()]
        assert fd.ask_save_as_filename(None, defaultextension=".txt") == str(tmp_path / "song.txt")

    def test_existing_suffix_kept(self, portal, tk_dialogs, tmp_path):
        portal.return_value = [(tmp_path / "song.cho").as_uri()]
        assert fd.ask_save_as_filename(None, defaultextension=".txt") == str(tmp_path / "song.cho")

    def test_doc_portal_path_left_alone(self, portal, tk_dialogs):
        portal.return_value = ["file:///run/user/1000/doc/ab12cd34/song"]
        assert fd.ask_save_as_filename(None, defaultextension=".txt") == "/run/user/1000/doc/ab12cd34/song"

    @pytest.mark.parametrize("answer, expected_name", [(True, "song.txt"), (False, None)])
    def test_confirms_overwrite_of_appended_name(self, portal, tk_dialogs, tmp_path, monkeypatch, answer, expected_name):
        (tmp_path / "song.txt").write_text("existing")
        portal.return_value = [(tmp_path / "song").as_uri()]
        ask = mock.Mock(return_value=answer)
        monkeypatch.setattr(fd.messagebox, "askyesno", ask)

        result = fd.ask_save_as_filename(None, defaultextension=".txt")

        ask.assert_called_once()
        assert result == (str(tmp_path / expected_name) if expected_name else "")

    def test_call_error_falls_back_to_tk(self, portal, tk_dialogs):
        portal.side_effect = fd.PortalUnavailableError("D-Bus error")
        result = fd.ask_save_as_filename(None, title="Save File As", defaultextension=".txt",
                                         filetypes=[("Text Files", "*.txt")])
        assert result == "/tk/saved.txt"
        tk_dialogs.save.assert_called_once_with(
            title="Save File As", filetypes=[("Text Files", "*.txt")], defaultextension=".txt"
        )

    def test_env_tk_passes_everything_through(self, portal, tk_dialogs, monkeypatch):
        monkeypatch.setenv(fd.ENV_OVERRIDE, "tk")
        fd.ask_save_as_filename(None, title="T", defaultextension=".mid", initialfile="a.mid", initialdir="/d")
        portal.assert_not_called()
        tk_dialogs.save.assert_called_once_with(
            title="T", defaultextension=".mid", initialfile="a.mid", initialdir="/d"
        )


# ----------------------------------------------------------------------
# Portal response handling and the D-Bus round-trip (fake connection)
# ----------------------------------------------------------------------

class TestInterpretResponse:
    def test_success(self):
        assert fd._interpret_response(0, {"uris": ("as", ["file:///a"])}) == ["file:///a"]

    def test_success_without_uris(self):
        assert fd._interpret_response(0, {}) == []

    def test_cancelled(self):
        assert fd._interpret_response(1, {}) is None

    def test_other_error_means_fallback(self):
        with pytest.raises(fd.PortalUnavailableError):
            fd._interpret_response(2, {})


def test_predict_request_path():
    assert fd._predict_request_path(":1.42", "tok") == "/org/freedesktop/portal/desktop/request/1_42/tok"


try:
    from jeepney import DBusAddress, HeaderFields, new_error, new_method_return, new_signal
except ImportError:  # pragma: no cover - jeepney is a regular dependency
    HAVE_JEEPNEY = False
else:
    HAVE_JEEPNEY = True

needs_jeepney = pytest.mark.skipif(not HAVE_JEEPNEY, reason="jeepney not installed")


class FakeConnection:
    """Just enough of jeepney.io.blocking.DBusConnection for _portal_request."""

    def __init__(self, response=(0, {"uris": ("as", ["file:///home/me/a.txt"])}),
                 probe_error=None, call_error=None, handle_override=None):
        self.unique_name = ":1.77"
        self.sent = []
        self.response = response
        self.probe_error = probe_error
        self.call_error = call_error
        self.handle_override = handle_override
        self._queue = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    @contextmanager
    def filter(self, rule, bufsize=1):
        self._queue = deque()
        yield self._queue

    def send_and_get_reply(self, msg, timeout=None):
        member = msg.header.fields[HeaderFields.member]
        self.sent.append((member, msg))
        if member == "Get":
            if self.probe_error:
                return new_error(msg, self.probe_error, "s", ("nope",))
            return new_method_return(msg, "v", (("u", 4),))
        if member == "AddMatch":
            return new_method_return(msg)
        if member in ("OpenFile", "SaveFile"):
            if self.call_error:
                return new_error(msg, self.call_error, "s", ("bad",))
            token = msg.body[2]["handle_token"][1]
            handle = self.handle_override or fd._predict_request_path(self.unique_name, token)
            # A Response for somebody else's request, which must be skipped...
            self._queue.append(self._signal("/org/freedesktop/portal/desktop/request/1_77/other", (0, {})))
            # ...then ours.
            self._queue.append(self._signal(handle, self.response))
            return new_method_return(msg, "o", (handle,))
        raise AssertionError(f"unexpected call {member}")

    def recv_until_filtered(self, queue, timeout=None):
        if not queue:
            raise ConnectionResetError("bus went away")
        return queue.popleft()

    @staticmethod
    def _signal(path, body):
        emitter = DBusAddress(path, interface="org.freedesktop.portal.Request")
        return new_signal(emitter, "Response", "ua{sv}", body)


@pytest.fixture
def fake_bus(monkeypatch):
    holder = {}

    def install(**kwargs):
        conn = FakeConnection(**kwargs)
        holder["conn"] = conn
        monkeypatch.setattr("jeepney.io.blocking.open_dbus_connection", lambda bus="SESSION": conn)
        return conn

    return install


@needs_jeepney
class TestPortalRequest:
    def test_success_and_subscription_order(self, fake_bus):
        conn = fake_bus()
        uris = fd._portal_request("OpenFile", "x11:abc", "Open", {"modal": ("b", True)})

        assert uris == ["file:///home/me/a.txt"]
        members = [m for m, _ in conn.sent]
        assert members == ["Get", "AddMatch", "OpenFile"]  # subscribed before calling

        add_match = conn.sent[1][1]
        open_call = conn.sent[2][1]
        token = open_call.body[2]["handle_token"][1]
        assert fd._predict_request_path(":1.77", token) in add_match.body[0]
        assert open_call.body[:2] == ("x11:abc", "Open")
        assert open_call.body[2]["modal"] == ("b", True)
        assert open_call.header.fields[HeaderFields.interface] == "org.freedesktop.portal.FileChooser"
        assert conn.closed

    def test_cancel(self, fake_bus):
        fake_bus(response=(1, {}))
        assert fd._portal_request("SaveFile", "", "Save", {}) is None

    def test_response_2_falls_back(self, fake_bus):
        fake_bus(response=(2, {}))
        with pytest.raises(fd.PortalUnavailableError):
            fd._portal_request("OpenFile", "", "Open", {})

    def test_missing_portal_is_remembered(self, fake_bus):
        fake_bus(probe_error="org.freedesktop.DBus.Error.ServiceUnknown")
        with pytest.raises(fd.PortalUnavailableError):
            fd._portal_request("OpenFile", "", "Open", {})
        assert fd._portal_known_missing is True

    def test_call_error_falls_back(self, fake_bus):
        fake_bus(call_error="org.freedesktop.DBus.Error.AccessDenied")
        with pytest.raises(fd.PortalUnavailableError):
            fd._portal_request("OpenFile", "", "Open", {})
        assert fd._portal_known_missing is False  # transient, try again next time

    def test_unexpected_handle_still_answered(self, fake_bus):
        conn = fake_bus(handle_override="/org/freedesktop/portal/desktop/request/legacy/42")
        assert fd._portal_request("OpenFile", "", "Open", {}) == ["file:///home/me/a.txt"]
        assert [m for m, _ in conn.sent] == ["Get", "AddMatch", "OpenFile", "AddMatch"]

    def test_no_session_bus(self, monkeypatch):
        def boom(bus="SESSION"):
            raise KeyError("DBUS_SESSION_BUS_ADDRESS")
        monkeypatch.setattr("jeepney.io.blocking.open_dbus_connection", boom)
        with pytest.raises(fd.PortalUnavailableError):
            fd._portal_request("OpenFile", "", "Open", {})
        assert fd._portal_known_missing is True

    def test_jeepney_missing(self, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "jeepney", None)
        with pytest.raises(fd.PortalUnavailableError):
            fd._portal_request("OpenFile", "", "Open", {})

    def test_connection_lost_while_dialog_open(self, fake_bus, monkeypatch):
        conn = fake_bus()
        monkeypatch.setattr(conn, "recv_until_filtered", mock.Mock(side_effect=OSError("gone")))
        assert fd._portal_request("OpenFile", "", "Open", {}) is None

    def test_end_to_end_through_public_api(self, fake_bus, on_linux, monkeypatch, tk_dialogs):
        fake_bus(response=(0, {"uris": ("as", ["file:///run/user/1000/doc/9f/My%20Song.txt"])}))
        monkeypatch.setattr(fd, "_parent_window_handle", lambda parent: "")
        path = fd.ask_open_filename(None, title="Open", filetypes=[("Text", "*.txt")])
        assert path == "/run/user/1000/doc/9f/My Song.txt"
        assert fd.display_path(path) == "My Song.txt"
        tk_dialogs.open.assert_not_called()


# ----------------------------------------------------------------------
# Threading / parent window helpers
# ----------------------------------------------------------------------

class TestRunInWorker:
    def test_runs_off_main_thread_without_tk(self):
        main = threading.get_ident()
        assert fd._run_in_worker(None, lambda: threading.get_ident() != main) is True

    def test_reraises_worker_exception(self):
        def fail():
            raise fd.PortalUnavailableError("x")
        with pytest.raises(fd.PortalUnavailableError):
            fd._run_in_worker(None, fail)

    def test_tk_events_keep_flowing(self):
        tk = pytest.importorskip("tkinter")
        if not (os.environ.get("DISPLAY") or os.name == "nt"):
            pytest.skip("no display")
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("Tk unavailable")
        root.withdraw()
        try:
            release = threading.Event()
            ticks = []

            def tick():
                ticks.append(1)
                if len(ticks) >= 3:
                    release.set()
                root.after(10, tick)

            root.after(10, tick)
            # The worker only finishes once Tk has run several callbacks,
            # which can only happen if the main thread keeps the loop going.
            assert fd._run_in_worker(root, lambda: release.wait(5)) is True
            assert len(ticks) >= 3
        finally:
            root.destroy()


class TestParentWindowHandle:
    def _widget(self, system="x11", frame="0x1c00009"):
        widget = mock.Mock()
        widget.tk.call.return_value = system
        widget.winfo_toplevel.return_value.wm_frame.return_value = frame
        return widget

    def test_x11_frame(self):
        assert fd._parent_window_handle(self._widget()) == "x11:1c00009"

    def test_non_x11(self):
        assert fd._parent_window_handle(self._widget(system="win32")) == ""

    def test_bad_frame(self):
        assert fd._parent_window_handle(self._widget(frame="")) == ""

    def test_no_parent_no_root(self, monkeypatch):
        monkeypatch.setattr(fd.tk, "_default_root", None, raising=False)
        assert fd._parent_window_handle(None) == ""
