"""Sub-agent spawning and management system."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

from cliide.ai.tools.base import (
    Tool, ToolCategory, ToolResult, RiskLevel,
    SubAgentTrustLevel, get_approval_target
)
from cliide.ai.event_bus import AgentEventBus, AgentEvent, AgentEventType, get_event_bus
from cliide.utils.logger import log


class SubAgentStatus(str, Enum):
    """Status of a sub-agent."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentTask:
    """Represents a sub-agent task."""
    task_id: str
    description: str
    status: SubAgentStatus = SubAgentStatus.PENDING
    trust_level: SubAgentTrustLevel = SubAgentTrustLevel.READ_ONLY
    result: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: list[str] = field(default_factory=list)
    tool_calls_count: int = 0
    discoveries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status.value,
            "trust_level": self.trust_level.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "tool_calls_count": self.tool_calls_count,
            "discoveries": self.discoveries,
        }


class SubAgentManager:
    """Manage spawned sub-agents for parallel task execution."""

    def __init__(
        self,
        vllm_client,
        workspace_root: str | Path,
        tool_registry,
        max_concurrent: int = 10,
        event_bus: AgentEventBus | None = None,
        user_confirmation_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
    ):
        """Initialize sub-agent manager.

        Args:
            vllm_client: VLLM client for AI calls
            workspace_root: Root directory of workspace
            tool_registry: Tool registry for sub-agents
            max_concurrent: Maximum concurrent sub-agents
            event_bus: Event bus for milestone communication
            user_confirmation_callback: Callback for user confirmations (HIGH risk)
        """
        self.client = vllm_client
        self.workspace_root = Path(workspace_root)
        self.tool_registry = tool_registry
        self._max_concurrent = max_concurrent
        self.event_bus = event_bus or get_event_bus()
        self.user_confirmation_callback = user_confirmation_callback

        self._tasks: dict[str, SubAgentTask] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks_lock = asyncio.Lock()  # Protects _tasks from concurrent access

    @property
    def max_concurrent(self) -> int:
        """Get current max concurrent limit."""
        return self._max_concurrent

    @max_concurrent.setter
    def max_concurrent(self, value: int) -> None:
        """Set max concurrent (takes effect on next spawn, not in-flight tasks)."""
        from cliide.utils.logger import log
        log(f"[SUBAGENT] max_concurrent changed to {value} (takes effect on restart)")
        self._max_concurrent = value
        # Don't recreate semaphore - would orphan in-flight tasks

    async def spawn(
        self,
        task_description: str,
        allowed_tools: list[str] | None = None,
        max_iterations: int = 25,
        timeout: int = 180,
        trust_level: SubAgentTrustLevel = SubAgentTrustLevel.READ_ONLY,
    ) -> str:
        """Spawn a sub-agent for a specific task.

        Args:
            task_description: Description of the task for the sub-agent
            allowed_tools: List of tool names the sub-agent can use (None = read-only tools)
            max_iterations: Maximum iterations for the sub-agent
            timeout: Timeout in seconds
            trust_level: Trust level for the sub-agent

        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())[:8]

        # Create task record
        task = SubAgentTask(
            task_id=task_id,
            description=task_description,
            trust_level=trust_level,
        )
        self._tasks[task_id] = task

        # Default to read-only tools if not specified
        if allowed_tools is None:
            allowed_tools = [
                "read_file", "list_directory", "grep", "search_files",
                "find_symbol", "extract_symbols", "get_file_summary",
                "git_status", "git_diff", "git_log"
            ]

        # Emit task started event
        await self.event_bus.emit(AgentEvent(
            event_type=AgentEventType.TASK_STARTED,
            source_id=task_id,
            data={
                "description": task_description,
                "trust_level": trust_level.value,
                "message": f"Sub-agent started: {task_description[:50]}...",
            },
            priority=3,
        ))

        # Start the sub-agent in background
        async_task = asyncio.create_task(
            self._run_sub_agent(task_id, task_description, allowed_tools, max_iterations, timeout)
        )
        self._running_tasks[task_id] = async_task

        return task_id

    async def _run_sub_agent(
        self,
        task_id: str,
        task_description: str,
        allowed_tools: list[str],
        max_iterations: int,
        timeout: int,
    ) -> None:
        """Run a sub-agent task.

        Args:
            task_id: Task ID
            task_description: Task description
            allowed_tools: Allowed tool names
            max_iterations: Maximum iterations
            timeout: Timeout in seconds
        """
        from cliide.core.config import get_config

        task = self._tasks[task_id]

        # Prevent nested sub-agent spawning (no fan-out from sub-agents)
        # This follows OpenClaw's pattern to prevent runaway recursion
        config = get_config()
        if not config.subagent.allow_nested_spawn:
            # Remove spawn_agent and related tools from allowed_tools
            nested_spawn_tools = {"spawn_agent", "list_agents", "get_agent_result"}
            allowed_tools = [t for t in allowed_tools if t not in nested_spawn_tools]
            log(f"[SUB_AGENT] Filtered nested spawn tools. Remaining: {allowed_tools}")

        async with self._semaphore:
            task.status = SubAgentStatus.RUNNING
            task.started_at = datetime.now()

            try:
                # Filter tool definitions
                all_tools = self.tool_registry.to_openai_functions()
                filtered_tools = [t for t in all_tools if t["function"]["name"] in allowed_tools]

                if not filtered_tools:
                    raise ValueError(f"No valid tools available: {allowed_tools}")

                # Build sub-agent prompt
                system_prompt = f"""You are a focused sub-agent working on a specific task.
