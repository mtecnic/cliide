"""Agent status panel for displaying sub-agent progress and tool calls."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncio

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.message import Message
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
        except NoMatches:
            pass  # Widget not mounted yet

    def watch_current_action(self, new_action: str) -> None:
        """React to action changes."""
        try:
            action_label = self.query_one(".task-action", Label)
            action_label.update(new_action)
        except NoMatches:
            pass  # Widget not mounted yet

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


class PlanStepWidget(Static):
    """Widget displaying a single plan step."""

    DEFAULT_CSS = """
    PlanStepWidget {
        layout: horizontal;
        height: 1;
        padding: 0 1;
    }

    PlanStepWidget .step-num {
        width: 3;
        color: $text-muted;
    }

    PlanStepWidget .step-desc {
        width: 1fr;
        color: $text;
    }

    PlanStepWidget .step-status {
        width: 2;
        text-align: right;
    }

    PlanStepWidget.pending .step-status {
        color: $text-muted;
    }

    PlanStepWidget.in_progress .step-status {
        color: $warning;
    }

    PlanStepWidget.completed .step-status {
        color: $success;
    }
    """

    status: reactive[str] = reactive("pending")

    def __init__(
        self,
        step_num: int,
        description: str,
        **kwargs: Any,
    ) -> None:
        """Initialize plan step widget.

        Args:
            step_num: Step number (1-indexed)
            description: Step description
        """
        super().__init__(**kwargs)
        self.step_num = step_num
        self.description = description

    def compose(self) -> ComposeResult:
        """Compose the step widget."""
        yield Label(f"{self.step_num}.", classes="step-num")
        yield Label(self._truncate(self.description), classes="step-desc")
        yield Label("○", classes="step-status")

    def _truncate(self, text: str) -> str:
        """Truncate description to fit."""
        max_len = 30
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text

    def watch_status(self, new_status: str) -> None:
        """React to status changes."""
        self.remove_class("pending", "in_progress", "completed")
        self.add_class(new_status)

        # Update status icon
        try:
            status_label = self.query_one(".step-status", Label)
            if new_status == "pending":
                status_label.update("○")
            elif new_status == "in_progress":
                status_label.update("▶")
            elif new_status == "completed":
                status_label.update("✓")
        except Exception:
            pass

    def set_in_progress(self) -> None:
        """Mark step as in progress."""
        self.status = "in_progress"

    def set_completed(self) -> None:
        """Mark step as completed."""
        self.status = "completed"


class PlanView(Widget):
    """Widget displaying agent's current plan with steps."""

    DEFAULT_CSS = """
    PlanView {
        layout: vertical;
        height: auto;
        max-height: 12;
        padding: 0 1;
        margin-bottom: 1;
        background: $primary 10%;
        border: round $primary;
    }

    PlanView .plan-header {
        text-style: bold;
        color: $primary;
        height: 1;
    }

    PlanView .plan-steps {
        height: auto;
        max-height: 10;
        overflow-y: auto;
    }

    PlanView:empty {
        height: 0;
        display: none;
    }
    """

    def __init__(self, source_id: str, steps: list[str], **kwargs: Any) -> None:
        """Initialize plan view.

        Args:
            source_id: Agent source ID
            steps: List of step descriptions
        """
        super().__init__(**kwargs)
        self.source_id = source_id
        self.steps = steps
        self._step_widgets: dict[int, PlanStepWidget] = {}

    def compose(self) -> ComposeResult:
        """Compose the plan view."""
        yield Static(f"📋 Plan ({len(self.steps)} steps)", classes="plan-header")
        with Container(classes="plan-steps"):
            for i, step in enumerate(self.steps, 1):
                widget = PlanStepWidget(i, step, id=f"plan-step-{i}")
                self._step_widgets[i] = widget
                yield widget

    def mark_step_in_progress(self, step_num: int) -> None:
        """Mark a step as in progress.

        Args:
            step_num: Step number (1-indexed)
        """
        if step_num in self._step_widgets:
            self._step_widgets[step_num].set_in_progress()

    def mark_step_completed(self, step_num: int) -> None:
        """Mark a step as completed.

        Args:
            step_num: Step number (1-indexed)
        """
        if step_num in self._step_widgets:
            self._step_widgets[step_num].set_completed()

    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(w.status == "completed" for w in self._step_widgets.values())


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
        if worker_id not in self._tools:
            return  # Already removed

        widget = self._tools.pop(worker_id)
        try:
            if widget.is_mounted:
                widget.remove()
        except Exception:
            pass  # Widget already gone

        # Show empty message if no tools left
        if not self._tools:
            try:
                scroll = self.query_one(VerticalScroll)
                if scroll.is_mounted:
                    scroll.mount(Static("No active tool calls", id="tools-empty"))
            except Exception:
                pass  # Container gone

    def get_active_count(self) -> int:
        """Get count of currently active tool calls."""
        return sum(1 for tw in self._tools.values() if tw.status == "running")


