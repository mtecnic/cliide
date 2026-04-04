"""Symbol search panel for Go-to-Symbol functionality."""

from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListItem, ListView, Static


# Symbol kind icons (LSP SymbolKind values)
SYMBOL_ICONS = {
    1: "📄",   # File
    2: "📦",   # Module
    3: "🔤",   # Namespace
    4: "📦",   # Package
    5: "🔷",   # Class
    6: "🔹",   # Method
    7: "📝",   # Property
    8: "🔸",   # Field
    9: "🛠️",   # Constructor
    10: "🔢",  # Enum
    11: "🔗",  # Interface
    12: "🔧",  # Function
    13: "📊",  # Variable
    14: "🔒",  # Constant
    15: "📜",  # String
    16: "#️⃣",  # Number
    17: "✅",  # Boolean
    18: "📐",  # Array
    19: "{ }",  # Object
    20: "🔑",  # Key
    21: "∅",   # Null
    22: "🔡",  # EnumMember
    23: "📋",  # Struct
    24: "📣",  # Event
    25: "⚡",  # Operator
    26: "📐",  # TypeParameter
}


class SymbolSelected(Message):
    """Message sent when a symbol is selected."""

    def __init__(self, line: int, character: int, name: str) -> None:
        """Initialize.

        Args:
            line: Line number (0-indexed)
            character: Character position (0-indexed)
            name: Symbol name
        """
        super().__init__()
        self.line = line
        self.character = character
        self.name = name


class SymbolSearchPanel(ModalScreen[tuple[int, int] | None]):
    """Modal panel for searching document symbols."""

    DEFAULT_CSS = """
    SymbolSearchPanel {
        align: center middle;
    }

    #symbol-container {
        width: 70;
        height: auto;
        max-height: 25;
        background: $panel;
        border: round $primary;
    }

    #symbol-header {
        dock: top;
        height: auto;
        background: $boost;
        border-bottom: heavy $primary;
    }

    #symbol-input {
        width: 1fr;
        border: round $accent;
        background: $surface;
    }

    #symbol-close {
        width: auto;
        min-width: 10;
        margin-left: 1;
    }

    #symbol-list {
        height: auto;
        max-height: 18;
        background: $surface;
    }

    #symbol-list > ListItem {
        padding: 0 1;
        border-left: heavy transparent;
    }

    #symbol-list > ListItem:hover {
        background: $boost;
        border-left: heavy $accent;
        color: $accent;
    }

    #symbol-list > .list-item--highlighted {
        background: $boost;
        border-left: heavy $primary;
        color: $primary;
        text-style: bold;
    }

    #no-symbols {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        symbols: list[dict[str, Any]] | None = None,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """Initialize.

        Args:
            symbols: List of LSP document symbols
            name: Widget name
            id: Widget ID
        """
        super().__init__(name=name, id=id)
        self._symbols = symbols or []
        self._filtered_symbols: list[dict[str, Any]] = []
        self._flat_symbols: list[dict[str, Any]] = []
        self._flatten_symbols(self._symbols)

    def _flatten_symbols(self, symbols: list[dict[str, Any]], prefix: str = "") -> None:
        """Flatten nested symbols into a flat list.

        Args:
            symbols: List of symbols (may have children)
            prefix: Parent path prefix
        """
        for symbol in symbols:
            name = symbol.get("name", "")
            full_name = f"{prefix}.{name}" if prefix else name

            # Add to flat list with path info
            self._flat_symbols.append({
                **symbol,
                "full_name": full_name,
            })

            # Recurse into children
            children = symbol.get("children", [])
            if children:
                self._flatten_symbols(children, full_name)

        self._filtered_symbols = self._flat_symbols.copy()

    def compose(self) -> ComposeResult:
        """Compose the panel."""
        with Container(id="symbol-container"):
            with Horizontal(id="symbol-header"):
                yield Input(placeholder="Search symbols (@)...", id="symbol-input")
                yield Button("✕ Close", id="symbol-close", variant="error")

            if not self._flat_symbols:
                yield Static("No symbols found in document", id="no-symbols")
            else:
                with ListView(id="symbol-list"):
                    for symbol in self._flat_symbols[:50]:  # Limit initial display
                        yield self._create_symbol_item(symbol)

    def _create_symbol_item(self, symbol: dict[str, Any]) -> ListItem:
        """Create a ListItem for a symbol.

        Args:
            symbol: Symbol data

        Returns:
            ListItem widget
        """
        kind = symbol.get("kind", 12)  # Default to Function
        icon = SYMBOL_ICONS.get(kind, "●")
        name = symbol.get("full_name", symbol.get("name", "?"))

        # Get line number
        range_data = symbol.get("range", symbol.get("selectionRange", {}))
        start = range_data.get("start", {})
        line = start.get("line", 0) + 1  # Convert to 1-indexed for display

        return ListItem(
            Static(f"{icon} {name} [dim]:{line}[/dim]"),
            id=f"symbol-{id(symbol)}",
            name=str(self._flat_symbols.index(symbol) if symbol in self._flat_symbols else 0),
        )

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#symbol-input").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter symbols based on input.

        Args:
            event: Input change event
        """
        query = event.value.lower().strip()
        if query.startswith("@"):
            query = query[1:]  # Remove @ prefix

        # Filter symbols
        if query:
            self._filtered_symbols = [
                s for s in self._flat_symbols
                if query in s.get("full_name", s.get("name", "")).lower()
            ]
        else:
            self._filtered_symbols = self._flat_symbols.copy()

        # Update list
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the symbol list."""
        try:
            list_view = self.query_one("#symbol-list", ListView)
            list_view.clear()

            for symbol in self._filtered_symbols[:50]:
                list_view.append(self._create_symbol_item(symbol))

        except Exception:
            pass  # List may not exist yet

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button press event
        """
        if event.button.id == "symbol-close":
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle symbol selection.

        Args:
            event: Selection event
        """
        try:
            # Get symbol index from item name
            idx = int(event.item.name) if event.item.name else 0
            if 0 <= idx < len(self._flat_symbols):
                symbol = self._flat_symbols[idx]
                range_data = symbol.get("range", symbol.get("selectionRange", {}))
                start = range_data.get("start", {})
                line = start.get("line", 0)
                character = start.get("character", 0)
                self.dismiss((line, character))
        except (ValueError, IndexError):
            pass

    def on_key(self, event) -> None:
        """Handle key events.

        Args:
            event: Key event
        """
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "enter":
            # Select first visible item
            try:
                list_view = self.query_one("#symbol-list", ListView)
                if list_view.highlighted_child:
                    list_view.action_select_cursor()
                elif self._filtered_symbols:
                    symbol = self._filtered_symbols[0]
                    range_data = symbol.get("range", symbol.get("selectionRange", {}))
                    start = range_data.get("start", {})
                    self.dismiss((start.get("line", 0), start.get("character", 0)))
            except Exception:
                pass
