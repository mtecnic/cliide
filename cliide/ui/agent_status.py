"""Agent status panel for displaying sub-agent progress and tool calls."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar, Static

from cliide.ai.event_bus import (
    AgentEvent,
    AgentEventType,
    get_event_bus,
)
from cliide.utils.logger import log


class AgentTaskWidget(Static):
    """Widget displaying a single sub-agent task with progress."""

    DEFAULT_CSS = """
    AgentTaskWidget {
        layout: vertical;
        height: auto;
        min-height: 3;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
        border: round $primary-lighten-2;
    }

    AgentTaskWidget.running {
        border: round $warning;
    }

    AgentTaskWidget.completed {
        border: round $success;
        opacity: 0.7;
    }

    AgentTaskWidget.failed {
        border: round $error;
    }

    AgentTaskWidget .task-header {
        layout: horizontal;
        height: 1;
        margin-bottom: 0;
    }

    AgentTaskWidget .task-id {
        width: auto;
        color: $text-muted;
        text-style: bold;
    }

    AgentTaskWidget .task-description {
        width: 1fr;
        padding-left: 1;
        color: $text;
    }

    AgentTaskWidget .task-progress {
        height: 1;
        margin: 0;
        padding: 0;
    }

    AgentTaskWidget .task-action {
        height: 1;
        color: $text-muted;
        text-style: italic;
    }

    AgentTaskWidget.completed .task-action {
        color: $success;
    }

    AgentTaskWidget.failed .task-action {
        color: $error;
    }
    """

    # Reactive properties
    task_status: reactive[str] = reactive("pending")
    progress: reactive[float] = reactive(0.0)
    current_action: reactive[str] = reactive("")

    def __init__(
        self,
        task_id: str,
        description: str,
        **kwargs: Any,
    ) -> None:
        """Initialize task widget.

        Args:
            task_id: Unique identifier for the task
            description: Task description
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.task_id = task_id
        self.description = description
        self.started_at = datetime.now()
        self.completed_at: datetime | None = None
        self.iteration = 0
        self.max_iterations = 25  # Default

    def compose(self) -> ComposeResult:
        """Compose the task widget."""
        with Static(classes="task-header"):
            yield Label(f"[{self.task_id[:8]}]", classes="task-id")
            yield Label(self._truncate_description(), classes="task-description")

        yield ProgressBar(total=100, show_eta=False, classes="task-progress")
        yield Label(self.current_action or "Starting...", classes="task-action")

    def _truncate_description(self) -> str:
        """Truncate description to fit in panel."""
        max_len = 35
        if len(self.description) > max_len:
            return self.description[:max_len - 3] + "..."
        return self.description

    def watch_task_status(self, new_status: str) -> None:
        """React to status changes."""
        # Update CSS classes
        self.remove_class("pending", "running", "completed", "failed")
        self.add_class(new_status)

    def watch_progress(self, new_progress: float) -> None:
        """React to progress changes."""
        try:
            progress_bar = self.query_one(ProgressBar)
            # ProgressBar expects integer percentage
            progress_bar.update(progress=int(new_progress * 100))
        except Exception:
            pass  # Widget might not be mounted yet

    def watch_current_action(self, new_action: str) -> None:
        """React to action changes."""
        try:
            action_label = self.query_one(".task-action", Label)
            action_label.update(new_action)
        except Exception:
            pass  # Widget might not be mounted yet

    def set_running(self) -> None:
        """Mark task as running."""
        self.task_status = "running"
        self.current_action = "Running..."

    def set_completed(self, message: str = "Completed") -> None:
        """Mark task as completed."""
        self.task_status = "completed"
        self.progress = 1.0
        self.completed_at = datetime.now()
        duration = (self.completed_at - self.started_at).total_seconds()
        self.current_action = f"Done in {duration:.1f}s - {message[:40]}"

    def set_failed(self, error: str = "Failed") -> None:
        """Mark task as failed."""
        self.task_status = "failed"
        self.completed_at = datetime.now()
        self.current_action = f"Error: {error[:50]}"

    def update_progress(self, iteration: int, max_iterations: int, message: str) -> None:
        """Update progress from milestone event.

        Args:
            iteration: Current iteration number
            max_iterations: Maximum iterations
            message: Milestone message
        """
        self.iteration = iteration
        self.max_iterations = max_iterations
        self.progress = min(iteration / max_iterations, 1.0)
        self.current_action = message

    def update_action(self, tool_name: str, args: dict[str, Any]) -> None:
        """Update current action from tool call.

        Args:
            tool_name: Name of the tool being called
            args: Tool arguments
        """
        # Format action based on tool
        if tool_name == "read_file":
            path = args.get("path", "file")
            # Just show filename
            filename = path.split("/")[-1] if "/" in path else path
            self.current_action = f"Reading {filename}..."
        elif tool_name == "write_file":
            path = args.get("path", "file")
            filename = path.split("/")[-1] if "/" in path else path
            self.current_action = f"Writing {filename}..."
        elif tool_name == "grep":
            pattern = args.get("pattern", "")[:20]
            self.current_action = f'Searching "{pattern}"...'
        elif tool_name == "find_files":
            pattern = args.get("pattern", "")[:20]
            self.current_action = f"Finding {pattern}..."
        elif tool_name == "run_command":
            cmd = args.get("command", "")[:30]
            self.current_action = f"Running: {cmd}..."
        else:
            self.current_action = f"Using {tool_name}..."


