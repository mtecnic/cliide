"""References panel widget for displaying symbol references."""

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, Static

from cliide.core.events import FileOpened
from cliide.lsp.protocol import uri_to_path


class ReferencesPanel(Widget):
    """References panel for displaying symbol references."""

    DEFAULT_CSS = """
    ReferencesPanel {
        layout: vertical;
        width: 55;
        height: 100%;
        border-left: round $primary;
        background: $surface;
    }

    #references-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $primary;
        padding: 0 1;
        color: $primary;
        text-style: bold;
    }

    #references-table {
        height: 1fr;
        background: $surface;
    }

    #references-table > .datatable--cursor {
        background: $boost;
        color: $primary;
        text-style: bold;
    }

    #references-table > .datatable--header {
        background: $panel;
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, symbol_name: str, references: list[Any], **kwargs: Any) -> None:
        """Initialize references panel.

        Args:
            symbol_name: Name of the symbol
            references: List of reference locations
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.symbol_name = symbol_name
        self.references = references

    def compose(self) -> ComposeResult:
        """Compose the references panel."""
        count = len(self.references)
        yield Static(
            f"🔗 '{self.symbol_name}' ({count} results)",
            id="references-header",
        )

        with VerticalScroll():
            table = DataTable(id="references-table", cursor_type="row")
            table.add_columns("File", "Line", "Preview")
            yield table

    def on_mount(self) -> None:
        """Handle mount event."""
        table = self.query_one("#references-table", DataTable)
        table.zebra_stripes = True
        table.show_cursor = True

        # Group references by file
        refs_by_file: dict[str, list[Any]] = {}

        for ref in self.references:
            uri = ref.get("uri", "")
            file_path = uri_to_path(uri)

            if file_path not in refs_by_file:
                refs_by_file[file_path] = []

            refs_by_file[file_path].append(ref)

        # Add rows
        for file_path, refs in sorted(refs_by_file.items()):
            # Add file header (could be styled differently)
            file_name = Path(file_path).name

            for ref in refs:
                range_data = ref.get("range", {})
                start = range_data.get("start", {})
                line = start.get("line", 0) + 1  # Convert to 1-indexed

                # TODO: Get preview of the line from file
                # For now, just show the location
                preview = f"Line {line}"

                # Add row
                table.add_row(
                    file_name,
                    str(line),
                    preview,
                    key=f"{file_path}:{line}",
                )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection - jump to reference location.

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

    def on_key(self, event: Any) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        # Close on Escape or Shift+F12
        if event.key == "escape" or (event.key == "f12" and event.shift):
            self.remove()
            event.stop()
