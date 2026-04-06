"""Status bar widget."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from cliide.core.agent_mode import AgentMode


class StatusBar(Widget):
    """Status bar showing file info and application state."""

    class SettingsClicked(Message):
        """Sent when the settings/connection indicator is clicked."""
        pass

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: #007acc;
        layout: horizontal;
    }

    #status-left {
        width: 1fr;
        padding: 0 1;
        background: #007acc;
        color: #ffffff;
        content-align: left middle;
    }

    #status-center {
        width: auto;
        padding: 0 1;
        background: #007acc;
        color: #ffffff;
        content-align: center middle;
    }

    #status-right {
        width: auto;
        padding: 0 1;
        background: #007acc;
        color: #ffffff;
        content-align: right middle;
    }

    #status-right:hover {
        background: #005a9e;
        text-style: bold;
    }

    .status-modified {
        color: #ffae57;
    }

    .status-error {
        color: #ff6b6b;
    }

    .status-connected {
        color: #73d0ff;
    }

    .status-disconnected {
        color: #ff6b6b;
    }

    .status-checking {
        color: #ffae57;
    }

    #status-mode {
        width: auto;
        padding: 0 2;
        content-align: center middle;
        text-style: bold;
        background: #005a9e;
        color: #ffffff;
    }

    #status-mode.mode-plan {
        background: #ff8c00;
        color: #000000;
    }

    #status-mode.mode-act {
        background: #16825d;
        color: #ffffff;
    }
    """

    def __init__(self, **kwargs: dict) -> None:
        """Initialize status bar.

        Args:
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.current_file = ""
        self.cursor_pos = (0, 0)
        self.file_modified = False
        self.ai_status = "Ready"
        self.connection_status = "checking"  # checking, connected, disconnected
        self.agent_mode = AgentMode.ACT  # Default to ACT mode

    def compose(self) -> ComposeResult:
        """Compose the status bar."""
        yield Static("📄 No file open", id="status-left")
        yield Static("📍 Line 0, Col 0", id="status-center")
        yield Static("ACT (F9)", id="status-mode", classes="mode-act")
        yield Static("🟡 Checking... (click to configure)", id="status-right")

    def update_file_info(self, file_path: str | None = None) -> None:
        """Update file information.

        Args:
            file_path: Current file path
        """
        if file_path:
            self.current_file = file_path
            file_name = Path(file_path).name
            modified = " [modified]" if self.file_modified else ""
            self.query_one("#status-left").update(f"📄 {file_name}{modified}")
        else:
            self.current_file = ""
            self.query_one("#status-left").update("No file open")

    def update_cursor_position(self, line: int, col: int) -> None:
        """Update cursor position.

        Args:
            line: Line number
            col: Column number
        """
        self.cursor_pos = (line, col)
        self.query_one("#status-center").update(f"📍 Line {line}, Col {col}")

    def update_ai_status(self, status: str) -> None:
        """Update AI status.

        Args:
            status: AI status text
        """
        self.ai_status = status
        status_widget = self.query_one("#status-right", Static)

        # Determine connection state from status
        if status.lower() in ["connected", "ready"]:
            self.connection_status = "connected"
            from cliide.core.config import get_config
            model = get_config().vllm.model
            status_widget.update(f"🟢 {model} (click to configure)")
            status_widget.remove_class("status-disconnected", "status-checking")
            status_widget.add_class("status-connected")
        elif status.lower() in ["disconnected", "error"]:
            self.connection_status = "disconnected"
            status_widget.update("🔴 Disconnected (click to configure)")
            status_widget.remove_class("status-connected", "status-checking")
            status_widget.add_class("status-disconnected")
        elif "processing" in status.lower() or "thinking" in status.lower():
            # Keep connection status, just show activity
            emoji = "⚡"
            status_widget.update(f"{emoji} {status}")
        else:
            # Other statuses, keep checking state
            self.connection_status = "checking"
            status_widget.update(f"🟡 {status}")
            status_widget.remove_class("status-connected", "status-disconnected")
            status_widget.add_class("status-checking")

    def update_connection_status(self, connected: bool) -> None:
        """Update connection status indicator.

        Args:
            connected: Whether VLLM is connected
        """
        if connected:
            self.update_ai_status("Connected")
        else:
            self.update_ai_status("Disconnected")

    def set_file_modified(self, modified: bool) -> None:
        """Set file modified state.

        Args:
            modified: Whether file is modified
        """
        self.file_modified = modified
        self.update_file_info(self.current_file if self.current_file else None)

    def update_agent_mode(self, mode: AgentMode) -> None:
        """Update the agent mode indicator.

        Args:
            mode: Current agent mode
        """
        self.agent_mode = mode
        mode_widget = self.query_one("#status-mode", Static)

        if mode == AgentMode.PLAN:
            mode_widget.update("PLAN (F9)")
            mode_widget.remove_class("mode-act")
            mode_widget.add_class("mode-plan")
        else:
            mode_widget.update("ACT (F9)")
            mode_widget.remove_class("mode-plan")
            mode_widget.add_class("mode-act")

    def on_click(self, event) -> None:
        """Handle click events on the status bar.

        Args:
            event: Click event
        """
        # Check if click was on the status-right widget
        if hasattr(event, 'widget') and event.widget.id == "status-right":
            self.post_message(self.SettingsClicked())
            event.stop()