class ApprovalWidget(Widget):
    """Widget for a single tool approval request."""

    DEFAULT_CSS = """
    ApprovalWidget {
        layout: vertical;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $warning 20%;
        border: round $warning;
    }

    ApprovalWidget .approval-header {
        text-style: bold;
        color: $warning;
    }

    ApprovalWidget .approval-args {
        color: $text-muted;
        height: auto;
        max-height: 3;
        overflow: hidden;
    }

    ApprovalWidget .approval-buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }

    ApprovalWidget Button {
        min-width: 6;
        height: 3;
        margin-right: 1;
        color: $text;
    }

    ApprovalWidget Button#approve {
        background: $success;
        color: $text;
    }

    ApprovalWidget Button#deny {
        background: $error;
        color: $text;
    }

    ApprovalWidget Button#auto-session {
        background: $warning;
        color: $background;
    }
    """

    class Approved(Message):
        """Sent when approval is granted."""
        def __init__(self, widget: "ApprovalWidget", auto_session: bool = False) -> None:
            super().__init__()
            self.widget = widget
            self.auto_session = auto_session

    class Denied(Message):
        """Sent when approval is denied."""
        def __init__(self, widget: "ApprovalWidget") -> None:
            super().__init__()
            self.widget = widget

    def __init__(
        self,
        tool_name: str,
        args: dict,
        future: asyncio.Future,
        **kwargs: Any
    ) -> None:
        """Initialize approval widget.

        Args:
            tool_name: Name of the tool requesting approval
            args: Tool arguments
            future: Future to resolve with approval result
        """
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.args = args
        self.future = future
        self._resolved = False  # Prevent double-handling from multiple events

    def compose(self) -> ComposeResult:
        """Compose the approval widget."""
        yield Static(f"⚠️ {self.tool_name}", classes="approval-header")

        # Format args for display
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in self.args.items())
        if len(args_str) > 60:
            args_str = args_str[:60] + "..."
        yield Static(args_str, classes="approval-args")

        with Horizontal(classes="approval-buttons"):
            yield Button("✓", id="approve", variant="success")
            yield Button("✗", id="deny", variant="error")
            yield Button("Auto", id="auto-session", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if self._resolved:
            return  # Already handled by another event
        self._resolved = True

        if event.button.id == "approve":
            if not self.future.done():
                self.future.set_result(True)
            self.post_message(self.Approved(self, auto_session=False))
            self.remove()
        elif event.button.id == "deny":
            if not self.future.done():
                self.future.set_result(False)
            self.post_message(self.Denied(self))
            self.remove()
        elif event.button.id == "auto-session":
            if not self.future.done():
                self.future.set_result(True)
            self.post_message(self.Approved(self, auto_session=True))
            self.remove()

    def on_key(self, event) -> None:
        """Handle key shortcuts."""
        if self._resolved:
            return  # Already handled by another event

        if event.key == "y":
            self._resolved = True
            if not self.future.done():
                self.future.set_result(True)
            self.post_message(self.Approved(self, auto_session=False))
            self.remove()
            event.stop()
        elif event.key == "n" or event.key == "escape":
            self._resolved = True
            if not self.future.done():
                self.future.set_result(False)
            self.post_message(self.Denied(self))
            self.remove()
            event.stop()
        elif event.key == "a":
            self._resolved = True
            if not self.future.done():
                self.future.set_result(True)
            self.post_message(self.Approved(self, auto_session=True))
            self.remove()
            event.stop()


class ApprovalQueue(Widget):
    """Queue of pending tool approval requests."""

    DEFAULT_CSS = """
    ApprovalQueue {
        layout: vertical;
        height: auto;
        max-height: 10;
        overflow-y: auto;
    }

    ApprovalQueue:empty {
        height: 0;
    }

    ApprovalQueue .queue-header {
        background: $warning;
        color: $text;
        text-style: bold;
        padding: 0 1;
        text-align: center;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize approval queue."""
        super().__init__(**kwargs)
        self._pending: list[ApprovalWidget] = []

    def compose(self) -> ComposeResult:
        """Compose the queue - initially empty."""
        yield from []

    def add_approval(self, tool_name: str, args: dict, future: asyncio.Future) -> None:
        """Add an approval request to the queue.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            future: Future to resolve with approval result
        """
        widget = ApprovalWidget(tool_name, args, future)
        self._pending.append(widget)

        # Add header if first item
        if len(self._pending) == 1:
            self.mount(Static("Pending Approvals", classes="queue-header"))

        self.mount(widget)
        log(f"[APPROVAL] Added to queue: {tool_name}")

    def on_approval_widget_approved(self, event: ApprovalWidget.Approved) -> None:
        """Handle approval - remove from pending list."""
        if event.widget in self._pending:
            self._pending.remove(event.widget)
            self._check_empty()

    def on_approval_widget_denied(self, event: ApprovalWidget.Denied) -> None:
        """Handle denial - remove from pending list."""
        if event.widget in self._pending:
            self._pending.remove(event.widget)
            self._check_empty()

    def _check_empty(self) -> None:
        """Remove header if queue is empty."""
        if not self._pending:
            try:
                header = self.query_one(".queue-header")
                header.remove()
            except Exception:
                pass

    def get_pending_count(self) -> int:
        """Get count of pending approvals."""
        return len(self._pending)


class TabbedAgentPanel(Widget):
    """Unified panel showing approvals, plans, tasks and tools."""

    DEFAULT_CSS = """
    TabbedAgentPanel {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: $panel;
        border-top: heavy $primary-darken-2;
    }

    TabbedAgentPanel .panel-header {
        dock: top;
        height: 1;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }

    TabbedAgentPanel .unified-content {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize agent panel."""
        super().__init__(**kwargs)
        self._event_bus = get_event_bus()

    def compose(self) -> ComposeResult:
        """Compose the unified panel."""
        yield Static("Tasks", classes="panel-header")
        # Approval queue at top (always visible when populated)
        yield ApprovalQueue(id="approval-queue")
        # Unified view with plans, tasks, and tools
        yield UnifiedAgentView(id="unified-view")

    def get_unified_view(self) -> "UnifiedAgentView":
        """Get the unified view component."""
        return self.query_one("#unified-view", UnifiedAgentView)

    def get_approval_queue(self) -> ApprovalQueue:
        """Get the approval queue component."""
        return self.query_one("#approval-queue", ApprovalQueue)

    def add_approval(self, tool_name: str, args: dict, future: asyncio.Future) -> None:
        """Add an approval request to the queue.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            future: Future to resolve with approval result
        """
        queue = self.get_approval_queue()
        queue.add_approval(tool_name, args, future)


class UnifiedAgentView(Widget):
    """Unified view showing plans, tasks, and tool calls in one scrollable area."""

    DEFAULT_CSS = """
    UnifiedAgentView {
        layout: vertical;
        height: 1fr;
    }

    UnifiedAgentView #unified-content {
        height: 1fr;
        padding: 1;
        overflow-y: auto;
    }

    UnifiedAgentView #unified-empty {
        color: $text-muted;
        text-style: italic;
        text-align: center;
        padding-top: 1;
    }

    UnifiedAgentView .section-header {
        color: $primary;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize unified view."""
        super().__init__(**kwargs)
        self._tasks: dict[str, AgentTaskWidget] = {}
        self._plans: dict[str, PlanView] = {}
        self._tools: dict[str, ToolCallWidget] = {}
        self._event_bus = get_event_bus()
        self._fade_delay_ms = 3000

    def compose(self) -> ComposeResult:
        """Compose the unified view."""
        with VerticalScroll(id="unified-content"):
            yield Static("No active tasks", id="unified-empty")

    def on_mount(self) -> None:
        """Subscribe to events on mount."""
        self._event_bus.subscribe("*", self._on_event)

    def on_unmount(self) -> None:
        """Unsubscribe on unmount."""
        self._event_bus.unsubscribe("*", self._on_event)

    async def _on_event(self, event: AgentEvent) -> None:
        """Handle all agent events."""
        source_id = event.source_id

        # Handle planning events
        if event.event_type == AgentEventType.PLAN_STARTED:
            await self._add_plan(event)
            return
        elif event.event_type == AgentEventType.PLAN_STEP_STARTED:
            self._update_plan_step(source_id, event, completed=False)
            return
        elif event.event_type == AgentEventType.PLAN_STEP_COMPLETED:
            self._update_plan_step(source_id, event, completed=True)
            return

        # Handle worker/tool events
        if event.event_type == AgentEventType.WORKER_STARTED:
            await self._add_tool(event)
            return
        elif event.event_type == AgentEventType.WORKER_COMPLETED:
            self._mark_tool_done(event, failed=False)
            return
        elif event.event_type == AgentEventType.WORKER_FAILED:
            self._mark_tool_done(event, failed=True)
            return

        # Ignore main agent events for tasks
        if source_id == "main":
            return

        # Handle sub-agent task events
        if event.event_type == AgentEventType.TASK_STARTED:
            await self._add_task(event)
        elif event.event_type in (AgentEventType.MILESTONE, AgentEventType.PROGRESS):
            self._update_task_progress(source_id, event)
        elif event.event_type == AgentEventType.TOOL_CALLED:
            self._update_task_action(source_id, event)
        elif event.event_type == AgentEventType.TASK_COMPLETED:
            self._mark_task_done(source_id, event, failed=False)
        elif event.event_type == AgentEventType.TASK_FAILED:
            self._mark_task_done(source_id, event, failed=True)

    def _remove_empty_placeholder(self) -> None:
        """Remove the empty placeholder if present."""
        try:
            empty = self.query_one("#unified-empty")
            empty.remove()
        except Exception:
            pass

    def _show_empty_if_needed(self) -> None:
        """Show empty message if nothing active."""
        if not self._tasks and not self._plans and not self._tools:
            try:
                content = self.query_one("#unified-content")
                if content.is_mounted:
                    content.mount(Static("No active tasks", id="unified-empty"))
            except Exception:
                pass

    async def _add_plan(self, event: AgentEvent) -> None:
        """Add a plan view."""
        source_id = event.source_id
        steps = event.data.get("steps", [])
        if not steps:
            return

        def do_add():
            if source_id in self._plans:
                self._plans[source_id].remove()

            self._remove_empty_placeholder()
            plan_view = PlanView(source_id, steps, id=f"plan-{source_id}")
            try:
                content = self.query_one("#unified-content")
                content.mount(plan_view, before=0)
                self._plans[source_id] = plan_view
            except Exception:
                pass

        self.call_later(do_add)

    def _update_plan_step(self, source_id: str, event: AgentEvent, completed: bool) -> None:
        """Update plan step status."""
        step_num = event.data.get("step_num", 0)

        def do_update():
            plan = self._plans.get(source_id)
            if plan and step_num > 0:
                if completed:
                    plan.mark_step_completed(step_num)
                else:
                    plan.mark_step_in_progress(step_num)
                if plan.is_complete():
                    self.set_timer(self._fade_delay_ms / 1000, lambda: self._remove_plan(source_id))

        self.call_later(do_update)

    def _remove_plan(self, source_id: str) -> None:
        """Remove a completed plan."""
        if source_id not in self._plans:
            return
        plan = self._plans.pop(source_id)
        try:
            if plan.is_mounted:
                plan.remove()
        except Exception:
            pass
        self._show_empty_if_needed()

    async def _add_tool(self, event: AgentEvent) -> None:
        """Add a tool call widget."""
        worker_id = event.source_id
        tool_name = event.data.get("tool", "unknown")
        args = event.data.get("args", {})

        def do_add():
            self._remove_empty_placeholder()
            widget = ToolCallWidget(worker_id, tool_name, args, id=f"tool-{worker_id}")
            try:
                content = self.query_one("#unified-content")
                content.mount(widget)
                self._tools[worker_id] = widget
            except Exception:
                pass

        self.call_later(do_add)

    def _mark_tool_done(self, event: AgentEvent, failed: bool) -> None:
        """Mark tool as done and schedule removal."""
        worker_id = event.source_id

        def do_mark():
            widget = self._tools.get(worker_id)
            if widget:
                if failed:
                    widget.mark_failed()
                    delay = self._fade_delay_ms * 2
                else:
                    widget.mark_completed()
                    delay = self._fade_delay_ms
                self.set_timer(delay / 1000, lambda: self._remove_tool(worker_id))

        self.call_later(do_mark)

    def _remove_tool(self, worker_id: str) -> None:
        """Remove a tool widget."""
        if worker_id not in self._tools:
            return
        widget = self._tools.pop(worker_id)
        try:
            if widget.is_mounted:
                widget.remove()
        except Exception:
            pass
        self._show_empty_if_needed()

    async def _add_task(self, event: AgentEvent) -> None:
        """Add a task widget."""
        task_id = event.source_id
        description = event.data.get("description", "Sub-agent task")

        def do_add():
            self._remove_empty_placeholder()
            widget = AgentTaskWidget(task_id, description, id=f"task-{task_id}")
            widget.set_running()
            try:
                content = self.query_one("#unified-content")
                content.mount(widget)
                self._tasks[task_id] = widget
            except Exception:
                pass

        self.call_later(do_add)

    def _update_task_progress(self, task_id: str, event: AgentEvent) -> None:
        """Update task progress."""
        iteration = event.data.get("iteration", 0)
        max_iterations = event.data.get("max_iterations", 25)
        message = event.data.get("message", "")

        def do_update():
            widget = self._tasks.get(task_id)
            if widget:
                widget.update_progress(iteration, max_iterations, message)

        self.call_later(do_update)

    def _update_task_action(self, task_id: str, event: AgentEvent) -> None:
        """Update task action."""
        tool_name = event.data.get("tool", "unknown")
        args = event.data.get("args", {})

        def do_update():
            widget = self._tasks.get(task_id)
            if widget:
                widget.update_action(tool_name, args)

        self.call_later(do_update)

    def _mark_task_done(self, task_id: str, event: AgentEvent, failed: bool) -> None:
        """Mark task as done and schedule removal."""
        result = event.data.get("result", "") if not failed else event.data.get("error", "")

        def do_mark():
            widget = self._tasks.get(task_id)
            if widget:
                if failed:
                    widget.set_failed(result)
                    delay = self._fade_delay_ms * 2
                else:
                    widget.set_completed(result)
                    delay = self._fade_delay_ms
                self.set_timer(delay / 1000, lambda: self._remove_task(task_id))

        self.call_later(do_mark)

    def _remove_task(self, task_id: str) -> None:
        """Remove a task widget."""
        if task_id not in self._tasks:
            return
        widget = self._tasks.pop(task_id)
        try:
            if widget.is_mounted:
                widget.remove()
        except Exception:
            pass
        self._show_empty_if_needed()


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
        self._plans: dict[str, PlanView] = {}  # source_id -> PlanView
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
        # Ignore worker events (handled by ToolCallsView)
        if event.event_type in (
            AgentEventType.WORKER_STARTED,
            AgentEventType.WORKER_COMPLETED,
            AgentEventType.WORKER_FAILED,
        ):
            return

        source_id = event.source_id

        # Handle planning events from any source (including main)
        if event.event_type == AgentEventType.PLAN_STARTED:
            await self._add_plan(event)
            return
        elif event.event_type == AgentEventType.PLAN_STEP_STARTED:
            self._update_plan_step(source_id, event, completed=False)
            return
        elif event.event_type == AgentEventType.PLAN_STEP_COMPLETED:
            self._update_plan_step(source_id, event, completed=True)
            return

        # Ignore other main agent events (sub-agent tasks only)
        if source_id == "main":
            return

        task_id = source_id

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

    async def _add_plan(self, event: AgentEvent) -> None:
        """Add a new plan view."""
        source_id = event.source_id
        steps = event.data.get("steps", [])

        if not steps:
            return

        def do_add_plan():
            # Remove existing plan from this source if any
            if source_id in self._plans:
                self._plans[source_id].remove()

            plan_view = PlanView(
                source_id=source_id,
                steps=steps,
                id=f"plan-{source_id}",
            )

            # Remove empty placeholder if present
            try:
                empty_label = self.query_one("#tasks-empty")
                empty_label.remove()
            except Exception:
                pass

            try:
                content = self.query_one("#tasks-content")
                # Mount plan at the top
                content.mount(plan_view, before=0)
                self._plans[source_id] = plan_view
                log(f"[AGENT_TASKS_VIEW] Mounted plan view: {source_id} with {len(steps)} steps")
            except Exception as e:
                log(f"[AGENT_TASKS_VIEW] Error mounting plan: {e}")

        self.call_later(do_add_plan)

    def _update_plan_step(self, source_id: str, event: AgentEvent, completed: bool) -> None:
        """Update a plan step status.

        Args:
            source_id: Agent source ID
            event: Plan step event
            completed: Whether step is completed or just started
        """
        step_num = event.data.get("step_num", 0)

        def do_update():
            plan_view = self._plans.get(source_id)
            if plan_view and step_num > 0:
                if completed:
                    plan_view.mark_step_completed(step_num)
                else:
                    plan_view.mark_step_in_progress(step_num)

                # Check if plan is complete - schedule removal
                if plan_view.is_complete():
                    self.set_timer(
                        self._fade_delay_ms / 1000,
                        lambda sid=source_id: self._remove_plan(sid)
                    )

        self.call_later(do_update)

    def _remove_plan(self, source_id: str) -> None:
        """Remove a completed plan view."""
        if source_id not in self._plans:
            return  # Already removed

        plan_view = self._plans.pop(source_id)
        try:
            if plan_view.is_mounted:
                plan_view.remove()
        except Exception:
            pass  # Widget already gone

        # Show empty message if nothing left
        if not self._tasks and not self._plans:
            try:
                content = self.query_one("#tasks-content")
                if content.is_mounted:
                    content.mount(Static("No active tasks", id="tasks-empty"))
            except Exception:
                pass

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
        if task_id not in self._tasks:
            return  # Already removed

        widget = self._tasks.pop(task_id)
        try:
            if widget.is_mounted:
                widget.remove()
        except Exception:
            pass  # Widget already gone

        # Show empty message if nothing left
        if not self._tasks and not self._plans:
            try:
                content = self.query_one("#tasks-content")
                if content.is_mounted:
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
        """Clear all completed and failed tasks, and completed plans."""
        to_remove = [
            tid for tid, tw in self._tasks.items()
            if tw.task_status in ("completed", "failed")
        ]

        for task_id in to_remove:
            task_widget = self._tasks.pop(task_id)
            task_widget.remove()

        # Also clear completed plans
        completed_plans = [
            sid for sid, pv in self._plans.items()
            if pv.is_complete()
        ]
        for source_id in completed_plans:
            plan_view = self._plans.pop(source_id)
            plan_view.remove()

        if not self._tasks and not self._plans:
            content = self.query_one("#tasks-content")
            content.mount(Static("No active tasks", id="tasks-empty"))

    def get_running_count(self) -> int:
        """Get count of currently running tasks."""
        return sum(1 for tw in self._tasks.values() if tw.task_status == "running")
