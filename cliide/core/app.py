"""Main cliide application."""

import sys
from pathlib import Path
from typing import Any

import aiofiles
import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header

from cliide.ai.code_actions import CodeActions
from cliide.ai.context_builder import ContextBuilder
from cliide.ai.event_bus import AgentEvent, AgentEventType, get_event_bus
from cliide.ai.prompt_manager import PromptManager
from cliide.core.config import Config, get_config
from cliide.core.events import AIRequestStarted, CommandExecuted, FileOpened, ToolConfirmationResult
from cliide.core.recent_projects import RecentProjectsManager
from cliide.core.session import SessionManager, SessionState
from cliide.lsp.manager import LanguageServerManager
from cliide.editor.formatting import CodeFormatter
from cliide.themes import CLIIDE_THEME
from cliide.ui.chat import ChatPanel
from cliide.ui.command_palette import CommandPalette
from cliide.ui.completion_menu import CompletionMenu
from cliide.ui.diff_view import DiffView
from cliide.ui.editor import EditorWidget
from cliide.ui.file_tree import FileTree
from cliide.ui.find_replace import FindReplacePanel, find_in_text, replace_in_text
from cliide.ui.problems_panel import ProblemsPanel
from cliide.ui.references_panel import ReferencesPanel
from cliide.ui.rename_panel import RenamePanel
from cliide.ui.project_picker import ProjectPicker
from cliide.ui.settings import SettingsScreen
from cliide.ui.statusbar import StatusBar
from cliide.ui.tab_bar import TabBar
from cliide.ui.agent_status import TabbedAgentPanel
from cliide.ui.splitter import Splitter, HorizontalSplitter
from cliide.utils.logger import log


