"""Action buttons for file tree operations."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button


class FileTreeAction(Message):
    """Message sent when a file tree action button is clicked."""

    def __init__(self, action: str) -> None:
        super().__init__()
        self.action = action


class FileTreeActions(Horizontal):
    """Action button bar for file tree operations."""

    DEFAULT_CSS = """
    FileTreeActions {
        height: 3;
        padding: 0;
        background: $surface;
        align: left middle;
    }

    FileTreeActions Button {
        min-width: 5;
        width: auto;
        height: 3;
        margin: 0;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        # Short labels that fit
        yield Button("+F", id="btn-new", variant="primary")
        yield Button("+D", id="btn-folder", variant="success")
        yield Button("X", id="btn-delete", variant="error")
        yield Button("Rn", id="btn-rename", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses and emit action messages."""
        event.stop()
        action_map = {
            "btn-new": "new_file",
            "btn-folder": "new_folder",
            "btn-delete": "delete",
            "btn-rename": "rename",
        }
        action = action_map.get(event.button.id)
        if action:
            self.post_message(FileTreeAction(action))
