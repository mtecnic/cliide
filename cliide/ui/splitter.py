"""Resizable splitter widget for panel layouts."""

from textual.events import MouseDown, MouseMove, MouseUp
from textual.widget import Widget
from rich.text import Text


class Splitter(Widget):
    """Vertical drag bar for resizing adjacent panels.

    Place between two panels to allow mouse-drag resizing.
    By default resizes the left panel; set resize_right=True to resize the right panel.
    """

    DEFAULT_CSS = """
    Splitter {
        width: 1;
        height: 100%;
        background: $surface-darken-1;
    }
    Splitter:hover {
        background: $primary;
    }
    Splitter.-dragging {
        background: $accent;
    }
    """

    def __init__(
        self,
        left_panel_id: str,
        right_panel_id: str | None = None,
        min_width: int = 10,
        resize_right: bool = False,
        **kwargs,
    ) -> None:
        """Initialize splitter.

        Args:
            left_panel_id: ID of the panel to the left
            right_panel_id: ID of the panel to the right
            min_width: Minimum width for the resized panel
            resize_right: If True, resize right panel instead of left
        """
        super().__init__(**kwargs)
        self.left_panel_id = left_panel_id
        self.right_panel_id = right_panel_id
        self.min_width = min_width
        self.resize_right = resize_right
        self._dragging = False
        self._start_x = 0
        self._panel_start_width = 0

    def on_mouse_down(self, event: MouseDown) -> None:
        """Start drag operation."""
        if event.button == 1:  # Left mouse button
            self.capture_mouse()
            self._dragging = True
            self._start_x = event.screen_x

            # Get current width of the panel we're resizing
            panel_id = self.right_panel_id if self.resize_right else self.left_panel_id
            try:
                panel = self.app.query_one(f"#{panel_id}")
                width = panel.styles.width
                if width is not None and width.value is not None:
                    self._panel_start_width = int(width.value)
                else:
                    self._panel_start_width = panel.size.width
            except Exception:
                self._panel_start_width = 30  # Fallback

            self.add_class("-dragging")
            event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        """Update panel width during drag."""
        if self._dragging:
            try:
                if self.resize_right:
                    # Resize right panel: dragging left = wider, right = narrower
                    right = self.app.query_one(f"#{self.right_panel_id}")
                    # Width = distance from splitter to right edge of screen
                    new_width = self.app.size.width - event.screen_x
                    new_width = max(self.min_width, new_width)
                    # Don't let it take more than 60% of screen
                    max_width = int(self.app.size.width * 0.6)
                    new_width = min(new_width, max_width)
                    right.styles.width = new_width
                else:
                    # Resize left panel (original behavior)
                    left = self.app.query_one(f"#{self.left_panel_id}")
                    left_x = left.region.x
                    new_width = event.screen_x - left_x
                    new_width = max(self.min_width, new_width)

                    # Reserve space for panels to the right
                    panels = ["left-column", "editor-container", "chat-container"]
                    try:
                        idx = panels.index(self.left_panel_id)
                        panels_to_right = len(panels) - idx - 1
                        reserved = panels_to_right * 26
                    except ValueError:
                        reserved = 80

                    max_splitter_x = self.app.size.width - reserved
                    max_width = max_splitter_x - left_x
                    new_width = min(new_width, max(self.min_width, max_width))
                    left.styles.width = new_width
            except Exception:
                pass

            event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """End drag operation."""
        if self._dragging:
            self.release_mouse()
            self._dragging = False
            self.remove_class("-dragging")
            event.stop()

    def render(self) -> Text:
        """Render the splitter bar."""
        # Use a thin vertical line character
        return Text("│" * self.size.height, style="dim")


class HorizontalSplitter(Widget):
    """Horizontal drag bar for resizing vertically stacked panels.

    Place between two panels to allow mouse-drag resizing.
    Resizes the top panel's height; bottom panel adjusts via flex.
    """

    DEFAULT_CSS = """
    HorizontalSplitter {
        width: 100%;
        height: 1;
        background: $surface-darken-1;
    }
    HorizontalSplitter:hover {
        background: $primary;
    }
    HorizontalSplitter.-dragging {
        background: $accent;
    }
    """

    def __init__(
        self,
        top_panel_id: str,
        bottom_panel_id: str | None = None,
        min_height: int = 3,
        **kwargs,
    ) -> None:
        """Initialize horizontal splitter.

        Args:
            top_panel_id: ID of the panel above (will be resized)
            bottom_panel_id: ID of the panel below (optional)
            min_height: Minimum height for the top panel
        """
        super().__init__(**kwargs)
        self.top_panel_id = top_panel_id
        self.bottom_panel_id = bottom_panel_id
        self.min_height = min_height
        self._dragging = False
        self._start_y = 0
        self._top_start_height = 0

    def on_mouse_down(self, event: MouseDown) -> None:
        """Start drag operation."""
        if event.button == 1:
            self.capture_mouse()
            self._dragging = True
            self._start_y = event.screen_y

            try:
                top = self.app.query_one(f"#{self.top_panel_id}")
                height = top.styles.height
                if height is not None and height.value is not None:
                    self._top_start_height = int(height.value)
                else:
                    self._top_start_height = top.size.height
            except Exception:
                self._top_start_height = 10

            self.add_class("-dragging")
            event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        """Update panel height during drag."""
        if self._dragging:
            try:
                top = self.app.query_one(f"#{self.top_panel_id}")
                top_y = top.region.y

                # Calculate desired height based on mouse position
                new_height = event.screen_y - top_y

                # Clamp: minimum height
                new_height = max(self.min_height, new_height)

                # Clamp: leave room for bottom panel (at least 3 rows)
                parent = self.parent
                if parent:
                    max_height = parent.size.height - 4  # 3 for bottom + 1 for splitter
                    new_height = min(new_height, max_height)

                top.styles.height = new_height
            except Exception:
                pass

            event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """End drag operation."""
        if self._dragging:
            self.release_mouse()
            self._dragging = False
            self.remove_class("-dragging")
            event.stop()

    def render(self) -> Text:
        """Render the splitter bar."""
        return Text("─" * self.size.width, style="dim")
