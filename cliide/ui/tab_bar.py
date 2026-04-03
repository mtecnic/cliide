"""File tab bar widget for managing multiple open files."""

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Button


class FileTab(Static):
    """Individual file tab widget."""

    DEFAULT_CSS = """
    FileTab {
        width: auto;
        height: 3;
        padding: 0 1;
        margin: 0 0 0 0;
        background: $panel;
        border-right: tall $background;
    }

    FileTab:hover {
        background: $boost;
    }

    FileTab.active {
        background: $surface;
        border-bottom: tall $primary;
    }

    FileTab.modified .tab-name {
        color: $warning;
    }

    FileTab .tab-name {
        width: auto;
    }

    FileTab .tab-close {
        width: 3;
        min-width: 3;
        padding: 0;
        margin: 0 0 0 1;
        background: transparent;
        border: none;
        color: $text-muted;
    }

    FileTab .tab-close:hover {
        color: $error;
        background: $error 20%;
    }
    """

    class Selected(Message):
        """Tab was selected."""

        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()

    class CloseRequested(Message):
        """Tab close was requested."""

        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()

    is_active: reactive[bool] = reactive(False)
    is_modified: reactive[bool] = reactive(False)

    def __init__(
        self,
        file_path: str,
        is_active: bool = False,
        is_modified: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize file tab.

        Args:
            file_path: Path to the file
            is_active: Whether this tab is currently active
            is_modified: Whether the file has unsaved changes
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.file_path = file_path
        self.is_active = is_active
        self.is_modified = is_modified

    def compose(self) -> ComposeResult:
        """Compose tab contents."""
        path = Path(self.file_path)
        name = path.name

        # Add modified indicator
        modified_indicator = " ●" if self.is_modified else ""

        yield Static(f"{name}{modified_indicator}", classes="tab-name")
        yield Button("×", classes="tab-close", variant="default")

    def on_mount(self) -> None:
        """Handle mount."""
        self._update_classes()

    def watch_is_active(self, active: bool) -> None:
        """React to active state changes."""
        self._update_classes()

    def watch_is_modified(self, modified: bool) -> None:
        """React to modified state changes."""
        self._update_classes()
        # Update the tab name with modified indicator
        try:
            name_widget = self.query_one(".tab-name", Static)
            path = Path(self.file_path)
            modified_indicator = " ●" if modified else ""
            name_widget.update(f"{path.name}{modified_indicator}")
        except Exception:
            pass

    def _update_classes(self) -> None:
        """Update CSS classes based on state."""
        self.set_class(self.is_active, "active")
        self.set_class(self.is_modified, "modified")

    def on_click(self) -> None:
        """Handle click on tab."""
        self.post_message(self.Selected(self.file_path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle close button click."""
        event.stop()
        self.post_message(self.CloseRequested(self.file_path))


class TabBar(Horizontal):
    """Horizontal tab bar for open files."""

    DEFAULT_CSS = """
    TabBar {
        width: 100%;
        height: 3;
        background: $panel;
        border-bottom: tall $primary;
        overflow-x: auto;
        overflow-y: hidden;
    }

    TabBar:empty {
        height: 0;
        display: none;
    }
    """

    class FileSelected(Message):
        """File was selected in tab bar."""

        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()

    class FileCloseRequested(Message):
        """File close was requested."""

        def __init__(self, file_path: str) -> None:
            self.file_path = file_path
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize tab bar."""
        super().__init__(**kwargs)
        self._tabs: dict[str, FileTab] = {}  # file_path -> FileTab
        self._active_path: str | None = None

    def add_tab(self, file_path: str, activate: bool = True) -> None:
        """Add a new tab for a file.

        Args:
            file_path: Path to the file
            activate: Whether to make this tab active
        """
        # Normalize path
        path_str = str(Path(file_path).resolve())

        # Check if tab already exists
        if path_str in self._tabs:
            if activate:
                self.activate_tab(path_str)
            return

        # Create new tab
        tab = FileTab(path_str, is_active=activate)
        self._tabs[path_str] = tab
        self.mount(tab)

        if activate:
            self._set_active(path_str)

    def remove_tab(self, file_path: str) -> str | None:
        """Remove a tab.

        Args:
            file_path: Path to the file

        Returns:
            Path of the next tab to activate, or None if no tabs left
        """
        path_str = str(Path(file_path).resolve())

        if path_str not in self._tabs:
            return None

        tab = self._tabs[path_str]

        # Determine next tab to activate
        next_path = None
        if path_str == self._active_path:
            # Find adjacent tab
            tab_paths = list(self._tabs.keys())
            idx = tab_paths.index(path_str)

            if len(tab_paths) > 1:
                # Prefer tab to the right, then to the left
                if idx < len(tab_paths) - 1:
                    next_path = tab_paths[idx + 1]
                else:
                    next_path = tab_paths[idx - 1]

        # Remove tab
        tab.remove()
        del self._tabs[path_str]

        # Activate next tab
        if next_path:
            self._set_active(next_path)
        else:
            self._active_path = None

        return next_path

    def activate_tab(self, file_path: str) -> None:
        """Activate a tab.

        Args:
            file_path: Path to the file
        """
        path_str = str(Path(file_path).resolve())

        if path_str in self._tabs:
            self._set_active(path_str)

    def set_modified(self, file_path: str, modified: bool) -> None:
        """Set modified state for a tab.

        Args:
            file_path: Path to the file
            modified: Whether the file is modified
        """
        path_str = str(Path(file_path).resolve())

        if path_str in self._tabs:
            self._tabs[path_str].is_modified = modified

    def _set_active(self, file_path: str) -> None:
        """Set the active tab.

        Args:
            file_path: Path to make active
        """
        # Deactivate previous
        if self._active_path and self._active_path in self._tabs:
            self._tabs[self._active_path].is_active = False

        # Activate new
        self._active_path = file_path
        if file_path in self._tabs:
            self._tabs[file_path].is_active = True

    def get_open_files(self) -> list[str]:
        """Get list of open file paths.

        Returns:
            List of file paths
        """
        return list(self._tabs.keys())

    def get_active_file(self) -> str | None:
        """Get the active file path.

        Returns:
            Active file path or None
        """
        return self._active_path

    def has_file(self, file_path: str) -> bool:
        """Check if a file is open in tabs.

        Args:
            file_path: Path to check

        Returns:
            True if file is open
        """
        path_str = str(Path(file_path).resolve())
        return path_str in self._tabs

    def on_file_tab_selected(self, event: FileTab.Selected) -> None:
        """Handle tab selection."""
        event.stop()
        self.activate_tab(event.file_path)
        self.post_message(self.FileSelected(event.file_path))

    def on_file_tab_close_requested(self, event: FileTab.CloseRequested) -> None:
        """Handle tab close request."""
        event.stop()
        self.post_message(self.FileCloseRequested(event.file_path))
