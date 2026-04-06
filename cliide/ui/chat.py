"""AI chat panel widget."""

import re
import time
from pathlib import Path
from typing import Optional

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.markup import escape
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Input, Static

from cliide.ai.context_builder import ContextBuilder
from cliide.ai.event_bus import AgentEvent, AgentEventType, get_event_bus
from cliide.ai.git_assist import GitAssist
from cliide.core.events import AIRequestStarted, ToolExecutionStarted, ToolExecutionCompleted
from cliide.core.session import ChatSession
from cliide.ui.chat_tabs import ChatTabs, ChatSessionSelected, NewChatRequested, CloseChatRequested
from cliide.ui.file_picker import FilePicker
from cliide.utils.logger import log


# Language detection for syntax highlighting
LANG_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "jsx": "jsx",
    "rs": "rust",
    "rb": "ruby",
    "sh": "bash",
    "shell": "bash",
    "yml": "yaml",
    "md": "markdown",
}

# Precompiled regex patterns (avoid recompiling on every message render)
_RE_JSON_OBJECT = re.compile(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', re.DOTALL)
_RE_CODE_BLOCK_JSON = re.compile(r'```(?:json)?\s*\n?(\{.*?\})\s*\n?```', re.DOTALL)
_RE_THINK_TAG = re.compile(r'<think>(.*?)</think>', re.DOTALL)
_RE_THINKING_TAG = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
_RE_CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
_RE_FILE_MENTION = re.compile(r'@([^\s]+)')


class ChatMessage(Static):
    """A single chat message."""

    def __init__(self, content: str, is_user: bool = False, **kwargs: dict) -> None:
        """Initialize chat message.

        Args:
            content: Message content
            is_user: Whether this is a user message
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.content = content
        self.is_user = is_user
        self.thinking_expanded = False  # Track if thinking section is expanded

    def _parse_thinking(self, content: str) -> tuple[str | None, str]:
        """Parse thinking from content using JSON format.

        Args:
            content: Message content (may be JSON or plain text)

        Returns:
            Tuple of (thinking_content, main_response)
        """
        import json

        # Try to find JSON object in the content (may be mixed with other text)
        try:
            # Look for JSON object pattern anywhere in content
            # Match { ... } including nested braces
            json_match = _RE_JSON_OBJECT.search(content)

            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)

                # Check if it has the expected structure
                if isinstance(parsed, dict) and 'answer' in parsed:
                    thinking = parsed.get('thinking', '').strip() if 'thinking' in parsed else None
                    answer = parsed.get('answer', '').strip()

                    # Extract any text BEFORE the JSON (this is likely thinking shown in plain text)
                    text_before_json = content[:json_match.start()].strip()

                    # If there's text before JSON and it's not "Thinking...", treat it as thinking
                    if text_before_json and text_before_json != "Thinking...":
                        # Combine text-before with JSON thinking field
                        if thinking:
                            combined_thinking = f"{text_before_json}\n\n{thinking}"
                        else:
                            combined_thinking = text_before_json
                        return combined_thinking, answer
                    elif thinking:
                        # Only JSON thinking exists
                        return thinking, answer
                    else:
                        # No thinking, just answer
                        return None, answer

        except (json.JSONDecodeError, ValueError, KeyError):
            # JSON parsing failed, fall through
            pass

        # Try markdown code block JSON
        code_block_match = _RE_CODE_BLOCK_JSON.search(content)
        if code_block_match:
            try:
                json_str = code_block_match.group(1)
                parsed = json.loads(json_str)

                if isinstance(parsed, dict) and 'answer' in parsed:
                    thinking = parsed.get('thinking', '').strip() if 'thinking' in parsed else None
                    answer = parsed.get('answer', '').strip()

                    # Extract text before code block
                    text_before = content[:code_block_match.start()].strip()
                    if text_before and text_before != "Thinking...":
                        if thinking:
                            combined_thinking = f"{text_before}\n\n{thinking}"
                        else:
                            combined_thinking = text_before
                        return combined_thinking, answer

                    return (thinking if thinking else None), answer
            except (json.JSONDecodeError, ValueError, KeyError):
                pass

        # Fallback: Check for XML-style tags (for compatibility)
        # Support both <think> (DeepSeek) and <thinking> (others)
        for tag_pattern in [_RE_THINK_TAG, _RE_THINKING_TAG]:
            thinking_match = tag_pattern.search(content)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
                main_response = tag_pattern.sub('', content).strip()
                return thinking, main_response

        # No structured thinking detected - return content as-is
        return None, content

    def on_click(self) -> None:
        """Handle click to toggle thinking section."""
        if not self.is_user:
            thinking, _ = self._parse_thinking(self.content)
            if thinking:
                self.thinking_expanded = not self.thinking_expanded
                self.refresh()

    def _highlight_code_blocks(self, text: str) -> str:
        """Process text to add syntax highlighting markers for code blocks.

        Args:
            text: Text that may contain markdown code blocks

        Returns:
            Text with code blocks formatted for Rich rendering
        """
        def replace_code_block(match: re.Match) -> str:
            lang = match.group(1).strip().lower()
            code = match.group(2)

            # Normalize language name
            lang = LANG_ALIASES.get(lang, lang) or "text"

            # Use Rich's markup for syntax blocks
            # Escape any Rich markup in the code first
            code_escaped = escape(code.rstrip())

            # Format as a styled code block
            border = "─" * 40
            lang_label = f" {lang} " if lang and lang != "text" else ""
            return f"\n[dim]{border}[/dim][bold cyan]{lang_label}[/bold cyan]\n[on #1e2430]{code_escaped}[/on #1e2430]\n[dim]{border}[/dim]\n"

        return _RE_CODE_BLOCK.sub(replace_code_block, text)

    def render(self) -> RenderableType:
        """Render the message using Rich Markdown."""
        prefix = "👤 You" if self.is_user else "🤖 AI"

        # For AI messages, check for thinking and render as Markdown
        if not self.is_user:
            thinking, main_response = self._parse_thinking(self.content)

            # Create header text
            if thinking:
                toggle = "[-]" if self.thinking_expanded else "[+]"
                header = Text(f"{prefix}: {toggle} Show thinking\n\n", style="bold")
            else:
                header = Text(f"{prefix}: ", style="bold")

            # Render main response as Markdown
            main_md = Markdown(main_response)

            if thinking and self.thinking_expanded:
                # Show thinking section (dimmed) then main response
                thinking_header = Text("💭 Thinking:\n", style="dim italic")
                thinking_md = Markdown(thinking)
                return Group(
                    header,
                    thinking_header,
                    thinking_md,
                    Text("\n"),
                    main_md
                )
            elif thinking:
                # Thinking exists but collapsed
                return Group(header, main_md)
            else:
                # No thinking
                return Group(header, main_md)

        # User message - simple text
        return Text(f"{prefix}: {self.content}")


class ToolExecutionMessage(Static):
    """A tool execution message showing tool calls."""

    def __init__(self, tool_name: str, args: dict, result: any = None, **kwargs: dict) -> None:
        """Initialize tool execution message.

        Args:
            tool_name: Name of the tool executed
            args: Arguments passed to the tool
            result: Optional ToolResult from execution
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.args = args
        self.result = result
        self.expanded = False

    def on_click(self) -> None:
        """Toggle expanded view."""
        self.expanded = not self.expanded
        self.refresh()

    def render(self) -> str:
        """Render the tool execution message."""
        # Build args summary
        args_summary = self._format_args_summary()

        # Start with tool call header
        if self.result is None:
            # Tool started but not completed
            lines = [f"🔧 [bold cyan]{self.tool_name}[/bold cyan]({args_summary})"]
            lines.append("   ⏳ Executing...")
        elif self.result.success:
            # Tool completed successfully
            toggle = "[-]" if self.expanded else "[+]"
            lines = [f"🔧 [bold green]{self.tool_name}[/bold green]({args_summary}) {toggle}"]
            lines.append(f"   ✓ {self.result.summary}")

            # Show line numbers if available
            if hasattr(self.result, 'metadata') and self.result.metadata:
                meta = self.result.metadata
                if 'line' in meta:
                    lines.append(f"   📍 Line {meta['line']}")
                elif 'start_line' in meta and 'end_line' in meta:
                    lines.append(f"   📍 Lines {meta['start_line']}-{meta['end_line']}")

            # Show details when expanded
            if self.expanded and self.result.data:
                lines.append("")
                lines.append("   [dim]Full Result:[/dim]")
                # Truncate very long data
                data_str = str(self.result.data)
                if len(data_str) > 500:
                    data_str = data_str[:500] + "\n   [dim]...(truncated)[/dim]"
                # Indent each line
                for line in data_str.split('\n'):
                    lines.append(f"   {line}")
        else:
            # Tool failed
            lines = [f"🔧 [bold red]{self.tool_name}[/bold red]({args_summary})"]
            lines.append(f"   ✗ Error: {self.result.error}")

        return "\n".join(lines)

    def _format_args_summary(self) -> str:
        """Format arguments for display in summary."""
        if not self.args:
            return ""

        # Show key arguments in summary
        parts = []
        for key, value in list(self.args.items())[:2]:  # Show first 2 args
            value_str = str(value)
            if len(value_str) > 40:
                value_str = value_str[:40] + "..."
            # Escape newlines
            value_str = value_str.replace("\n", "\\n")
            parts.append(f"{key}={value_str!r}")

        if len(self.args) > 2:
            parts.append(f"... +{len(self.args) - 2} more")

        return ", ".join(parts)


class AgentCompletionCard(Static):
    """Distinct card showing sub-agent completion summary."""

    DEFAULT_CSS = """
    AgentCompletionCard {
        layout: vertical;
        height: auto;
        padding: 1;
        margin: 1 0;
        background: $surface;
        border: round $primary;
        color: #ffffff;
    }

    AgentCompletionCard.success {
        border: round $success;
    }

    AgentCompletionCard.failed {
        border: round $error;
    }

    AgentCompletionCard .completion-header {
        text-style: bold;
        margin-bottom: 1;
    }

    AgentCompletionCard .completion-summary {
        color: #cccccc;
        padding-left: 2;
    }

    AgentCompletionCard .completion-time {
        color: #888888;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        task_id: str,
        summary: str,
        success: bool = True,
        duration: float | None = None,
        **kwargs: dict,
    ) -> None:
        """Initialize completion card.

        Args:
            task_id: Sub-agent task identifier
            summary: Completion summary text
            success: Whether the task succeeded
            duration: Optional duration in seconds
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.task_id = task_id
        self.summary = summary
        self.success = success
        self.duration = duration

        # Set appropriate CSS class
        if success:
            self.add_class("success")
        else:
            self.add_class("failed")

    def render(self) -> str:
        """Render the completion card."""
        status_icon = "[bold green]✅[/bold green]" if self.success else "[bold red]❌[/bold red]"
        status_text = "completed" if self.success else "failed"

        lines = [
            f"{status_icon} [bold]Agent [{self.task_id[:8]}] {status_text}[/bold]",
            "",
        ]

        # Truncate summary if too long
        summary = self.summary
        if len(summary) > 200:
            summary = summary[:197] + "..."

        # Split summary into lines and indent
        for line in summary.split('\n'):
            lines.append(f"  {line}")

        # Add duration if available
        if self.duration is not None:
            lines.append("")
            lines.append(f"  [dim italic]Duration: {self.duration:.1f}s[/dim italic]")

        return "\n".join(lines)


class ChatPanel(Widget):
    """AI chat panel widget."""

    DEFAULT_CSS = """
    ChatPanel {
        layout: vertical;
    }

    #chat-messages {
        height: 1fr;
        border: round $primary;
        background: $background;
    }

    #chat-header {
        color: $primary;
        text-style: bold;
        border-bottom: heavy $primary;
        padding: 0 1;
        background: $boost;
    }

    #chat-input {
        dock: bottom;
        height: auto;
        border: round $accent;
        background: $surface;
    }

    ChatMessage {
        margin: 0;
        padding: 0 1;
        border-left: heavy $primary;
    }

    ChatMessage:hover {
        background: $boost;
    }

    .user-message {
        background: $boost;
        border-left: heavy $accent;
        color: $accent;
    }

    .ai-message {
        background: $panel;
        border-left: heavy $success;
        color: $text;
    }

    .ai-message:hover {
        background: $surface;
        text-style: none;
    }

    ToolExecutionMessage {
        margin: 0;
        padding: 0 1;
        border-left: heavy $warning;
        background: $panel;
        color: $text;
    }

    ToolExecutionMessage:hover {
        background: $surface;
    }
    """

    def __init__(self, workspace_path: Optional[Path] = None, **kwargs: dict) -> None:
        """Initialize chat panel.

        Args:
            workspace_path: Workspace root path for file picker
            **kwargs: Additional arguments for Widget
        """
        super().__init__(**kwargs)
        self.conversation_history: list[dict[str, str]] = []
        self.current_ai_message: Optional[ChatMessage] = None
        self.workspace_path = workspace_path or Path.cwd()
        self.file_picker: Optional[FilePicker] = None
        self.at_symbol_position: Optional[int] = None
        self.mentioned_files: list[str] = []

        # Multi-session support
        self.sessions: dict[str, ChatSession] = {}
        self.active_session_id: str | None = None

        # Chunk buffering for reduced UI updates
        self._chunk_buffer: str = ""
        self._last_flush_time: float = 0.0
        self._flush_interval: float = 0.05  # 50ms batching
        self._user_at_bottom: bool = True  # Track if user is scrolled to bottom

        # Track active tool messages for correlation
        self._active_tool_messages: dict[str, any] = {}

        # Request ID for streaming correlation (prevents stale closure issues)
        self._current_request_id: int = 0
        self._streaming_request_id: int | None = None

        # Tool message TTL tracking for cleanup
        self._tool_message_timestamps: dict[str, float] = {}
        self._tool_ttl_seconds: float = 30.0  # Clean up orphaned tool messages after 30s

    def compose(self) -> ComposeResult:
        """Compose the chat panel."""
        yield ChatTabs(id="chat-tabs")

        with VerticalScroll(id="chat-messages"):
            yield Static("AI Chat - Ask questions or request code actions", id="chat-header")

        yield Input(placeholder="Ask AI anything...", id="chat-input")

    def on_mount(self) -> None:
        """Handle mount - focus the input and subscribe to events."""
        # Give input focus after a brief delay to ensure it's rendered
        self.set_timer(0.1, lambda: self.query_one("#chat-input", Input).focus())

        # Event bus reference (subscriptions disabled - agent status shown in Agent panel instead)
        self._event_bus = get_event_bus()
        # self._event_bus.subscribe(AgentEventType.TASK_COMPLETED, self._on_agent_completed)
        # self._event_bus.subscribe(AgentEventType.TASK_FAILED, self._on_agent_failed)

        # Initialize default session if none exists
        if not self.sessions:
            self.create_new_session("Main")

    def on_unmount(self) -> None:
        """Unsubscribe from events on unmount."""
        # Agent completion subscriptions disabled - nothing to unsubscribe
        pass

    # -------------------------------------------------------------------------
    # Multi-session management
    # -------------------------------------------------------------------------

    def create_new_session(self, name: str | None = None) -> str:
        """Create a new chat session and switch to it.

        Args:
            name: Optional name for the session

        Returns:
            The new session's ID
        """
        import uuid
        from datetime import datetime

        session_id = str(uuid.uuid4())[:8]
        name = name or f"Chat {len(self.sessions) + 1}"

        session = ChatSession(
            id=session_id,
            name=name,
            history=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.sessions[session_id] = session

        # Update tabs UI
        try:
            chat_tabs = self.query_one("#chat-tabs", ChatTabs)
            chat_tabs.add_session(session_id, name)
        except NoMatches:
            pass  # Tabs not mounted yet during initialization

        # Switch to the new session
        self.switch_to_session(session_id)

        log(f"[CHAT] Created new session: {name} ({session_id})")
        return session_id

    def switch_to_session(self, session_id: str) -> None:
        """Switch to a different chat session.

        Args:
            session_id: ID of the session to switch to
        """
        if session_id not in self.sessions:
            log(f"[CHAT] Session not found: {session_id}")
            return

        # Save current session's history
        if self.active_session_id and self.active_session_id in self.sessions:
            self.sessions[self.active_session_id].history = self.conversation_history.copy()

        # Load new session
        self.active_session_id = session_id
        session = self.sessions[session_id]
        self.conversation_history = session.history.copy()

        # Clear and re-render messages
        self._render_session_messages()

        # Update tabs UI
        try:
            chat_tabs = self.query_one("#chat-tabs", ChatTabs)
            chat_tabs.set_active(session_id)
        except NoMatches:
            pass  # Tabs not mounted yet

        log(f"[CHAT] Switched to session: {session.name} ({session_id})")

    def _render_session_messages(self) -> None:
        """Clear and re-render all messages for the current session."""
        try:
            messages_container = self.query_one("#chat-messages", VerticalScroll)

            # Remove all messages except the header
            for child in list(messages_container.children):
                if child.id != "chat-header":
                    child.remove()

            # Re-render messages from history
            for msg in self.conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "user":
                    message_widget = ChatMessage(content, is_user=True)
                    message_widget.add_class("user-message")
                elif role == "assistant":
                    message_widget = ChatMessage(content, is_user=False)
                    message_widget.add_class("ai-message")
                else:
                    continue  # Skip system messages

                messages_container.mount(message_widget)

            # Reset current AI message tracker
            self.current_ai_message = None

            # Scroll to bottom
            self.call_later(lambda: messages_container.scroll_end(animate=False))
        except Exception as e:
            log(f"[CHAT] Error rendering session: {e}")

    def delete_session(self, session_id: str) -> None:
        """Delete a chat session.

        Args:
            session_id: ID of the session to delete
        """
        if session_id not in self.sessions:
            return

        # Can't delete the only session
        if len(self.sessions) <= 1:
            log("[CHAT] Cannot delete the only session")
            return

        # Remove from sessions
        del self.sessions[session_id]

        # Update tabs UI
        try:
            chat_tabs = self.query_one("#chat-tabs", ChatTabs)
            chat_tabs.remove_session(session_id)
        except NoMatches:
            pass  # Tabs not mounted

        # If we deleted the active session, switch to another
        if self.active_session_id == session_id:
            remaining_id = list(self.sessions.keys())[0]
            self.switch_to_session(remaining_id)

        log(f"[CHAT] Deleted session: {session_id}")

    def get_all_sessions(self) -> list[ChatSession]:
        """Get all chat sessions for persistence.

        Returns:
            List of all ChatSession objects
        """
        # Ensure current session is up to date
        if self.active_session_id and self.active_session_id in self.sessions:
            self.sessions[self.active_session_id].history = self.conversation_history.copy()

        return list(self.sessions.values())

    def restore_sessions(
        self, sessions: list[ChatSession], active_id: str | None = None
    ) -> None:
        """Restore chat sessions from saved state.

        Args:
            sessions: List of sessions to restore
            active_id: ID of the session to make active
        """
        # Clear existing sessions
        self.sessions.clear()
        self.conversation_history = []
        self.active_session_id = None

        # Clear messages UI
        try:
            messages_container = self.query_one("#chat-messages", VerticalScroll)
            for child in list(messages_container.children):
                if child.id != "chat-header":
                    child.remove()
        except NoMatches:
            pass  # Container not mounted yet

        # Restore sessions
        for session in sessions:
            self.sessions[session.id] = session
            try:
                chat_tabs = self.query_one("#chat-tabs", ChatTabs)
                chat_tabs.add_session(session.id, session.name)
            except NoMatches:
                pass  # Tabs not mounted during restore

        # Switch to active session (or first available)
        if active_id and active_id in self.sessions:
            self.switch_to_session(active_id)
        elif self.sessions:
            self.switch_to_session(list(self.sessions.keys())[0])
        else:
            # No sessions to restore, create a default one
            self.create_new_session("Main")

        log(f"[CHAT] Restored {len(sessions)} sessions")

    def clear_all_sessions(self) -> None:
        """Clear all sessions and create a fresh one."""
        self.sessions.clear()
        self.conversation_history = []
        self.active_session_id = None

        # Clear tabs
        try:
            chat_tabs = self.query_one("#chat-tabs", ChatTabs)
            for sid in list(chat_tabs._sessions.keys()):
                chat_tabs.remove_session(sid)
        except NoMatches:
            pass  # Tabs not mounted

        # Clear messages
        self._render_session_messages()

        # Create default session
        self.create_new_session("Main")

    # Event handlers for ChatTabs messages

    def on_chat_session_selected(self, event: ChatSessionSelected) -> None:
        """Handle session selection from tabs.

        Args:
            event: Session selected event
        """
        self.switch_to_session(event.session_id)

    def on_new_chat_requested(self, event: NewChatRequested) -> None:
        """Handle new chat request from tabs.

        Args:
            event: New chat requested event
        """
        self.create_new_session()

    def on_close_chat_requested(self, event: CloseChatRequested) -> None:
        """Handle close chat request from tabs.

        Args:
            event: Close chat requested event
        """
        self.delete_session(event.session_id)

    async def _on_agent_completed(self, event: AgentEvent) -> None:
        """Handle sub-agent completion events."""
        # Ignore main agent events
        if event.source_id == "main":
            return

        task_id = event.source_id
        result = event.data.get("result", "Task completed")
        duration = event.data.get("duration")

        # Add completion card at the bottom of chat
        self.add_agent_completion(
            task_id=task_id,
            summary=result,
            success=True,
            duration=duration,
        )

    async def _on_agent_failed(self, event: AgentEvent) -> None:
        """Handle sub-agent failure events."""
        # Ignore main agent events
        if event.source_id == "main":
            return

        task_id = event.source_id
        error = event.data.get("error", "Unknown error")
        duration = event.data.get("duration")

        # Add failure card at the bottom of chat
        self.add_agent_completion(
            task_id=task_id,
            summary=f"Error: {error}",
            success=False,
            duration=duration,
        )

    def on_vertical_scroll_scroll_y(self) -> None:
        """Track scroll position to know if user is at bottom."""
        try:
            messages = self.query_one("#chat-messages", VerticalScroll)
            # Check if we're within 50 pixels of the bottom
            # This allows for some tolerance so small content changes don't break tracking
            at_bottom = (messages.max_scroll_y - messages.scroll_y) < 50
            self._user_at_bottom = at_bottom
        except Exception:
            pass

    def send_message(self, message: str) -> None:
        """Send a message to the AI.

        Args:
            message: Message to send
        """
        if not message.strip():
            return

        # Handle slash commands
        if message.startswith("/"):
            self._handle_slash_command(message)
            return

        # Check for @mentioned files FIRST and create enhanced message
        mentioned_files = self.get_mentioned_files_content(message)
        enhanced_message = message

        if mentioned_files:
            # Format files and add to message
            files_context = ContextBuilder.format_mentioned_files(mentioned_files)
            enhanced_message = f"{message}{files_context}"
            log(f"[CHAT] Enhanced message with {len(mentioned_files)} files, total length: {len(enhanced_message)}")

        # Add ENHANCED message to conversation history (with file content)
        self.conversation_history.append({"role": "user", "content": enhanced_message})

        # Add user message to chat (display original, not the enhanced version with file dumps)
        messages = self.query_one("#chat-messages")
        user_msg = ChatMessage(message, is_user=True)
        user_msg.add_class("user-message")
        messages.mount(user_msg)

        # Show which files were loaded
        if mentioned_files:
            files_list = ", ".join(mentioned_files.keys())
            system_msg = ChatMessage(f"📎 Loaded files: {files_list}", is_user=False)
            system_msg.add_class("ai-message")
            messages.mount(system_msg)
            log(f"[CHAT] Displaying loaded files to user: {files_list}")

        # Clear input
        chat_input = self.query_one("#chat-input", Input)
        chat_input.value = ""

        # Call AI handler with ENHANCED message
        log(f"[CHAT] Calling AI handler with enhanced message (length: {len(enhanced_message)})")
        from cliide.core.events import AIRequestStarted
        event = AIRequestStarted(enhanced_message)

        # Get the app and call the handler directly
        if hasattr(self.app, 'on_ai_request_started'):
            log(f"[CHAT] Found handler, calling it")
            self.app.on_ai_request_started(event)
        else:
            log(f"[CHAT] ERROR: No handler found on app!")

        # Add placeholder for AI response with request ID tracking
        self._current_request_id += 1
        self._streaming_request_id = self._current_request_id
        ai_msg = ChatMessage("Thinking...", is_user=False)
        ai_msg.add_class("ai-message")
        self.current_ai_message = ai_msg
        messages.mount(ai_msg)

        # Scroll to bottom
        messages.scroll_end(animate=False)

    def _handle_slash_command(self, message: str) -> None:
        """Handle slash commands like /commit and /review.

        Args:
            message: Command message starting with /
        """
        command = message.split()[0].lower()
        args = message[len(command):].strip()

        if command == "/commit":
            self.run_worker(self._handle_commit_command(args))
        elif command == "/review":
            self.run_worker(self._handle_review_command())
        elif command == "/diff":
            self.run_worker(self._handle_diff_command())
        elif command == "/undo":
            self.run_worker(self._handle_undo_command())
        elif command == "/help":
            self._show_command_help()
        else:
            # Unknown command, show as message
            messages = self.query_one("#chat-messages")
            error_msg = ChatMessage(f"Unknown command: {command}\nType /help for available commands.", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            messages.scroll_end(animate=False)

    def _show_command_help(self) -> None:
        """Show available slash commands."""
        help_text = """**Available Commands:**

• `/commit` - Generate AI commit message for staged changes
• `/commit -a` - Stage all changes and generate commit message
• `/diff` - Show uncommitted changes (staged + unstaged)
• `/undo` - Undo the last cliide-generated commit
• `/review` - AI review of uncommitted changes
• `/help` - Show this help message"""

        messages = self.query_one("#chat-messages")
        help_msg = ChatMessage(help_text, is_user=False)
        help_msg.add_class("ai-message")
        messages.mount(help_msg)
        messages.scroll_end(animate=False)

    async def _handle_commit_command(self, args: str) -> None:
        """Handle /commit command.

        Args:
            args: Command arguments (-a to stage all)
        """
        messages = self.query_one("#chat-messages")
        git_assist = GitAssist(self.workspace_path)

        if not git_assist.is_git_repo:
            error_msg = ChatMessage("❌ Not a git repository", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Stage all if -a flag
        if "-a" in args:
            status_msg = ChatMessage("📦 Staging all changes...", is_user=False)
            status_msg.add_class("ai-message")
            messages.mount(status_msg)
            messages.scroll_end(animate=False)

            success, msg = await git_assist.stage_all()
            if not success:
                error_msg = ChatMessage(f"❌ Failed to stage: {msg}", is_user=False)
                error_msg.add_class("ai-message")
                messages.mount(error_msg)
                return

        # Get staged diff
        diff = await git_assist.get_staged_diff()
        if not diff:
            error_msg = ChatMessage("❌ No staged changes. Stage files with `git add` or use `/commit -a`", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        staged_files = await git_assist.get_staged_files()

        # Show status
        files_list = ", ".join(staged_files[:5])
        if len(staged_files) > 5:
            files_list += f" (+{len(staged_files) - 5} more)"

        status_msg = ChatMessage(f"🔍 Analyzing changes in: {files_list}", is_user=False)
        status_msg.add_class("ai-message")
        messages.mount(status_msg)
        messages.scroll_end(animate=False)

        # Generate commit message prompt
        prompt = git_assist.generate_commit_prompt(diff, staged_files)

        # Send to AI
        self.conversation_history.append({"role": "user", "content": prompt})

        # Create placeholder for AI response
        ai_msg = ChatMessage("✨ Generating commit message...", is_user=False)
        ai_msg.add_class("ai-message")
        self.current_ai_message = ai_msg
        messages.mount(ai_msg)
        messages.scroll_end(animate=False)

        # Call AI handler
        from cliide.core.events import AIRequestStarted
        event = AIRequestStarted(prompt)
        if hasattr(self.app, 'on_ai_request_started'):
            self.app.on_ai_request_started(event)

    async def _handle_review_command(self) -> None:
        """Handle /review command for AI code review."""
        messages = self.query_one("#chat-messages")
        git_assist = GitAssist(self.workspace_path)

        if not git_assist.is_git_repo:
            error_msg = ChatMessage("❌ Not a git repository", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Get all changes (staged + unstaged)
        diff = await git_assist.get_all_changes_diff()
        if not diff:
            error_msg = ChatMessage("❌ No uncommitted changes to review", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Show status
        status_msg = ChatMessage("🔍 Reviewing your changes...", is_user=False)
        status_msg.add_class("ai-message")
        messages.mount(status_msg)
        messages.scroll_end(animate=False)

        # Generate review prompt
        prompt = git_assist.generate_review_prompt(diff)

        # Send to AI
        self.conversation_history.append({"role": "user", "content": prompt})

        # Create placeholder for AI response
        ai_msg = ChatMessage("📝 Generating code review...", is_user=False)
        ai_msg.add_class("ai-message")
        self.current_ai_message = ai_msg
        messages.mount(ai_msg)
        messages.scroll_end(animate=False)

        # Call AI handler
        from cliide.core.events import AIRequestStarted
        event = AIRequestStarted(prompt)
        if hasattr(self.app, 'on_ai_request_started'):
            self.app.on_ai_request_started(event)

    async def _handle_diff_command(self) -> None:
        """Handle /diff command to show uncommitted changes."""
        messages = self.query_one("#chat-messages")
        git_assist = GitAssist(self.workspace_path)

        if not git_assist.is_git_repo:
            error_msg = ChatMessage("❌ Not a git repository", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Get status first
        status = await git_assist.get_status()
        if not status:
            info_msg = ChatMessage("✅ Working tree clean - no uncommitted changes", is_user=False)
            info_msg.add_class("ai-message")
            messages.mount(info_msg)
            return

        # Get full diff
        diff = await git_assist.get_all_changes_diff()

        if not diff:
            # Show status even if diff is empty (e.g., untracked files)
            status_msg = ChatMessage(f"📋 **Git Status:**\n```\n{status}\n```", is_user=False)
            status_msg.add_class("ai-message")
            messages.mount(status_msg)
        else:
            # Truncate diff if too long
            max_diff_length = 5000
            if len(diff) > max_diff_length:
                diff = diff[:max_diff_length] + "\n\n[... diff truncated ...]"

            diff_msg = ChatMessage(f"📋 **Git Status:**\n```\n{status}\n```\n\n**Changes:**\n```diff\n{diff}\n```", is_user=False)
            diff_msg.add_class("ai-message")
            messages.mount(diff_msg)

        messages.scroll_end(animate=False)

    async def _handle_undo_command(self) -> None:
        """Handle /undo command to revert last AI commit."""
        from cliide.ai.git_assist import CLIIDE_MARKER

        messages = self.query_one("#chat-messages")
        git_assist = GitAssist(self.workspace_path)

        if not git_assist.is_git_repo:
            error_msg = ChatMessage("❌ Not a git repository", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Get last commit info
        commit_info = await git_assist.get_last_commit_info()
        if not commit_info:
            error_msg = ChatMessage("❌ Could not get last commit info", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)
            return

        # Check if it was a cliide commit
        if not git_assist.is_cliide_commit(commit_info["message"]):
            warn_msg = ChatMessage(
                f"⚠️ Last commit was not made by cliide:\n\n"
                f"**{commit_info['message'][:50]}{'...' if len(commit_info['message']) > 50 else ''}**\n\n"
                f"Only cliide-generated commits (marked with `{CLIIDE_MARKER}`) can be undone with `/undo`.\n"
                f"Use `git reset --soft HEAD~1` manually if you want to undo this commit.",
                is_user=False
            )
            warn_msg.add_class("ai-message")
            messages.mount(warn_msg)
            return

        # Undo the commit
        status_msg = ChatMessage(f"🔄 Undoing commit: **{commit_info['message'][:50]}**...", is_user=False)
        status_msg.add_class("ai-message")
        messages.mount(status_msg)
        messages.scroll_end(animate=False)

        success, result = await git_assist.reset_last_commit(soft=True)

        if success:
            success_msg = ChatMessage(
                f"✅ Commit undone successfully!\n\n"
                f"Changes from **{commit_info['message'][:50]}** are now staged.\n"
                f"You can modify them and commit again.",
                is_user=False
            )
            success_msg.add_class("ai-message")
            messages.mount(success_msg)
        else:
            error_msg = ChatMessage(f"❌ Failed to undo commit: {result}", is_user=False)
            error_msg.add_class("ai-message")
            messages.mount(error_msg)

        messages.scroll_end(animate=False)

    def start_ai_response(self, request_id: int | None = None) -> None:
        """Start a new AI response (replaces "Thinking..." with empty message).

        Args:
            request_id: Optional request ID to validate against current streaming
        """
        # Check request ID to prevent stale closures
        if request_id is not None and request_id != self._streaming_request_id:
            log(f"[CHAT] Ignoring start_ai_response for stale request {request_id}")
            return

        if self.current_ai_message and self.current_ai_message.content == "Thinking...":
            self.current_ai_message.content = ""
            self.current_ai_message.refresh()  # Just refresh, don't manually update text

    def append_ai_chunk(self, chunk: str, request_id: int | None = None) -> None:
        """Append a chunk to the current AI response.

        Uses buffering to batch UI updates for better performance.

        Args:
            chunk: Text chunk to append
            request_id: Optional request ID to validate against current streaming
        """
        # Check request ID to prevent stale closures
        if request_id is not None and request_id != self._streaming_request_id:
            log(f"[CHAT] Ignoring chunk for stale request {request_id}")
            return

        if not self.current_ai_message:
            return

        # Add chunk to buffer
        self._chunk_buffer += chunk

        # Check if we should flush
        now = time.monotonic()
        if now - self._last_flush_time >= self._flush_interval:
            self._flush_chunk_buffer()

    def _flush_chunk_buffer(self) -> None:
        """Flush the chunk buffer to the UI."""
        if not self._chunk_buffer or not self.current_ai_message:
            return

        # Update message content
        self.current_ai_message.content += self._chunk_buffer
        self._chunk_buffer = ""
        self._last_flush_time = time.monotonic()

        # Refresh the message widget
        self.current_ai_message.refresh()

        # Only scroll if user was at bottom (don't interrupt reading)
        if self._user_at_bottom:
            messages = self.query_one("#chat-messages")
            messages.scroll_end(animate=False)

    def finish_ai_response(self, request_id: int | None = None) -> None:
        """Finish the current AI response.

        Args:
            request_id: Optional request ID to validate against current streaming
        """
        # Check request ID to prevent stale closures
        if request_id is not None and request_id != self._streaming_request_id:
            log(f"[CHAT] Ignoring finish_ai_response for stale request {request_id}")
            return

        # Flush any remaining buffered chunks
        self._flush_chunk_buffer()

        if self.current_ai_message:
            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": self.current_ai_message.content
            })
            self.current_ai_message = None

        # Reset buffer state
        self._chunk_buffer = ""
        self._streaming_request_id = None
        self._user_at_bottom = True  # Reset scroll tracking

    def add_ai_response(self, response: str) -> None:
        """Add complete AI response to chat (non-streaming).

        Args:
            response: AI response text
        """
        messages = self.query_one("#chat-messages")

        # Remove "Thinking..." placeholder
        if self.current_ai_message:
            self.current_ai_message.remove()

        # Add AI response
        ai_msg = ChatMessage(response, is_user=False)
        ai_msg.add_class("ai-message")
        messages.mount(ai_msg)

        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": response})
        self.current_ai_message = None

        # Scroll to bottom
        messages.scroll_end(animate=False)

    def add_error_message(self, error: str) -> None:
        """Add an error message to chat.

        Args:
            error: Error message
        """
        messages = self.query_one("#chat-messages")

        # Remove placeholder if exists
        if self.current_ai_message:
            self.current_ai_message.remove()

        # Add error message
        error_msg = ChatMessage(f"❌ Error: {error}", is_user=False)
        error_msg.add_class("ai-message")
        messages.mount(error_msg)

        self.current_ai_message = None

        # Scroll to bottom
        messages.scroll_end(animate=False)

    def add_agent_completion(
        self,
        task_id: str,
        summary: str,
        success: bool = True,
        duration: float | None = None,
    ) -> None:
        """Add agent completion card at the bottom of chat.

        This ensures the completion summary always appears at the END of the chat,
        after any tool spam, providing a clear final status.

        Args:
            task_id: Sub-agent task identifier
            summary: Completion summary text
            success: Whether the task succeeded
            duration: Optional duration in seconds
        """
        messages = self.query_one("#chat-messages")

        # Create and mount the completion card
        card = AgentCompletionCard(
            task_id=task_id,
            summary=summary,
            success=success,
            duration=duration,
        )
        messages.mount(card)

        # Always scroll to show the completion
        messages.scroll_end(animate=False)
        self._user_at_bottom = True  # Reset scroll tracking

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history.

        Returns:
            List of message dicts
        """
        return self.conversation_history.copy()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission.

        Args:
            event: Input submitted event
        """
        # Only handle if it's from our chat input
        if event.input.id == "chat-input":
            # If file picker is open, select file instead of sending message
            if self.file_picker and self.file_picker.is_attached:
                try:
                    list_view = self.file_picker.query_one("#file-picker-list")
                    if list_view.index is not None and list_view.index < len(self.file_picker.files):
                        file_path = self.file_picker.files[list_view.index]
                        self.on_file_picker_file_selected(FilePicker.FileSelected(file_path))
                    event.stop()
                except Exception:
                    # Picker was removed, just send message normally
                    event.stop()
                    self.send_message(event.value)
            else:
                event.stop()  # Prevent bubbling
                self.send_message(event.value)

    def on_key(self, event) -> None:
        """Handle key events for file picker navigation.

        Args:
            event: Key event
        """
        # If file picker is open, intercept navigation keys
        if self.file_picker and self.file_picker.is_attached and hasattr(event, 'key'):
            if event.key == 'escape':
                # Close file picker
                self._close_file_picker()
                event.stop()
                event.prevent_default()
            elif event.key in ('up', 'down'):
                # Navigate file list
                try:
                    list_view = self.file_picker.query_one("#file-picker-list")
                    current_index = list_view.index or 0

                    if event.key == 'down':
                        new_index = min(current_index + 1, len(self.file_picker.files) - 1)
                    else:  # up
                        new_index = max(current_index - 1, 0)

                    list_view.index = new_index
                    event.stop()  # Don't let input handle arrow keys
                    event.prevent_default()
                except Exception:
                    # Picker was removed, ignore
                    pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to detect @ for file picker.

        Args:
            event: Input changed event
        """
        # Only handle if it's from our chat input
        if event.input.id != "chat-input":
            return

        value = event.value
        cursor_pos = len(value)  # Textual Input doesn't expose cursor position, use end

        # Check if @ was just typed
        if value and value[-1] == "@":
            self.at_symbol_position = cursor_pos - 1
            self._show_file_picker("")
        elif self.file_picker and self.at_symbol_position is not None:
            # Update file picker filter based on text after @
            text_after_at = value[self.at_symbol_position + 1:]
            # If there's a space, close the file picker
            if " " in text_after_at:
                self._close_file_picker()
            else:
                # Guard against picker being removed - check if it's still mounted
                if self.file_picker and self.file_picker.is_attached:
                    self.file_picker.update_filter(text_after_at)
        elif self.file_picker and "@" not in value:
            # @ was deleted, close file picker
            self._close_file_picker()

    def _show_file_picker(self, filter_text: str = "") -> None:
        """Show the file picker popup.

        Args:
            filter_text: Initial filter text
        """
        # Remove existing picker if any
        self._close_file_picker()

        # Create and mount new file picker to ChatPanel so messages bubble here
        self.file_picker = FilePicker(self.workspace_path, filter_text)
        self.mount(self.file_picker)

    def _close_file_picker(self) -> None:
        """Close the file picker if open."""
        if self.file_picker:
            # Store reference and clear it first
            picker = self.file_picker
            self.file_picker = None
            self.at_symbol_position = None
            # Then remove from DOM
            if picker.is_attached:
                picker.remove()

    def on_file_picker_file_selected(self, event: FilePicker.FileSelected) -> None:
        """Handle file selection from file picker.

        Args:
            event: File selected event
        """
        from cliide.utils.logger import log
        log(f"[CHAT] File selected: {event.file_path}")

        # Save position BEFORE closing (which clears it)
        at_pos = self.at_symbol_position
        log(f"[CHAT] at_symbol_position: {at_pos}")

        # Close file picker to prevent update_filter being called
        self._close_file_picker()

        chat_input = self.query_one("#chat-input", Input)
        current_value = chat_input.value
        log(f"[CHAT] Current value: '{current_value}'")

        if at_pos is not None:
            # Replace everything after @ with @filename
            before_at = current_value[:at_pos]
            new_value = f"{before_at}@{event.file_path} "
            log(f"[CHAT] Setting new value: '{new_value}'")

            # Refocus FIRST, then set value
            chat_input.focus()
            chat_input.value = new_value

            # Move cursor to end and clear any selection
            self.call_after_refresh(lambda: self._set_cursor_end(chat_input, len(new_value)))
            log(f"[CHAT] Scheduled cursor move to position: {len(new_value)}")

            # Track mentioned file
            if event.file_path not in self.mentioned_files:
                self.mentioned_files.append(event.file_path)

    def _set_cursor_end(self, input_widget: Input, position: int) -> None:
        """Set cursor to end position after refresh.

        Args:
            input_widget: The input widget
            position: Cursor position to set
        """
        from cliide.utils.logger import log
        if input_widget is None:
            log("[CHAT] _set_cursor_end called with None input_widget")
            return
        input_widget.cursor_position = position
        # Also clear any selection by setting cursor blink to visible
        input_widget.action_cursor_right()
        input_widget.action_cursor_left()
        log(f"[CHAT] Cursor set to end position: {position}")

    def extract_file_mentions(self, message: str) -> list[str]:
        """Extract @file mentions from message.

        Args:
            message: Chat message

        Returns:
            List of file paths mentioned
        """
        # Pattern to match @filename (ends at space or end of string)
        matches = _RE_FILE_MENTION.findall(message)
        return matches

    def get_mentioned_files_content(self, message: str) -> dict[str, str]:
        """Get content of all @mentioned files.

        Args:
            message: Chat message

        Returns:
            Dict mapping file path to content
        """
        file_mentions = self.extract_file_mentions(message)
        log(f"[CHAT] Extracted file mentions from message: {file_mentions}")
        file_contents: dict[str, str] = {}

        MAX_FILE_SIZE = 100_000  # 100KB limit for @mentioned files

        for file_path in file_mentions:
            full_path = self.workspace_path / file_path
            log(f"[CHAT] Checking file: {full_path}, exists: {full_path.exists()}, is_file: {full_path.is_file() if full_path.exists() else False}")
            if full_path.exists() and full_path.is_file():
                try:
                    file_size = full_path.stat().st_size
                    if file_size > MAX_FILE_SIZE:
                        file_contents[file_path] = f"[File too large: {file_size:,} bytes. Max: {MAX_FILE_SIZE:,} bytes]"
                        log(f"[CHAT] File {file_path} too large: {file_size} bytes")
                        continue
                    content = full_path.read_text(encoding="utf-8")
                    file_contents[file_path] = content
                    log(f"[CHAT] Successfully read file {file_path}, length: {len(content)}")
                except Exception as e:
                    log(f"[CHAT] Error reading @mentioned file {file_path}: {e}")
            else:
                log(f"[CHAT] File not found or not a file: {full_path}")

        log(f"[CHAT] Returning {len(file_contents)} file contents")
        return file_contents

    def get_current_request_id(self) -> int | None:
        """Get the current streaming request ID.

        Returns:
            Current request ID or None if not streaming
        """
        return self._streaming_request_id

    def add_tool_execution(self, tool_name: str, args: dict, tool_call_id: str | None = None) -> ToolExecutionMessage:
        """Add a tool execution message to chat.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            tool_call_id: Optional ID for tracking

        Returns:
            The created ToolExecutionMessage widget
        """
        # Clean up any expired tool messages first
        self._cleanup_expired_tool_messages()

        messages = self.query_one("#chat-messages")
        tool_msg = ToolExecutionMessage(tool_name, args)
        messages.mount(tool_msg)
        messages.scroll_end(animate=False)

        # Track timestamp for TTL cleanup
        if tool_call_id:
            self._tool_message_timestamps[tool_call_id] = time.monotonic()

        return tool_msg

    def _cleanup_expired_tool_messages(self) -> None:
        """Remove tool messages that have exceeded TTL without completion."""
        now = time.monotonic()
        expired_ids = [
            tool_id for tool_id, timestamp in self._tool_message_timestamps.items()
            if now - timestamp > self._tool_ttl_seconds
        ]

        for tool_id in expired_ids:
            # Remove from tracking
            self._tool_message_timestamps.pop(tool_id, None)
            self._active_tool_messages.pop(tool_id, None)
            log(f"[CHAT] Cleaned up expired tool message: {tool_id}")

    def update_tool_execution(self, tool_msg: ToolExecutionMessage, result: any) -> None:
        """Update a tool execution message with result.

        Args:
            tool_msg: The tool message to update
            result: Tool result
        """
        tool_msg.result = result
        tool_msg.refresh()

    def on_tool_execution_started(self, event: ToolExecutionStarted) -> None:
        """Handle tool execution started event.

        Args:
            event: Tool execution started event
        """
        log(f"[CHAT] Tool execution started: {event.tool_name}")
        # Track the tool message for later updates
        tool_msg = self.add_tool_execution(event.tool_name, event.args, event.tool_call_id)

        # Store reference with tool_call_id for updates
        if event.tool_call_id:
            self._active_tool_messages[event.tool_call_id] = tool_msg

    def on_tool_execution_completed(self, event: ToolExecutionCompleted) -> None:
        """Handle tool execution completed event.

        Args:
            event: Tool execution completed event
        """
        log(f"[CHAT] Tool execution completed: {event.tool_name}")

        # Find and update the corresponding tool message
        if event.tool_call_id in self._active_tool_messages:
            tool_msg = self._active_tool_messages[event.tool_call_id]
            self.update_tool_execution(tool_msg, event.result)
            # Clean up the references
            del self._active_tool_messages[event.tool_call_id]
            self._tool_message_timestamps.pop(event.tool_call_id, None)

    def clear_tool_messages(self) -> None:
        """Remove all tool execution messages from chat."""
        try:
            tool_messages = self.query(ToolExecutionMessage)
            for msg in tool_messages:
                msg.remove()
            # Clear tracking dicts
            self._active_tool_messages.clear()
            self._tool_message_timestamps.clear()
            log("[CHAT] Cleared tool messages")
        except Exception as e:
            log(f"[CHAT] Error clearing tool messages: {e}")
