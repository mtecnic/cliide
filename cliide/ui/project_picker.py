"""Project picker modal for switching between projects."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, TabbedContent, TabPane

from cliide.core.recent_projects import RecentProject, RecentProjectsManager
from cliide.ui.directory_browser import DirectoryBrowser, DirectorySelected, get_default_browse_path


class ProjectListItem(ListItem):
    """A list item representing a recent project."""

    def __init__(self, project: RecentProject, **kwargs) -> None:
        """Initialize the list item.

        Args:
            project: Recent project data
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        """Create the list item content."""
        yield Static(f"[bold]{self.project.name}[/bold]", classes="project-name")
        yield Static(
            f"[dim]{self.project.path}[/dim]  [italic]{self.project.time_ago()}[/italic]",
            classes="project-path",
        )


class ProjectPicker(ModalScreen[Path | None]):
    """Modal screen for selecting a project to open."""

    DEFAULT_CSS = """
    ProjectPicker {
        align: center middle;
    }

    ProjectPicker > Container {
        width: 80;
        height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ProjectPicker #title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $primary;
    }

    ProjectPicker TabbedContent {
        height: 1fr;
    }

    ProjectPicker #filter {
        margin-bottom: 1;
    }

    ProjectPicker ListView {
        height: 1fr;
        background: $background;
        border: round $primary;
    }

    ProjectPicker ListItem {
        padding: 0 1;
        height: auto;
    }

    ProjectPicker ListItem.--highlight {
        background: $boost;
    }

    ProjectPicker .project-name {
        color: $text;
    }

    ProjectPicker .project-path {
        color: $text-muted;
    }

    ProjectPicker DirectoryBrowser {
        height: 1fr;
        border: round $primary;
    }

    ProjectPicker #buttons {
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    ProjectPicker #buttons Button {
        margin-left: 1;
    }

    ProjectPicker #empty-message {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Open"),
    ]

    def __init__(
        self,
        recent_projects: RecentProjectsManager,
        startup_mode: bool = False,
        **kwargs,
    ) -> None:
        """Initialize the project picker.

        Args:
            recent_projects: Manager for recent projects
            startup_mode: If True, cancel exits app instead of closing modal
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.recent_projects = recent_projects
        self.startup_mode = startup_mode
        self._filter_text = ""
        self._selected_path: Path | None = None

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        title = "Welcome to cliide" if self.startup_mode else "Switch Project"

        with Container():
            yield Static(title, id="title")

            with TabbedContent():
                with TabPane("Recent", id="recent-tab"):
                    yield Input(placeholder="Filter projects...", id="filter")
                    yield ListView(id="project-list")

                with TabPane("Browse", id="browse-tab"):
                    yield DirectoryBrowser(get_default_browse_path(), id="dir-browser")

            with Horizontal(id="buttons"):
                yield Button("Open", variant="primary", id="open-btn")
                if self.startup_mode:
                    yield Button("Quit", variant="error", id="cancel-btn")
                else:
                    yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        """Initialize the project list on mount."""
        self._populate_project_list()

    def _populate_project_list(self, filter_text: str = "") -> None:
        """Populate the project list with recent projects.

        Args:
            filter_text: Optional filter text
        """
        list_view = self.query_one("#project-list", ListView)
        list_view.clear()

        projects = self.recent_projects.get_all(filter_existing=True)

        # Filter by text if provided
        if filter_text:
            filter_lower = filter_text.lower()
            projects = [
                p
                for p in projects
                if filter_lower in p.name.lower() or filter_lower in p.path.lower()
            ]

        if not projects:
            # Show empty message
            list_view.mount(
                ListItem(
                    Static(
                        "No recent projects" if not filter_text else "No matching projects",
                        id="empty-message",
                    )
                )
            )
        else:
            for project in projects:
                list_view.mount(ProjectListItem(project))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "filter":
            self._filter_text = event.value
            self._populate_project_list(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle project selection from list.

        Args:
            event: List view selected event
        """
        if isinstance(event.item, ProjectListItem):
            self._selected_path = Path(event.item.project.path)
            self.dismiss(self._selected_path)

    def on_directory_selected(self, event: DirectorySelected) -> None:
        """Handle directory selection from browser.

        Args:
            event: Directory selected event
        """
        self._selected_path = event.path
        self.dismiss(self._selected_path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        if event.button.id == "open-btn":
            self.action_select()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def action_select(self) -> None:
        """Select the current item."""
        # Check which tab is active
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active

        if active_tab == "recent-tab":
            # Get selected item from list
            list_view = self.query_one("#project-list", ListView)
            if list_view.highlighted_child:
                item = list_view.highlighted_child
                if isinstance(item, ProjectListItem):
                    self._selected_path = Path(item.project.path)
                    self.dismiss(self._selected_path)
        elif active_tab == "browse-tab":
            # Get selected directory from browser
            browser = self.query_one("#dir-browser", DirectoryBrowser)
            path = browser.get_selected()
            if path:
                self._selected_path = path
                self.dismiss(self._selected_path)

    def action_cancel(self) -> None:
        """Cancel the picker."""
        self.dismiss(None)
