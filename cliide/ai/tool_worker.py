"""Tool worker pool for async tool execution delegation."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from cliide.ai.event_bus import AgentEvent, AgentEventType, get_event_bus
from cliide.ai.tools.base import ToolRegistry, ToolResult


class WorkerStatus(str, Enum):
    """Status of a tool worker."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ToolWorker:
    """Represents a single tool execution worker."""

    worker_id: str
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    parent_task_id: str | None = None  # For grouping in UI
    status: WorkerStatus = WorkerStatus.PENDING
    result: ToolResult | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


# Tools that are fast enough to run inline (no delegation needed)
INLINE_TOOLS = {
    "list_agents",
    "get_agent_result",
    "list_pending_approvals",
    "recall_memory",
    "approve_subagent",  # Needs immediate response
}

# Tools that are safe to run in parallel (read-only, no side effects)
PARALLEL_SAFE_TOOLS = {
    "read_file",
    "list_directory",
    "grep",
    "search_files",
    "find_symbol",
    "extract_symbols",
    "get_file_summary",
    "git_status",
    "git_diff",
    "git_log",
    "recall_memory",
    "web_search",
    "fetch_url",
}

# Tools that must run sequentially (have side effects or need ordering)
SEQUENTIAL_TOOLS = {
    "write_file",
    "edit_file",
    "run_command",
    "git_commit",
    "git_add",
    "git_push",
    "git_checkout",
    "store_memory",
    "delete_file",
    "create_directory",
}


def classify_tool(tool_name: str) -> str:
    """Classify a tool as 'inline', 'parallel', or 'sequential'.

    Args:
        tool_name: Name of the tool

    Returns:
        Classification: 'inline', 'parallel', or 'sequential'
    """
    if tool_name in INLINE_TOOLS:
        return "inline"
    elif tool_name in SEQUENTIAL_TOOLS:
        return "sequential"
    else:
        # Default to parallel for unknown tools (read operations)
        return "parallel"


