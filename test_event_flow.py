#!/usr/bin/env python3
"""Test event flow from chat to AI handler."""

import sys
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.containers import Container

from cliide.ui.chat import ChatPanel
from cliide.core.events import AIRequestStarted


class DebugApp(App):
    """Debug app to trace event flow."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield ChatPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount."""
        print("App mounted", file=sys.stderr)

    async def on_ai_request_started(self, event: AIRequestStarted) -> None:
        """Handle AI request - with logging."""
        print(f"[DEBUG] AI request received: {event.prompt}", file=sys.stderr)

        chat = self.query_one(ChatPanel)

        try:
            print("[DEBUG] Starting AI response", file=sys.stderr)
            chat.start_ai_response()

            # Simulate response
            print("[DEBUG] Appending chunks", file=sys.stderr)
            chat.append_ai_chunk("Debug response: ")
            chat.append_ai_chunk(f"I received your message: {event.prompt}")

            print("[DEBUG] Finishing response", file=sys.stderr)
            chat.finish_ai_response()

            print("[DEBUG] AI response complete", file=sys.stderr)

        except Exception as e:
            print(f"[DEBUG] Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            chat.add_error_message(str(e))


if __name__ == "__main__":
    print("Starting debug app...")
    print("Type a message in the chat and press Enter")
    print("Watch the terminal for debug messages")
    print("Press Ctrl+Q to quit")
    print()

    app = DebugApp()
    app.run()
