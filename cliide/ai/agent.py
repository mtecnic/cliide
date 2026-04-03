"""Tool-calling agent implementation."""

import asyncio
import json
from collections import deque
from typing import Any, AsyncIterator, Awaitable, Callable
from pathlib import Path

from cliide.utils.logger import log
from cliide.ai.tools.base import ToolRegistry, get_tool_registry
from cliide.ai.memory import AgentMemory, MemoryCategory
from cliide.ai.event_bus import AgentEventBus, AgentEvent, AgentEventType, get_event_bus
from cliide.ai.checkpoint import CheckpointManager
from cliide.ai.tools.filesystem import (
    ReadFileTool, WriteFileTool, ListDirectoryTool,
    CreateFileTool, MkdirTool, BatchWriteTool
)
from cliide.ai.tools.search import SearchFilesTool, GrepTool, FindSymbolTool
from cliide.ai.tools.analysis import ExtractSymbolsTool, GetFileSummaryTool
from cliide.ai.tools.rules import FollowRuleTool, ListRulesTool
from cliide.ai.tools.shell import RunCommandTool
from cliide.ai.tools.git import (
    GitStatusTool, GitDiffTool, GitLogTool, GitCommitTool,
    GitAddTool, GitBranchTool
)
from cliide.ai.tools.testing import RunTestsTool
from cliide.ai.tools.project import ChangeDirectoryTool
from cliide.ai.tools.memory_tools import (
    StoreMemoryTool, RecallMemoryTool, ForgetMemoryTool, MemorySummaryTool
)
from cliide.ai.sub_agent import (
    SubAgentManager, SpawnAgentTool, ListAgentsTool, GetAgentResultTool,
    ApproveSubagentTool, ListPendingApprovalsTool
)
from cliide.ai.tool_worker import ToolWorkerPool, should_delegate, classify_tool, SEQUENTIAL_TOOLS
from cliide.utils.audit_log import get_audit_logger
from cliide.core.config import get_config


