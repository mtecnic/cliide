"""Diff view widget for showing code changes."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static, TextArea


class DiffView(Widget):
    """Side-by-side diff view for code changes."""

    DEFAULT_CSS = """
    DiffView {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: $panel;
        border: round $primary;
        layer: overlay;
    }

    #diff-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $primary;
        padding: 0 1;
        color: $primary;
        text-style: bold;
    }

    #diff-content {
        height: 1fr;
        layout: horizontal;
    }

    #diff-before {
        width: 1fr;
        border: round $error;
        background: $surface;
        margin-right: 1;
    }

    #diff-after {
        width: 1fr;
        border: round $success;
        background: $surface;
    }

    #diff-buttons {
        dock: bottom;
        height: auto;
        align: center middle;
        background: $surface;
        border-top: heavy $accent;
    }

    #diff-buttons Button {
        margin: 0 1;
        border: round $primary;
    }

    DiffView TextArea {
        height: 1fr;
    }

    .diff-label {
        dock: top;
        height: 1;
        background: $boost;
        padding: 0 1;
        text-style: bold;
    }

    .diff-label-before {
        color: $error;
    }

    .diff-label-after {
        color: $success;
    }
    """

    class ChangesAccepted(Message):
        """Sent when user accepts the changes."""

        def __init__(self, new_code: str) -> None:
            """Initialize message.

            Args:
                new_code: The new code
            """
            super().__init__()
            self.new_code = new_code

    class ChangesRejected(Message):
        """Sent when user rejects the changes."""

        pass

    def __init__(self, original_code: str, new_code: str, **kwargs: Any) -> None:
        """Initialize diff view.

        Args:
            original_code: Original code
            new_code: Modified code
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.original_code = original_code
        self.new_code = new_code

    def compose(self) -> ComposeResult:
        """Compose the diff view."""
        yield Static(
            "🔄 AI Code Changes - Review and Apply",
            id="diff-header",
        )

        with Container(id="diff-content"):
            with Vertical(id="diff-before"):
                yield Static("❌ Before (Original)", classes="diff-label diff-label-before")
                before_editor = TextArea(
                    self.original_code,
                    read_only=True,
                    show_line_numbers=True,
                    id="diff-before-editor",
                )
                yield before_editor

            with Vertical(id="diff-after"):
                yield Static("✅ After (AI Suggested)", classes="diff-label diff-label-after")
                after_editor = TextArea(
                    self.new_code,
                    read_only=True,
                    show_line_numbers=True,
                    id="diff-after-editor",
                )
                yield after_editor

        with Horizontal(id="diff-buttons"):
            yield Button("Accept Changes", id="diff-accept", variant="success")
            yield Button("Reject", id="diff-reject", variant="error")

    def on_mount(self) -> None:
        """Handle mount event."""
        # Set same language for both editors if possible
        try:
            before = self.query_one("#diff-before-editor", TextArea)
            after = self.query_one("#diff-after-editor", TextArea)

            # Try to detect language from code
            if self.original_code.strip().startswith("def ") or "import " in self.original_code:
                before.language = "python"
                after.language = "python"
            elif self.original_code.strip().startswith("function ") or "const " in self.original_code:
                before.language = "javascript"
                after.language = "javascript"
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button pressed event
        """
        if event.button.id == "diff-accept":
            self.post_message(self.ChangesAccepted(self.new_code))
            self.remove()

        elif event.button.id == "diff-reject":
            self.post_message(self.ChangesRejected())
            self.remove()

    def on_key(self, event: Any) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        # Close on Escape
        if event.key == "escape":
            self.post_message(self.ChangesRejected())
            self.remove()
            event.stop()