Your task: {task_description}

IMPORTANT:
- Focus ONLY on the assigned task
- Use the available tools to gather information or make changes
- Report your findings clearly and concisely
- If you cannot complete the task, explain why

Available tools: {', '.join(allowed_tools)}
"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Complete this task: {task_description}"}
                ]

                # Run agent loop
                iteration = 0
                result_text = ""
                milestone_interval = 3  # Emit milestone every N iterations
                collected_findings = []  # Accumulate tool outputs for result

                while iteration < max_iterations:
                    iteration += 1

                    # Emit milestone events periodically
                    if iteration == 1 or iteration % milestone_interval == 0:
                        await self.event_bus.emit_milestone(
                            source_id=task_id,
                            message=f"Iteration {iteration}/{max_iterations}: working on {task_description[:30]}...",
                            iteration=iteration,
                            priority=2 if iteration == 1 else 1,
                        )

                    # Call AI with tools
                    try:
                        response = await asyncio.wait_for(
                            self.client.chat_completion(
                                messages=messages,
                                tools=filtered_tools,
                                stream=False
                            ),
                            timeout=60  # Fixed timeout per API call
                        )
                    except asyncio.TimeoutError:
                        raise TimeoutError(f"Sub-agent API call timed out after 60s (iteration {iteration})")

                    if not response.get("choices"):
                        break

                    choices = response["choices"]
                    if not isinstance(choices, list):
                        log(f"[SUB_AGENT] Unexpected choices type: {type(choices)}, value: {choices}")
                        raise TypeError(f"Expected list for choices, got {type(choices).__name__}")

                    choice = choices[0]
                    message = choice.get("message", {}) if isinstance(choice, dict) else choice
                    tool_calls = message.get("tool_calls", []) if isinstance(message, dict) else []

                    # No tool calls - we have the final answer
                    if not tool_calls:
                        result_text = message.get("content", "")
                        break

                    # Process tool calls
                    tool_results = []
                    for tool_call in tool_calls:
                        function = tool_call["function"]
                        tool_name = function["name"]

                        # Validate tool is allowed
                        if tool_name not in allowed_tools:
                            tool_results.append({
                                "tool_call_id": tool_call.get("id"),
                                "role": "tool",
                                "name": tool_name,
                                "content": f"Error: Tool {tool_name} not allowed for this sub-agent"
                            })
                            continue

                        # Parse arguments
                        import json
                        try:
                            args = json.loads(function.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}

                        # Log progress
                        task.progress.append(f"[{iteration}] Using {tool_name}")
                        task.tool_calls_count += 1

                        # Emit tool called event
                        await self.event_bus.emit_tool_called(task_id, tool_name, args)

                        # Check approval routing based on trust level
                        tool = self.tool_registry.get(tool_name)
                        if tool:
                            risk_level = tool.classify_risk(args)
                            approval_target = get_approval_target(task.trust_level, risk_level)

                            if approval_target == "denied":
                                tool_results.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "role": "tool",
                                    "name": tool_name,
                                    "content": f"Error: Operation denied - trust level {task.trust_level.value} cannot perform {risk_level.value} risk operations"
                                })
                                continue

                            elif approval_target == "main_agent":
                                # Request approval via event bus
                                approved = await self.event_bus.request_approval(
                                    source_id=task_id,
                                    tool_name=tool_name,
                                    args=args,
                                    risk_level=risk_level.value,
                                    timeout=30.0,
                                )
                                if not approved:
                                    tool_results.append({
                                        "tool_call_id": tool_call.get("id"),
                                        "role": "tool",
                                        "name": tool_name,
                                        "content": "Error: Operation denied by main agent"
                                    })
                                    continue

                            elif approval_target == "user":
                                # Request user confirmation
                                if self.user_confirmation_callback:
                                    approved = await self.user_confirmation_callback(tool_name, args)
                                    if not approved:
                                        tool_results.append({
                                            "tool_call_id": tool_call.get("id"),
                                            "role": "tool",
                                            "name": tool_name,
                                            "content": "Error: Operation denied by user"
                                        })
                                        continue
                                else:
                                    # No callback, deny by default for safety
                                    tool_results.append({
                                        "tool_call_id": tool_call.get("id"),
                                        "role": "tool",
                                        "name": tool_name,
                                        "content": "Error: High-risk operation requires user approval, but no approval mechanism available"
                                    })
                                    continue

                        # Execute tool with error recovery
                        try:
                            result = await self.tool_registry.execute_tool(
                                tool_name, args, confirmation_mode="auto"
                            )
                        except Exception as e:
                            # Per-tool error recovery - don't crash the whole agent
                            log(f"[SUBAGENT] Tool {tool_name} failed: {e}")
                            from cliide.ai.tools.base import ToolResult
                            result = ToolResult(success=False, error=f"Tool execution failed: {e}")

                        result_msg = result.to_message()
                        tool_results.append({
                            "tool_call_id": tool_call.get("id"),
                            "role": "tool",
                            "name": tool_name,
                            "content": result_msg
                        })

                        # Capture significant findings for result
                        if result.success and len(result_msg) > 50:
                            collected_findings.append(f"[{tool_name}]: {result_msg[:500]}")

                    # Add to conversation
                    messages.append(message)
                    messages.extend(tool_results)

                # If no explicit result yet, ask for a summary of findings
                if not result_text and messages:
                    messages.append({
                        "role": "user",
                        "content": "Based on what you've discovered, provide a brief summary of your findings. Do not use any more tools - just summarize what you learned."
                    })
                    try:
                        summary_response = await asyncio.wait_for(
                            self.client.chat_completion(
                                messages=messages,
                                tools=None,  # No tools for summary
                                stream=False
                            ),
                            timeout=30
                        )
                        if summary_response.get("choices"):
                            result_text = summary_response["choices"][0]["message"].get("content", "")
                    except Exception:
                        pass  # Keep empty result if summary fails

                # Task completed - include collected findings in result
                task.status = SubAgentStatus.COMPLETED
                if collected_findings:
                    findings_text = "\n\n".join(collected_findings[-10:])  # Last 10 findings
                    if result_text:
                        task.result = f"{result_text}\n\n## Tool Findings:\n{findings_text}"
                    else:
                        task.result = f"## Tool Findings:\n{findings_text}"
                else:
                    task.result = result_text or "Task completed (no explicit result)"

                # Emit completion event
                await self.event_bus.emit(AgentEvent(
                    event_type=AgentEventType.TASK_COMPLETED,
                    source_id=task_id,
                    data={
                        "result": task.result[:200] if task.result else "",
                        "iterations": iteration,
                        "tool_calls": task.tool_calls_count,
                        "message": f"Sub-agent completed: {task_description[:30]}...",
                    },
                    priority=4,
                ))
                task.completed_at = datetime.now()

            except Exception as e:
                task.status = SubAgentStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()

                # Emit failure event
                await self.event_bus.emit(AgentEvent(
                    event_type=AgentEventType.TASK_FAILED,
                    source_id=task_id,
                    data={
                        "error": str(e),
                        "description": task_description[:50],
                        "message": f"Sub-agent failed: {str(e)[:100]}",
                    },
                    priority=6,
                ))

            finally:
                # Clean up running task reference
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]
                # Clean up old completed tasks to prevent memory leak
                await self._cleanup_old_tasks()

    async def _cleanup_old_tasks(self, max_completed: int = 50) -> None:
        """Remove old completed tasks to prevent memory leak."""
        async with self._tasks_lock:
            completed_tasks = [
                (tid, task) for tid, task in self._tasks.items()
                if task.status in [SubAgentStatus.COMPLETED, SubAgentStatus.FAILED]
            ]
            if len(completed_tasks) > max_completed:
                # Sort by completion time, remove oldest
                completed_tasks.sort(key=lambda x: x[1].completed_at or x[1].started_at or 0)
                for tid, _ in completed_tasks[:-max_completed]:
                    del self._tasks[tid]

    async def check_status(self, task_id: str) -> dict[str, Any] | None:
        """Check sub-agent status.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None

    async def get_result(self, task_id: str, wait: bool = False, timeout: int = 60) -> dict[str, Any] | None:
        """Get sub-agent result.

        Args:
            task_id: Task ID
            wait: Whether to wait for completion
            timeout: Wait timeout in seconds

        Returns:
            Task result dict or None if not found
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        if wait and task.status in [SubAgentStatus.PENDING, SubAgentStatus.RUNNING]:
            # Wait for completion
            async_task = self._running_tasks.get(task_id)
            if async_task:
                try:
                    await asyncio.wait_for(async_task, timeout=timeout)
                except asyncio.TimeoutError:
                    return {"error": f"Timeout waiting for task {task_id}"}

        return task.to_dict()

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running sub-agent.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found or already done
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status not in [SubAgentStatus.PENDING, SubAgentStatus.RUNNING]:
            return False

        # Cancel the async task
        async_task = self._running_tasks.get(task_id)
        if async_task:
            async_task.cancel()

        task.status = SubAgentStatus.CANCELLED
        task.completed_at = datetime.now()

        return True

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks.

        Returns:
            List of task dicts
        """
        return [task.to_dict() for task in self._tasks.values()]


# Tools for sub-agent management

class SpawnAgentTool(Tool):
    """Tool to spawn a sub-agent for parallel task execution."""

    def __init__(self, sub_agent_manager: SubAgentManager):
        """Initialize the tool.

        Args:
            sub_agent_manager: Sub-agent manager instance
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False  # Spawning is safe
        self._risk_level = RiskLevel.LOW
        self.manager = sub_agent_manager

    @property
    def name(self) -> str:
        return "spawn_agent"

    @property
    def description(self) -> str:
        return """IMPORTANT: Spawn sub-agents for faster parallel execution.

ALWAYS use spawn_agent for:
- Exploring/scanning directories or project structure
- Searching across multiple files or areas
- Summarizing codebases or large file sets
- Any task requiring many sequential tool calls

Example: To scan a project, spawn 2-3 agents for different directories simultaneously.
Much faster than sequential tool calls! Sub-agents have read-only tools by default."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of the task for the sub-agent"
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: List of tools the sub-agent can use. Default is read-only tools."
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum iterations for the sub-agent (default: 25)"
                }
            },
            "required": ["task"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Spawn a sub-agent."""
        task_description = args.get("task", "")
        tools = args.get("tools")
        max_iterations = args.get("max_iterations", 25)

        if not task_description:
            return ToolResult(success=False, error="Task description is required")

        try:
            task_id = await self.manager.spawn(
                task_description=task_description,
                allowed_tools=tools,
                max_iterations=max_iterations,
            )

            return ToolResult(
                success=True,
                data={"task_id": task_id},
                summary=f"Spawned sub-agent (ID: {task_id}) for: {task_description[:50]}...",
                metadata={"task_id": task_id, "task": task_description}
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to spawn sub-agent: {e}")


class ListAgentsTool(Tool):
    """Tool to list running and completed sub-agents."""

    def __init__(self, sub_agent_manager: SubAgentManager):
        """Initialize the tool."""
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.manager = sub_agent_manager

    @property
    def name(self) -> str:
        return "list_agents"

    @property
    def description(self) -> str:
        return "List all spawned sub-agents and their current status."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:  # noqa: ARG002
        """List sub-agents."""
        _ = args  # Unused but required by interface
        tasks = self.manager.list_tasks()

        if not tasks:
            return ToolResult(
                success=True,
                data="No sub-agents have been spawned.",
                summary="No active sub-agents"
            )

        # Format output
        lines = []
        for task in tasks:
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(task["status"], "?")

            lines.append(f"{status_icon} [{task['task_id']}] {task['status']}: {task['description'][:50]}...")

        output = "\n".join(lines)

        return ToolResult(
            success=True,
            data=output,
            summary=f"Found {len(tasks)} sub-agent(s)",
            metadata={"tasks": tasks}
        )


class GetAgentResultTool(Tool):
    """Tool to get the result of a completed sub-agent."""

    def __init__(self, sub_agent_manager: SubAgentManager):
        """Initialize the tool."""
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.manager = sub_agent_manager

    @property
    def name(self) -> str:
        return "get_agent_result"

    @property
    def description(self) -> str:
        return "Get the result of a sub-agent task. Optionally wait for completion."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID returned by spawn_agent"
                },
                "wait": {
                    "type": "boolean",
                    "description": "Whether to wait for the task to complete (default: false)"
                }
            },
            "required": ["task_id"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Get sub-agent result."""
        task_id = args.get("task_id", "")
        wait = args.get("wait", False)

        if not task_id:
            return ToolResult(success=False, error="task_id is required")

        result = await self.manager.get_result(task_id, wait=wait)

        if not result:
            return ToolResult(success=False, error=f"Task not found: {task_id}")

        # Format output
        status = result["status"]
        if status == "completed":
            output = f"Task completed:\n\n{result['result']}"
            summary = f"Task {task_id} completed successfully"
        elif status == "failed":
            output = f"Task failed:\n\n{result['error']}"
            summary = f"Task {task_id} failed"
        elif status in ["pending", "running"]:
            progress = "\n".join(result.get("progress", [])) or "No progress yet"
            output = f"Task still {status}.\n\nProgress:\n{progress}"
            summary = f"Task {task_id} is {status}"
        else:
            output = f"Task status: {status}"
            summary = f"Task {task_id}: {status}"

        return ToolResult(
            success=True,
            data=output,
            summary=summary,
            metadata=result
        )


class ApproveSubagentTool(Tool):
    """Tool to approve or deny a sub-agent's pending action."""

    def __init__(self, event_bus: AgentEventBus):
        """Initialize the tool.

        Args:
            event_bus: Event bus for approval responses
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.event_bus = event_bus

    @property
    def name(self) -> str:
        return "approve_subagent"

    @property
    def description(self) -> str:
        return """Approve or deny a sub-agent's pending action.
Use this when a sub-agent requests approval for a medium-risk operation.
Check pending approvals with list_pending_approvals first."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "The approval request ID from the pending approvals list"
                },
                "approved": {
                    "type": "boolean",
                    "description": "Whether to approve (true) or deny (false) the action"
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for the decision"
                }
            },
            "required": ["request_id", "approved"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Approve or deny a sub-agent action."""
        request_id = args.get("request_id", "")
        approved = args.get("approved", False)
        reason = args.get("reason", "")

        if not request_id:
            return ToolResult(success=False, error="request_id is required")

        try:
            delivered = await self.event_bus.respond_to_approval(
                request_id=request_id,
                approved=approved,
                responder_id="main",
            )

            if delivered:
                action = "approved" if approved else "denied"
                msg = f"Request {request_id} {action}"
                if reason:
                    msg += f": {reason}"
                return ToolResult(
                    success=True,
                    data=msg,
                    summary=f"Sub-agent action {action}"
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Request {request_id} not found or already processed"
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to process approval: {e}")


class ListPendingApprovalsTool(Tool):
    """Tool to list pending sub-agent approval requests."""

    def __init__(self, event_bus: AgentEventBus):
        """Initialize the tool.

        Args:
            event_bus: Event bus to check for pending approvals
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.event_bus = event_bus

    @property
    def name(self) -> str:
        return "list_pending_approvals"

    @property
    def description(self) -> str:
        return """List all pending approval requests from sub-agents.
Shows requests waiting for your approval decision."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """List pending approvals."""
        _ = args  # Unused but required by interface

        try:
            pending = self.event_bus.get_pending_approvals()

            if not pending:
                return ToolResult(
                    success=True,
                    data="No pending approval requests.",
                    summary="No pending approvals"
                )

            # Format output
            lines = []
            for event in pending:
                request_id = event.data.get("request_id", "unknown")
                tool = event.data.get("tool", "unknown")
                risk = event.data.get("risk_level", "unknown")
                source = event.source_id

                lines.append(
                    f"[{request_id}] from {source}: {tool} ({risk} risk)"
                )
                # Show relevant args
                tool_args = event.data.get("args", {})
                if tool_args:
                    for key, value in list(tool_args.items())[:3]:
                        val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                        lines.append(f"  - {key}: {val_str}")

            output = "\n".join(lines)

            return ToolResult(
                success=True,
                data=output,
                summary=f"{len(pending)} pending approval(s)",
                metadata={"count": len(pending)}
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list pending approvals: {e}")