class ToolAgent:
    """Agent that can call tools to accomplish tasks."""

    def __init__(
        self,
        vllm_client,
        workspace_root: str | Path,
        confirmation_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
        memory: AgentMemory | None = None,
        event_bus: AgentEventBus | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        """Initialize the agent.

        Args:
            vllm_client: VLLM client instance for AI calls
            workspace_root: Root directory of workspace
            confirmation_callback: Async callback for user confirmation (tool_name, args) -> bool
            memory: Optional AgentMemory instance (created if not provided)
            event_bus: Optional AgentEventBus instance (uses global if not provided)
            checkpoint_manager: Optional CheckpointManager (created if not provided)
        """
        self.client = vllm_client
        self.workspace_root = Path(workspace_root)
        self.confirmation_callback = confirmation_callback

        # Get configuration
        self.config = get_config()
        tools_config = self.config.tools

        # Initialize memory system (persistent per-project)
        self.memory = memory or AgentMemory(self.workspace_root)

        # Initialize event bus (for milestone communication)
        self.event_bus = event_bus or get_event_bus()

        # Initialize checkpoint manager (for state recovery)
        self.checkpoint_manager = checkpoint_manager or CheckpointManager(self.workspace_root)

        # Initialize tool registry
        self.registry = get_tool_registry()

        # Initialize sub-agent manager
        self.sub_agent_manager: SubAgentManager | None = None

        # Initialize tool worker pool (created after tools registered)
        self.worker_pool: ToolWorkerPool | None = None

        # Register all tools
        self._register_tools()

        # Set confirmation callback
        if confirmation_callback:
            self.registry.set_confirmation_callback(confirmation_callback)

        # Initialize audit logger
        self.audit_logger = get_audit_logger(enabled=tools_config.audit_log_enabled)

        # Subscribe to sub-agent events
        self._setup_event_handlers()

    def _register_tools(self) -> None:
        """Register all available tools."""
        config = self.config.tools

        # Filesystem tools
        self.registry.register(ReadFileTool(
            self.workspace_root,
            max_file_size_mb=config.max_file_size_mb
        ))
        self.registry.register(WriteFileTool(
            self.workspace_root,
            max_file_size_mb=config.max_file_size_mb
        ))
        self.registry.register(ListDirectoryTool(self.workspace_root))
        self.registry.register(CreateFileTool(self.workspace_root))
        self.registry.register(MkdirTool(self.workspace_root))

        # Search tools
        self.registry.register(SearchFilesTool(self.workspace_root))
        self.registry.register(GrepTool(
            self.workspace_root,
            max_file_size_mb=config.max_file_size_mb
        ))
        self.registry.register(FindSymbolTool(self.workspace_root))

        # Analysis tools
        self.registry.register(ExtractSymbolsTool(self.workspace_root))
        self.registry.register(GetFileSummaryTool(self.workspace_root))

        # Rules tools
        self.registry.register(FollowRuleTool(self.workspace_root))
        self.registry.register(ListRulesTool())

        # Shell execution tool
        self.registry.register(RunCommandTool(
            self.workspace_root,
            timeout=config.timeout_seconds
        ))

        # Git tools
        self.registry.register(GitStatusTool(self.workspace_root))
        self.registry.register(GitDiffTool(self.workspace_root))
        self.registry.register(GitLogTool(self.workspace_root))
        self.registry.register(GitCommitTool(self.workspace_root))
        self.registry.register(GitAddTool(self.workspace_root))
        self.registry.register(GitBranchTool(self.workspace_root))

        # Testing tool
        self.registry.register(RunTestsTool(
            self.workspace_root,
            timeout=config.timeout_seconds * 4  # Tests get more time
        ))

        # Project management tool
        self.registry.register(ChangeDirectoryTool(self.event_bus))

        # Batch write tool for multi-file edits
        self.registry.register(BatchWriteTool(
            self.workspace_root,
            max_file_size_mb=config.max_file_size_mb
        ))

        # Sub-agent tools (for parallel task execution)
        # Use inference concurrency limit for sub-agents too
        inference_max = self.config.inference.max_concurrent_requests
        self.sub_agent_manager = SubAgentManager(
            vllm_client=self.client,
            workspace_root=self.workspace_root,
            tool_registry=self.registry,
            max_concurrent=inference_max,
        )
        self.registry.register(SpawnAgentTool(self.sub_agent_manager))
        self.registry.register(ListAgentsTool(self.sub_agent_manager))
        self.registry.register(GetAgentResultTool(self.sub_agent_manager))

        # Memory tools (for persistent context)
        self.registry.register(StoreMemoryTool(self.memory))
        self.registry.register(RecallMemoryTool(self.memory))
        self.registry.register(ForgetMemoryTool(self.memory))
        self.registry.register(MemorySummaryTool(self.memory))

        # Approval tools (for sub-agent trust escalation)
        self.registry.register(ApproveSubagentTool(self.event_bus))
        self.registry.register(ListPendingApprovalsTool(self.event_bus))

        # Initialize tool worker pool for async execution
        worker_config = self.config.tool_worker
        inference_config = self.config.inference
        self.worker_pool = ToolWorkerPool(
            tool_registry=self.registry,
            max_concurrent=inference_config.max_concurrent_requests,
            timeout_seconds=worker_config.timeout_seconds,
            confirmation_mode=config.confirmation_mode,
        )

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for sub-agent communication."""
        # Handle sub-agent milestones
        async def on_milestone(event: AgentEvent) -> None:
            # Store significant milestones in memory
            if event.priority >= 5:
                self.memory.store(
                    key=f"milestone_{event.source_id}_{event.timestamp.isoformat()[:19]}",
                    value=event.data.get("message", str(event.data)),
                    category=MemoryCategory.DISCOVERY,
                    source=event.source_id,
                    ttl=3600 * 24,  # 24 hours
                )

        # Handle discoveries from sub-agents
        async def on_discovery(event: AgentEvent) -> None:
            # Store discoveries in memory for future reference
            key = event.data.get("key", f"discovery_{event.source_id}")
            self.memory.store(
                key=key,
                value=event.data.get("value", event.data),
                category=MemoryCategory.DISCOVERY,
                source=event.source_id,
            )

        # Handle approval requests from sub-agents
        async def on_approval_needed(event: AgentEvent) -> None:
            # Log pending approvals (actual approval handled separately)
            self.memory.store(
                key=f"pending_approval_{event.data.get('request_id')}",
                value=event.data,
                category=MemoryCategory.CONTEXT,
                source=event.source_id,
                ttl=300,  # 5 minutes
            )

        # Subscribe to events
        self.event_bus.subscribe(AgentEventType.MILESTONE, on_milestone)
        self.event_bus.subscribe(AgentEventType.DISCOVERY, on_discovery)
        self.event_bus.subscribe(AgentEventType.APPROVAL_NEEDED, on_approval_needed)

    def should_confirm_tool(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation.

        Args:
            tool_name: Name of the tool

        Returns:
            True if confirmation is required
        """
        config = self.config.tools
        tool = self.registry.get(tool_name)

        if not tool:
            return False

        confirmation_mode = config.confirmation_mode

        if confirmation_mode == "all":
            return True
        elif confirmation_mode == "auto":
            return False
        elif confirmation_mode == "dangerous":
            return tool.requires_confirmation
        else:
            # Default to dangerous mode
            return tool.requires_confirmation

    async def run(
        self,
        messages: list[dict[str, str]],
        max_iterations: int = 5,
        stream: bool = True,
        use_tools: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agent loop with tool calling.

        Args:
            messages: Conversation messages
            max_iterations: Maximum tool call iterations
            stream: Whether to stream responses
            use_tools: Whether to enable tool calling (False for pure text generation)

        Yields:
            Events: {"type": "text", "content": str} or
                   {"type": "tool_start", "tool": str, "args": dict} or
                   {"type": "tool_result", "tool": str, "result": ToolResult} or
                   {"type": "error", "message": str}
        """
        config = self.config.tools
        log(f"[AGENT.RUN] Starting with {len(messages)} messages, max_iterations={max_iterations}, tools_enabled={config.enabled}, use_tools={use_tools}")

        if not config.enabled or not use_tools:
            # Tools disabled, just run normal completion
            log("[AGENT.RUN] Tools disabled, using streaming completion")
            async for chunk in self.client.stream_with_system("You are a helpful AI assistant.", messages[-1]["content"]):
                yield {"type": "text", "content": chunk}
            yield {"type": "done", "reason": "complete"}
            return

        # Get tool definitions
        tool_definitions = self.registry.to_openai_functions()
        log(f"[AGENT.RUN] Got {len(tool_definitions)} tool definitions")

        iteration = 0
        current_messages = messages.copy()
        recent_tool_patterns: deque[tuple[str, ...]] = deque(maxlen=3)

        while iteration < max_iterations:
            iteration += 1
            log(f"[AGENT.RUN] Starting iteration {iteration}/{max_iterations}")

            # Progress indicator for all iterations
            yield {"type": "progress", "message": f"Waiting for AI... (iteration {iteration})"}

            # Call AI with tools (with timeout)
            try:
                log(f"[AGENT.RUN] Calling AI with {len(current_messages)} messages, {len(tool_definitions)} tools")
                response = await asyncio.wait_for(
                    self.client.chat_completion(
                        messages=current_messages,
                        tools=tool_definitions,
                        stream=False  # We need the full response to check for tool calls
                    ),
                    timeout=120  # 2 minute timeout per AI call
                )
                log(f"[AGENT.RUN] AI response received, has choices: {bool(response.get('choices'))}")

                # Check if response has tool calls
                if not response.get("choices"):
                    yield {"type": "error", "message": "No response from AI"}
                    yield {"type": "done", "reason": "error"}
                    return

                choice = response["choices"][0]
                message = choice["message"]

                # Check for tool calls
                tool_calls = message.get("tool_calls", [])

                if not tool_calls:
                    # No tool calls, return the assistant's message
                    content = message.get("content", "")
                    if content:
                        yield {"type": "text", "content": content}
                    yield {"type": "done", "reason": "complete"}
                    return

                # Check for repetitive tool patterns (infinite loop detection)
                tool_pattern = tuple(sorted(tc["function"]["name"] for tc in tool_calls))
                recent_tool_patterns.append(tool_pattern)

                # Detect exact 3x repeat
                if len(recent_tool_patterns) >= 3 and all(p == tool_pattern for p in recent_tool_patterns[-3:]):
                    yield {"type": "warning", "message": f"Detected repetitive tool pattern (3x): {tool_pattern}"}
                    yield {"type": "done", "reason": "loop_detected"}
                    return

                # Detect alternating A,B,A,B,A,B pattern (6 iterations)
                if len(recent_tool_patterns) >= 6:
                    last_6 = recent_tool_patterns[-6:]
                    if (last_6[0] == last_6[2] == last_6[4] and
                        last_6[1] == last_6[3] == last_6[5] and
                        last_6[0] != last_6[1]):
                        yield {"type": "warning", "message": f"Detected alternating tool loop: {last_6[0]} <-> {last_6[1]}"}
                        yield {"type": "done", "reason": "loop_detected"}
                        return

                # Process tool calls with adaptive batching based on concurrency limits
                # and tool classification (sequential vs parallel-safe)
                tool_results = []
                all_results: dict[str, Any] = {}

                # Get concurrency limit from config
                inference_config = get_config().inference
                max_concurrent = inference_config.max_concurrent_requests

                # Separate tools by classification
                parsed_tools: list[dict[str, Any]] = []
                for tool_call in tool_calls:
                    function = tool_call["function"]
                    tool_name = function["name"]
                    args_str = function.get("arguments", "{}")
                    tool_call_id = tool_call.get("id", "")

                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        yield {
                            "type": "error",
                            "message": f"Invalid JSON in tool call: {args_str}"
                        }
                        continue

                    classification = classify_tool(tool_name)
                    parsed_tools.append({
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "args": args,
                        "classification": classification,
                    })

                # Split into sequential and parallel-safe tools
                sequential_tools = [t for t in parsed_tools if t["classification"] == "sequential"]
                parallel_tools = [t for t in parsed_tools if t["classification"] != "sequential"]

                # Helper to execute a single tool
                async def execute_tool(tool_info: dict) -> dict:
                    tool_name = tool_info["tool_name"]
                    args = tool_info["args"]
                    tool_call_id = tool_info["tool_call_id"]

                    # Emit tool start event
                    yield_data = {
                        "type": "tool_start",
                        "tool": tool_name,
                        "args": args,
                        "tool_call_id": tool_call_id
                    }

                    try:
                        if self.worker_pool and should_delegate(tool_name):
                            await self.worker_pool.submit(
                                tool_call_id=tool_call_id,
                                tool_name=tool_name,
                                args=args,
                            )
                            result_dict = await self.worker_pool.wait_for_all(
                                [tool_call_id],
                                timeout=config.timeout_seconds * 2,
                            )
                            result = result_dict.get(tool_call_id)
                        else:
                            result = await asyncio.wait_for(
                                self.registry.execute_tool(
                                    tool_name,
                                    args,
                                    confirmation_mode=config.confirmation_mode
                                ),
                                timeout=config.timeout_seconds
                            )
                    except asyncio.TimeoutError:
                        from cliide.ai.tools.base import ToolResult
                        result = ToolResult(
                            success=False,
                            error=f"Tool execution timed out after {config.timeout_seconds}s"
                        )
                    except Exception as e:
                        from cliide.ai.tools.base import ToolResult
                        result = ToolResult(
                            success=False,
                            error=f"Tool execution failed: {str(e)}"
                        )

                    return {
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "args": args,
                        "result": result,
                        "yield_data": yield_data,
                    }

                # Phase 1: Execute sequential tools one at a time (order matters)
                for tool_info in sequential_tools:
                    tool_result = await execute_tool(tool_info)
                    yield tool_result["yield_data"]  # tool_start
                    all_results[tool_result["tool_call_id"]] = tool_result
                    log(f"[AGENT] Sequential tool {tool_info['tool_name']} completed")

                # Phase 2: Execute parallel-safe tools in batches
                if parallel_tools:
                    # Emit all start events first
                    for tool_info in parallel_tools:
                        yield {
                            "type": "tool_start",
                            "tool": tool_info["tool_name"],
                            "args": tool_info["args"],
                            "tool_call_id": tool_info["tool_call_id"]
                        }

                    # Process in batches of max_concurrent
                    for i in range(0, len(parallel_tools), max_concurrent):
                        batch = parallel_tools[i:i + max_concurrent]
                        log(f"[AGENT] Processing parallel batch {i//max_concurrent + 1}: {len(batch)} tools (max_concurrent={max_concurrent})")

                        # Submit all tools in this batch
                        if self.worker_pool:
                            for tool_info in batch:
                                if should_delegate(tool_info["tool_name"]):
                                    await self.worker_pool.submit(
                                        tool_call_id=tool_info["tool_call_id"],
                                        tool_name=tool_info["tool_name"],
                                        args=tool_info["args"],
                                    )

                            # Wait for batch to complete
                            batch_ids = [t["tool_call_id"] for t in batch if should_delegate(t["tool_name"])]
                            if batch_ids:
                                batch_results = await self.worker_pool.wait_for_all(
                                    batch_ids,
                                    timeout=config.timeout_seconds * 2,
                                )
                                for tool_info in batch:
                                    tcid = tool_info["tool_call_id"]
                                    if tcid in batch_results:
                                        all_results[tcid] = {
                                            "tool_call_id": tcid,
                                            "tool_name": tool_info["tool_name"],
                                            "args": tool_info["args"],
                                            "result": batch_results[tcid],
                                        }
                        else:
                            # No worker pool, execute inline sequentially
                            for tool_info in batch:
                                tool_result = await execute_tool(tool_info)
                                all_results[tool_result["tool_call_id"]] = tool_result

                # Phase 3: Process all results
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", "")
                    function = tool_call["function"]
                    tool_name = function["name"]

                    # Get result from all_results
                    if tool_call_id in all_results:
                        info = all_results[tool_call_id]
                        result = info["result"]
                        args = info["args"]
                    else:
                        # Should not happen - log warning to help debug concurrency issues
                        log(f"[AGENT] WARNING: No result for tool_call_id={tool_call_id}, tool={tool_name}")
                        from cliide.ai.tools.base import ToolResult
                        result = ToolResult(success=False, error="No result found")
                        args = {}

                    # Log execution
                    await self.audit_logger.log_execution(
                        tool_name=tool_name,
                        args=args,
                        result_success=result.success,
                        approved=True,
                        error=result.error if not result.success else None
                    )

                    # Emit tool result event
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                        "tool_call_id": tool_call_id
                    }

                    # Emit TOOL_COMPLETED to event bus for UI updates
                    await self.event_bus.emit(AgentEvent(
                        event_type=AgentEventType.TOOL_COMPLETED,
                        source_id="main",
                        data={"tool": tool_name, "success": result.success}
                    ))

                    # Prepare result for AI
                    result_content = result.to_message() if hasattr(result, 'to_message') else str(result)
                    tool_results.append({
                        "tool_call_id": tool_call_id,
                        "role": "tool",
                        "name": tool_name,
                        "content": result_content
                    })

                # Add assistant message and tool results to conversation
                current_messages.append(message)
                current_messages.extend(tool_results)

                # Prune messages if too long (keep system message + recent context)
                MAX_CONTEXT_MESSAGES = 30
                if len(current_messages) > MAX_CONTEXT_MESSAGES:
                    system_msg = current_messages[0] if current_messages[0].get("role") == "system" else None
                    if system_msg:
                        current_messages = [system_msg] + current_messages[-(MAX_CONTEXT_MESSAGES - 1):]
                    else:
                        current_messages = current_messages[-MAX_CONTEXT_MESSAGES:]

                # Continue the loop to get AI's response with tool results

            except asyncio.TimeoutError:
                yield {"type": "error", "message": "AI response timed out after 120 seconds"}
                yield {"type": "done", "reason": "timeout"}
                return

            except Exception as e:
                yield {"type": "error", "message": f"Agent error: {str(e)}"}
                yield {"type": "done", "reason": "error"}
                return

        # Max iterations reached
        yield {
            "type": "error",
            "message": f"Maximum iterations ({max_iterations}) reached"
        }
        yield {"type": "done", "reason": "max_iterations"}

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Simple chat interface with tool support.

        Args:
            user_message: User's message
            conversation_history: Previous conversation messages

        Yields:
            Agent events
        """
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})

        async for event in self.run(messages):
            yield event


    async def run_autonomous(
        self,
        task: str,
        max_iterations: int = 50,
        checkpoint_interval: int = 10,
        resume_from: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run autonomous task execution with progress checkpoints.

        Args:
            task: High-level task description
            max_iterations: Maximum iterations
            checkpoint_interval: Iterations between progress reports
            resume_from: Optional checkpoint ID to resume from

        Yields:
            Events including progress checkpoints
        """
        # Store task in memory for context
        self.memory.store(
            key="current_autonomous_task",
            value=task,
            category=MemoryCategory.CONTEXT,
            source="main",
        )

        # Emit task started event
        await self.event_bus.emit(AgentEvent(
            event_type=AgentEventType.TASK_STARTED,
            source_id="main",
            data={"task": task, "max_iterations": max_iterations},
            priority=5,
        ))

        # Check for resume from checkpoint
        start_iteration = 0
        tool_results_history: list[dict[str, Any]] = []

        if resume_from:
            checkpoint = await self.checkpoint_manager.restore_checkpoint(resume_from)
            if checkpoint:
                messages = checkpoint.messages
                start_iteration = checkpoint.iteration
                tool_results_history = checkpoint.tool_results
                yield {
                    "type": "checkpoint_restored",
                    "checkpoint_id": resume_from,
                    "iteration": start_iteration,
                    "message": f"Resumed from checkpoint at iteration {start_iteration}"
                }
            else:
                yield {"type": "error", "message": f"Checkpoint not found: {resume_from}"}
                return
        else:
            # Build autonomous system prompt
            # Include relevant memories for context
            memory_context = self.memory.get_context_for_prompt(max_entries=5)

            system_prompt = f"""You are an autonomous coding agent working on a complex task.

TASK: {task}

{memory_context if memory_context else ""}

IMPORTANT GUIDELINES:
1. Break down the task into smaller steps
2. Use tools to explore the codebase before making changes
3. Test your changes when possible
4. Report progress periodically
5. If stuck, explain the blocker clearly

Available tools allow you to:
- Read and write files
- Search code (grep, find symbols)
- Run commands and tests
- Manage git (status, diff, commit)
- Spawn sub-agents for parallel work

Work autonomously but report significant progress. Stop when the task is complete.
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Complete this task autonomously: {task}"}
            ]

        # Yield start event
        yield {
            "type": "autonomous_start",
            "task": task,
            "max_iterations": max_iterations,
            "resumed_from": resume_from,
        }

        iteration = start_iteration
        config = self.config.tools
        tool_definitions = self.registry.to_openai_functions()

        while iteration < max_iterations:
            iteration += 1

            # Create checkpoint at intervals
            if iteration % checkpoint_interval == 0:
                checkpoint_id = await self.checkpoint_manager.create_checkpoint(
                    task_id="main_autonomous",
                    iteration=iteration,
                    messages=messages,
                    tool_results=tool_results_history,
                    memory=self.memory,
                    metadata={"task": task},
                )

                # Emit checkpoint event
                await self.event_bus.emit(AgentEvent(
                    event_type=AgentEventType.CHECKPOINT_CREATED,
                    source_id="main",
                    data={"checkpoint_id": checkpoint_id, "iteration": iteration},
                ))

                yield {
                    "type": "checkpoint",
                    "checkpoint_id": checkpoint_id,
                    "iteration": iteration,
                    "max_iterations": max_iterations,
                    "message": f"Progress: {iteration}/{max_iterations} iterations"
                }

            # Call AI with tools
            try:
                response = await self.client.chat_completion(
                    messages=messages,
                    tools=tool_definitions,
                    stream=False
                )

                if not response.get("choices"):
                    yield {"type": "error", "message": "No response from AI"}
                    return

                choice = response["choices"][0]
                message = choice["message"]
                tool_calls = message.get("tool_calls", [])

                # Check finish reason
                finish_reason = choice.get("finish_reason", "")

                if not tool_calls:
                    # No tool calls - AI has finished or is responding
                    content = message.get("content", "")
                    if content:
                        yield {"type": "text", "content": content}

                    # Check if AI signals completion
                    if "TASK COMPLETE" in content.upper() or finish_reason == "stop":
                        # Emit completion event
                        await self.event_bus.emit(AgentEvent(
                            event_type=AgentEventType.TASK_COMPLETED,
                            source_id="main",
                            data={"task": task, "iterations": iteration},
                            priority=5,
                        ))

                        # Store completion in memory
                        self.memory.store(
                            key=f"task_completed_{iteration}",
                            value=f"Completed: {task}",
                            category=MemoryCategory.DECISION,
                            source="main",
                        )

                        yield {
                            "type": "autonomous_complete",
                            "iterations": iteration,
                            "message": "Task marked as complete by AI"
                        }
                        return

                    # Continue the loop
                    messages.append(message)
                    messages.append({
                        "role": "user",
                        "content": "Continue with the task. If complete, say 'TASK COMPLETE' and summarize what was done."
                    })
                    continue

                # Process tool calls
                tool_results = []
                for tool_call in tool_calls:
                    function = tool_call["function"]
                    tool_name = function["name"]
                    args_str = function.get("arguments", "{}")

                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        continue

                    # Emit tool called event
                    await self.event_bus.emit_tool_called("main", tool_name, args)

                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "args": args,
                        "tool_call_id": tool_call.get("id")
                    }

                    # Execute tool
                    try:
                        result = await asyncio.wait_for(
                            self.registry.execute_tool(
                                tool_name,
                                args,
                                confirmation_mode=config.confirmation_mode
                            ),
                            timeout=config.timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        result = type('ToolResult', (), {
                            'success': False,
                            'error': f"Tool timed out after {config.timeout_seconds}s",
                            'to_message': lambda: "Error: Tool timed out"
                        })()
                    except Exception as e:
                        err_msg = str(e)
                        result = type('ToolResult', (), {
                            'success': False,
                            'error': err_msg,
                            'to_message': lambda msg=err_msg: f"Error: {msg}"
                        })()

                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                        "tool_call_id": tool_call.get("id")
                    }

                    # Emit TOOL_COMPLETED to event bus for UI updates
                    await self.event_bus.emit(AgentEvent(
                        event_type=AgentEventType.TOOL_COMPLETED,
                        source_id="main",
                        data={"tool": tool_name, "success": getattr(result, 'success', True)}
                    ))

                    result_content = result.to_message() if hasattr(result, 'to_message') else str(result)
                    tool_results.append({
                        "tool_call_id": tool_call.get("id"),
                        "role": "tool",
                        "name": tool_name,
                        "content": result_content
                    })

                    # Store tool result in history for checkpointing
                    tool_results_history.append({
                        "tool": tool_name,
                        "args": args,
                        "success": getattr(result, 'success', True),
                        "iteration": iteration,
                    })

                # Add to conversation
                messages.append(message)
                messages.extend(tool_results)

            except Exception as e:
                # Emit error event
                await self.event_bus.emit(AgentEvent(
                    event_type=AgentEventType.ERROR,
                    source_id="main",
                    data={"error": str(e), "iteration": iteration},
                    priority=8,
                ))
                yield {"type": "error", "message": f"Autonomous mode error: {str(e)}"}
                return

        # Max iterations reached
        yield {
            "type": "autonomous_incomplete",
            "iterations": max_iterations,
            "message": f"Maximum iterations ({max_iterations}) reached"
        }


def create_tool_agent(
    vllm_client,
    workspace_root: str | Path,
    confirmation_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
) -> ToolAgent:
    """Factory function to create a ToolAgent.

    Args:
        vllm_client: VLLM client instance
        workspace_root: Root directory of workspace
        confirmation_callback: Optional confirmation callback

    Returns:
        Configured ToolAgent instance
    """
    return ToolAgent(
        vllm_client=vllm_client,
        workspace_root=workspace_root,
        confirmation_callback=confirmation_callback
    )
