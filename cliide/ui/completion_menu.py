"""Completion menu widget for LSP code completion."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import ListItem, ListView, Static

from cliide.lsp.protocol import completion_item_kind_to_icon


class CompletionMenu(Widget):
    """Popup completion menu for code completion."""

    DEFAULT_CSS = """
    CompletionMenu {
        width: 60;
        height: auto;
        max-height: 15;
        background: $panel;
        border: solid $primary;
        layer: overlay;
    }

    CompletionMenu ListView {
        height: auto;
        max-height: 15;
    }

    CompletionMenu ListItem {
        padding: 0 1;
    }

    CompletionMenu .completion-label {
        color: $text;
    }

    CompletionMenu .completion-detail {
        color: $text-muted;
        margin-left: 2;
    }
    """

    class CompletionSelected(Message):
        """Sent when a completion is selected."""

        def __init__(self, item: dict[str, Any]) -> None:
            """Initialize message.

            Args:
                item: Selected completion item
            """
            super().__init__()
            self.item = item

    def __init__(self, items: list[dict[str, Any]], **kwargs: Any) -> None:
        """Initialize completion menu.

        Args:
            items: Completion items
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.items = items

    def compose(self) -> ComposeResult:
        """Compose the completion menu."""
        with VerticalScroll():
            list_view = ListView()

            for item in self.items:
                # Get label and kind
                label = item.get("label", "")
                kind = item.get("kind")
                detail = item.get("detail", "")

                # Get icon for kind
                icon = completion_item_kind_to_icon(kind)

                # Build item text
                if detail:
                    text = f"{icon} {label}  [dim]{detail}[/dim]"
                else:
                    text = f"{icon} {label}"

                list_item = ListItem(Static(text))
                list_view.append(list_item)

            yield list_view

    def on_mount(self) -> None:
        """Handle mount - focus the list."""
        list_view = self.query_one(ListView)
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle item selection.

        Args:
            event: Selection event
        """
        # Get selected index
        list_view = self.query_one(ListView)
        selected_index = list_view.index

        if 0 <= selected_index < len(self.items):
            item = self.items[selected_index]

            # Post completion selected message
            self.post_message(self.CompletionSelected(item))

    def on_key(self, event: Any) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        # Close on Escape
        if event.key == "escape":
            self.remove()
            event.stop()
