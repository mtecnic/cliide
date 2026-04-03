"""File tree widget for browsing project files."""

from pathlib import Path

from textual.widgets import DirectoryTree

from cliide.core.events import FileOpened


class FileTree(DirectoryTree):
    """File tree widget for project navigation."""

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
    """

    def __init__(self, path: str, **kwargs: dict) -> None:
        """Initialize file tree.

        Args:
            path: Root directory path
            **kwargs: Additional arguments for DirectoryTree
        """
        # Disable auto-watching to avoid async warnings
        super().__init__(path, **kwargs)
        self.auto_expand = False

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
