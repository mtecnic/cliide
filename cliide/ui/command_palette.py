"""Command palette widget."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListItem, ListView, Static

from cliide.core.events import CommandExecuted


class CommandPalette(ModalScreen[str]):
    """Command palette modal for executing commands."""

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
    }

    #palette-container {
        width: 80;
        height: auto;
        max-height: 25;
        background: $panel;
        border: round $primary;
    }

    #palette-header {
        dock: top;
        height: auto;
        background: $boost;
        border-bottom: heavy $primary;
    }

    #palette-input {
        width: 1fr;
        border: round $accent;
        background: $surface;
    }

    #palette-close {
        width: auto;
        min-width: 10;
        margin-left: 1;
    }

    #palette-list {
        height: auto;
        max-height: 18;
        background: $surface;
    }

    #palette-list > ListItem {
        padding: 0 1;
        border-left: heavy transparent;
    }

    #palette-list > ListItem:hover {
        background: $boost;
        border-left: heavy $accent;
        color: $accent;
    }

    #palette-list > .list-item--highlighted {
        background: $boost;
        border-left: heavy $primary;
        color: $primary;
        text-style: bold;
    }
    """

    COMMANDS = [
        ("📂 Open File", "open_file", "Open a file from the project"),
        ("💾 Save File", "save_file", "Save the current file"),
        ("❌ Close File", "close_file", "Close the current file"),
        ("📁 Switch Project", "switch_project", "Open a different project folder"),
        ("💬 New Chat", "new_chat", "Start a new chat conversation"),
        ("💡 Explain Code", "explain_code", "Explain selected code with AI"),
        ("🔧 Refactor Code", "refactor_code", "Get AI suggestions for refactoring"),
        ("🐛 Fix Issues", "fix_issues", "Get AI suggestions for fixing issues"),
        ("🌳 Toggle File Tree", "toggle_file_tree", "Show/hide file tree"),
        ("💬 Toggle Chat", "toggle_chat", "Show/hide AI chat panel"),
        ("⚙️ VLLM Settings", "vllm_settings", "Configure VLLM API connection"),
        ("🚪 Quit", "quit", "Exit cliide"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the command palette."""
        with Container(id="palette-container"):
            with Horizontal(id="palette-header"):
                yield Input(placeholder="Type a command...", id="palette-input")
                yield Button("✕ Close", id="palette-close", variant="error")
            with ListView(id="palette-list"):
                for name, cmd, desc in self.COMMANDS:
                    yield ListItem(Static(f"{name} - {desc}"))

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#palette-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter commands based on input.

        Args:
            event: Input changed event
        """
        query = event.value.lower()
        list_view = self.query_one("#palette-list", ListView)

        # Clear current items
        list_view.clear()

        # Add matching commands
        for name, cmd, desc in self.COMMANDS:
            if query in name.lower() or query in desc.lower():
                list_view.append(ListItem(Static(f"{name} - {desc}")))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle command selection.

        Args:
            event: List view selected event
        """
        # Get selected command
        selected_idx = event.list_view.index
        if selected_idx is not None and selected_idx < len(self.COMMANDS):
            name, cmd, desc = self.COMMANDS[selected_idx]
            self.post_message(CommandExecuted(cmd))

        # Dismiss palette
        self.dismiss()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission.

        Args:
            event: Input submitted event
        """
        list_view = self.query_one("#palette-list", ListView)

        # Execute first visible command
        if len(list_view.children) > 0:
            first_item = list_view.children[0]
            if isinstance(first_item, ListItem):
                # Find matching command
                text = str(first_item.children[0].render())
                for name, cmd, desc in self.COMMANDS:
                    if name in text:
                        self.post_message(CommandExecuted(cmd))
                        break

        # Dismiss palette
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button pressed event
        """
        if event.button.id == "palette-close":
            self.dismiss()

    def on_key(self, event: object) -> None:
        """Handle key events.

        Args:
            event: Key event
        """
        if hasattr(event, "key") and event.key == "escape":
            self.dismiss()
            if hasattr(event, "stop"):
                event.stop()
