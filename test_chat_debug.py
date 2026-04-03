#!/usr/bin/env python3
"""Debug chat input issues."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, Static

class DebugChatApp(App):
    """Simple app to test chat input."""

    def compose(self) -> ComposeResult:
        yield Static("Type in the input and press Enter:")
        yield Input(placeholder="Test input...", id="test-input")
        yield Static("Output will appear here:", id="output")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input."""
        output = self.query_one("#output", Static)
        output.update(f"Received: {event.value}")

        # Clear input
        event.input.value = ""

if __name__ == "__main__":
    app = DebugChatApp()
    app.run()