class CliideApp(App[None]):
    """Main cliide application."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #left-column {
        width: 32;
        layout: vertical;
        background: $surface;
        overflow: hidden;
    }

    #file-tree-container {
        height: 1fr;
        background: $surface;
    }

    #file-tree-container.hidden {
        display: none;
    }

    #agent-panel-container {
        height: 15;
        background: $panel;
        overflow: hidden;
    }

    #agent-panel-container.hidden {
        display: none;
    }

    #editor-container {
        width: 1fr;
        layout: vertical;
        background: $background;
    }

    #tab-bar {
        width: 100%;
        height: auto;
        min-height: 0;
    }

    #chat-container {
        width: 55;
        background: $surface;
    }

    #problems-panel {
        display: none;
        border: round $warning;
        background: $panel;
    }

    #problems-panel.visible {
        display: block;
    }

    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+p", "command_palette", "Command Palette", show=True),
        Binding("ctrl+o", "switch_project", "Switch Project", show=True),
        Binding("ctrl+s", "save_file", "Save", show=True),
        Binding("ctrl+k", "toggle_chat", "AI Chat", show=True),
        Binding("ctrl+j", "toggle_agents", "Agents", show=True),
        Binding("ctrl+e", "explain_code", "Explain Code", show=True),
        Binding("ctrl+b", "toggle_file_tree", "Toggle File Tree", show=True),
        Binding("ctrl+comma", "vllm_settings", "Settings", show=True),
        Binding("ctrl+space", "trigger_completion", "Completion", show=False),
        Binding("ctrl+shift+n", "new_chat", "New Chat", show=False),
        Binding("f12", "goto_definition", "Go to Definition", show=False),
        Binding("shift+f12", "find_references", "Find References", show=False),
        Binding("f2", "rename_symbol", "Rename", show=False),
        Binding("ctrl+shift+m", "toggle_problems", "Problems", show=True),
        Binding("ctrl+f", "find_replace", "Find & Replace", show=True),
        Binding("ctrl+shift+f", "format_code", "Format Code", show=True),
    ]

    def __init__(self, project_path: Path | None = None, **kwargs: Any) -> None:
        """Initialize the application.

        Args:
            project_path: Path to project directory (None shows startup picker)
            **kwargs: Additional arguments for App
        """
        super().__init__(**kwargs)
        self.config = get_config()

        # Track whether we were given a project path (for startup picker)
        self._initial_project_path = project_path
        self.project_path = project_path or Path.cwd()

        self.command_palette_visible = False
        self.code_actions = CodeActions(
            workspace_root=self.project_path,
            confirmation_callback=self._tool_confirmation_callback,
        )
        self.prompt_manager = PromptManager()
        self.lsp_manager = LanguageServerManager(self.project_path)
        self.problems_panel_visible = False
        self.pending_code_edit: dict[str, Any] | None = None  # Track code editing in progress
        self.auto_approve_session = False  # When True, skip all tool confirmations

        # Session and recent projects management
        self.session_manager = SessionManager(self.project_path)
        self.recent_projects = RecentProjectsManager()

        # Register and apply custom theme
        self.register_theme(CLIIDE_THEME)
        self.theme = "cliide"

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()

        with Container(id="main-container"):
            # Left column: File tree + Agent panel stacked vertically
            with Container(id="left-column"):
                with Container(id="file-tree-container"):
                    yield FileTree(str(self.project_path))

                # Horizontal splitter between file tree and agent panel
                yield HorizontalSplitter("file-tree-container", "agent-panel-container", min_height=5)

                with Container(id="agent-panel-container"):
                    yield TabbedAgentPanel()

            # Splitter: left column | editor
            yield Splitter("left-column", "editor-container", min_width=15)

            # Editor + Tab Bar + Problems
            with Container(id="editor-container"):
                yield TabBar(id="tab-bar")
                yield EditorWidget()
                yield ProblemsPanel(id="problems-panel")

            # Splitter: editor | chat (resize_right anchors chat to right edge)
            yield Splitter("editor-container", "chat-container", min_width=25, resize_right=True)

            # Chat panel
            with Container(id="chat-container"):
                yield ChatPanel(workspace_path=self.project_path)

        yield StatusBar()
        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount event."""
        # Subscribe to events
        event_bus = get_event_bus()
        event_bus.subscribe(AgentEventType.TOOL_COMPLETED, self._on_tool_completed)
        event_bus.subscribe(AgentEventType.PROJECT_CHANGED, self._on_project_changed)

        # Show startup picker if no initial project path
        if self._initial_project_path is None:
            self._show_startup_picker()
            return  # Rest of initialization happens after project selection

        # Normal initialization with project
        await self._initialize_project()

    async def _initialize_project(self) -> None:
        """Initialize the app with the current project path."""
        self.title = f"cliide - {self.project_path.name}"
        self.sub_title = str(self.project_path)

        # Apply UI config
        if not self.config.ui.show_file_tree:
            self.query_one("#file-tree-container").add_class("hidden")

        if not self.config.ui.show_chat_panel:
            self.query_one("#chat-container").add_class("hidden")

        # Check AI connection
        statusbar = self.query_one(StatusBar)
        try:
            connected = await self.code_actions.client.check_connection()
            if connected:
                statusbar.update_ai_status("Connected")
            else:
                statusbar.update_ai_status("Disconnected")
        except Exception:
            statusbar.update_ai_status("Disconnected")

        # Connect editor to LSP manager
        editor = self.query_one(EditorWidget)
        editor.lsp_manager = self.lsp_manager

        # Register diagnostic handler
        self.lsp_manager.register_diagnostic_handler(self._handle_diagnostics)

        # Add to recent projects
        self.recent_projects.add(self.project_path)

        # Restore session
        self._restore_session()

    def _show_startup_picker(self) -> None:
        """Show project picker on startup when no path given."""
        def on_selected(path: Path | None) -> None:
            if path:
                self.project_path = path
                self.session_manager = SessionManager(path)
                self.code_actions = CodeActions(
                    workspace_root=path,
                    confirmation_callback=self._tool_confirmation_callback,
                )
                self.lsp_manager = LanguageServerManager(path)

                # Update file tree
                try:
                    file_tree = self.query_one(FileTree)
                    file_tree.path = str(path)
                    file_tree.reload()
                except Exception:
                    pass

                # Update chat workspace
                try:
                    chat = self.query_one(ChatPanel)
                    chat.workspace_path = path
                except Exception:
                    pass

                # Run initialization
                self.run_worker(self._initialize_project())
            else:
                # User cancelled - exit app
                self.exit()

        self.push_screen(
            ProjectPicker(self.recent_projects, startup_mode=True),
            callback=on_selected,
        )

    async def _on_project_changed(self, event: AgentEvent) -> None:
        """Handle project change events from AI tool or UI.

        Args:
            event: Project changed event
        """
        new_path = Path(event.data.get("path", ""))
        if new_path.exists() and new_path.is_dir():
            await self._switch_project(new_path)

    async def _switch_project(self, new_path: Path) -> None:
        """Switch to a different project.

        Args:
            new_path: Path to the new project
        """
        log(f"[APP] Switching project to: {new_path}")

        # Save current session
        self._save_session()

        # Stop LSP servers
        await self.lsp_manager.stop_all_servers()

        # Update project path
        self.project_path = new_path

        # Reinitialize managers
        self.session_manager = SessionManager(new_path)
        self.code_actions = CodeActions(
            workspace_root=new_path,
            confirmation_callback=self._tool_confirmation_callback,
        )
        self.lsp_manager = LanguageServerManager(new_path)

        # Update file tree
        try:
            file_tree = self.query_one(FileTree)
            file_tree.path = str(new_path)
            file_tree.reload()
        except Exception as e:
            log(f"[APP] Error updating file tree: {e}")

        # Update chat workspace and clear sessions
        try:
            chat = self.query_one(ChatPanel)
            chat.workspace_path = new_path
            chat.clear_all_sessions()
        except Exception as e:
            log(f"[APP] Error updating chat: {e}")

        # Clear tabs
        try:
            tab_bar = self.query_one(TabBar)
            for path in list(tab_bar._tabs.keys()):
                tab_bar.remove_tab(path)
        except Exception as e:
            log(f"[APP] Error clearing tabs: {e}")

        # Clear editor
        try:
            editor = self.query_one(EditorWidget)
            editor.text = ""
            editor.current_file = None
        except Exception as e:
            log(f"[APP] Error clearing editor: {e}")

        # Re-initialize
        await self._initialize_project()

        log(f"[APP] Project switch complete: {new_path.name}")

    def _save_session(self) -> None:
        """Save current session state."""
        try:
            tab_bar = self.query_one(TabBar)
            chat = self.query_one(ChatPanel)

            state = SessionState(
                open_files=list(tab_bar._tabs.keys()),
                active_file=tab_bar._active_path,
                chat_sessions=chat.get_all_sessions(),
                active_chat_id=chat.active_session_id,
            )
            self.session_manager.save(state)
            log(f"[APP] Session saved: {len(state.open_files)} files, {len(state.chat_sessions)} chats")
        except Exception as e:
            log(f"[APP] Error saving session: {e}")

    def _restore_session(self) -> None:
        """Restore session state if exists."""
        state = self.session_manager.load()
        if not state:
            log("[APP] No session to restore")
            return

        # Restore tabs
        for file_path in state.open_files:
            if Path(file_path).exists():
                try:
                    self._open_file_internal(file_path, activate=False)
                except Exception as e:
                    log(f"[APP] Error restoring tab {file_path}: {e}")

        # Activate last active file
        if state.active_file and Path(state.active_file).exists():
            try:
                self._open_file_internal(state.active_file, activate=True)
            except Exception as e:
                log(f"[APP] Error activating file: {e}")

        # Restore chat sessions
        if state.chat_sessions:
            try:
                chat = self.query_one(ChatPanel)
                chat.restore_sessions(state.chat_sessions, state.active_chat_id)
            except Exception as e:
                log(f"[APP] Error restoring chat sessions: {e}")

        log(f"[APP] Session restored: {len(state.open_files)} files, {len(state.chat_sessions)} chats")

    def _open_file_internal(self, file_path: str, activate: bool = True) -> None:
        """Internal method to open a file without posting messages.

        Args:
            file_path: Path to the file
            activate: Whether to activate the tab
        """
        import aiofiles

        async def load_and_open():
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()

            editor = self.query_one(EditorWidget)
            tab_bar = self.query_one(TabBar)

            # Add tab
            tab_bar.add_tab(file_path, activate=activate)

            if activate:
                editor.text = content
                editor.current_file = Path(file_path)
                editor.is_modified = False

        self.run_worker(load_and_open())

    async def _on_tool_completed(self, event: Any) -> None:
        """Handle tool completion events to refresh UI."""
        tool_name = event.data.get("tool", "")
        # Refresh file tree when files are written or created
        if tool_name in ("write_file", "create_file", "create_directory"):
            def refresh_tree() -> None:
                try:
                    file_tree = self.query_one(FileTree)
                    file_tree.reload()
                except Exception:
                    pass  # Tree might not exist
            self.call_later(refresh_tree)

    def action_quit(self) -> None:
        """Quit the application."""
        # Stop LSP servers before exiting (async)
        self.run_worker(self._quit_with_cleanup())

    async def _quit_with_cleanup(self) -> None:
        """Async quit handler with proper cleanup."""
        # Stop all LSP servers
        await self.lsp_manager.stop_all_servers()
        # Now exit
        self.exit()

    def action_command_palette(self) -> None:
        """Show command palette."""
        if not self.command_palette_visible:
            def on_dismiss(result: str | None = None) -> None:
                self.command_palette_visible = False

            self.push_screen(CommandPalette(), callback=on_dismiss)
            self.command_palette_visible = True

    def action_vllm_settings(self) -> None:
        """Show VLLM settings screen."""
        async def on_dismiss(saved: bool | None = None) -> None:
            log(f"[APP] Settings screen dismissed with saved={saved}")
            if saved:
                # Config was saved, reload VLLM client
                log("[APP] Reloading VLLM client...")
                await self._reload_vllm_client()

        self.push_screen(SettingsScreen(), callback=on_dismiss)

    async def _tool_confirmation_callback(self, tool_name: str, args: dict) -> bool:
        """Callback for tool confirmation - routes to agent panel approval queue.

        Args:
            tool_name: Name of the tool requesting confirmation
            args: Tool arguments

        Returns:
            True if user approves, False otherwise
        """
        # Skip confirmation if auto-approve is enabled for this session
        if self.auto_approve_session:
            log(f"[APP] Auto-approving tool: {tool_name}")
            return True

        import asyncio

        # Create a future to wait for user response (use running loop for Textual compatibility)
        loop = asyncio.get_running_loop()
        confirmation_future: asyncio.Future[bool] = loop.create_future()

        # Add to the agent panel's approval queue
        try:
            agent_panel = self.query_one(TabbedAgentPanel)
            agent_panel.add_approval(tool_name, args, confirmation_future)
            log(f"[APP] Added tool approval request to queue: {tool_name}")
        except Exception as e:
            log(f"[APP] Error adding to approval queue: {e}, auto-approving")
            return True

        # Wait for user response
        result = await confirmation_future

        return result

    def on_tool_confirmation_result(self, event: ToolConfirmationResult) -> None:
        """Handle tool confirmation result to check for auto-session flag."""
        if event.auto_session:
            log("[APP] Auto-approve enabled for this session")
            self.auto_approve_session = True

    def on_approval_widget_approved(self, event) -> None:
        """Handle approval widget approved - check for auto-session flag."""
        if hasattr(event, 'auto_session') and event.auto_session:
            log("[APP] Auto-approve enabled for this session (from panel)")
            self.auto_approve_session = True

    async def _reload_vllm_client(self) -> None:
        """Reload VLLM client with new configuration."""
        log("[APP] _reload_vllm_client called")
        statusbar = self.query_one(StatusBar)
        statusbar.update_ai_status("Checking...")

        # Force reload config from file to get latest saved values
        from cliide.core.config import reload_config
        from cliide.ai.vllm_client import reset_client

        self.config = reload_config()
        log(f"[APP] Reloaded config from disk - URL: {self.config.vllm.base_url}, Model: {self.config.vllm.model}, API Key: {'***' if self.config.vllm.api_key else 'None'}")

        # CRITICAL: Reset the cached VLLM client so it will be recreated with new config
        reset_client()
        log("[APP] Reset cached VLLM client")

        # Reinitialize code actions (which will now create a NEW VLLM client with new config)
        self.code_actions = CodeActions(
            workspace_root=self.project_path,
            confirmation_callback=self._tool_confirmation_callback,
        )
        log("[APP] Created new CodeActions instance")
        log(f"[APP] CodeActions client URL: {self.code_actions.client.config.vllm.base_url}")

        # Test connection
        try:
            log("[APP] Testing connection...")
            connected = await self.code_actions.client.check_connection()
            log(f"[APP] Connection test result: {connected}")
            if connected:
                statusbar.update_connection_status(True)
            else:
                statusbar.update_connection_status(False)
        except Exception as e:
            log(f"[APP] Connection test error: {e}")
            statusbar.update_connection_status(False)

    def action_save_file(self) -> None:
        """Save the current file."""
        editor = self.query_one(EditorWidget)
        editor.save_current_file()

    def action_toggle_chat(self) -> None:
        """Toggle chat panel visibility."""
        chat_container = self.query_one("#chat-container")
        chat_container.toggle_class("hidden")

    def action_toggle_file_tree(self) -> None:
        """Toggle file tree visibility."""
        file_tree_container = self.query_one("#file-tree-container")
        file_tree_container.toggle_class("hidden")

    def action_toggle_agents(self) -> None:
        """Toggle agent status panel visibility."""
        agent_container = self.query_one("#agent-panel-container")
        agent_container.toggle_class("hidden")

    def action_switch_project(self) -> None:
        """Show project picker to switch projects (Ctrl+O)."""
        def on_selected(path: Path | None) -> None:
            if path and path != self.project_path:
                self.run_worker(self._switch_project(path))

        self.push_screen(
            ProjectPicker(self.recent_projects, startup_mode=False),
            callback=on_selected,
        )

    def action_new_chat(self) -> None:
        """Create a new chat session (Ctrl+Shift+N)."""
        try:
            chat = self.query_one(ChatPanel)
            chat.create_new_session()
        except Exception as e:
            log(f"[APP] Error creating new chat: {e}")

    def action_explain_code(self) -> None:
        """Explain selected code using AI."""
        editor = self.query_one(EditorWidget)
        selected_text = editor.get_selected_text()

        if selected_text:
            # Show chat panel if hidden
            chat_container = self.query_one("#chat-container")
            chat_container.remove_class("hidden")

            # Send explain command to chat
            chat = self.query_one(ChatPanel)
            chat.send_message(f"Explain this code:\n\n```\n{selected_text}\n```")

    def action_toggle_problems(self) -> None:
        """Toggle problems panel visibility."""
        problems_panel = self.query_one("#problems-panel")
        if self.problems_panel_visible:
            problems_panel.remove_class("visible")
            self.problems_panel_visible = False
        else:
            problems_panel.add_class("visible")
            self.problems_panel_visible = True

    def action_trigger_completion(self) -> None:
        """Trigger code completion."""
        self.run_worker(self._trigger_completion())

    async def _trigger_completion(self) -> None:
        """Async handler for code completion."""
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            return

        line, char = editor.get_cursor_position()
        file_path = str(editor.current_file)

        # Request completions from LSP
        items = await self.lsp_manager.completion(file_path, line, char)

        if items and len(items) > 0:
            # Show completion menu
            menu = CompletionMenu(items)
            self.mount(menu)

            # TODO: Position menu near cursor

    def action_goto_definition(self) -> None:
        """Go to definition."""
        self.run_worker(self._goto_definition())

    async def _goto_definition(self) -> None:
        """Async handler for go-to-definition."""
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            return

        line, char = editor.get_cursor_position()
        file_path = str(editor.current_file)

        # Request definition from LSP
        locations = await self.lsp_manager.definition(file_path, line, char)

        if locations and len(locations) > 0:
            location = locations[0]
            uri = location.get("uri", "")

            from cliide.lsp.protocol import uri_to_path

            target_file = uri_to_path(uri)
            target_range = location.get("range", {})
            target_start = target_range.get("start", {})
            target_line = target_start.get("line", 0)
            target_char = target_start.get("character", 0)

            # Open file (if different from current)
            if target_file != str(editor.current_file):
                await editor.open_file(target_file)

            # Jump to line
            editor.jump_to_line(target_line, target_char)

    def action_find_references(self) -> None:
        """Find all references."""
        self.run_worker(self._find_references())

    async def _find_references(self) -> None:
        """Async handler for find references."""
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            return

        line, char = editor.get_cursor_position()
        file_path = str(editor.current_file)

        # Get symbol name under cursor
        symbol_name = editor.get_word_at_cursor() or "symbol"

        # Request references from LSP
        references = await self.lsp_manager.references(file_path, line, char)

        if references and len(references) > 0:
            # Show references panel
            panel = ReferencesPanel(symbol_name, references)
            self.mount(panel)

    def action_rename_symbol(self) -> None:
        """Rename symbol."""
        self.run_worker(self._rename_symbol())

    async def _rename_symbol(self) -> None:
        """Async handler for rename symbol."""
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            return

        line, char = editor.get_cursor_position()
        file_path = str(editor.current_file)

        # Get current symbol name from editor
        old_name = editor.get_word_at_cursor()

        if not old_name:
            self.notify("No symbol under cursor", severity="warning")
            return

        # Show rename panel (will request rename from LSP when user confirms)
        panel = RenamePanel(old_name)
        self.mount(panel)

        # Note: The actual rename will be triggered when user confirms in the panel

    def action_find_replace(self) -> None:
        """Show find & replace panel."""
        panel = FindReplacePanel()
        self.mount(panel)

    def action_format_code(self) -> None:
        """Format current code."""
        self.run_worker(self._format_code())

    async def _format_code(self) -> None:
        """Async handler for code formatting."""
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            self.notify("No file open", severity="warning")
            return

        # Get current code
        code = editor.text
        file_path = str(editor.current_file)

        # Format code
        formatted = await CodeFormatter.format_code(code, file_path=file_path)

        if formatted:
            # Replace all text
            editor.text = formatted
            self.notify("Code formatted", severity="information")
        else:
            self.notify("Formatter not available (install black/prettier)", severity="warning")

    async def on_find_replace_panel_find_requested(
        self, event: FindReplacePanel.FindRequested
    ) -> None:
        """Handle find request.

        Args:
            event: Find requested event
        """
        editor = self.query_one(EditorWidget)

        # Get current cursor position
        cursor_line, cursor_col = editor.get_cursor_position()

        # Convert to character position
        lines = editor.text.split("\n")
        start_pos = sum(len(line) + 1 for line in lines[:cursor_line]) + cursor_col

        # Find in text
        result = find_in_text(
            editor.text,
            event.pattern,
            event.is_regex,
            event.case_sensitive,
            start_pos,
        )

        if result:
            start, end = result

            # Convert character positions to line/col
            text_before = editor.text[:start]
            line = text_before.count("\n")
            col = start - text_before.rfind("\n") - 1 if "\n" in text_before else start

            # Jump to match and select it
            editor.jump_to_line(line, col)

            # Calculate end position
            text_between = editor.text[start:end]
            end_line = line + text_between.count("\n")
            end_col = (
                col + len(text_between.split("\n")[-1])
                if "\n" not in text_between
                else len(text_between.split("\n")[-1])
            )

            # Select the match
            editor.select_range(line, col, end_line, end_col)

            self.notify(f"Found at line {line + 1}", severity="information")
        else:
            self.notify("Not found", severity="warning")

    async def on_find_replace_panel_replace_requested(
        self, event: FindReplacePanel.ReplaceRequested
    ) -> None:
        """Handle replace request.

        Args:
            event: Replace requested event
        """
        editor = self.query_one(EditorWidget)

        # Replace in text
        new_text = replace_in_text(
            editor.text,
            event.pattern,
            event.replacement,
            event.is_regex,
            event.case_sensitive,
            event.replace_all,
        )

        if new_text != editor.text:
            editor.text = new_text
            count = "all" if event.replace_all else "1"
            self.notify(f"Replaced {count} occurrence(s)", severity="information")
        else:
            self.notify("No matches found", severity="warning")

    def _handle_diagnostics(self, file_path: str, diagnostics: list[Any]) -> None:
        """Handle diagnostics from LSP.

        Args:
            file_path: File path
            diagnostics: List of diagnostics
        """
        # Update editor
        editor = self.query_one(EditorWidget)
        editor.set_diagnostics(file_path, diagnostics)

        # Update problems panel
        problems_panel = self.query_one("#problems-panel", ProblemsPanel)
        problems_panel.update_diagnostics(file_path, diagnostics)

    async def on_file_opened(self, event: FileOpened) -> None:
        """Handle file opened event."""
        editor = self.query_one(EditorWidget)
        await editor.open_file(event.path)

        # Update tab bar
        try:
            tab_bar = self.query_one("#tab-bar", TabBar)
            tab_bar.add_tab(event.path, activate=True)
        except Exception:
            pass  # Tab bar might not be mounted yet

        # Update status bar
        statusbar = self.query_one(StatusBar)
        statusbar.update_file_info(event.path)

    async def on_tab_bar_file_selected(self, event: TabBar.FileSelected) -> None:
        """Handle tab selection."""
        editor = self.query_one(EditorWidget)
        await editor.open_file(event.file_path)

        # Update status bar
        statusbar = self.query_one(StatusBar)
        statusbar.update_file_info(event.file_path)

    async def on_tab_bar_file_close_requested(self, event: TabBar.FileCloseRequested) -> None:
        """Handle tab close request."""
        editor = self.query_one(EditorWidget)

        # Check if file is modified (would need to prompt for save)
        # For now, just close without save prompt
        tab_bar = self.query_one("#tab-bar", TabBar)
        next_file = tab_bar.remove_tab(event.file_path)

        if next_file:
            # Open the next file
            await editor.open_file(next_file)
            # Update status bar
            statusbar = self.query_one(StatusBar)
            statusbar.update_file_info(next_file)
        else:
            # No more files open - clear editor
            editor.text = ""
            editor.current_file = None

    def on_status_bar_settings_clicked(self, message: StatusBar.SettingsClicked) -> None:
        """Handle clicks on the status bar settings indicator.

        Args:
            message: Settings clicked message
        """
        self.action_vllm_settings()

    def on_ai_request_started(self, event: AIRequestStarted) -> None:
        """Handle AI request event.

        Args:
            event: AI request started event
        """
        log(f"[APP] ===== HANDLER CALLED ===== prompt: {event.prompt}")
        log(f"[APP] Handler type: {type(self).__name__}")

        # Run async handler
        self.run_worker(self._handle_ai_request(event))

    async def _handle_ai_request(self, event: AIRequestStarted) -> None:
        """Async handler for AI requests.

        Args:
            event: AI request started event
        """
        log(f"[APP] Starting async handler for: {event.prompt}")

        chat = self.query_one(ChatPanel)
        statusbar = self.query_one(StatusBar)
        editor = self.query_one(EditorWidget)

        try:
            # Update status
            log("[APP] Updating status to Processing")
            statusbar.update_ai_status("Processing...")

            # Parse command if present
            log(f"[APP] Parsing command from: {event.prompt}")
            command, content = self.prompt_manager.parse_command(event.prompt)
            log(f"[APP] Command: {command}, Content: {content}")

            # Note: @mentioned files are already parsed and appended by chat.send_message()
            # No need to re-parse here - the prompt already contains file contents

            # Start streaming response
            log("[APP] Starting AI response")
            chat.start_ai_response()

            if command:
                # Handle slash command
                log(f"[APP] Handling command: {command}")
                selected_code = editor.get_selected_text()
                file_path = str(editor.current_file) if editor.current_file else None
                language = self.code_actions.context_builder._detect_language(file_path) if file_path else None

                # Build code context - send full file (local VLLM has flexible context)
                if selected_code:
                    code_context = selected_code
                elif editor.current_file and editor.text:
                    code_context = editor.text
                    log(f"[APP] Sending full file: {len(editor.text)} chars, {len(editor.text.splitlines())} lines")
                else:
                    code_context = None

                # Check if this is a code editing command
                is_code_edit = command in ["apply", "edit"]

                if is_code_edit and code_context:
                    # Collect full response for diff view
                    log(f"[APP] Code edit command detected: {command}")
                    full_response = ""
                    async for chunk in self.code_actions.handle_command(
                        command, content, code_context, language
                    ):
                        full_response += chunk
                        chat.append_ai_chunk(chunk)

                    # Extract code from response
                    new_code = CodeActions.extract_code_from_response(full_response)

                    if new_code:
                        # Store for diff view
                        self.pending_code_edit = {
                            "original": code_context,
                            "new": new_code,
                            "selection": editor.selection if selected_code else None,
                        }
                        log(f"[APP] Extracted {len(new_code)} chars of code")
                    else:
                        log("[APP] Could not extract code block from response")

                else:
                    # Regular command - just stream to chat
                    log(f"[APP] Calling handle_command")
                    chunk_count = 0
                    async for chunk in self.code_actions.handle_command(
                        command, content, code_context, language
                    ):
                        chunk_count += 1
                        chat.append_ai_chunk(chunk)
                    log(f"[APP] Received {chunk_count} chunks from command")

            else:
                # Regular chat with tool-calling agent
                log("[APP] Handling regular chat with ToolAgent")
                selected_code = editor.get_selected_text()
                file_path = str(editor.current_file) if editor.current_file else None
                file_name = editor.current_file.name if editor.current_file else None
                language = ContextBuilder._detect_language(file_path) if file_path else None
                conversation_history = chat.get_conversation_history()

                # Build code context - send full file (local VLLM has flexible context)
                if selected_code:
                    code_context = selected_code
                elif editor.current_file and editor.text:
                    code_context = editor.text
                    log(f"[APP] Sending full file: {len(editor.text)} chars, {len(editor.text.splitlines())} lines")
                else:
                    code_context = None

                log(f"[APP] Prompt length: {len(event.prompt)}, has_code={bool(code_context)}, file={file_name}, lang={language}")
                log(f"[APP] Conversation history has {len(conversation_history)} messages")

                event_count = 0
                async for agent_event in self.code_actions.chat(
                    event.prompt,
                    code_context=code_context,
                    file_name=file_name,
                    language=language,
                    conversation_history=conversation_history,
                ):
                    event_count += 1
                    event_type = agent_event.get("type", "")

                    if event_type == "text":
                        # Text chunk from AI
                        content = agent_event.get("content", "")
                        if content:
                            if event_count <= 5:
                                log(f"[APP] Text event {event_count}: {content[:30]}...")
                            chat.append_ai_chunk(content)

                    elif event_type == "tool_start":
                        # Tool execution starting - show in chat
                        tool_name = agent_event.get("tool", "")
                        args = agent_event.get("args", {})
                        tool_call_id = agent_event.get("tool_call_id")
                        log(f"[APP] Tool start: {tool_name} with args: {args}")
                        # Add tool execution to chat directly
                        tool_msg = chat.add_tool_execution(tool_name, args, tool_call_id)
                        # Track for later update
                        if not hasattr(self, '_active_tool_messages'):
                            self._active_tool_messages = {}
                        if tool_call_id:
                            self._active_tool_messages[tool_call_id] = tool_msg

                    elif event_type == "tool_result":
                        # Tool execution completed - update in chat
                        tool_name = agent_event.get("tool", "")
                        result = agent_event.get("result")
                        tool_call_id = agent_event.get("tool_call_id")
                        log(f"[APP] Tool result: {tool_name} success={getattr(result, 'success', False)}")
                        # Update the tool message in chat
                        if hasattr(self, '_active_tool_messages') and tool_call_id in self._active_tool_messages:
                            tool_msg = self._active_tool_messages[tool_call_id]
                            chat.update_tool_execution(tool_msg, result)
                            del self._active_tool_messages[tool_call_id]

                    elif event_type == "error":
                        # Error occurred
                        error_msg = agent_event.get("message", "Unknown error")
                        log(f"[APP] Agent error: {error_msg}")
                        chat.add_error_message(f"Agent error: {error_msg}")

                    elif event_type == "progress":
                        # Progress indicator - show in status bar
                        progress_msg = agent_event.get("message", "Working...")
                        log(f"[APP] Progress: {progress_msg}")
                        statusbar.update_ai_status(progress_msg)

                    elif event_type == "warning":
                        # Warning message
                        warn_msg = agent_event.get("message", "")
                        log(f"[APP] Warning: {warn_msg}")
                        chat.append_ai_chunk(f"\n⚠️ {warn_msg}\n")

                log(f"[APP] Total events received: {event_count}")

            # Finish response
            log("[APP] Finishing AI response")
            chat.finish_ai_response()
            statusbar.update_ai_status("Ready")

            # If we have pending code edit, show inline diff in editor
            if self.pending_code_edit:
                log("[APP] Showing inline diff in editor")
                editor = self.query_one(EditorWidget)
                editor.show_diff(
                    self.pending_code_edit["original"],
                    self.pending_code_edit["new"],
                )
                # Update status bar to show diff mode
                statusbar.update_ai_status("Review changes: [Y]Accept [N]Reject")

            # Clear tool messages from chat now that we have the final response
            chat.clear_tool_messages()
            log("[APP] AI request completed successfully")

        except Exception as e:
            log(f"[APP] Error: {e}")
            import traceback
            log(f"[APP] Traceback: {traceback.format_exc()}")
            chat.add_error_message(str(e))
            statusbar.update_ai_status("Error")

    async def on_completion_menu_completion_selected(
        self, event: CompletionMenu.CompletionSelected
    ) -> None:
        """Handle completion selection.

        Args:
            event: Completion selected event
        """
        editor = self.query_one(EditorWidget)
        item = event.item

        # Get text to insert
        insert_text = item.get("insertText") or item.get("label", "")

        # Insert the completion at cursor
        editor.insert_text_at_cursor(insert_text)
        log(f"[APP] Inserted completion: {insert_text}")

        # Remove the completion menu
        menu = event.sender
        await menu.remove()

    async def on_rename_panel_rename_applied(
        self, event: RenamePanel.RenameApplied
    ) -> None:
        """Handle rename applied.

        Args:
            event: Rename applied event
        """
        editor = self.query_one(EditorWidget)

        if not editor.current_file:
            return

        # Get rename info
        rename_info = event.workspace_edit
        new_name = rename_info.get("new_name")

        if not new_name:
            return

        # Get cursor position and request rename from LSP
        line, char = editor.get_cursor_position()
        file_path = str(editor.current_file)

        workspace_edit = await self.lsp_manager.rename(file_path, line, char, new_name)

        if not workspace_edit:
            self.notify("Rename failed", severity="error")
            return

        # Apply workspace edit
        await self._apply_workspace_edit(workspace_edit)
        self.notify(f"Renamed to '{new_name}'", severity="information")

    async def _apply_workspace_edit(self, workspace_edit: dict[str, Any]) -> None:
        """Apply a workspace edit (multi-file refactoring).

        Args:
            workspace_edit: LSP WorkspaceEdit
        """
        from cliide.lsp.protocol import uri_to_path

        editor = self.query_one(EditorWidget)
        changes = workspace_edit.get("changes", {})

        for uri, edits in changes.items():
            file_path = uri_to_path(uri)
            log(f"[APP] Applying {len(edits)} edits to {file_path}")

            # Read current file content
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
            except Exception as e:
                log(f"[APP] Error reading {file_path}: {e}")
                continue

            # Apply edits in reverse order (to maintain positions)
            sorted_edits = sorted(
                edits,
                key=lambda e: (
                    e.get("range", {}).get("start", {}).get("line", 0),
                    e.get("range", {}).get("start", {}).get("character", 0),
                ),
                reverse=True,
            )

            lines = content.split("\n")

            for edit in sorted_edits:
                range_data = edit.get("range", {})
                start = range_data.get("start", {})
                end = range_data.get("end", {})
                new_text = edit.get("newText", "")

                start_line = start.get("line", 0)
                start_char = start.get("character", 0)
                end_line = end.get("line", 0)
                end_char = end.get("character", 0)

                # Apply edit to lines
                if start_line == end_line:
                    # Single line edit
                    line = lines[start_line]
                    lines[start_line] = line[:start_char] + new_text + line[end_char:]
                else:
                    # Multi-line edit
                    start_line_content = lines[start_line][:start_char]
                    end_line_content = lines[end_line][end_char:]

                    # Remove lines in between
                    del lines[start_line : end_line + 1]

                    # Insert new content
                    new_lines = (start_line_content + new_text + end_line_content).split("\n")
                    for i, new_line in enumerate(new_lines):
                        lines.insert(start_line + i, new_line)

            # Write back
            new_content = "\n".join(lines)

            try:
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(new_content)
                log(f"[APP] Wrote changes to {file_path}")

                # If this is the current file, reload it
                if str(editor.current_file) == file_path:
                    await editor.open_file(file_path)

            except Exception as e:
                log(f"[APP] Error writing {file_path}: {e}")

    async def on_diff_view_changes_accepted(self, event: DiffView.ChangesAccepted) -> None:
        """Handle diff view changes accepted.

        Args:
            event: Changes accepted event
        """
        if not self.pending_code_edit:
            return

        editor = self.query_one(EditorWidget)
        selection = self.pending_code_edit["selection"]

        if selection:
            # Replace the selected text with new code
            start, end = selection
            editor.replace_text_range(start, end, event.new_code)
            log(f"[APP] Applied code changes ({len(event.new_code)} chars)")
            self.notify("Code changes applied", severity="information")

        # Clear pending edit
        self.pending_code_edit = None

    async def on_diff_view_changes_rejected(self, event: DiffView.ChangesRejected) -> None:
        """Handle diff view changes rejected.

        Args:
            event: Changes rejected event
        """
        log("[APP] Code changes rejected by user")
        self.pending_code_edit = None
        self.notify("Changes discarded", severity="warning")

    async def on_editor_widget_diff_accepted(self, event: EditorWidget.DiffAccepted) -> None:
        """Handle inline diff accepted.

        Args:
            event: Diff accepted event
        """
        log("[APP] Inline diff accepted")
        self.pending_code_edit = None
        self.notify("Code changes applied", severity="information")

        # Update status bar
        statusbar = self.query_one(StatusBar)
        statusbar.update_ai_status("Ready")

    async def on_editor_widget_diff_rejected(self, event: EditorWidget.DiffRejected) -> None:
        """Handle inline diff rejected.

        Args:
            event: Diff rejected event
        """
        log("[APP] Inline diff rejected by user")
        self.pending_code_edit = None
        self.notify("Changes discarded", severity="warning")

        # Update status bar
        statusbar = self.query_one(StatusBar)
        statusbar.update_ai_status("Ready")

    def action_accept_diff(self) -> None:
        """Accept current diff if in diff mode."""
        editor = self.query_one(EditorWidget)
        if editor.diff_mode:
            editor.accept_diff()

    def action_reject_diff(self) -> None:
        """Reject current diff if in diff mode."""
        editor = self.query_one(EditorWidget)
        if editor.diff_mode:
            editor.reject_diff()

    async def on_command_executed(self, event: CommandExecuted) -> None:
        """Handle command executed event."""
        if event.command == "open_file":
            file_path = event.args.get("path")
            if file_path:
                self.post_message(FileOpened(file_path))

        # Add command handlers here
        elif event.command == "save_file":
            self.action_save_file()
        elif event.command == "close_file":
            editor = self.query_one(EditorWidget)
            editor.close_file()
        elif event.command == "explain_code":
            self.action_explain_code()
        elif event.command == "refactor_code":
            chat = self.query_one(ChatPanel)
            chat.send_message("/refactor")
        elif event.command == "fix_issues":
            chat = self.query_one(ChatPanel)
            chat.send_message("/fix")
        elif event.command == "toggle_file_tree":
            self.action_toggle_file_tree()
        elif event.command == "toggle_chat":
            self.action_toggle_chat()
        elif event.command == "vllm_settings":
            self.action_vllm_settings()
        elif event.command == "switch_project":
            self.action_switch_project()
        elif event.command == "new_chat":
            self.action_new_chat()
        elif event.command == "quit":
            self.action_quit()


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file",
)
@click.option(
    "--oapi-url",
    type=str,
    help="Set OpenAI-compatible API URL (e.g., http://localhost:8000/v1) and save to config",
)
@click.option(
    "--model",
    type=str,
    help="Set model name (e.g., google--gemma-3-12b-it) and save to config",
)
@click.version_option(version="0.1.0", prog_name="cliide")
def main(path: Path | None = None, config: Path | None = None, oapi_url: str | None = None, model: str | None = None) -> None:
    """cliide - AI-first CLI IDE powered by local VLLM models.

    PATH: Optional path to project directory (defaults to current directory)
    """
    # Handle --oapi-url flag
    if oapi_url:
        from cliide.core.config import update_vllm_url

        update_vllm_url(oapi_url)
        return  # Exit after updating config

    # Handle --model flag
    if model:
        from cliide.core.config import update_vllm_model

        update_vllm_model(model)
        return  # Exit after updating config

    # Load config
    if config:
        from cliide.core.config import set_config

        cfg = Config.load_from_file(config)
        set_config(cfg)

    # Create and run app
    app = CliideApp(project_path=path)
    app.run()


if __name__ == "__main__":
    main()