class AgentStatusPanel(Widget):
    """Panel showing all running and recent sub-agent tasks."""

    DEFAULT_CSS = """
    AgentStatusPanel {
        layout: vertical;
        width: 40;
        background: $panel;
        border-left: heavy $primary-darken-2;
    }

    AgentStatusPanel #agent-panel-header {
        dock: top;
        height: 1;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    AgentStatusPanel #agent-panel-content {
        height: 1fr;
        padding: 1;
    }

    AgentStatusPanel #agent-panel-empty {
        color: $text-muted;
        text-style: italic;
        text-align: center;
        padding-top: 2;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize agent status panel."""
        super().__init__(**kwargs)
        self._tasks: dict[str, AgentTaskWidget] = {}
        self._event_bus = get_event_bus()
        self._max_completed_tasks = 5  # Keep N most recent completed tasks

    def compose(self) -> ComposeResult:
        """Compose the panel."""
        yield Static("Sub-Agents", id="agent-panel-header")
        with VerticalScroll(id="agent-panel-content"):
            yield Static("No active tasks", id="agent-panel-empty")

    def on_mount(self) -> None:
        """Subscribe to events on mount."""
        # Subscribe to all events
        self._event_bus.subscribe("*", self._on_agent_event)

    def on_unmount(self) -> None:
        """Unsubscribe on unmount."""
        self._event_bus.unsubscribe("*", self._on_agent_event)

    async def _on_agent_event(self, event: AgentEvent) -> None:
        """Handle agent events.

        Args:
            event: The agent event
        """
        # Ignore main agent events
        if event.source_id == "main":
            return

        task_id = event.source_id

        if event.event_type == AgentEventType.TASK_STARTED:
            await self._add_task(event)
        elif event.event_type == AgentEventType.MILESTONE:
            self._update_progress(task_id, event)
        elif event.event_type == AgentEventType.PROGRESS:
            self._update_progress(task_id, event)
        elif event.event_type == AgentEventType.TOOL_CALLED:
            self._update_action(task_id, event)
        elif event.event_type == AgentEventType.TASK_COMPLETED:
            self._mark_completed(task_id, event)
        elif event.event_type == AgentEventType.TASK_FAILED:
            self._mark_failed(task_id, event)

        # Update header with counts
        self._update_header()

    async def _add_task(self, event: AgentEvent) -> None:
        """Add a new task widget.

        Args:
            event: Task started event
        """
        task_id = event.source_id
        description = event.data.get("description", "Sub-agent task")

        # Create task widget
        task_widget = AgentTaskWidget(
            task_id=task_id,
            description=description,
            id=f"task-{task_id}",
        )
        task_widget.set_running()

        # Remove empty placeholder if present
        try:
            empty_label = self.query_one("#agent-panel-empty")
            empty_label.remove()
        except Exception:
            pass

        # Add to container
        content = self.query_one("#agent-panel-content")
        await content.mount(task_widget)

        # Track it
        self._tasks[task_id] = task_widget

    def _update_progress(self, task_id: str, event: AgentEvent) -> None:
        """Update task progress from event.

        Args:
            task_id: Task identifier
            event: Milestone/progress event
        """
        task_widget = self._tasks.get(task_id)
        if not task_widget:
            return

        iteration = event.data.get("iteration", 0)
        max_iterations = event.data.get("max_iterations", 25)
        message = event.data.get("message", "")

        task_widget.update_progress(iteration, max_iterations, message)

    def _update_action(self, task_id: str, event: AgentEvent) -> None:
        """Update task action from tool call event.

        Args:
            task_id: Task identifier
            event: Tool called event
        """
        task_widget = self._tasks.get(task_id)
        if not task_widget:
            return

        tool_name = event.data.get("tool", "unknown")
        args = event.data.get("args", {})

        task_widget.update_action(tool_name, args)

    def _mark_completed(self, task_id: str, event: AgentEvent) -> None:
        """Mark task as completed.

        Args:
            task_id: Task identifier
            event: Task completed event
        """
        task_widget = self._tasks.get(task_id)
        if not task_widget:
            return

        result = event.data.get("result", "")
        # Truncate result for display
        if len(result) > 100:
            result = result[:97] + "..."

        task_widget.set_completed(result or "Done")

        # Prune old completed tasks
        self._prune_completed_tasks()

    def _mark_failed(self, task_id: str, event: AgentEvent) -> None:
        """Mark task as failed.

        Args:
            task_id: Task identifier
            event: Task failed event
        """
        task_widget = self._tasks.get(task_id)
        if not task_widget:
            return

        error = event.data.get("error", "Unknown error")
        task_widget.set_failed(error)

    def _prune_completed_tasks(self) -> None:
        """Remove old completed tasks to prevent panel overflow."""
        completed = [
            (tid, tw) for tid, tw in self._tasks.items()
            if tw.task_status == "completed" and tw.completed_at
        ]

        # Sort by completion time
        completed.sort(key=lambda x: x[1].completed_at or datetime.min)

        # Remove oldest if too many
        while len(completed) > self._max_completed_tasks:
            task_id, task_widget = completed.pop(0)
            task_widget.remove()
            del self._tasks[task_id]

    def _update_header(self) -> None:
        """Update panel header with task counts."""
        running = sum(1 for tw in self._tasks.values() if tw.task_status == "running")
        completed = sum(1 for tw in self._tasks.values() if tw.task_status == "completed")
        failed = sum(1 for tw in self._tasks.values() if tw.task_status == "failed")

        header = self.query_one("#agent-panel-header", Static)

        if running > 0:
            header.update(f"Sub-Agents ({running} active)")
        elif completed > 0 or failed > 0:
            parts = []
            if completed > 0:
                parts.append(f"{completed} done")
            if failed > 0:
                parts.append(f"{failed} failed")
            header.update(f"Sub-Agents ({', '.join(parts)})")
        else:
            header.update("Sub-Agents")

    def clear_completed(self) -> None:
        """Clear all completed and failed tasks."""
        to_remove = [
            tid for tid, tw in self._tasks.items()
            if tw.task_status in ("completed", "failed")
        ]

        for task_id in to_remove:
            task_widget = self._tasks.pop(task_id)
            task_widget.remove()

        # Show empty message if no tasks left
        if not self._tasks:
            content = self.query_one("#agent-panel-content")
            content.mount(Static("No active tasks", id="agent-panel-empty"))

        self._update_header()

    def get_running_count(self) -> int:
        """Get count of currently running tasks."""
        return sum(1 for tw in self._tasks.values() if tw.task_status == "running")


