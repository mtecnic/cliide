"""Event bus for agent communication and milestone notifications."""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

from cliide.utils.logger import log


# Lock for thread-safe singleton access
_event_bus_lock = threading.Lock()


class AgentEventType(str, Enum):
    """Types of events that can be emitted."""
    # Task lifecycle
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # Progress milestones
    MILESTONE = "milestone"
    PROGRESS = "progress"

    # Tool events
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    # Discoveries and decisions
    DISCOVERY = "discovery"
    DECISION = "decision"

    # Errors and warnings
    ERROR = "error"
    WARNING = "warning"

    # Approvals
    APPROVAL_NEEDED = "approval_needed"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Checkpoints
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"

    # Memory
    MEMORY_STORED = "memory_stored"
    MEMORY_PROPOSED = "memory_proposed"

    # Worker events (for tool delegation)
    WORKER_STARTED = "worker_started"
    WORKER_COMPLETED = "worker_completed"
    WORKER_FAILED = "worker_failed"

    # Project events
    PROJECT_CHANGED = "project_changed"

    # Planning events
    PLAN_STARTED = "plan_started"
    PLAN_STEP_STARTED = "plan_step_started"
    PLAN_STEP_COMPLETED = "plan_step_completed"


@dataclass
class AgentEvent:
    """An event emitted by an agent."""
    event_type: AgentEventType
    source_id: str  # "main" or sub-agent task_id
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more important (0-10)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "source_id": self.source_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentEvent":
        """Create from dictionary."""
        return cls(
            event_type=AgentEventType(data["event_type"]),
            source_id=data["source_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data.get("data", {}),
            priority=data.get("priority", 0),
        )

    def format_message(self) -> str:
        """Format event as human-readable message."""
        icon = {
            AgentEventType.TASK_STARTED: "▶️",
            AgentEventType.TASK_COMPLETED: "✅",
            AgentEventType.TASK_FAILED: "❌",
            AgentEventType.TASK_CANCELLED: "🚫",
            AgentEventType.MILESTONE: "🎯",
            AgentEventType.PROGRESS: "📊",
            AgentEventType.TOOL_CALLED: "🔧",
            AgentEventType.TOOL_COMPLETED: "✔️",
            AgentEventType.TOOL_FAILED: "⚠️",
            AgentEventType.DISCOVERY: "💡",
            AgentEventType.DECISION: "🤔",
            AgentEventType.ERROR: "❌",
            AgentEventType.WARNING: "⚠️",
            AgentEventType.APPROVAL_NEEDED: "🔐",
            AgentEventType.APPROVAL_GRANTED: "✅",
            AgentEventType.APPROVAL_DENIED: "🚫",
            AgentEventType.CHECKPOINT_CREATED: "💾",
            AgentEventType.CHECKPOINT_RESTORED: "📂",
            AgentEventType.MEMORY_STORED: "🧠",
            AgentEventType.MEMORY_PROPOSED: "💭",
            AgentEventType.WORKER_STARTED: "⚡",
            AgentEventType.WORKER_COMPLETED: "✔️",
            AgentEventType.WORKER_FAILED: "💥",
            AgentEventType.PROJECT_CHANGED: "📁",
            AgentEventType.PLAN_STARTED: "📋",
            AgentEventType.PLAN_STEP_STARTED: "▶️",
            AgentEventType.PLAN_STEP_COMPLETED: "✅",
        }.get(self.event_type, "•")

        message = self.data.get("message", str(self.data))
        return f"{icon} [{self.source_id}] {self.event_type.value}: {message}"


# Type for event callbacks
EventCallback = Callable[[AgentEvent], Awaitable[None]]


class AgentEventBus:
    """Event bus for milestone-based agent communication.

    Supports pub/sub pattern for event notifications between agents.
    Maintains event history for context.
    """

    def __init__(self, max_history: int = 100):
        """Initialize event bus.

        Args:
            max_history: Maximum events to keep in history
        """
        self.max_history = max_history

        # Subscribers: event_type -> list of callbacks
        self._subscribers: dict[str, list[EventCallback]] = {}

        # Event queue for async processing
        self._event_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

        # Event history
        self._history: list[AgentEvent] = []

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Pending approval requests: request_id -> Future
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}

    def subscribe(
        self,
        event_type: AgentEventType | str,
        callback: EventCallback,
    ) -> None:
        """Subscribe to events of a type.

        Args:
            event_type: Event type to subscribe to, or "*" for all events
            callback: Async callback function to call on event
        """
        key = event_type.value if isinstance(event_type, AgentEventType) else event_type
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)

    def unsubscribe(
        self,
        event_type: AgentEventType | str,
        callback: EventCallback,
    ) -> None:
        """Unsubscribe from events.

        Args:
            event_type: Event type to unsubscribe from
            callback: Callback to remove
        """
        key = event_type.value if isinstance(event_type, AgentEventType) else event_type
        if key in self._subscribers:
            try:
                self._subscribers[key].remove(callback)
            except ValueError:
                pass

    async def emit(self, event: AgentEvent) -> None:
        """Emit an event to all subscribers.

        Args:
            event: The event to emit
        """
        async with self._lock:
            # Add to history
            self._history.append(event)

            # Prune history if needed
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]

        # Get callbacks for this event type and wildcard
        callbacks = []
        event_key = event.event_type.value

        if event_key in self._subscribers:
            callbacks.extend(self._subscribers[event_key])
        if "*" in self._subscribers:
            callbacks.extend(self._subscribers["*"])

        # Call all callbacks
        log(f"[EVENT_BUS] Emitting {event.event_type.value} from {event.source_id}, {len(callbacks)} callbacks")
        for callback in callbacks:
            try:
                await callback(event)
            except Exception as e:
                # Log callback errors
                log(f"[EVENT_BUS] Callback error: {type(e).__name__}: {e}")

    async def emit_milestone(
        self,
        source_id: str,
        message: str,
        iteration: int | None = None,
        priority: int = 0,
    ) -> None:
        """Convenience method to emit a milestone event.

        Args:
            source_id: Source of the event
            message: Milestone message
            iteration: Optional iteration number
            priority: Event priority
        """
        data: dict[str, Any] = {"message": message}
        if iteration is not None:
            data["iteration"] = iteration

        await self.emit(AgentEvent(
            event_type=AgentEventType.MILESTONE,
            source_id=source_id,
            data=data,
            priority=priority,
        ))

    async def emit_tool_called(
        self,
        source_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> None:
        """Convenience method to emit a tool called event.

        Args:
            source_id: Source of the event
            tool_name: Name of the tool
            args: Tool arguments
        """
        await self.emit(AgentEvent(
            event_type=AgentEventType.TOOL_CALLED,
            source_id=source_id,
            data={"tool": tool_name, "args": args},
        ))

    async def emit_discovery(
        self,
        source_id: str,
        key: str,
        value: Any,
        priority: int = 5,
    ) -> None:
        """Convenience method to emit a discovery event.

        Args:
            source_id: Source of the event
            key: Discovery key/title
            value: What was discovered
            priority: Event priority
        """
        await self.emit(AgentEvent(
            event_type=AgentEventType.DISCOVERY,
            source_id=source_id,
            data={"key": key, "value": value, "message": f"{key}: {value}"},
            priority=priority,
        ))

    async def request_approval(
        self,
        source_id: str,
        tool_name: str,
        args: dict[str, Any],
        risk_level: str,
        timeout: float = 60.0,
    ) -> bool:
        """Request approval and wait for response.

        Args:
            source_id: Requesting agent
            tool_name: Tool needing approval
            args: Tool arguments
            risk_level: Risk level string
            timeout: Timeout in seconds

        Returns:
            True if approved, False if denied or timed out
        """
        import uuid
        request_id = str(uuid.uuid4())[:8]

        # Create future for response
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending_approvals[request_id] = future

        # Emit approval request
        await self.emit(AgentEvent(
            event_type=AgentEventType.APPROVAL_NEEDED,
            source_id=source_id,
            data={
                "request_id": request_id,
                "tool": tool_name,
                "args": args,
                "risk_level": risk_level,
                "message": f"Approval needed for {tool_name} ({risk_level} risk)",
            },
            priority=10,  # High priority
        ))

        try:
            # Wait for approval with timeout
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return False
        finally:
            # Clean up
            self._pending_approvals.pop(request_id, None)

    async def respond_to_approval(
        self,
        request_id: str,
        approved: bool,
        responder_id: str = "main",
    ) -> bool:
        """Respond to an approval request.

        Args:
            request_id: The approval request ID
            approved: Whether to approve
            responder_id: Who is responding

        Returns:
            True if response was delivered, False if request not found
        """
        future = self._pending_approvals.get(request_id)
        if future is None:
            return False

        if not future.done():
            future.set_result(approved)

        # Emit response event
        await self.emit(AgentEvent(
            event_type=AgentEventType.APPROVAL_GRANTED if approved else AgentEventType.APPROVAL_DENIED,
            source_id=responder_id,
            data={
                "request_id": request_id,
                "approved": approved,
                "message": f"Request {request_id} {'approved' if approved else 'denied'}",
            },
        ))

        return True

    async def emit_plan_started(
        self,
        source_id: str,
        steps: list[str],
    ) -> None:
        """Emit a plan started event.

        Args:
            source_id: Source of the event
            steps: List of plan step descriptions
        """
        await self.emit(AgentEvent(
            event_type=AgentEventType.PLAN_STARTED,
            source_id=source_id,
            data={
                "steps": steps,
                "total_steps": len(steps),
                "message": f"Planning {len(steps)} steps",
            },
            priority=5,
        ))

    async def emit_plan_step(
        self,
        source_id: str,
        step_num: int,
        description: str,
        completed: bool = False,
    ) -> None:
        """Emit a plan step event.

        Args:
            source_id: Source of the event
            step_num: Step number (1-indexed)
            description: Step description
            completed: Whether step is completed or just started
        """
        event_type = (
            AgentEventType.PLAN_STEP_COMPLETED if completed
            else AgentEventType.PLAN_STEP_STARTED
        )
        await self.emit(AgentEvent(
            event_type=event_type,
            source_id=source_id,
            data={
                "step_num": step_num,
                "description": description,
                "message": f"Step {step_num}: {description}",
            },
        ))

    def get_pending_approvals(self) -> list[AgentEvent]:
        """Get list of pending approval requests.

        Returns:
            List of APPROVAL_NEEDED events that haven't been responded to
        """
        pending_ids = set(self._pending_approvals.keys())
        return [
            e for e in self._history
            if e.event_type == AgentEventType.APPROVAL_NEEDED
            and e.data.get("request_id") in pending_ids
        ]

    def get_recent_events(
        self,
        source_id: str | None = None,
        event_types: list[AgentEventType] | None = None,
        limit: int = 20,
    ) -> list[AgentEvent]:
        """Get recent events from history.

        Args:
            source_id: Optional filter by source
            event_types: Optional filter by event types
            limit: Maximum events to return

        Returns:
            List of events, most recent first
        """
        events = list(reversed(self._history))

        if source_id is not None:
            events = [e for e in events if e.source_id == source_id]

        if event_types is not None:
            type_values = {t.value for t in event_types}
            events = [e for e in events if e.event_type.value in type_values]

        return events[:limit]

    def get_events_for_context(
        self,
        source_ids: list[str] | None = None,
        max_events: int = 10,
    ) -> str:
        """Get events formatted for prompt context.

        Args:
            source_ids: Optional list of sources to include
            max_events: Maximum events to include

        Returns:
            Formatted string for prompt injection
        """
        events = list(reversed(self._history))

        if source_ids is not None:
            events = [e for e in events if e.source_id in source_ids]

        events = events[:max_events]

        if not events:
            return ""

        lines = ["## Recent Agent Activity"]
        for event in events:
            lines.append(event.format_message())

        return "\n".join(lines)

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics.

        Returns:
            Statistics dict
        """
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}

        for event in self._history:
            by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
            by_source[event.source_id] = by_source.get(event.source_id, 0) + 1

        return {
            "total_events": len(self._history),
            "by_type": by_type,
            "by_source": by_source,
            "pending_approvals": len(self._pending_approvals),
            "subscriber_count": sum(len(s) for s in self._subscribers.values()),
        }


# Global event bus instance
_global_event_bus: AgentEventBus | None = None


def get_event_bus() -> AgentEventBus:
    """Get the global event bus instance (thread-safe).

    Returns:
        Global AgentEventBus instance
    """
    global _global_event_bus
    if _global_event_bus is None:
        with _event_bus_lock:
            # Double-check inside lock
            if _global_event_bus is None:
                _global_event_bus = AgentEventBus()
    return _global_event_bus


def reset_event_bus() -> None:
    """Reset the global event bus instance (thread-safe)."""
    global _global_event_bus
    with _event_bus_lock:
        _global_event_bus = None
