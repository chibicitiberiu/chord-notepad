"""Frame mixin for common frame functionality."""

import tkinter as tk


class FrameMixin:
    """Mixin providing common frame functionality.

    Provides a template pattern for creating composite widgets
    with consistent initialization and layout.

    Example:
        class MyPanel(tk.Frame, FrameMixin):
            def __init__(self, parent, **kwargs):
                tk.Frame.__init__(self, parent, **kwargs)
                self.init_frame()

            def _create_widgets(self):
                self.title_label = tk.Label(self, text="My Panel")
                self.content_text = tk.Text(self, height=10)

            def _layout_widgets(self):
                self.title_label.pack(anchor='w', pady=5)
                self.content_text.pack(fill='both', expand=True)
    """

    def init_frame(self) -> None:
        """Initialize the frame using template methods.

        Call this after the frame is created to trigger the template method pattern.
        Subclasses should call this in their __init__ after tk.Frame.__init__.
        """
        self._create_widgets()
        self._layout_widgets()
        self._bind_events()

    def _create_widgets(self) -> None:
        """Create all widgets for this frame.

        Override this to instantiate child widgets.
        Don't layout them here - that's done in _layout_widgets.

        Example:
            def _create_widgets(self):
                self.label = tk.Label(self, text="Hello")
                self.button = tk.Button(self, text="Click", command=self._on_click)
        """
        raise NotImplementedError("Subclasses must implement _create_widgets")

    def _layout_widgets(self) -> None:
        """Layout widgets using pack, grid, or place.

        Override this to arrange the widgets created in _create_widgets.

        Example:
            def _layout_widgets(self):
                self.label.grid(row=0, column=0, sticky='w')
                self.button.grid(row=1, column=0, pady=5)
        """
        pass

    def _bind_events(self) -> None:
        """Bind events to handlers.

        Override this to set up event bindings.

        Example:
            def _bind_events(self):
                self.bind('<Configure>', self._on_resize)
        """
        pass

    def clear(self) -> None:
        """Clear all child widgets from this frame.

        Useful for refreshing or resetting the frame content.
        """
        # Type assertion for mypy
        assert isinstance(self, tk.Frame)

        for widget in self.winfo_children():
            widget.destroy()

    def enable(self) -> None:
        """Enable this frame and all child widgets."""
        self._set_state('normal')

    def disable(self) -> None:
        """Disable this frame and all child widgets."""
        self._set_state('disabled')

    def _set_state(self, state: str) -> None:
        """Set state for all child widgets.

        Args:
            state: Widget state ('normal', 'disabled', etc.)
        """
        # Type assertion for mypy
        assert isinstance(self, tk.Frame)

        for widget in self.winfo_children():
            try:
                widget.configure(state=state)
            except tk.TclError:
                # Some widgets don't support state configuration
                pass

    def show(self) -> None:
        """Show this frame (make visible)."""
        # Type assertion for mypy
        assert isinstance(self, tk.Frame)

        self.pack()

    def hide(self) -> None:
        """Hide this frame (make invisible but keep in memory)."""
        # Type assertion for mypy
        assert isinstance(self, tk.Frame)

        self.pack_forget()

    def toggle_visibility(self) -> None:
        """Toggle visibility of this frame."""
        # Type assertion for mypy
        assert isinstance(self, tk.Frame)

        if self.winfo_viewable():
            self.hide()
        else:
            self.show()
