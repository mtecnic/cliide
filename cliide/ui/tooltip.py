"""Hover tooltip widget for showing documentation and type info."""

from __future__ import annotations

import asyncio
from typing import Any

from rich.markdown import Markdown
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static
from textual.geometry import Offset


class HoverTooltip(Container):
    """Tooltip widget for displaying hover information from LSP."""

    DEFAULT_CSS = """
    HoverTooltip {
        display: none;
        position: absolute;
        width: auto;
        max-width: 60;
        height: auto;
        max-height: 15;
        background: $surface;
        border: round $primary;
        padding: 0 1;
        layer: tooltip;
        overflow-y: auto;
    }

    HoverTooltip.visible {
        display: block;
    }

    HoverTooltip #tooltip-content {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize tooltip."""
        super().__init__(**kwargs)
        self._content: str = ""
        self._hide_timer: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        """Compose tooltip content."""
        yield Static("", id="tooltip-content")

    def show_at(self, content: str, x: int, y: int) -> None:
        """Show tooltip at position with content.

        Args:
            content: Markdown content to display
            x: X position in terminal cells
            y: Y position in terminal cells
        """
        if not content or not content.strip():
            self.hide()
            return

        # Cancel pending hide
        if self._hide_timer:
            self._hide_timer.cancel()
            self._hide_timer = None

        self._content = content

        # Update content
        try:
            content_widget = self.query_one("#tooltip-content", Static)
            # Parse as markdown for rich formatting
            content_widget.update(Markdown(content))
        except Exception:
            pass

        # Position tooltip
        self.styles.offset = (x, y)

        # Show tooltip
        self.add_class("visible")

    def hide(self) -> None:
        """Hide the tooltip."""
        self.remove_class("visible")
        self._content = ""

    def hide_after(self, delay: float = 0.3) -> None:
        """Schedule hiding the tooltip after a delay.

        Args:
            delay: Delay in seconds
        """
        if self._hide_timer:
            self._hide_timer.cancel()

        async def _delayed_hide() -> None:
            await asyncio.sleep(delay)
            self.hide()

        try:
            self._hide_timer = asyncio.create_task(_delayed_hide())
        except RuntimeError:
            # No event loop, just hide immediately
            self.hide()

    @property
    def is_visible(self) -> bool:
        """Check if tooltip is currently visible."""
        return self.has_class("visible")


def parse_hover_content(hover_result: dict | None) -> str:
    """Parse LSP hover result into displayable content.

    Args:
        hover_result: LSP hover response

    Returns:
        Formatted string content
    """
    if not hover_result:
        return ""

    contents = hover_result.get("contents")
    if not contents:
        return ""

    # Handle MarkupContent
    if isinstance(contents, dict):
        kind = contents.get("kind", "plaintext")
        value = contents.get("value", "")
        if kind == "markdown":
            return value
        return f"```\n{value}\n```"

    # Handle MarkedString array
    if isinstance(contents, list):
        parts = []
        for item in contents:
            if isinstance(item, dict):
                lang = item.get("language", "")
                value = item.get("value", "")
                if lang:
                    parts.append(f"```{lang}\n{value}\n```")
                else:
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        return "\n\n".join(parts)

    # Handle plain string
    if isinstance(contents, str):
        return contents

    return ""
