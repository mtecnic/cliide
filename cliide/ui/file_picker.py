"""File picker popup for @mentions in chat."""

import os
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static


class FilePicker(Widget):
    """Popup file picker for @mentions."""

    DEFAULT_CSS = """
    FilePicker {
        layer: overlay;
        width: 60;
        height: 20;
        background: $panel;
        border: round $primary;
        offset: 2 2;
    }

    #file-picker-header {
        dock: top;
        height: 2;
        background: $boost;
        color: $primary;
        text-style: bold;
        padding: 0 1;
        border-bottom: heavy $primary;
    }

    #file-picker-list {
        height: 1fr;
        background: $surface;
    }

    FilePicker ListView {
        background: $surface;
    }

    FilePicker ListItem {
        padding: 0 1;
        border-left: heavy transparent;
    }

    FilePicker ListItem:hover {
        background: $boost;
        border-left: heavy $accent;
        color: $accent;
    }

    FilePicker ListView > .list-item--highlighted {
        background: $boost;
        border-left: heavy $primary;
        color: $primary;
        text-style: bold;
    }
    """

    class FileSelected(Message):
        """Sent when a file is selected."""

        def __init__(self, file_path: str) -> None:
            """Initialize message.

            Args:
                file_path: Selected file path (relative to workspace)
            """
            super().__init__()
            self.file_path = file_path

    def __init__(self, workspace_path: Path, filter_text: str = "", **kwargs) -> None:
        """Initialize file picker.

        Args:
            workspace_path: Root workspace path
            filter_text: Initial filter text (text after @)
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.workspace_path = workspace_path
        self.filter_text = filter_text.lower()
        self.files: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose the file picker."""
        yield Static("📁 Type to filter • ↑↓ navigate • Enter/Esc", id="file-picker-header")
        yield ListView(id="file-picker-list")

    def on_mount(self) -> None:
        """Handle mount - populate file list."""
        self._populate_files()
        # Don't steal focus - let chat input keep it for typing

    def _populate_files(self) -> None:
        """Populate the file list."""
        list_view = self.query_one("#file-picker-list", ListView)
        list_view.clear()
        self.files.clear()  # Clear files list too

        # Directories to skip (speeds up file scanning significantly)
        ignore_dirs = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".pytest_cache", ".mypy_cache", "dist", "build", ".tox",
            "eggs", ".eggs", "site-packages", ".egg-info"
        }

        # File extensions to include
        valid_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".yaml", ".yml"}

        max_files = 500
        file_count = 0

        # Use os.walk for fast directory traversal with filtering
        for root, dirs, files in os.walk(self.workspace_path):
            # Remove ignored directories from dirs IN PLACE to prevent os.walk from entering them
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for filename in files:
                # Check extension
                ext = os.path.splitext(filename)[1].lower()
                if ext not in valid_extensions:
                    continue

                # Get relative path
                full_path = Path(root) / filename
                try:
                    relative_path = full_path.relative_to(self.workspace_path)
                    relative_str = str(relative_path)

                    # Apply filter
                    if self.filter_text and self.filter_text not in relative_str.lower():
                        continue

                    self.files.append(relative_str)
                    list_view.append(ListItem(Static(relative_str)))
                    file_count += 1

                    # Stop if we have enough files
                    if file_count >= max_files:
                        break

                except ValueError:
                    continue

            if file_count >= max_files:
                break

        # Set initial selection (don't focus - let chat input keep focus for typing)
        if len(list_view.children) > 0:
            list_view.index = 0

    def update_filter(self, filter_text: str) -> None:
        """Update the filter and refresh file list.

        Args:
            filter_text: New filter text
        """
        self.filter_text = filter_text.lower()
        self._populate_files()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle file selection.

        Args:
            event: Selection event
        """
        # Use the index to get the file path from our list
        list_view = event.list_view
        if list_view.index is not None and list_view.index < len(self.files):
            file_path = self.files[list_view.index]
            self.post_message(self.FileSelected(file_path))
            # Don't remove here - let ChatPanel close it after handling message

    def on_key(self, event) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        if event.key == "escape":
            self.remove()
            event.stop()
