"""Window mixin for common window functionality."""

import tkinter as tk
from typing import Optional


class WindowMixin:
    """Mixin providing common window functionality.

    Provides template methods and utilities for window setup.
    Can be used with both tk.Tk (root window) and tk.Toplevel (secondary windows).

    Example:
        class MyWindow(tk.Toplevel, WindowMixin):
            def __init__(self, parent):
                tk.Toplevel.__init__(self, parent)
                self.title("My Window")
                self.init_window()

            def _create_widgets(self):
                tk.Label(self, text="Hello").pack()

            def _bind_events(self):
                self.bind('<Escape>', lambda e: self.destroy())
    """

    def init_window(self) -> None:
        """Initialize the window using template methods.

        Call this after the window is created to trigger the template method pattern.
        Subclasses should call this in their __init__ after setting up the window.
        """
        self._setup_window()
        self._create_widgets()
        self._layout_widgets()
        self._bind_events()

    def _setup_window(self) -> None:
        """Configure window properties.

        Override this to set window geometry, resizable, protocol handlers, etc.

        Example:
            def _setup_window(self):
                self.geometry("800x600")
                self.resizable(True, True)
                self.protocol("WM_DELETE_WINDOW", self._on_close)
        """
        pass

    def _create_widgets(self) -> None:
        """Create all widgets for this window.

        Override this to instantiate widgets. Don't pack/grid them here.

        Example:
            def _create_widgets(self):
                self.label = tk.Label(self, text="Hello")
                self.button = tk.Button(self, text="Click")
        """
        raise NotImplementedError("Subclasses must implement _create_widgets")

    def _layout_widgets(self) -> None:
        """Layout widgets using pack, grid, or place.

        Override this to arrange widgets.

        Example:
            def _layout_widgets(self):
                self.label.pack(pady=10)
                self.button.pack(pady=5)
        """
        pass

    def _bind_events(self) -> None:
        """Bind events to handlers.

        Override this to set up event bindings.

        Example:
            def _bind_events(self):
                self.button.bind('<Button-1>', self._on_click)
                self.bind('<Escape>', self._on_escape)
        """
        pass

    def center_on_screen(self, width: Optional[int] = None, height: Optional[int] = None) -> None:
        """Center window on screen.

        Args:
            width: Window width (uses current if None)
            height: Window height (uses current if None)
        """
        # Type assertion for mypy
        assert isinstance(self, (tk.Tk, tk.Toplevel))

        self.update_idletasks()

        if width is None:
            width = self.winfo_width()
        if height is None:
            height = self.winfo_height()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

    def center_on_parent(self) -> None:
        """Center window on parent window.

        Only works for tk.Toplevel windows that have a master.
        """
        # Type assertion for mypy
        assert isinstance(self, (tk.Tk, tk.Toplevel))

        self.update_idletasks()

        parent_x = self.master.winfo_x()
        parent_y = self.master.winfo_y()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        window_width = self.winfo_width()
        window_height = self.winfo_height()

        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2

        self.geometry(f"+{x}+{y}")

    def set_icon(self, icon_path: str) -> bool:
        """Set window icon.

        Args:
            icon_path: Path to icon file

        Returns:
            True if icon was set successfully
        """
        # Type assertion for mypy
        assert isinstance(self, (tk.Tk, tk.Toplevel))

        try:
            from pathlib import Path
            path = Path(icon_path)

            if not path.exists():
                return False

            if path.suffix.lower() == '.ico':
                self.iconbitmap(str(path))
            else:
                img = tk.PhotoImage(file=str(path))
                self.iconphoto(True, img)

            return True
        except Exception:
            return False

    def show_modal(self) -> None:
        """Show window as modal dialog.

        Grabs all events and waits for window to be destroyed.
        Only works for tk.Toplevel windows.
        """
        # Type assertion for mypy
        assert isinstance(self, tk.Toplevel)

        self.transient(self.master)
        self.grab_set()
        self.wait_window()

    def close(self) -> None:
        """Close the window.

        Override this if you need custom close handling.
        """
        # Type assertion for mypy
        assert isinstance(self, (tk.Tk, tk.Toplevel))

        self.destroy()