class ToolCallWidget(Static):
    """Widget displaying a single active tool call."""

    DEFAULT_CSS = """
    ToolCallWidget {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
        border-left: tall $warning;
    }

    ToolCallWidget.completed {
        border-left: tall $success;
        opacity: 0.6;
    }

    ToolCallWidget.failed {
        border-left: tall $error;
    }

    ToolCallWidget .tool-header {
        layout: horizontal;
        height: 1;
    }

    ToolCallWidget .tool-icon {
        width: 2;
        color: $warning;
    }

    ToolCallWidget.completed .tool-icon {
        color: $success;
    }

    ToolCallWidget.failed .tool-icon {
        color: $error;
    }

    ToolCallWidget .tool-name {
        width: auto;
        color: $text;
        text-style: bold;
    }

    ToolCallWidget .tool-args {
        height: 1;
        color: $text-muted;
        text-style: italic;
    }

    ToolCallWidget .tool-duration {
        color: $text-muted;
        padding-left: 1;
    }
    """

    def __init__(
        self,
        worker_id: str,
        tool_name: str,
        args: dict[str, Any],
        parent_task: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize tool call widget.

        Args:
            worker_id: Unique worker identifier
            tool_name: Name of the tool being called
            args: Tool arguments
            parent_task: Optional parent task ID for grouping
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.worker_id = worker_id
        self.tool_name = tool_name
        self.args = args
        self.parent_task = parent_task
        self.status = "running"
        self.started_at = datetime.now()

    def compose(self) -> ComposeResult:
        """Compose the tool call widget."""
        with Static(classes="tool-header"):
            yield Label("⚡", classes="tool-icon")
            yield Label(self.tool_name, classes="tool-name")

        yield Label(self._format_args(), classes="tool-args")

    def _format_args(self) -> str:
        """Format tool arguments for display."""
        if not self.args:
            return "()"

        # Format based on tool type
        if self.tool_name == "read_file":
            path = self.args.get("path", "")
            filename = path.split("/")[-1] if "/" in path else path
            return f"({filename})"
        elif self.tool_name == "write_file":
            path = self.args.get("path", "")
            filename = path.split("/")[-1] if "/" in path else path
            return f"({filename})"
        elif self.tool_name == "grep":
            pattern = self.args.get("pattern", "")[:20]
            return f'("{pattern}")'
        elif self.tool_name == "find_files":
            pattern = self.args.get("pattern", "")[:20]
            return f"({pattern})"
        elif self.tool_name == "run_command":
            cmd = self.args.get("command", "")[:25]
            return f"({cmd})"
        else:
            # Generic: show first arg value truncated
            if self.args:
                first_val = str(list(self.args.values())[0])[:25]
                return f"({first_val})"
            return "()"

    def mark_completed(self) -> None:
        """Mark this tool call as completed."""
        self.status = "completed"
        self.remove_class("running")
        self.add_class("completed")
        try:
            icon = self.query_one(".tool-icon", Label)
            icon.update("✓")
        except Exception:
            pass

    def mark_failed(self) -> None:
        """Mark this tool call as failed."""
        self.status = "failed"
        self.remove_class("running")
        self.add_class("failed")
        try:
            icon = self.query_one(".tool-icon", Label)
            icon.update("✗")
        except Exception:
            pass


class ToolCallsView(Widget):
    """View showing active tool calls grouped by task."""

    DEFAULT_CSS = """
    ToolCallsView {
        layout: vertical;
        height: 1fr;
        padding: 1;
    }

    ToolCallsView #tools-empty {
        color: $text-muted;
        text-style: italic;
        text-align: center;
        padding-top: 2;
    }

    ToolCallsView .task-group {
        margin-bottom: 1;
    }

    ToolCallsView .task-group-header {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize tool calls view."""
        super().__init__(**kwargs)
        self._tools: dict[str, ToolCallWidget] = {}
        self._event_bus = get_event_bus()
        self._remove_delay_ms = 2500  # Keep completed tools visible for 2.5s

    def compose(self) -> ComposeResult:
        """Compose the view."""
        with VerticalScroll():
            yield Static("No active tool calls", id="tools-empty")

    def on_mount(self) -> None:
        """Subscribe to worker events on mount."""
        self._event_bus.subscribe(AgentEventType.WORKER_STARTED, self._on_worker_started)
        self._event_bus.subscribe(AgentEventType.WORKER_COMPLETED, self._on_worker_done)
        self._event_bus.subscribe(AgentEventType.WORKER_FAILED, self._on_worker_failed)

    def on_unmount(self) -> None:
        """Unsubscribe on unmount."""
        self._event_bus.unsubscribe(AgentEventType.WORKER_STARTED, self._on_worker_started)
        self._event_bus.unsubscribe(AgentEventType.WORKER_COMPLETED, self._on_worker_done)
        self._event_bus.unsubscribe(AgentEventType.WORKER_FAILED, self._on_worker_failed)

    async def _on_worker_started(self, event: AgentEvent) -> None:
        """Add new tool call widget when worker starts."""
        worker_id = event.source_id
        tool_name = event.data.get("tool", "unknown")
        args = event.data.get("args", {})
        parent_task = event.data.get("parent_task_id")

        # Create tool widget
        widget = ToolCallWidget(
            worker_id=worker_id,
            tool_name=tool_name,
            args=args,
            parent_task=parent_task,
            id=f"tool-{worker_id}",
        )

        # Remove empty placeholder if present
        try:
            empty_label = self.query_one("#tools-empty")
            empty_label.remove()
        except Exception:
            pass

        # Add to container
        scroll = self.query_one(VerticalScroll)
        await scroll.mount(widget)
        self._tools[worker_id] = widget

    async def _on_worker_done(self, event: AgentEvent) -> None:
        """Handle worker completion - mark and schedule removal."""
        worker_id = event.source_id
        if worker_id in self._tools:
            widget = self._tools[worker_id]
            widget.mark_completed()
            # Schedule removal after brief delay
            self.set_timer(self._remove_delay_ms / 1000, lambda: self._remove_tool(worker_id))

    async def _on_worker_failed(self, event: AgentEvent) -> None:
        """Handle worker failure - mark and schedule removal."""
        worker_id = event.source_id
        if worker_id in self._tools:
            widget = self._tools[worker_id]
            widget.mark_failed()
            # Keep failed tools visible a bit longer
            self.set_timer((self._remove_delay_ms * 2) / 1000, lambda: self._remove_tool(worker_id))

    def _remove_tool(self, worker_id: str) -> None:
        """Remove a tool widget from the view."""
        if worker_id in self._tools:
            widget = self._tools.pop(worker_id)
            widget.remove()

            # Show empty message if no tools left
            if not self._tools:
                scroll = self.query_one(VerticalScroll)
                scroll.mount(Static("No active tool calls", id="tools-empty"))

    def get_active_count(self) -> int:
        """Get count of currently active tool calls."""
        return sum(1 for tw in self._tools.values() if tw.status == "running")


class TabbedAgentPanel(Widget):
    """Tabbed panel with Agents and Tools views."""

    DEFAULT_CSS = """
    TabbedAgentPanel {
        layout: vertical;
        width: 32;
        background: $panel;
        border-left: heavy $primary-darken-2;
    }

    TabbedAgentPanel .tab-bar {
        dock: top;
        height: 1;
        layout: horizontal;
        background: $primary-darken-2;
    }

    TabbedAgentPanel .tab {
        width: 1fr;
        min-width: 10;
        height: 1;
        text-align: center;
        color: #aaaaaa;
        background: $primary-darken-3;
        border: none;
    }

    TabbedAgentPanel .tab:hover {
        background: $primary-darken-1;
        color: #ffffff;
    }

    TabbedAgentPanel .tab.active {
        background: $primary-darken-2;
        color: #ffffff;
        text-style: bold;
    }

    TabbedAgentPanel .tab-content {
        height: 1fr;
    }

    TabbedAgentPanel .hidden {
        display: none;
    }
    """

    active_tab: reactive[str] = reactive("agents")

    def __init__(self, **kwargs: Any) -> None:
        """Initialize tabbed agent panel."""
        super().__init__(**kwargs)
        self._event_bus = get_event_bus()

    def compose(self) -> ComposeResult:
        """Compose the tabbed panel."""
        with Horizontal(classes="tab-bar"):
            yield Button("Agents", id="tab-agents", classes="tab active")
            yield Button("Tools", id="tab-tools", classes="tab")

        with Container(classes="tab-content"):
            yield AgentTasksView(id="agents-view")
            yield ToolCallsView(id="tools-view", classes="hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle tab button presses."""
        if event.button.id == "tab-agents":
            self.active_tab = "agents"
        elif event.button.id == "tab-tools":
            self.active_tab = "tools"

    def watch_active_tab(self, tab: str) -> None:
        """React to tab changes - toggle view visibility."""
        try:
            agents_view = self.query_one("#agents-view")
            tools_view = self.query_one("#tools-view")

            # Toggle visibility
            agents_view.set_class(tab != "agents", "hidden")
            tools_view.set_class(tab != "tools", "hidden")

            # Update tab button styling
            agents_btn = self.query_one("#tab-agents", Button)
            tools_btn = self.query_one("#tab-tools", Button)

            agents_btn.set_class(tab == "agents", "active")
            tools_btn.set_class(tab == "tools", "active")
        except Exception:
            pass  # Views might not be mounted yet

    def get_agents_view(self) -> AgentTasksView:
        """Get the agents view component."""
        return self.query_one("#agents-view", AgentTasksView)

    def get_tools_view(self) -> ToolCallsView:
        """Get the tools view component."""
        return self.query_one("#tools-view", ToolCallsView)


class AgentTasksView(Widget):
    """View showing sub-agent tasks with progress (content from old AgentStatusPanel)."""

    DEFAULT_CSS = """
    AgentTasksView {
        layout: vertical;
        height: 1fr;
    }

    AgentTasksView #tasks-content {
        height: 1fr;
        padding: 1;
    }

    AgentTasksView #tasks-empty {
        color: $text-muted;
        text-style: italic;
        text-align: center;
        padding-top: 2;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize agent tasks view."""
        super().__init__(**kwargs)
        self._tasks: dict[str, AgentTaskWidget] = {}
        self._event_bus = get_event_bus()
        self._max_completed_tasks = 5
        self._fade_delay_ms = 3000  # 3 second delay before removal

    def compose(self) -> ComposeResult:
        """Compose the view."""
        with VerticalScroll(id="tasks-content"):
            yield Static("No active tasks", id="tasks-empty")

    def on_mount(self) -> None:
        """Subscribe to events on mount."""
        self._event_bus.subscribe("*", self._on_agent_event)

    def on_unmount(self) -> None:
        """Unsubscribe on unmount."""
        self._event_bus.unsubscribe("*", self._on_agent_event)

    async def _on_agent_event(self, event: AgentEvent) -> None:
        """Handle agent events."""
        log(f"[AGENT_TASKS_VIEW] Received event: {event.event_type.value} from {event.source_id}")
        # Ignore main agent and worker events
        if event.source_id == "main":
            return
        # Ignore worker events (handled by ToolCallsView)
        if event.event_type in (
            AgentEventType.WORKER_STARTED,
            AgentEventType.WORKER_COMPLETED,
            AgentEventType.WORKER_FAILED,
        ):
            return

        task_id = event.source_id

        if event.event_type == AgentEventType.TASK_STARTED:
            log(f"[AGENT_TASKS_VIEW] Adding task: {task_id}")
            await self._add_task(event)
        elif event.event_type == AgentEventType.MILESTONE:
            self._update_progress(task_id, event)
        elif event.event_type == AgentEventType.PROGRESS:
            self._update_progress(task_id, event)
        elif event.event_type == AgentEventType.TOOL_CALLED:
            self._update_action(task_id, event)
        elif event.event_type == AgentEventType.TASK_COMPLETED:
            self._mark_completed(task_id, event)
        elif event.event_type == AgentEventType.TASK_FAILED:
            self._mark_failed(task_id, event)

    async def _add_task(self, event: AgentEvent) -> None:
        """Add a new task widget."""
        task_id = event.source_id
        description = event.data.get("description", "Sub-agent task")

        # Schedule UI update on Textual's event loop
        def do_add_task():
            task_widget = AgentTaskWidget(
                task_id=task_id,
                description=description,
                id=f"task-{task_id}",
            )
            task_widget.set_running()

            # Remove empty placeholder if present
            try:
                empty_label = self.query_one("#tasks-empty")
                empty_label.remove()
            except Exception:
                pass

            try:
                content = self.query_one("#tasks-content")
                content.mount(task_widget)
                self._tasks[task_id] = task_widget
                log(f"[AGENT_TASKS_VIEW] Mounted task widget: {task_id}")
            except Exception as e:
                log(f"[AGENT_TASKS_VIEW] Error mounting task: {e}")

        self.call_later(do_add_task)

    def _update_progress(self, task_id: str, event: AgentEvent) -> None:
        """Update task progress from event."""
        iteration = event.data.get("iteration", 0)
        max_iterations = event.data.get("max_iterations", 25)
        message = event.data.get("message", "")

        def do_update():
            task_widget = self._tasks.get(task_id)
            if task_widget:
                task_widget.update_progress(iteration, max_iterations, message)

        self.call_later(do_update)

    def _update_action(self, task_id: str, event: AgentEvent) -> None:
        """Update task action from tool call event."""
        tool_name = event.data.get("tool", "unknown")
        args = event.data.get("args", {})

        def do_update():
            task_widget = self._tasks.get(task_id)
            if task_widget:
                task_widget.update_action(tool_name, args)

        self.call_later(do_update)

    def _mark_completed(self, task_id: str, event: AgentEvent) -> None:
        """Mark task as completed with delayed removal."""
        result = event.data.get("result", "")
        if len(result) > 100:
            result = result[:97] + "..."

        def do_complete():
            task_widget = self._tasks.get(task_id)
            if task_widget:
                task_widget.set_completed(result or "Done")
                # Schedule delayed removal
                self.set_timer(
                    self._fade_delay_ms / 1000,
                    lambda tid=task_id: self._remove_task(tid)
                )

        self.call_later(do_complete)

    def _mark_failed(self, task_id: str, event: AgentEvent) -> None:
        """Mark task as failed."""
        error = event.data.get("error", "Unknown error")

        def do_fail():
            task_widget = self._tasks.get(task_id)
            if task_widget:
                task_widget.set_failed(error)
                # Schedule delayed removal for failed tasks too
                self.set_timer(
                    (self._fade_delay_ms * 2) / 1000,
                    lambda tid=task_id: self._remove_task(tid)
                )

        self.call_later(do_fail)

    def _remove_task(self, task_id: str) -> None:
        """Remove a task after fade delay."""
        if task_id in self._tasks:
            widget = self._tasks.pop(task_id)
            widget.remove()

            # Show empty message if no tasks left
            if not self._tasks:
                try:
                    content = self.query_one("#tasks-content")
                    content.mount(Static("No active tasks", id="tasks-empty"))
                except Exception:
                    pass

    def _prune_completed_tasks(self) -> None:
        """Remove old completed tasks to prevent overflow."""
        completed = [
            (tid, tw) for tid, tw in self._tasks.items()
            if tw.task_status == "completed" and tw.completed_at
        ]

        completed.sort(key=lambda x: x[1].completed_at or datetime.min)

        while len(completed) > self._max_completed_tasks:
            task_id, task_widget = completed.pop(0)
            task_widget.remove()
            del self._tasks[task_id]

    def clear_completed(self) -> None:
        """Clear all completed and failed tasks."""
        to_remove = [
            tid for tid, tw in self._tasks.items()
            if tw.task_status in ("completed", "failed")
        ]

        for task_id in to_remove:
            task_widget = self._tasks.pop(task_id)
            task_widget.remove()

        if not self._tasks:
            content = self.query_one("#tasks-content")
            content.mount(Static("No active tasks", id="tasks-empty"))

    def get_running_count(self) -> int:
        """Get count of currently running tasks."""
        return sum(1 for tw in self._tasks.values() if tw.task_status == "running")
