"""Problems panel widget for displaying LSP diagnostics."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, Static

from cliide.core.events import FileOpened
from cliide.lsp.protocol import diagnostic_severity_to_string, uri_to_path


class ProblemsPanel(Widget):
    """Problems panel for displaying diagnostics."""

    DEFAULT_CSS = """
    ProblemsPanel {
        layout: vertical;
        height: 15;
        border-top: heavy $warning;
        background: $surface;
    }

    #problems-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $warning;
        padding: 0 1;
        color: $warning;
        text-style: bold;
    }

    #problems-table {
        height: 1fr;
        background: $surface;
    }

    #problems-table > .datatable--cursor {
        background: $boost;
        color: $warning;
        text-style: bold;
    }

    #problems-table > .datatable--header {
        background: $panel;
        color: $warning;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize problems panel.

        Args:
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.all_diagnostics: dict[str, list[Any]] = {}  # file_path -> diagnostics

    def compose(self) -> ComposeResult:
        """Compose the problems panel."""
        yield Static("🐛 Problems", id="problems-header")

        with VerticalScroll():
            table = DataTable(id="problems-table", cursor_type="row")
            table.add_columns("Severity", "File", "Line", "Message")
            yield table

    def on_mount(self) -> None:
        """Handle mount event."""
        # Set up table styling
        table = self.query_one("#problems-table", DataTable)
        table.zebra_stripes = True
        table.show_cursor = True

    def update_diagnostics(self, file_path: str, diagnostics: list[Any]) -> None:
        """Update diagnostics for a file.

        Args:
            file_path: File path
            diagnostics: List of LSP diagnostics
        """
        # Store diagnostics
        if diagnostics:
            self.all_diagnostics[file_path] = diagnostics
        else:
            # Remove if no diagnostics
            self.all_diagnostics.pop(file_path, None)

        # Rebuild table
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the diagnostics table."""
        table = self.query_one("#problems-table", DataTable)
        table.clear()

        # Count diagnostics
        total_count = sum(len(diags) for diags in self.all_diagnostics.values())

        # Update header
        header = self.query_one("#problems-header", Static)
        if total_count == 0:
            header.update("Problems (No issues)")
        else:
            # Count by severity
            errors = 0
            warnings = 0
            for diagnostics in self.all_diagnostics.values():
                for diag in diagnostics:
                    severity = diag.get("severity", 1)
                    if severity == 1:  # Error
                        errors += 1
                    elif severity == 2:  # Warning
                        warnings += 1

            header.update(f"Problems (❌ {errors} errors, ⚠️ {warnings} warnings)")

        # Add rows
        for file_path, diagnostics in sorted(self.all_diagnostics.items()):
            for diag in diagnostics:
                severity = diag.get("severity", 1)
                severity_str = diagnostic_severity_to_string(severity)

                # Get icon based on severity
                if severity == 1:  # Error
                    icon = "❌"
                elif severity == 2:  # Warning
                    icon = "⚠️"
                elif severity == 3:  # Info
                    icon = "ℹ️"
                else:  # Hint
                    icon = "💡"

                # Get location
                range_data = diag.get("range", {})
                start = range_data.get("start", {})
                line = start.get("line", 0) + 1  # Convert to 1-indexed

                # Get message (first line only)
                message = diag.get("message", "").split("\n")[0]

                # Add row with metadata
                table.add_row(
                    f"{icon} {severity_str}",
                    file_path,
                    str(line),
                    message,
                    key=f"{file_path}:{line}",
                )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection - jump to diagnostic location.

        Args:
            event: Row selected event
        """
        if not event.row_key:
            return

        # Parse key (format: "file_path:line")
        key_str = str(event.row_key.value)
        parts = key_str.rsplit(":", 1)

        if len(parts) == 2:
            file_path, line_str = parts
            try:
                line = int(line_str) - 1  # Convert back to 0-indexed

                # Get the app and editor
                app = self.app
                from cliide.ui.editor import EditorWidget

                async def open_and_jump() -> None:
                    """Open file and jump to line."""
                    editor = app.query_one(EditorWidget)

                    # Open file if different
                    if str(editor.current_file) != file_path:
                        await editor.open_file(file_path)

                    # Jump to line
                    editor.jump_to_line(line)

                # Run as worker
                app.run_worker(open_and_jump())

            except ValueError:
                pass
