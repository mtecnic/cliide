#!/usr/bin/env python3
"""Test chat panel standalone."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from cliide.ui.chat import ChatPanel
from cliide.core.events import AIRequestStarted


class TestChatApp(App):
    """Test app with just chat panel."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatPanel()
        yield Footer()

    async def on_ai_request_started(self, event: AIRequestStarted) -> None:
        """Handle AI request."""
        chat = self.query_one(ChatPanel)

        # Simulate AI response
        chat.start_ai_response()
        chat.append_ai_chunk("This is a test response to: ")
        chat.append_ai_chunk(event.prompt)
        chat.finish_ai_response()


if __name__ == "__main__":
    print("Testing chat panel...")
    print("Try typing a message and pressing Enter")
    print("Press Ctrl+Q to quit")
    app = TestChatApp()
    app.run()
