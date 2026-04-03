#!/usr/bin/env python3
"""Test if AIRequestStarted event is being received AT ALL."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container

from cliide.ui.chat import ChatPanel
from cliide.core.events import AIRequestStarted


class SyncTestApp(App):
    """Test app with simple sync handler."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Event count: 0", id="counter")
        with Container():
            yield ChatPanel()
        yield Footer()

    def on_ai_request_started(self, event: AIRequestStarted) -> None:
        """Simple SYNC handler to see if event is received."""
        # Update counter
        counter = self.query_one("#counter", Static)
        current = int(counter.renderable.split(": ")[1])
        counter.update(f"Event count: {current + 1}")

        # Show the message
        self.notify(f"Received: {event.prompt}")

        # Try to update chat immediately (no AI call)
        chat = self.query_one(ChatPanel)
        chat.start_ai_response()
        chat.append_ai_chunk(f"SYNC TEST: I got your message '{event.prompt}'")
        chat.finish_ai_response()


if __name__ == "__main__":
    print("Testing if AIRequestStarted events are received...")
    print("Type a message and press Enter")
    print("You should see:")
    print("  1. Event count increase")
    print("  2. A notification")
    print("  3. A response in chat")
    print()
    app = SyncTestApp()
    app.run()
