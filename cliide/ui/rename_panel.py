"""Rename panel widget for symbol renaming with preview."""

from pathlib import Path
from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Checkbox, DataTable, Input, Static

from cliide.lsp.protocol import uri_to_path


class RenamePanel(Widget):
    """Rename panel with preview for symbol renaming."""

    DEFAULT_CSS = """
    RenamePanel {
        layout: vertical;
        width: 85;
        height: auto;
        max-height: 35;
        background: $panel;
        border: round $primary;
        layer: overlay;
        offset: 2 2;
    }

    #rename-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $primary;
        padding: 0 1;
        color: $primary;
        text-style: bold;
    }

    #rename-input-container {
        height: auto;
        padding: 1;
        background: $surface;
    }

    #rename-new-name {
        width: 1fr;
        border: round $accent;
        background: $background;
    }

    #rename-preview {
        height: 1fr;
        min-height: 12;
        background: $surface;
    }

    #rename-preview > .datatable--cursor {
        background: $boost;
        color: $primary;
        text-style: bold;
    }

    #rename-preview > .datatable--header {
        background: $panel;
        color: $accent;
        text-style: bold;
    }

    #rename-buttons {
        height: auto;
        align: center middle;
        background: $surface;
        border-top: heavy $accent;
    }

    #rename-buttons Button {
        margin: 0 1;
        border: round $primary;
    }
    """

    class RenameApplied(Message):
        """Sent when rename is applied."""

        def __init__(self, workspace_edit: dict[str, Any]) -> None:
            """Initialize message.

            Args:
                workspace_edit: WorkspaceEdit to apply
            """
            super().__init__()
            self.workspace_edit = workspace_edit

    def __init__(
        self,
        old_name: str,
        workspace_edit: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize rename panel.

        Args:
            old_name: Current symbol name
            workspace_edit: Optional WorkspaceEdit from LSP
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.old_name = old_name
        self.workspace_edit = workspace_edit
        self.file_checkboxes: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        """Compose the rename panel."""
        yield Static(
            f"✏️ Rename '{self.old_name}':",
            id="rename-header",
        )

        with Container(id="rename-input-container"):
            yield Input(
                value=self.old_name,
                placeholder="New name",
                id="rename-new-name",
            )

        if self.workspace_edit:
            with VerticalScroll(id="rename-preview"):
                yield Static("Preview changes:")
                table = DataTable(id="rename-preview-table", cursor_type="none")
                table.add_columns("Apply", "File", "Location", "Change")
                yield table

        with Horizontal(id="rename-buttons"):
            yield Button("Apply", id="rename-apply", variant="success")
            yield Button("Cancel", id="rename-cancel", variant="error")

    def on_mount(self) -> None:
        """Handle mount event."""
        # Focus the input
        input_widget = self.query_one("#rename-new-name", Input)
        input_widget.focus()
        input_widget.select_all()

        # Populate preview if available
        if self.workspace_edit:
            self._populate_preview()

    def _populate_preview(self) -> None:
        """Populate the preview table with changes."""
        if not self.workspace_edit:
            return

        table = self.query_one("#rename-preview-table", DataTable)

        # Get document changes
        changes = self.workspace_edit.get("changes", {})

        for uri, edits in changes.items():
            file_path = uri_to_path(uri)
            file_name = Path(file_path).name

            # Default to selected
            self.file_checkboxes[file_path] = True

            for edit in edits:
                range_data = edit.get("range", {})
                start = range_data.get("start", {})
                line = start.get("line", 0) + 1  # 1-indexed

                new_text = edit.get("newText", "")

                # Add row with checkbox indicator
                table.add_row(
                    "☑",  # Checked by default
                    file_name,
                    f"Line {line}",
                    f"→ {new_text}",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button pressed event
        """
        if event.button.id == "rename-apply":
            # Get new name
            input_widget = self.query_one("#rename-new-name", Input)
            new_name = input_widget.value.strip()

            if new_name and new_name != self.old_name:
                # Post message with new name (app will handle LSP request)
                self.post_message(self.RenameApplied({"old_name": self.old_name, "new_name": new_name}))

            self.remove()

        elif event.button.id == "rename-cancel":
            self.remove()

    def on_key(self, event: Any) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        # Close on Escape
        if event.key == "escape":
            self.remove()
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key).

        Args:
            event: Input submitted event
        """
        # Trigger apply button
        apply_button = self.query_one("#rename-apply", Button)
        apply_button.press()
