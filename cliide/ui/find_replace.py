"""Find & Replace panel widget."""

import re
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Static


class FindReplacePanel(Widget):
    """Find and replace panel with regex support."""

    DEFAULT_CSS = """
    FindReplacePanel {
        layout: vertical;
        width: 70;
        height: auto;
        max-height: 20;
        background: $panel;
        border: round $primary;
        layer: overlay;
        offset: 2 2;
    }

    #find-replace-header {
        dock: top;
        height: 1;
        background: $boost;
        border-bottom: heavy $primary;
        padding: 0 1;
        color: $primary;
        text-style: bold;
    }

    #find-replace-inputs {
        padding: 1;
        background: $surface;
    }

    #find-replace-options {
        padding: 0 1;
        background: $panel;
        border-top: heavy $accent;
        border-bottom: heavy $accent;
    }

    #find-replace-buttons {
        height: auto;
        align: center middle;
        background: $surface;
    }

    FindReplacePanel Input {
        margin: 0;
        border: round $accent;
        background: $background;
    }

    FindReplacePanel Button {
        margin: 0 1;
        border: round $primary;
    }

    FindReplacePanel Checkbox {
        margin: 0 1;
    }
    """

    class FindRequested(Message):
        """Sent when user requests find."""

        def __init__(
            self,
            pattern: str,
            is_regex: bool,
            case_sensitive: bool,
        ) -> None:
            """Initialize message.

            Args:
                pattern: Search pattern
                is_regex: Use regex
                case_sensitive: Case sensitive search
            """
            super().__init__()
            self.pattern = pattern
            self.is_regex = is_regex
            self.case_sensitive = case_sensitive

    class ReplaceRequested(Message):
        """Sent when user requests replace."""

        def __init__(
            self,
            pattern: str,
            replacement: str,
            is_regex: bool,
            case_sensitive: bool,
            replace_all: bool,
        ) -> None:
            """Initialize message.

            Args:
                pattern: Search pattern
                replacement: Replacement text
                is_regex: Use regex
                case_sensitive: Case sensitive search
                replace_all: Replace all occurrences
            """
            super().__init__()
            self.pattern = pattern
            self.replacement = replacement
            self.is_regex = is_regex
            self.case_sensitive = case_sensitive
            self.replace_all = replace_all

    def compose(self) -> ComposeResult:
        """Compose the find/replace panel."""
        yield Static("🔍 Find & Replace", id="find-replace-header")

        with Vertical(id="find-replace-inputs"):
            yield Input(placeholder="Find...", id="find-input")
            yield Input(placeholder="Replace with...", id="replace-input")

        with Horizontal(id="find-replace-options"):
            yield Checkbox("Regex", id="regex-checkbox")
            yield Checkbox("Case sensitive", id="case-checkbox")

        with Horizontal(id="find-replace-buttons"):
            yield Button("Find Next", id="find-next", variant="primary")
            yield Button("Replace", id="replace-one")
            yield Button("Replace All", id="replace-all")
            yield Button("Close", id="close-btn")

    def on_mount(self) -> None:
        """Handle mount - focus the find input."""
        find_input = self.query_one("#find-input", Input)
        find_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button pressed event
        """
        find_input = self.query_one("#find-input", Input)
        replace_input = self.query_one("#replace-input", Input)
        regex_checkbox = self.query_one("#regex-checkbox", Checkbox)
        case_checkbox = self.query_one("#case-checkbox", Checkbox)

        pattern = find_input.value
        replacement = replace_input.value
        is_regex = regex_checkbox.value
        case_sensitive = case_checkbox.value

        if event.button.id == "find-next":
            if pattern:
                self.post_message(
                    self.FindRequested(pattern, is_regex, case_sensitive)
                )

        elif event.button.id == "replace-one":
            if pattern:
                self.post_message(
                    self.ReplaceRequested(
                        pattern, replacement, is_regex, case_sensitive, False
                    )
                )

        elif event.button.id == "replace-all":
            if pattern:
                self.post_message(
                    self.ReplaceRequested(
                        pattern, replacement, is_regex, case_sensitive, True
                    )
                )

        elif event.button.id == "close-btn":
            self.remove()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key).

        Args:
            event: Input submitted event
        """
        if event.input.id == "find-input":
            # Trigger find next
            find_next_btn = self.query_one("#find-next", Button)
            find_next_btn.press()

    def on_key(self, event: Any) -> None:
        """Handle key press.

        Args:
            event: Key event
        """
        # Close on Escape
        if event.key == "escape":
            self.remove()
            event.stop()


def find_in_text(
    text: str,
    pattern: str,
    is_regex: bool = False,
    case_sensitive: bool = True,
    start_pos: int = 0,
) -> tuple[int, int] | None:
    """Find pattern in text.

    Args:
        text: Text to search
        pattern: Search pattern
        is_regex: Use regex
        case_sensitive: Case sensitive search
        start_pos: Start position

    Returns:
        (start, end) tuple or None if not found
    """
    flags = 0 if case_sensitive else re.IGNORECASE

    if is_regex:
        try:
            match = re.search(pattern, text[start_pos:], flags=flags)
            if match:
                return (start_pos + match.start(), start_pos + match.end())
        except re.error:
            return None
    else:
        # Literal search
        if case_sensitive:
            index = text.find(pattern, start_pos)
        else:
            index = text.lower().find(pattern.lower(), start_pos)

        if index != -1:
            return (index, index + len(pattern))

    return None


def replace_in_text(
    text: str,
    pattern: str,
    replacement: str,
    is_regex: bool = False,
    case_sensitive: bool = True,
    replace_all: bool = False,
) -> str:
    """Replace pattern in text.

    Args:
        text: Text to search/replace
        pattern: Search pattern
        replacement: Replacement text
        is_regex: Use regex
        case_sensitive: Case sensitive search
        replace_all: Replace all occurrences

    Returns:
        Modified text
    """
    flags = 0 if case_sensitive else re.IGNORECASE

    if is_regex:
        try:
            if replace_all:
                return re.sub(pattern, replacement, text, flags=flags)
            else:
                return re.sub(pattern, replacement, text, count=1, flags=flags)
        except re.error:
            return text
    else:
        # Literal replace
        if case_sensitive:
            if replace_all:
                return text.replace(pattern, replacement)
            else:
                return text.replace(pattern, replacement, 1)
        else:
            # Case-insensitive literal replace is more complex
            # Use regex with escaped pattern
            escaped = re.escape(pattern)
            if replace_all:
                return re.sub(escaped, replacement, text, flags=re.IGNORECASE)
            else:
                return re.sub(escaped, replacement, text, count=1, flags=re.IGNORECASE)
