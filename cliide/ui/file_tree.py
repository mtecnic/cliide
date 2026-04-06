"""File tree widget for browsing project files."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.binding import Binding
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry

from cliide.core.events import FileCreated, FileDeleted, FileOpened, FileRenamed


# Git status codes
GIT_STATUS_ICONS = {
    "M": ("M", "yellow"),      # Modified
    "A": ("A", "green"),       # Added
    "D": ("D", "red"),         # Deleted
    "R": ("R", "cyan"),        # Renamed
    "C": ("C", "cyan"),        # Copied
    "U": ("U", "magenta"),     # Updated but unmerged
    "?": ("?", "bright_black"),  # Untracked
    "!": ("!", "dim"),         # Ignored
}


class FileTree(DirectoryTree):
    """File tree widget for project navigation with git status."""

    BINDINGS = [
        Binding("n", "new_file", "New File", show=False),
        Binding("N", "new_folder", "New Folder", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("r", "rename", "Rename", show=False),
    ]

    DEFAULT_CSS = """
    FileTree {
        background: $surface;
        border: round $primary;
    }

    FileTree > .directory-tree--folder {
        color: $accent;
        text-style: bold;
    }

    FileTree > .directory-tree--file {
        color: $text;
    }

    FileTree > .directory-tree--cursor {
        background: $boost;
        color: $primary;
        text-style: bold;
    }

    FileTree > .directory-tree--highlight {
        background: $boost;
    }

    /* Git status styles */
    FileTree .git-modified {
        color: yellow;
    }

    FileTree .git-added {
        color: green;
    }

    FileTree .git-deleted {
        color: red;
    }

    FileTree .git-untracked {
        color: $text-muted;
    }
    """

    def __init__(self, path: str, **kwargs: Any) -> None:
        """Initialize file tree.

        Args:
            path: Root directory path
            **kwargs: Additional arguments for DirectoryTree
        """
        # Disable auto-watching to avoid async warnings
        super().__init__(path, **kwargs)
        self.auto_expand = False

        # Git status tracking
        self._git_status: dict[str, str] = {}  # relative_path -> status code
        self._root_path = Path(path).resolve()
        self._is_git_repo = (self._root_path / ".git").exists()

        # Cache for relative path lookups (avoids repeated computation in render_label)
        self._rel_path_cache: dict[Path, str | None] = {}

    def on_mount(self) -> None:
        """Load git status after a short delay (don't block startup)."""
        if self._is_git_repo:
            # Defer git status to not slow down initial render
            self.set_timer(0.5, self._deferred_git_load)

    def _deferred_git_load(self) -> None:
        """Load git status after initial render."""
        if self._is_git_repo:
            self.run_worker(self._load_git_status())

    async def _load_git_status(self) -> None:
        """Load git status for all files."""
        try:
            # Run git status --porcelain in background
            process = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain", "-uall",
                cwd=str(self._root_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0:
                self._parse_git_status(stdout.decode("utf-8", errors="replace"))
                self.refresh()

        except Exception:
            # Git not available or error
            pass

    def _parse_git_status(self, output: str) -> None:
        """Parse git status --porcelain output.

        Args:
            output: Git status output
        """
        self._git_status.clear()

        for line in output.splitlines():
            if len(line) < 3:
                continue

            # Format: XY filename
            # X = index status, Y = working tree status
            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:].strip()

            # Handle renamed files (have " -> " in the path)
            if " -> " in file_path:
                file_path = file_path.split(" -> ")[1]

            # Prioritize worktree status for display
            if worktree_status != " " and worktree_status != "!":
                self._git_status[file_path] = worktree_status
            elif index_status != " " and index_status != "!":
                self._git_status[file_path] = index_status

    def refresh_git_status(self) -> None:
        """Refresh git status (call after file changes)."""
        if self._is_git_repo:
            self.run_worker(self._load_git_status())

    def _get_relative_path(self, file_path: Path) -> str | None:
        """Get cached relative path string for a file.

        Args:
            file_path: Absolute file path

        Returns:
            Relative path string or None if not under root
        """
        if file_path in self._rel_path_cache:
            return self._rel_path_cache[file_path]

        try:
            rel = str(file_path.relative_to(self._root_path)).replace("\\", "/")
            self._rel_path_cache[file_path] = rel
            return rel
        except ValueError:
            self._rel_path_cache[file_path] = None
            return None

    def render_label(
        self, node: DirEntry, base_style, style
    ) -> Text:
        """Render tree node label with git status.

        Args:
            node: Tree node
            base_style: Base style
            style: Applied style

        Returns:
            Rich Text with label
        """
        # Get base label from parent
        label = super().render_label(node, base_style, style)

        # Add git status indicator for files (only if we have git status data)
        if self._is_git_repo and self._git_status and node.data and node.data.path:
            rel_str = self._get_relative_path(node.data.path)
            if rel_str and rel_str in self._git_status:
                status_code = self._git_status[rel_str]
                if status_code in GIT_STATUS_ICONS:
                    icon, color = GIT_STATUS_ICONS[status_code]
                    status_text = Text(f"[{icon}] ", style=color)
                    return Text.assemble(status_text, label)

        return label

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection.

        Args:
            event: File selected event
        """
        event.stop()
        file_path = str(event.path)

        # Only open text files (basic filter)
        if self._is_text_file(file_path):
            self.post_message(FileOpened(file_path))

    def _is_text_file(self, path: str) -> bool:
        """Check if a file is a text file.

        Args:
            path: File path

        Returns:
            True if file is likely a text file
        """
        text_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".rs",
            ".go",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".css",
            ".scss",
            ".html",
            ".xml",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".md",
            ".txt",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
            ".vim",
            ".lua",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".r",
            ".sql",
        }

        file_path = Path(path)
        return file_path.suffix.lower() in text_extensions

    def _get_selected_path(self) -> Path | None:
        """Get the currently selected path (file or folder).

        Returns:
            Selected path or None if nothing selected
        """
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.path
        return None

    def _get_parent_folder(self) -> Path:
        """Get the parent folder for new file/folder creation.

        Returns:
            Parent folder path (either selected folder or parent of selected file)
        """
        selected = self._get_selected_path()
        if selected:
            if selected.is_dir():
                return selected
            return selected.parent
        return self._root_path

    async def action_new_file(self) -> None:
        """Create a new file in the selected directory."""
        from cliide.ui.dialogs import InputDialog

        parent = self._get_parent_folder()

        def on_submit(name: str) -> None:
            if name:
                new_path = parent / name
                try:
                    new_path.touch()
                    self.reload()
                    self.refresh_git_status()
                    self.post_message(FileCreated(str(new_path)))
                    # Open the new file
                    self.post_message(FileOpened(str(new_path)))
                except Exception:
                    pass  # Silently fail if cannot create

        self.app.push_screen(
            InputDialog(
                title="New File",
                prompt=f"Create file in: {parent.name}/",
                placeholder="filename.ext",
            ),
            on_submit,
        )

    async def action_new_folder(self) -> None:
        """Create a new folder in the selected directory."""
        from cliide.ui.dialogs import InputDialog

        parent = self._get_parent_folder()

        def on_submit(name: str) -> None:
            if name:
                new_path = parent / name
                try:
                    new_path.mkdir(parents=True, exist_ok=True)
                    self.reload()
                    self.refresh_git_status()
                    self.post_message(FileCreated(str(new_path)))
                except Exception:
                    pass  # Silently fail if cannot create

        self.app.push_screen(
            InputDialog(
                title="New Folder",
                prompt=f"Create folder in: {parent.name}/",
                placeholder="foldername",
            ),
            on_submit,
        )

    async def action_delete(self) -> None:
        """Delete the selected file or folder."""
        from cliide.ui.dialogs import ConfirmDialog

        selected = self._get_selected_path()
        if not selected or selected == self._root_path:
            return  # Don't delete root

        is_dir = selected.is_dir()
        item_type = "folder" if is_dir else "file"

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                try:
                    if is_dir:
                        shutil.rmtree(selected)
                    else:
                        selected.unlink()
                    self.reload()
                    self.refresh_git_status()
                    self.post_message(FileDeleted(str(selected)))
                except Exception:
                    pass  # Silently fail if cannot delete

        self.app.push_screen(
            ConfirmDialog(
                title=f"Delete {item_type.title()}",
                message=f"Delete {item_type} '{selected.name}'?",
                confirm_label="Delete",
                danger=True,
            ),
            on_confirm,
        )

    async def action_rename(self) -> None:
        """Rename the selected file or folder."""
        from cliide.ui.dialogs import InputDialog

        selected = self._get_selected_path()
        if not selected or selected == self._root_path:
            return  # Don't rename root

        def on_submit(new_name: str) -> None:
            if new_name and new_name != selected.name:
                new_path = selected.parent / new_name
                try:
                    selected.rename(new_path)
                    self.reload()
                    self.refresh_git_status()
                    self.post_message(FileRenamed(str(selected), str(new_path)))
                except Exception:
                    pass  # Silently fail if cannot rename

        self.app.push_screen(
            InputDialog(
                title="Rename",
                prompt="New name:",
                placeholder=selected.name,
                initial_value=selected.name,
            ),
            on_submit,
        )
