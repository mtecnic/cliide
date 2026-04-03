"""Loading screen for app startup."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Label, ProgressBar, Static


class LoadingScreen(Screen):
    """Loading screen displayed during app initialization."""

    DEFAULT_CSS = """
    LoadingScreen {
        align: center middle;
        background: $background;
    }

    #loading-container {
        width: 70;
        height: auto;
        background: $panel;
        border: round $primary;
        padding: 2;
    }

    #loading-title {
        text-align: center;
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    #loading-subtitle {
        text-align: center;
        color: $accent;
        margin-bottom: 2;
    }

    #loading-progress {
        width: 100%;
        margin-bottom: 1;
    }

    #loading-status {
        text-align: center;
        color: $text 80%;
        height: 1;
    }

    #loading-details {
        text-align: center;
        color: $text 60%;
        height: 3;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the loading screen."""
        with Container(id="loading-container"):
            yield Static("╔══════════════════════════╗\n"
                        "║      C L I I D E      ║\n"
                        "╚══════════════════════════╝",
                        id="loading-title")
            yield Static("AI-First CLI IDE", id="loading-subtitle")
            yield ProgressBar(id="loading-progress", total=100, show_eta=False)
            yield Static("Initializing...", id="loading-status")
            yield Static("", id="loading-details")

    def update_progress(self, percent: int, status: str, details: str = "") -> None:
        """Update the loading progress.

        Args:
            percent: Progress percentage (0-100)
            status: Main status message
            details: Additional details (optional)
        """
        progress_bar = self.query_one("#loading-progress", ProgressBar)
        status_label = self.query_one("#loading-status", Static)
        details_label = self.query_one("#loading-details", Static)

        progress_bar.update(progress=percent)
        status_label.update(status)
        details_label.update(details)
