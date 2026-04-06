"""Plan/Act mode indicator widget."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cliide.core.agent_mode import AgentMode


class ModeIndicator(Widget):
    """Visual indicator for Plan/Act agent mode."""

    DEFAULT_CSS = """
    ModeIndicator {
        height: 1;
        width: 100%;
        background: #1a1a2e;
    }

    #mode-label {
        width: 100%;
        text-align: center;
        text-style: bold;
        padding: 0 1;
    }

    #mode-label.mode-act {
        background: #4ecdc4;
        color: #000000;
    }

    #mode-label.mode-plan {
        background: #ffae57;
        color: #000000;
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the mode indicator."""
        super().__init__(**kwargs)
        self._mode = AgentMode.ACT

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        yield Static("⚡ ACT MODE", id="mode-label", classes="mode-act")

    def update_mode(self, mode: AgentMode) -> None:
        """Update the displayed mode.

        Args:
            mode: The current agent mode
        """
        self._mode = mode
        label = self.query_one("#mode-label", Static)

        if mode == AgentMode.PLAN:
            label.update("📋 PLAN MODE")
            label.remove_class("mode-act")
            label.add_class("mode-plan")
        else:
            label.update("⚡ ACT MODE")
            label.remove_class("mode-plan")
            label.add_class("mode-act")