class ToolWorkerPool:
    """Manages concurrent tool execution workers.

    Executes tools asynchronously in a worker pool, emitting events
    for UI updates. Main agent submits tools and waits for results.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_concurrent: int = 10,
        timeout_seconds: int = 60,
        confirmation_mode: str = "moderate",
    ):
        """Initialize the worker pool.

        Args:
            tool_registry: Registry containing tools to execute
            max_concurrent: Maximum parallel workers
            timeout_seconds: Per-tool timeout in seconds
            confirmation_mode: Tool confirmation mode
        """
        self._tool_registry = tool_registry
        self._max_concurrent = max_concurrent
        self._timeout_seconds = timeout_seconds
        self._confirmation_mode = confirmation_mode

        self._event_bus = get_event_bus()

        # Worker tracking
        self._workers: dict[str, ToolWorker] = {}
        self._running_tasks: dict[str, asyncio.Task[None]] = {}

        # Results and synchronization
        self._results: dict[str, ToolResult] = {}
        self._result_events: dict[str, asyncio.Event] = {}

        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def submit(
        self,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        parent_task_id: str | None = None,
    ) -> str:
        """Submit a tool for async execution.

        Args:
            tool_call_id: Unique ID for this tool call
            tool_name: Name of the tool to execute
            args: Tool arguments
            parent_task_id: Optional parent task ID for grouping

        Returns:
            Worker ID for tracking
        """
        worker_id = str(uuid.uuid4())[:8]

        # Create worker
        worker = ToolWorker(
            worker_id=worker_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            args=args,
            parent_task_id=parent_task_id,
        )
        self._workers[worker_id] = worker

        # Create result event for waiting
        self._result_events[tool_call_id] = asyncio.Event()

        # Start execution task
        task = asyncio.create_task(self._execute_worker(worker))
        self._running_tasks[worker_id] = task

        return worker_id

    async def _execute_worker(self, worker: ToolWorker) -> None:
        """Execute a single worker task.

        Args:
            worker: The worker to execute
        """
        async with self._semaphore:
            worker.status = WorkerStatus.RUNNING
            worker.started_at = datetime.now()

            # Emit WORKER_STARTED event
            await self._event_bus.emit(
                AgentEvent(
                    event_type=AgentEventType.WORKER_STARTED,
                    source_id=worker.worker_id,
                    data={
                        "tool_call_id": worker.tool_call_id,
                        "tool": worker.tool_name,
                        "args": worker.args,
                        "parent_task_id": worker.parent_task_id,
                    },
                )
            )

            try:
                # Execute the tool with timeout
                result = await asyncio.wait_for(
                    self._tool_registry.execute_tool(
                        worker.tool_name,
                        worker.args,
                        confirmation_mode=self._confirmation_mode,
                    ),
                    timeout=self._timeout_seconds,
                )

                worker.result = result
                worker.status = WorkerStatus.COMPLETED

                # Emit WORKER_COMPLETED event
                await self._event_bus.emit(
                    AgentEvent(
                        event_type=AgentEventType.WORKER_COMPLETED,
                        source_id=worker.worker_id,
                        data={
                            "tool_call_id": worker.tool_call_id,
                            "tool": worker.tool_name,
                            "success": result.success,
                            "duration_ms": int(
                                (datetime.now() - worker.started_at).total_seconds() * 1000
                            )
                            if worker.started_at
                            else 0,
                        },
                    )
                )

            except asyncio.TimeoutError:
                worker.status = WorkerStatus.FAILED
                worker.error = f"Tool timed out after {self._timeout_seconds}s"
                worker.result = ToolResult(success=False, error=worker.error)

                await self._event_bus.emit(
                    AgentEvent(
                        event_type=AgentEventType.WORKER_FAILED,
                        source_id=worker.worker_id,
                        data={
                            "tool_call_id": worker.tool_call_id,
                            "tool": worker.tool_name,
                            "error": worker.error,
                        },
                    )
                )

            except asyncio.CancelledError:
                worker.status = WorkerStatus.CANCELLED
                worker.error = "Worker was cancelled"
                worker.result = ToolResult(success=False, error=worker.error)
                raise  # Re-raise to propagate cancellation

            except Exception as e:
                worker.status = WorkerStatus.FAILED
                worker.error = str(e)
                worker.result = ToolResult(
                    success=False, error=f"Tool execution failed: {e}"
                )

                await self._event_bus.emit(
                    AgentEvent(
                        event_type=AgentEventType.WORKER_FAILED,
                        source_id=worker.worker_id,
                        data={
                            "tool_call_id": worker.tool_call_id,
                            "tool": worker.tool_name,
                            "error": worker.error,
                        },
                    )
                )

            finally:
                worker.completed_at = datetime.now()

                # Store result and signal waiters
                if worker.result:
                    self._results[worker.tool_call_id] = worker.result

                if worker.tool_call_id in self._result_events:
                    self._result_events[worker.tool_call_id].set()

                # Clean up running task
                self._running_tasks.pop(worker.worker_id, None)

    async def wait_for_result(
        self,
        tool_call_id: str,
        timeout: float | None = None,
    ) -> ToolResult:
        """Wait for a specific tool's result.

        Args:
            tool_call_id: The tool call ID to wait for
            timeout: Optional timeout (uses default if not specified)

        Returns:
            The tool result
        """
        timeout = timeout or self._timeout_seconds

        if tool_call_id not in self._result_events:
            return ToolResult(success=False, error=f"Unknown tool_call_id: {tool_call_id}")

        try:
            await asyncio.wait_for(
                self._result_events[tool_call_id].wait(),
                timeout=timeout,
            )
            return self._results.get(
                tool_call_id,
                ToolResult(success=False, error="Result not found"),
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Timeout waiting for tool result after {timeout}s",
            )

    async def wait_for_all(
        self,
        tool_call_ids: list[str],
        timeout: float | None = None,
    ) -> dict[str, ToolResult]:
        """Wait for multiple tools to complete.

        Args:
            tool_call_ids: List of tool call IDs to wait for
            timeout: Overall timeout for all tools

        Returns:
            Dict mapping tool_call_id to result
        """
        timeout = timeout or (self._timeout_seconds * 2)  # Allow more time for batches

        results: dict[str, ToolResult] = {}

        try:
            async with asyncio.timeout(timeout):
                for tool_call_id in tool_call_ids:
                    if tool_call_id in self._result_events:
                        await self._result_events[tool_call_id].wait()
                        results[tool_call_id] = self._results.get(
                            tool_call_id,
                            ToolResult(success=False, error="Result not found"),
                        )
                    else:
                        results[tool_call_id] = ToolResult(
                            success=False,
                            error=f"Unknown tool_call_id: {tool_call_id}",
                        )

        except asyncio.TimeoutError:
            # Return whatever we have, mark remaining as timed out
            for tool_call_id in tool_call_ids:
                if tool_call_id not in results:
                    results[tool_call_id] = ToolResult(
                        success=False,
                        error=f"Overall wait timed out after {timeout}s",
                    )

        return results

    def get_result(self, tool_call_id: str) -> ToolResult | None:
        """Get result if available (non-blocking).

        Args:
            tool_call_id: The tool call ID

        Returns:
            Result if available, None otherwise
        """
        return self._results.get(tool_call_id)

    def get_pending_count(self) -> int:
        """Get number of tools still executing."""
        return len(self._running_tasks)

    def get_worker(self, worker_id: str) -> ToolWorker | None:
        """Get worker by ID."""
        return self._workers.get(worker_id)

    async def cancel(self, worker_id: str) -> bool:
        """Cancel a running worker.

        Args:
            worker_id: Worker to cancel

        Returns:
            True if cancelled, False if not found or already done
        """
        task = self._running_tasks.get(worker_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Cancel all running workers and clean up.

        Args:
            timeout: Time to wait for cancellations
        """
        # Cancel all running tasks
        for task in list(self._running_tasks.values()):
            task.cancel()

        # Wait for cancellations to complete
        if self._running_tasks:
            await asyncio.wait(
                list(self._running_tasks.values()),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )

        # Clean up
        self._workers.clear()
        self._running_tasks.clear()
        self._results.clear()
        self._result_events.clear()


def should_delegate(tool_name: str) -> bool:
    """Check if a tool should be delegated to worker pool.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool should be delegated, False for inline execution
    """
    return tool_name not in INLINE_TOOLS
