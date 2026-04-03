"""AI-powered code actions."""

import asyncio
import re
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from cliide.ai.context_builder import ContextBuilder
from cliide.ai.prompt_manager import PromptManager
from cliide.ai.vllm_client import get_client


class CodeActions:
    """High-level AI-powered code actions."""

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        confirmation_callback: Callable[[str, dict], Awaitable[bool]] | None = None,
    ) -> None:
        """Initialize code actions.

        Args:
            workspace_root: Root directory for tool operations
            confirmation_callback: Callback for tool confirmation dialogs
        """
        self.client = get_client()
        self.prompt_manager = PromptManager()
        self.context_builder = ContextBuilder()
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.confirmation_callback = confirmation_callback

        # Initialize the tool agent for agentic chat
        from cliide.ai.agent import ToolAgent
        self._agent = ToolAgent(
            vllm_client=self.client,
            workspace_root=self.workspace_root,
            confirmation_callback=confirmation_callback,
        )

    async def explain_code(
        self, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Explain code using AI.

        Args:
            code: Code to explain
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("explain")
        user_prompt = self.prompt_manager.build_explain_prompt(code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def refactor_code(
        self, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Get refactoring suggestions.

        Args:
            code: Code to refactor
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("refactor")
        user_prompt = self.prompt_manager.build_refactor_prompt(code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def fix_code(
        self, code: str, error: Optional[str] = None, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Get bug fix suggestions.

        Args:
            code: Code with bugs
            error: Error message if available
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("fix")
        user_prompt = self.prompt_manager.build_fix_prompt(code, error, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def generate_tests(
        self, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Generate tests for code.

        Args:
            code: Code to test
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("test")
        user_prompt = self.prompt_manager.build_test_prompt(code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def generate_docs(
        self, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Generate documentation for code.

        Args:
            code: Code to document
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("document")
        user_prompt = self.prompt_manager.build_document_prompt(code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def chat(
        self,
        message: str,
        code_context: Optional[str] = None,
        file_name: Optional[str] = None,
        language: Optional[str] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
        use_tools: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """General chat with AI using tool-calling agent.

        Args:
            message: User message
            code_context: Current code context
            file_name: Current file name
            language: Programming language of current file
            conversation_history: Previous messages
            use_tools: Whether to enable tool calling (default True)

        Yields:
            Event dicts: {"type": "text", "content": str} or
                        {"type": "tool_start", "tool": str, "args": dict, "tool_call_id": str} or
                        {"type": "tool_result", "tool": str, "result": ToolResult, "tool_call_id": str} or
                        {"type": "error", "message": str}
        """
        from cliide.utils.logger import log

        # Build prompt with context
        user_prompt = self.prompt_manager.build_chat_prompt(
            message, code_context, file_name, language
        )

        # Build message history
        messages = []

        # Add tool-aware system prompt
        system_prompt = self.prompt_manager.get_system_prompt("agent")
        messages.append({"role": "system", "content": system_prompt})

        # Add conversation history (already includes current message from chat panel)
        if conversation_history:
            log(f"[CODE_ACTIONS] Using conversation history with {len(conversation_history)} messages")
            trimmed_history = self.context_builder.build_conversation_context(
                conversation_history
            )
            # Filter out system messages from history (we already added one)
            filtered_history = [m for m in trimmed_history if m.get("role") != "system"]
            messages.extend(filtered_history)
            # Log the last user message to verify it has file content
            if filtered_history:
                last_user_msg = next((m for m in reversed(filtered_history) if m.get("role") == "user"), None)
                if last_user_msg:
                    msg_content = last_user_msg.get("content", "")
                    log(f"[CODE_ACTIONS] Last user message length: {len(msg_content)}")
                    log(f"[CODE_ACTIONS] Has 'Referenced files': {'Referenced files' in msg_content}")
        else:
            # No history, add current message
            log(f"[CODE_ACTIONS] No history, using user_prompt length: {len(user_prompt)}")
            messages.append({"role": "user", "content": user_prompt})

        # Check for exploration-type requests that benefit from parallel sub-agents
        exploration_keywords = [
            "scan", "summarize", "explore", "overview", "structure",
            "project", "codebase", "all files", "directory", "what is this"
        ]
        is_exploration = any(kw in message.lower() for kw in exploration_keywords)

        # Use parallel sub-agents for exploration tasks
        if use_tools and is_exploration:
            log("[CODE_ACTIONS] Detected exploration request - using parallel sub-agents")
            async for event in self._explore_with_subagents(message, messages):
                yield event
            return

        # Use tool agent for agentic responses
        if use_tools:
            from cliide.core.config import get_config
            config = get_config()
            max_iterations = config.tools.max_iterations
            log(f"[CODE_ACTIONS] Running with ToolAgent (max_iterations={max_iterations})")
            async for event in self._agent.run(messages, max_iterations=max_iterations):
                yield event
        else:
            # Fallback to direct chat without tools
            log("[CODE_ACTIONS] Running without tools (direct chat)")
            response = await self.client.chat_completion(messages, stream=True)
            if isinstance(response, str):
                yield {"type": "text", "content": response}
            else:
                async for chunk in response:
                    yield {"type": "text", "content": chunk}

    async def _explore_with_subagents(
        self,
        message: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[dict[str, Any]]:
        """Force parallel sub-agent spawning for exploration tasks.

        Args:
            message: Original user message
            messages: Full message list including system prompt

        Yields:
            Event dicts for UI updates
        """
        from cliide.utils.logger import log

        manager = self._agent.sub_agent_manager
        if manager is None:
            yield {"type": "error", "message": "Sub-agent manager not initialized"}
            return

        # Use configured concurrency limit (respects user's hardware)
        config = get_config()
        max_concurrent = config.inference.max_concurrent_requests

        yield {"type": "text", "content": f"Launching exploration agents (max {max_concurrent} parallel)...\n\n"}

        try:
            # Define exploration tasks based on workspace structure
            exploration_tasks = [
                "List and describe all top-level directories and key files in the project root",
                "Find Python source files and summarize main modules and their purposes",
                "Find configuration files (*.toml, *.yaml, *.json, *.cfg) and summarize settings",
                "Find README, documentation files, and summarize project description",
                "Identify the project type, frameworks used, and entry points",
            ]

            # Spawn agents in batches respecting concurrency limit
            log(f"[EXPLORE] Spawning {len(exploration_tasks)} sub-agents (max_concurrent={max_concurrent})")
            task_ids = []
            for i in range(0, len(exploration_tasks), max_concurrent):
                batch = exploration_tasks[i:i + max_concurrent]
                log(f"[EXPLORE] Spawning batch {i//max_concurrent + 1}: {len(batch)} agents")
                spawn_coros = [
                    manager.spawn(task, max_iterations=15)
                    for task in batch
                ]
                batch_ids = await asyncio.gather(*spawn_coros)
                task_ids.extend(batch_ids)

            yield {"type": "text", "content": f"Spawned {len(task_ids)} exploration agents. Waiting for results...\n\n"}

            # Wait for all to complete in parallel
            wait_coros = [
                manager.get_result(tid, wait=True, timeout=180)
                for tid in task_ids
            ]
            results = await asyncio.gather(*wait_coros, return_exceptions=True)

            # Collect successful results
            summaries = []
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    log(f"[EXPLORE] Agent {i} failed: {result}")
                    summaries.append(f"Agent {i+1}: Failed - {str(result)[:100]}")
                elif isinstance(result, dict) and result.get("result"):
                    summaries.append(f"Agent {i+1} ({exploration_tasks[i][:30]}...):\n{result['result']}")
                else:
                    summaries.append(f"Agent {i+1}: No result")

            yield {"type": "text", "content": "All agents completed. Synthesizing results...\n\n"}

            # Synthesize with main agent
            synthesis_prompt = f"""You explored this project with parallel agents. Here are their findings:

{chr(10).join(summaries)}

Based on these findings, provide a clear, organized summary responding to: "{message}"

Structure your response with:
1. Project Overview (what is this project?)
2. Key Components (main directories/modules)
3. Tech Stack (languages, frameworks, tools)
4. Notable Features"""

            synthesis_messages = [
                {"role": "system", "content": "Synthesize exploration results into a clear summary. You have all the information you need - DO NOT call any tools. Just write the summary directly."},
                {"role": "user", "content": synthesis_prompt},
            ]

            log(f"[SYNTHESIS] Starting synthesis (tools disabled)")
            event_count = 0
            try:
                async for event in self._agent.run(synthesis_messages, max_iterations=1, use_tools=False):
                    event_count += 1
                    log(f"[SYNTHESIS] Event {event_count}: type={event.get('type', 'unknown')}")
                    yield event
                log(f"[SYNTHESIS] Completed with {event_count} events")
            except Exception as e:
                log(f"[SYNTHESIS] ERROR: {type(e).__name__}: {e}")
                yield {"type": "error", "message": f"Synthesis failed: {str(e)}"}
                yield {"type": "done", "reason": "error"}

        finally:
            # Cleanup handled by sub-agent manager
            pass

    async def apply_code_change(
        self, instruction: str, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Apply AI-suggested changes to code.

        Args:
            instruction: What to change
            code: Original code
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("apply")
        user_prompt = self.prompt_manager.build_apply_prompt(instruction, code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    async def edit_code(
        self, instruction: str, code: str, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Edit code based on instructions.

        Args:
            instruction: What to change
            code: Original code
            language: Programming language

        Yields:
            Response chunks
        """
        system_prompt = self.prompt_manager.get_system_prompt("edit")
        user_prompt = self.prompt_manager.build_edit_prompt(instruction, code, language)

        async for chunk in self.client.stream_with_system(system_prompt, user_prompt):
            yield chunk

    @staticmethod
    def extract_code_from_response(response: str) -> Optional[str]:
        """Extract code block from AI response.

        Args:
            response: AI response text

        Returns:
            Extracted code or None
        """
        # Look for markdown code blocks
        pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Return the first (or largest) code block
            return max(matches, key=len).strip()

        return None

    async def handle_command(
        self, command: str, content: str, code: Optional[str] = None, language: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Handle slash command.

        Args:
            command: Command name (explain, refactor, fix, test, doc, apply, edit)
            content: Additional content/context
            code: Code to act on
            language: Programming language

        Yields:
            Response chunks
        """
        # Determine what code to use
        target_code = content if content else code

        if not target_code:
            yield "No code provided. Please select code or provide it after the command."
            return

        # Route to appropriate action
        if command == "explain":
            async for chunk in self.explain_code(target_code, language):
                yield chunk
        elif command == "refactor":
            async for chunk in self.refactor_code(target_code, language):
                yield chunk
        elif command == "fix":
            async for chunk in self.fix_code(target_code, language=language):
                yield chunk
        elif command == "test":
            async for chunk in self.generate_tests(target_code, language):
                yield chunk
        elif command in ["doc", "document"]:
            async for chunk in self.generate_docs(target_code, language):
                yield chunk
        elif command == "apply":
            # Split content into instruction and code
            # Format: /apply <instruction>
            # Uses selected code
            if not code:
                yield "No code selected. Select code and use /apply <instruction>"
                return
            async for chunk in self.apply_code_change(content, code, language):
                yield chunk
        elif command == "edit":
            # Format: /edit <instruction>
            # Uses selected code
            if not code:
                yield "No code selected. Select code and use /edit <instruction>"
                return
            async for chunk in self.edit_code(content, code, language):
                yield chunk
        elif command == "auto":
            # Autonomous mode - run task with full autonomy
            if not content:
                yield "Usage: /auto <task description>\n\nExample: /auto refactor the authentication module and add tests"
                return

            # Run autonomous agent
            async for event in self._agent.run_autonomous(
                task=content,
                max_iterations=50,
                checkpoint_interval=10,
            ):
                event_type = event.get("type", "")

                if event_type == "text":
                    yield event.get("content", "")
                elif event_type == "autonomous_start":
                    yield f"\n🤖 **Starting autonomous mode**\nTask: {event.get('task', '')}\n\n"
                elif event_type == "checkpoint":
                    yield f"\n📊 **Checkpoint** ({event.get('iteration', 0)}/{event.get('max_iterations', 0)} iterations)\n"
                elif event_type == "autonomous_complete":
                    yield f"\n✅ **Task complete** in {event.get('iterations', 0)} iterations\n"
                elif event_type == "autonomous_incomplete":
                    yield f"\n⚠️ **Task incomplete** - reached {event.get('iterations', 0)} iterations\n"
                elif event_type == "tool_start":
                    yield f"\n🔧 Using `{event.get('tool', '')}`: {_summarize_args(event.get('args', {}))}\n"
                elif event_type == "tool_result":
                    result = event.get("result")
                    if result is not None and hasattr(result, 'success') and not result.success:
                        yield f"❌ Tool failed: {getattr(result, 'error', 'Unknown error')}\n"
                elif event_type == "error":
                    yield f"\n❌ **Error**: {event.get('message', 'Unknown error')}\n"
        else:
            yield f"Unknown command: /{command}\nAvailable: /explain, /refactor, /fix, /test, /doc, /apply, /edit, /auto"


def _summarize_args(args: dict) -> str:
    """Summarize tool arguments for display.

    Args:
        args: Tool arguments

    Returns:
        Short summary string
    """
    if not args:
        return "(no args)"

    # Summarize common arg patterns
    if "path" in args:
        return args["path"]
    if "command" in args:
        cmd = args["command"]
        return cmd[:50] + "..." if len(cmd) > 50 else cmd
    if "pattern" in args:
        return f"pattern='{args['pattern']}'"
    if "content" in args:
        content_len = len(args.get("content", ""))
        return f"({content_len} chars)"
    if "task" in args:
        task = args["task"]
        return task[:40] + "..." if len(task) > 40 else task

    # Generic summary
    keys = list(args.keys())[:3]
    return ", ".join(f"{k}=..." for k in keys)
