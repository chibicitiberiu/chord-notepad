"""UI helper utilities for common Tkinter patterns."""

import tkinter as tk
from typing import Callable, Optional


class ToolTip:
    """Create a tooltip for a given widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        """Initialize the tooltip.

        Args:
            widget: Widget to attach tooltip to
            text: Text to display in tooltip
            delay: Delay in milliseconds before showing tooltip
        """
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.schedule_id: Optional[str] = None

        # Bind events
        self.widget.bind('<Enter>', self._on_enter)
        self.widget.bind('<Leave>', self._on_leave)
        self.widget.bind('<Button>', self._on_leave)  # Hide on click

    def _on_enter(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse enter event."""
        self._unschedule()
        self.schedule_id = self.widget.after(self.delay, self._show_tooltip)

    def _on_leave(self, event: Optional[tk.Event] = None) -> None:
        """Handle mouse leave event."""
        self._unschedule()
        self._hide_tooltip()

    def _unschedule(self) -> None:
        """Cancel scheduled tooltip display."""
        if self.schedule_id:
            self.widget.after_cancel(self.schedule_id)
            self.schedule_id = None

    def _show_tooltip(self) -> None:
        """Display the tooltip."""
        if self.tooltip_window or not self.text:
            return

        # Get widget position
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        # Create tooltip window
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)  # No window decorations
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        # Create label with text
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            background="#ffffe0",
            foreground="black",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Arial", "9", "normal"),
            padx=5,
            pady=3
        )
        label.pack()

    def _hide_tooltip(self) -> None:
        """Hide the tooltip."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


def create_tooltip(widget: tk.Widget, text: str, delay: int = 500) -> ToolTip:
    """Create a tooltip for a widget.

    Args:
        widget: Widget to attach tooltip to
        text: Tooltip text
        delay: Delay before showing (milliseconds)

    Returns:
        ToolTip instance

    Example:
        button = tk.Button(root, text="Click me")
        create_tooltip(button, "This button does something")
    """
    return ToolTip(widget, text, delay)


def bind_mousewheel(widget: tk.Widget, callback: Callable, platform: Optional[str] = None) -> None:
    """Cross-platform mousewheel binding.

    Args:
        widget: Widget to bind to
        callback: Function to call on scroll (receives delta as argument)
        platform: Force specific platform binding (None = auto-detect)

    Example:
        def on_scroll(delta):
            canvas.yview_scroll(-delta, "units")

        bind_mousewheel(canvas, on_scroll)
    """
    import sys

    if platform is None:
        platform = sys.platform

    if platform.startswith('linux'):
        # Linux uses Button-4 and Button-5
        widget.bind('<Button-4>', lambda e: callback(1))
        widget.bind('<Button-5>', lambda e: callback(-1))
    elif platform == 'darwin':
        # macOS
        widget.bind('<MouseWheel>', lambda e: callback(e.delta))
    else:
        # Windows
        widget.bind('<MouseWheel>', lambda e: callback(e.delta // 120))


def center_window(window: tk.Tk | tk.Toplevel, width: Optional[int] = None,
                  height: Optional[int] = None) -> None:
    """Center a window on the screen.

    Args:
        window: Window to center
        width: Window width (uses current if None)
        height: Window height (uses current if None)

    Example:
        root = tk.Tk()
        center_window(root, 800, 600)
    """
    # Update to get current geometry if needed
    window.update_idletasks()

    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()

    # Calculate position
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")


def set_icon(window: tk.Tk | tk.Toplevel, icon_path: str) -> bool:
    """Set window icon cross-platform.

    Args:
        window: Window to set icon for
        icon_path: Path to icon file (.ico on Windows, .png/.xbm on Linux/Mac)

    Returns:
        True if icon was set successfully

    Example:
        set_icon(root, "resources/icon.png")
    """
    try:
        from pathlib import Path
        path = Path(icon_path)

        if not path.exists():
            return False

        if path.suffix.lower() == '.ico':
            window.iconbitmap(str(path))
        else:
            # For .png and other formats
            img = tk.PhotoImage(file=str(path))
            window.iconphoto(True, img)

        return True
    except Exception:
        return False


def create_scrollable_frame(parent: tk.Widget, **kwargs) -> tuple[tk.Frame, tk.Canvas, tk.Scrollbar]:
    """Create a scrollable frame widget.

    Args:
        parent: Parent widget
        **kwargs: Additional arguments passed to the frame

    Returns:
        Tuple of (frame, canvas, scrollbar)

    Example:
        frame, canvas, scrollbar = create_scrollable_frame(root)
        # Add widgets to frame
        tk.Label(frame, text="Content").pack()
    """
    # Create canvas and scrollbar
    canvas = tk.Canvas(parent, **kwargs)
    scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    # Create frame inside canvas
    frame = tk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=frame, anchor=tk.NW)

    # Configure scroll region when frame changes size
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width)

    frame.bind('<Configure>', on_frame_configure)
    canvas.bind('<Configure>', on_canvas_configure)

    # Pack widgets
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Bind mousewheel
    bind_mousewheel(canvas, lambda delta: canvas.yview_scroll(-delta, "units"))

    return frame, canvas, scrollbar
