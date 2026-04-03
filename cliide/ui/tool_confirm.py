"""Tool confirmation dialog for user approval."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label
from textual.binding import Binding

from cliide.core.events import ToolConfirmationResult


class ToolConfirmationDialog(ModalScreen):
    """Modal dialog for tool confirmation."""

    BINDINGS = [
        Binding("y", "approve", "Approve", show=True),
        Binding("n", "deny", "Deny", show=True),
        Binding("a", "auto_session", "Auto-approve session", show=True),
        Binding("escape", "deny", "Cancel", show=False),
    ]

    CSS = """
    ToolConfirmationDialog {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        border: round $warning;
        background: $surface;
        padding: 1 2;
        margin: 1 2;
    }

    #title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    #tool_name {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #args_container {
        border: solid $primary;
        background: $panel;
        padding: 1;
        margin-bottom: 1;
        max-height: 15;
        overflow-y: auto;
    }

    #warning {
        color: $warning;
        text-style: italic;
        margin-bottom: 1;
    }

    #buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
    }

    .approve {
        background: $success;
    }

    .deny {
        background: $error;
    }

    .auto {
        background: $primary;
    }
    """

    def __init__(self, tool_name: str, args: dict, description: str | None = None):
        """Initialize confirmation dialog.

        Args:
            tool_name: Name of the tool requiring confirmation
            args: Arguments passed to the tool
            description: Optional description of what the tool does
        """
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self.description = description or f"Execute {tool_name}"
        self.result_posted = False

    def compose(self) -> ComposeResult:
        """Compose the dialog UI."""
        with Container(id="dialog"):
            yield Static("🔒 Tool Confirmation Required", id="title")
            yield Static(f"Tool: {self.tool_name}", id="tool_name")

            if self.description:
                yield Static(self.description)

            # Show arguments
            yield Static("Arguments:", classes="section_title")
            with Vertical(id="args_container"):
                for key, value in self.args.items():
                    # Format value - truncate if too long
                    value_str = str(value)
                    if len(value_str) > 200:
                        value_str = value_str[:200] + "..."

                    # Replace newlines for display
                    value_str = value_str.replace("\n", "\\n")

                    yield Static(f"{key}: {value_str}")

            # Warning
            yield Static(
                "⚠️  This tool will make changes to your system. Please review carefully.",
                id="warning"
            )

            # Buttons
            with Horizontal(id="buttons"):
                yield Button("Approve (Y)", variant="success", classes="approve", id="approve")
                yield Button("Auto (A)", variant="primary", classes="auto", id="auto")
                yield Button("Deny (N)", variant="error", classes="deny", id="deny")

    def action_approve(self) -> None:
        """Approve the tool execution."""
        if not self.result_posted:
            self.result_posted = True
            self.post_message(ToolConfirmationResult(approved=True, tool_name=self.tool_name))
            self.dismiss(True)

    def action_deny(self) -> None:
        """Deny the tool execution."""
        if not self.result_posted:
            self.result_posted = True
            self.post_message(ToolConfirmationResult(approved=False, tool_name=self.tool_name))
            self.dismiss(False)

    def action_auto_session(self) -> None:
        """Approve and enable auto-approve for rest of session."""
        if not self.result_posted:
            self.result_posted = True
            self.post_message(ToolConfirmationResult(approved=True, tool_name=self.tool_name, auto_session=True))
            self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "approve":
            self.action_approve()
        elif event.button.id == "auto":
            self.action_auto_session()
        elif event.button.id == "deny":
            self.action_deny()
