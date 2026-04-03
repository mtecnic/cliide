#!/usr/bin/env python3
"""Test if custom events work at all."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static
from textual.message import Message


class TestEvent(Message):
    """Test event."""

    def __init__(self, data: str) -> None:
        super().__init__()
        self.data = data


class TestApp(App):
    """Test if events work."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Event count: 0", id="counter")
        yield Button("Click Me", id="test-button")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        # Post custom event
        print(f"Button pressed, posting event")
        self.post_message(TestEvent("test data"))

    def on_test_event(self, event: TestEvent) -> None:
        """Handle custom event."""
        print(f"Event received: {event.data}")
        counter = self.query_one("#counter", Static)
        current = int(counter.renderable.split(": ")[1])
        counter.update(f"Event count: {current + 1}")
        self.notify(f"Got event with: {event.data}")


if __name__ == "__main__":
    print("Testing custom events...")
    print("Click the button and see if event count increases")
    app = TestApp()
    app.run()
