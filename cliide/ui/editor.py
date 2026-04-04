"""Text editor widget."""

import difflib
from pathlib import Path
from typing import Any, Optional

import aiofiles
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import TextArea

from cliide.core.events import FileSaved


class EditorWidget(TextArea):
    """Text editor widget with file handling and inline diff support."""

    # Messages for diff accept/reject
    class DiffAccepted(Message):
        """Sent when user accepts inline diff changes."""
        def __init__(self, new_code: str) -> None:
            super().__init__()
            self.new_code = new_code

    class DiffRejected(Message):
        """Sent when user rejects inline diff changes."""
        pass

    DEFAULT_CSS = """
    EditorWidget {
        background: $background;
        border: round $primary;
    }

    EditorWidget:focus {
        border: round $accent;
    }

    EditorWidget > .text-area--cursor-line {
        background: $boost;
    }

    EditorWidget > .text-area--selection {
        background: $primary 30%;
    }

    EditorWidget.-diff-mode {
        border: round $warning;
    }
    """

    # Reactive property for diff mode
    diff_mode: reactive[bool] = reactive(False)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize editor widget.

        Args:
            **kwargs: Additional arguments for TextArea
        """
        super().__init__(
            theme="monokai",
            show_line_numbers=True,
            **kwargs,
        )
        self.current_file: Path | None = None
        self.is_modified = False
        self.lsp_manager: Optional[Any] = None  # Set by app
        self.document_version: int = 0
        self.diagnostics: dict[str, list[Any]] = {}  # file_path -> diagnostics

        # Diff mode state
        self._diff_original: str | None = None
        self._diff_new: str | None = None
        self._diff_lines: dict[int, str] = {}  # line -> 'added'|'removed'|'changed'

    def show_diff(self, original: str, new_code: str) -> None:
        """Show proposed changes inline with diff highlighting.

        Args:
            original: Original code content
            new_code: Proposed new code
        """
        self._diff_original = original
        self._diff_new = new_code
        self.diff_mode = True

        # Calculate line-level diff
        self._calculate_diff_lines(original, new_code)

        # Show new code in editor (read-only during diff)
        self.text = new_code
        self.read_only = True
        self.add_class("-diff-mode")

    def _calculate_diff_lines(self, original: str, new_code: str) -> None:
        """Calculate which lines are added/changed.

        Args:
            original: Original code
            new_code: New code
        """
        self._diff_lines = {}
        original_lines = original.splitlines()
        new_lines = new_code.splitlines()

        # Use difflib to find changes
        matcher = difflib.SequenceMatcher(None, original_lines, new_lines)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                # New lines added
                for line_num in range(j1, j2):
                    self._diff_lines[line_num] = 'added'
            elif tag == 'replace':
                # Lines changed
                for line_num in range(j1, j2):
                    self._diff_lines[line_num] = 'changed'
            # 'equal' and 'delete' don't mark new lines

    def accept_diff(self) -> None:
        """Accept the proposed changes."""
        if self.diff_mode and self._diff_new:
            new_code = self._diff_new
            self._clear_diff_state()
            self.read_only = False
            self.is_modified = True
            self.post_message(self.DiffAccepted(new_code))

    def reject_diff(self) -> None:
        """Reject the proposed changes and restore original."""
        if self.diff_mode and self._diff_original is not None:
            original = self._diff_original
            self._clear_diff_state()
            self.text = original
            self.read_only = False
            self.post_message(self.DiffRejected())

    def _clear_diff_state(self) -> None:
        """Clear diff mode state."""
        self._diff_original = None
        self._diff_new = None
        self._diff_lines = {}
        self.diff_mode = False
        self.remove_class("-diff-mode")

    def get_diff_line_status(self, line: int) -> str | None:
        """Get diff status for a line.

        Args:
            line: Line number (0-indexed)

        Returns:
            'added', 'changed', or None
        """
        return self._diff_lines.get(line)

    def on_key(self, event) -> None:
        """Handle key events - Y/N for diff mode accept/reject.

        Args:
            event: Key event
        """
        if self.diff_mode:
            if event.key == "y":
                self.accept_diff()
                event.stop()
            elif event.key == "n":
                self.reject_diff()
                event.stop()
            elif event.key == "escape":
                self.reject_diff()
                event.stop()

    async def open_file(self, file_path: str) -> None:
        """Open a file in the editor.

        Args:
            file_path: Path to file to open
        """
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            self.text = f"Error: Cannot open {file_path}"
            return

        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()

            self.text = content
            self.current_file = path
            self.is_modified = False
            self.document_version = 1

            # Set language based on file extension
            self._set_language_from_file(path)

            # Notify LSP that file was opened
            if self.lsp_manager:
                await self.lsp_manager.did_open(str(path), content)

        except Exception as e:
            self.text = f"Error opening file: {e}"

    def save_current_file(self) -> None:
        """Save the current file."""
        if self.current_file:
            self.save_file(str(self.current_file))

    async def save_file(self, file_path: str | None = None) -> None:
        """Save content to a file.

        Args:
            file_path: Path to save to (uses current_file if None)
        """
        path = Path(file_path) if file_path else self.current_file

        if not path:
            return

        try:
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(self.text)

            self.is_modified = False
            self.post_message(FileSaved(str(path)))

            # Notify LSP that file was saved
            if self.lsp_manager:
                await self.lsp_manager.did_save(str(path))

        except Exception as e:
            self.text = f"Error saving file: {e}"

    def get_selected_text(self) -> str:
        """Get currently selected text.

        Returns:
            Selected text or empty string
        """
        if self.selection:
            start, end = self.selection
            lines = self.text.split("\n")

            # Handle single line selection
            if start[0] == end[0]:
                line = lines[start[0]]
                return line[start[1] : end[1]]

            # Handle multi-line selection
            selected_lines = []
            for i in range(start[0], end[0] + 1):
                if i < len(lines):
                    line = lines[i]
                    if i == start[0]:
                        selected_lines.append(line[start[1] :])
                    elif i == end[0]:
                        selected_lines.append(line[: end[1]])
                    else:
                        selected_lines.append(line)

            return "\n".join(selected_lines)

        return ""

    def _set_language_from_file(self, path: Path) -> None:
        """Set editor language based on file extension.

        Args:
            path: File path
        """
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".css": "css",
            ".html": "html",
            ".xml": "xml",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
        }

        suffix = path.suffix.lower()
        language = extension_map.get(suffix)

        # Try to set language, fall back to None (plain text) if not available
        try:
            self.language = language
        except Exception:
            # Language not available, use plain text
            self.language = None

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle text changes.

        Args:
            event: Change event
        """
        if self.current_file:
            self.is_modified = True

            # Notify LSP of change
            if self.lsp_manager:
                self.document_version += 1
                self.run_worker(
                    self.lsp_manager.did_change(
                        str(self.current_file), self.document_version, self.text
                    )
                )

    def get_cursor_position(self) -> tuple[int, int]:
        """Get current cursor position.

        Returns:
            (line, character) tuple (0-indexed)
        """
        if self.cursor_location:
            return self.cursor_location
        return (0, 0)

    def set_diagnostics(self, file_path: str, diagnostics: list[Any]) -> None:
        """Store diagnostics for a file.

        Args:
            file_path: File path
            diagnostics: List of LSP diagnostics
        """
        self.diagnostics[file_path] = diagnostics

        # If this is the current file, apply inline highlights
        if self.current_file and str(self.current_file) == file_path:
            self._apply_diagnostic_highlights(diagnostics)
            self.refresh()

    def _apply_diagnostic_highlights(self, diagnostics: list[Any]) -> None:
        """Apply visual highlights for diagnostics.

        Args:
            diagnostics: List of LSP diagnostics
        """
        # Store diagnostic lines for rendering
        self._diagnostic_lines: dict[int, list[dict]] = {}

        for diag in diagnostics:
            range_data = diag.get("range", {})
            start = range_data.get("start", {})
            line = start.get("line", 0)
            severity = diag.get("severity", 1)  # 1=Error, 2=Warning, 3=Info, 4=Hint
            message = diag.get("message", "")

            if line not in self._diagnostic_lines:
                self._diagnostic_lines[line] = []

            self._diagnostic_lines[line].append({
                "severity": severity,
                "message": message,
                "start_char": start.get("character", 0),
                "end_char": range_data.get("end", {}).get("character", 0),
            })

        # Note: Textual's TextArea doesn't have a direct API for inline highlighting.
        # The diagnostics are stored and can be shown via:
        # 1. Problems panel (already implemented)
        # 2. Hover tooltips (would need custom implementation)
        # 3. Gutter icons (would need custom widget)

        # For now, we store them for potential use in status bar or tooltips
        self.refresh()

    def get_diagnostics_at_line(self, line: int) -> list[dict]:
        """Get diagnostics at a specific line.

        Args:
            line: Line number (0-indexed)

        Returns:
            List of diagnostics at that line
        """
        if hasattr(self, '_diagnostic_lines'):
            return self._diagnostic_lines.get(line, [])
        return []

    def get_diagnostic_summary(self) -> dict[str, int]:
        """Get summary of diagnostics.

        Returns:
            Dict with error/warning/info/hint counts
        """
        counts = {"error": 0, "warning": 0, "info": 0, "hint": 0}

        if hasattr(self, '_diagnostic_lines'):
            for diags in self._diagnostic_lines.values():
                for d in diags:
                    severity = d.get("severity", 1)
                    if severity == 1:
                        counts["error"] += 1
                    elif severity == 2:
                        counts["warning"] += 1
                    elif severity == 3:
                        counts["info"] += 1
                    elif severity == 4:
                        counts["hint"] += 1

        return counts

    def close_file(self) -> None:
        """Close the current file."""
        self.current_file = None
        self.text = ""
        self.is_modified = False
        self._diagnostic_lines = {}

    def get_diagnostics_for_current_file(self) -> list[Any]:
        """Get diagnostics for the currently open file.

        Returns:
            List of diagnostics
        """
        if self.current_file:
            return self.diagnostics.get(str(self.current_file), [])
        return []

    def insert_text_at_cursor(self, text: str) -> None:
        """Insert text at the current cursor position.

        Args:
            text: Text to insert
        """
        cursor = self.cursor_location
        # Insert by replacing a zero-width range
        self.replace(text, cursor, cursor)

    def replace_text_range(
        self, start: tuple[int, int], end: tuple[int, int], text: str
    ) -> None:
        """Replace text in a range with new text.

        Args:
            start: Start position (line, column)
            end: End position (line, column)
            text: Replacement text
        """
        self.replace(text, start, end)

    def get_word_at_cursor(self) -> str:
        """Get the word under the cursor.

        Returns:
            Word at cursor or empty string
        """
        cursor = self.cursor_location

        # Get word boundaries
        word_start = self.get_cursor_word_left_location()
        word_end = self.get_cursor_word_right_location()

        if word_start == word_end:
            return ""

        # Extract text between boundaries
        return self.get_text_in_range(word_start, word_end)

    def jump_to_line(self, line: int, column: int = 0) -> None:
        """Jump to a specific line and column.

        Args:
            line: Line number (0-indexed)
            column: Column number (0-indexed)
        """
        # Set cursor location
        self.cursor_location = (line, column)

        # Scroll to make the line visible (center it if possible)
        self.scroll_to_center(line)

    def select_range(
        self, start_line: int, start_col: int, end_line: int, end_col: int
    ) -> None:
        """Select text in a range.

        Args:
            start_line: Start line (0-indexed)
            start_col: Start column (0-indexed)
            end_line: End line (0-indexed)
            end_col: End column (0-indexed)
        """
        from textual.widgets.text_area import Selection

        self.selection = Selection(
            start=(start_line, start_col),
            end=(end_line, end_col),
        )

    def get_line_content(self, line: int) -> str:
        """Get the content of a specific line.

        Args:
            line: Line number (0-indexed)

        Returns:
            Line content or empty string if line doesn't exist
        """
        try:
            return self.get_line(line)
        except IndexError:
            return ""

    def get_text_in_range(self, start: tuple[int, int], end: tuple[int, int]) -> str:
        """Get text between two positions.

        Args:
            start: Start position (line, column)
            end: End position (line, column)

        Returns:
            Text in range
        """
        start_line, start_col = start
        end_line, end_col = end

        lines = self.text.split("\n")

        # Single line case
        if start_line == end_line:
            if start_line < len(lines):
                return lines[start_line][start_col:end_col]
            return ""

        # Multi-line case
        result = []

        for line_num in range(start_line, end_line + 1):
            if line_num >= len(lines):
                break

            line = lines[line_num]

            if line_num == start_line:
                result.append(line[start_col:])
            elif line_num == end_line:
                result.append(line[:end_col])
            else:
                result.append(line)

        return "\n".join(result)

    def scroll_to_center(self, line: int) -> None:
        """Scroll to center a line in the viewport.

        Args:
            line: Line number (0-indexed)
        """
        # TextArea doesn't have a direct "scroll to line" method,
        # but we can try to scroll by setting cursor location
        # which should trigger auto-scrolling
        # This is a best-effort implementation
        pass  # cursor_location setter should handle scrolling
