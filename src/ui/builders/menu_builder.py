"""Fluent builder for Tkinter menus."""

import tkinter as tk
from typing import Callable, Optional, Any


class MenuBuilder:
    """Fluent builder for creating Tkinter menus.

    Provides a chainable interface for constructing menus with commands,
    checkbuttons, radiobuttons, separators, and submenus.

    Example:
        menubar = tk.Menu(root)

        file_menu = MenuBuilder(menubar) \\
            .add_command("New", new_file, accelerator="Ctrl+N") \\
            .add_command("Open", open_file, accelerator="Ctrl+O") \\
            .add_separator() \\
            .add_command("Save", save_file, accelerator="Ctrl+S") \\
            .add_separator() \\
            .add_command("Exit", root.quit, accelerator="Ctrl+Q") \\
            .build()

        menubar.add_cascade(label="File", menu=file_menu)
    """

    def __init__(self, parent: tk.Menu, tearoff: int = 0):
        """Initialize the menu builder.

        Args:
            parent: Parent menu or menubar
            tearoff: Whether menu can be torn off (0 = no, 1 = yes)
        """
        self._parent = parent
        self._menu = tk.Menu(parent, tearoff=tearoff)

    def add_command(
        self,
        label: str,
        command: Optional[Callable] = None,
        accelerator: Optional[str] = None,
        underline: Optional[int] = None,
        state: str = 'normal'
    ) -> 'MenuBuilder':
        """Add a command item to the menu.

        Args:
            label: Menu item label
            command: Function to call when item is clicked
            accelerator: Keyboard shortcut text (display only, doesn't bind)
            underline: Index of character to underline for keyboard nav
            state: Item state ('normal', 'disabled', 'active')

        Returns:
            Self for method chaining

        Example:
            builder.add_command("Save", save_func, accelerator="Ctrl+S")
        """
        kwargs: dict[str, Any] = {'label': label, 'state': state}

        if command:
            kwargs['command'] = command
        if accelerator:
            kwargs['accelerator'] = accelerator
        if underline is not None:
            kwargs['underline'] = underline

        self._menu.add_command(**kwargs)
        return self

    def add_separator(self) -> 'MenuBuilder':
        """Add a separator line to the menu.

        Returns:
            Self for method chaining

        Example:
            builder.add_command("Cut", cut).add_separator().add_command("Paste", paste)
        """
        self._menu.add_separator()
        return self

    def add_checkbutton(
        self,
        label: str,
        variable: tk.Variable,
        command: Optional[Callable] = None,
        accelerator: Optional[str] = None
    ) -> 'MenuBuilder':
        """Add a checkbutton item to the menu.

        Args:
            label: Menu item label
            variable: BooleanVar or IntVar to track checked state
            command: Function to call when toggled
            accelerator: Keyboard shortcut text

        Returns:
            Self for method chaining

        Example:
            word_wrap_var = tk.BooleanVar(value=True)
            builder.add_checkbutton("Word Wrap", word_wrap_var, toggle_wrap)
        """
        kwargs: dict[str, Any] = {'label': label, 'variable': variable}

        if command:
            kwargs['command'] = command
        if accelerator:
            kwargs['accelerator'] = accelerator

        self._menu.add_checkbutton(**kwargs)
        return self

    def add_radiobutton(
        self,
        label: str,
        variable: tk.Variable,
        value: Any,
        command: Optional[Callable] = None,
        accelerator: Optional[str] = None
    ) -> 'MenuBuilder':
        """Add a radiobutton item to the menu.

        Args:
            label: Menu item label
            variable: Variable shared by all radiobuttons in the group
            value: Value to set variable to when selected
            command: Function to call when selected
            accelerator: Keyboard shortcut text

        Returns:
            Self for method chaining

        Example:
            notation_var = tk.StringVar(value="american")
            builder.add_radiobutton("American", notation_var, "american", on_change)
            builder.add_radiobutton("European", notation_var, "european", on_change)
        """
        kwargs: dict[str, Any] = {'label': label, 'variable': variable, 'value': value}

        if command:
            kwargs['command'] = command
        if accelerator:
            kwargs['accelerator'] = accelerator

        self._menu.add_radiobutton(**kwargs)
        return self

    def add_cascade(
        self,
        label: str,
        submenu: 'MenuBuilder',
        underline: Optional[int] = None
    ) -> 'MenuBuilder':
        """Add a cascading submenu.

        Args:
            label: Submenu label
            submenu: MenuBuilder for the submenu
            underline: Index of character to underline

        Returns:
            Self for method chaining

        Example:
            submenu = MenuBuilder(menubar).add_command("Item 1", func1)
            builder.add_cascade("Submenu", submenu)
        """
        kwargs: dict[str, Any] = {'label': label, 'menu': submenu.build()}

        if underline is not None:
            kwargs['underline'] = underline

        self._menu.add_cascade(**kwargs)
        return self

    def build(self) -> tk.Menu:
        """Build and return the completed menu.

        Returns:
            The constructed tk.Menu object

        Example:
            menu = builder.add_command("Item", func).build()
            menubar.add_cascade(label="Menu", menu=menu)
        """
        return self._menu

    @staticmethod
    def create_menubar(root: tk.Tk | tk.Toplevel) -> tk.Menu:
        """Create and attach a menubar to a window.

        Args:
            root: Window to attach menubar to

        Returns:
            The created menubar

        Example:
            menubar = MenuBuilder.create_menubar(root)
            file_menu = MenuBuilder(menubar).add_command("Exit", root.quit).build()
            menubar.add_cascade(label="File", menu=file_menu)
        """
        menubar = tk.Menu(root)
        root.config(menu=menubar)
        return menubar
