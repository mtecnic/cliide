"""Directory browser widget for project selection."""

import os
from pathlib import Path
from typing import Iterable

from textual.message import Message
from textual.widgets import DirectoryTree


def get_default_browse_path() -> Path:
    """Get a sensible default path for browsing projects.

    On WSL: Returns /mnt/c/Users/{username}/ if it exists
    On native Linux/Mac: Returns home directory

    Returns:
        Best starting path for project browsing
    """
    # Check if we're in WSL
    is_wsl = False
    try:
        with open("/proc/version", "r") as f:
            is_wsl = "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        pass

    if is_wsl:
        # Try to find Windows user directory
        # Check common locations
        windows_user = os.environ.get("USER", os.environ.get("USERNAME", ""))
        possible_paths = [
            Path(f"/mnt/c/Users/{windows_user}"),
            Path("/mnt/c/Users"),
            Path("/mnt/c"),
        ]
        for p in possible_paths:
            if p.exists() and p.is_dir():
                return p

    # Fall back to home directory
    return Path.home()


class DirectorySelected(Message):
    """Message emitted when a directory is selected."""

    def __init__(self, path: Path) -> None:
        """Initialize the message.

        Args:
            path: The selected directory path
        """
        super().__init__()
        self.path = path


class DirectoryBrowser(DirectoryTree):
    """Directory tree browser for project selection.

    Shows both files and directories for context (so users can recognize
    projects by their contents like package.json, README.md, etc.),
    but only directories can be selected as projects.
    Works on both native Linux and WSL (Windows paths at /mnt/c/, etc.).
    """

    DEFAULT_CSS = """
    DirectoryBrowser {
        background: $surface;
        height: 1fr;
    }

    DirectoryBrowser > .directory-tree--folder {
        color: $accent;
        text-style: bold;
    }

    DirectoryBrowser > .directory-tree--cursor {
        background: $boost;
        color: $primary;
        text-style: bold;
    }

    DirectoryBrowser > .directory-tree--highlight {
        background: $boost;
    }
    """

    def __init__(self, path: str | Path = "~", **kwargs) -> None:
        """Initialize the directory browser.

        Args:
            path: Starting directory path (defaults to home)
            **kwargs: Additional arguments for DirectoryTree
        """
        # Expand ~ to home directory
        start_path = Path(path).expanduser().resolve()
        if not start_path.exists():
            start_path = Path.home()

        super().__init__(str(start_path), **kwargs)
        self.selected_path: Path | None = None

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Filter paths, showing both files and directories.

        Files are shown for context (to help identify projects by their contents
        like package.json, README.md, etc.) but only directories can be selected.
        Hidden files/directories (starting with .) are hidden for cleaner browsing.

        Args:
            paths: Paths to filter

        Returns:
            Filtered paths (both files and directories, excluding hidden)
        """
        return [p for p in paths if not p.name.startswith(".")]

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Handle directory selection (double-click or enter).

        Args:
            event: Directory selected event
        """
        self.selected_path = event.path
        self.post_message(DirectorySelected(event.path))

    def on_tree_node_highlighted(self, event: DirectoryTree.NodeHighlighted) -> None:
        """Track currently highlighted node.

        Args:
            event: Node highlighted event
        """
        if event.node.data:
            path = event.node.data.path
            if path.is_dir():
                self.selected_path = path

    def get_selected(self) -> Path | None:
        """Get currently selected/highlighted directory.

        Returns:
            Selected path or None
        """
        return self.selected_path

    def navigate_to(self, path: Path) -> None:
        """Navigate to a specific directory.

        Args:
            path: Directory to navigate to
        """
        path = Path(path).expanduser().resolve()
        if path.exists() and path.is_dir():
            self.path = str(path)
            self.reload()
