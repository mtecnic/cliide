"""Integrated terminal widget."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, RichLog, Static
from textual.binding import Binding


class TerminalPanel(Container):
    """Integrated terminal panel."""

    BINDINGS = [
        Binding("escape", "focus_editor", "Back to Editor", show=False),
    ]

    DEFAULT_CSS = """
    TerminalPanel {
        height: 15;
        background: $surface;
        border-top: heavy $primary;
    }

    TerminalPanel.hidden {
        display: none;
    }

    #terminal-header {
        height: 1;
        background: $boost;
        padding: 0 1;
    }

    #terminal-output {
        height: 1fr;
        background: $surface;
        padding: 0 1;
    }

    #terminal-input {
        dock: bottom;
        height: 3;
        border: tall $primary;
    }

    #terminal-input:focus {
        border: tall $accent;
    }
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize terminal.

        Args:
            working_dir: Initial working directory
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._cwd = working_dir or Path.cwd()
        self._process: asyncio.subprocess.Process | None = None
        self._history: list[str] = []
        self._history_index = 0

    def compose(self) -> ComposeResult:
        """Compose the terminal."""
        yield Static(f" Terminal - {self._cwd}", id="terminal-header")
        yield RichLog(id="terminal-output", highlight=True, markup=True)
        yield Input(placeholder="Enter command...", id="terminal-input")

    def on_mount(self) -> None:
        """Initialize on mount."""
        output = self.query_one("#terminal-output", RichLog)
        output.write(f"[dim]Terminal ready. Working directory: {self._cwd}[/dim]")
        output.write("[dim]Type 'help' for available commands, 'clear' to clear.[/dim]")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        if event.input.id != "terminal-input":
            return

        command = event.value.strip()
        event.input.value = ""

        if not command:
            return

        # Add to history
        self._history.append(command)
        self._history_index = len(self._history)

        output = self.query_one("#terminal-output", RichLog)
        output.write(f"[bold green]$[/] {command}")

        # Handle built-in commands
        if command == "clear":
            output.clear()
            return
        elif command == "help":
            output.write("[dim]Built-in commands:[/dim]")
            output.write("  [cyan]clear[/]  - Clear terminal")
            output.write("  [cyan]cd DIR[/] - Change directory")
            output.write("  [cyan]pwd[/]    - Print working directory")
            output.write("  [cyan]exit[/]   - Close terminal")
            output.write("[dim]Or run any shell command.[/dim]")
            return
        elif command == "exit":
            self.add_class("hidden")
            self.app.query_one("EditorWidget").focus()
            return
        elif command == "pwd":
            output.write(str(self._cwd))
            return
        elif command.startswith("cd "):
            path = command[3:].strip()
            await self._change_directory(path, output)
            return

        # Run shell command
        await self._run_command(command, output)

    async def _change_directory(self, path: str, output: RichLog) -> None:
        """Change working directory."""
        try:
            # Handle ~ for home
            if path.startswith("~"):
                path = os.path.expanduser(path)

            new_path = Path(path)
            if not new_path.is_absolute():
                new_path = self._cwd / new_path

            new_path = new_path.resolve()

            if new_path.is_dir():
                self._cwd = new_path
                self.query_one("#terminal-header", Static).update(f" Terminal - {self._cwd}")
                output.write(f"[dim]Changed to {self._cwd}[/dim]")
            else:
                output.write(f"[red]Not a directory: {path}[/red]")
        except Exception as e:
            output.write(f"[red]Error: {e}[/red]")

    async def _run_command(self, command: str, output: RichLog) -> None:
        """Run a shell command."""
        try:
            # Determine shell
            shell = os.environ.get("SHELL", "/bin/bash")
            if os.name == "nt":
                shell = os.environ.get("COMSPEC", "cmd.exe")

            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self._cwd),
                env={**os.environ, "TERM": "dumb"},  # Disable colors that might break
            )

            self._process = process

            # Read output
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                output.write(text)

            await process.wait()

            if process.returncode != 0:
                output.write(f"[dim]Exit code: {process.returncode}[/dim]")

        except Exception as e:
            output.write(f"[red]Error: {e}[/red]")
        finally:
            self._process = None

    def on_key(self, event) -> None:
        """Handle key events for history."""
        input_widget = self.query_one("#terminal-input", Input)

        if not input_widget.has_focus:
            return

        if event.key == "up":
            # Previous command
            if self._history and self._history_index > 0:
                self._history_index -= 1
                input_widget.value = self._history[self._history_index]
                input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()

        elif event.key == "down":
            # Next command
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                input_widget.value = self._history[self._history_index]
                input_widget.cursor_position = len(input_widget.value)
            elif self._history_index == len(self._history) - 1:
                self._history_index = len(self._history)
                input_widget.value = ""
            event.prevent_default()

    def action_focus_editor(self) -> None:
        """Focus back to editor."""
        try:
            self.app.query_one("EditorWidget").focus()
        except Exception:
            pass

    def focus_input(self) -> None:
        """Focus the input field."""
        self.query_one("#terminal-input", Input).focus()

    def toggle(self) -> None:
        """Toggle terminal visibility."""
        if self.has_class("hidden"):
            self.remove_class("hidden")
            self.focus_input()
        else:
            self.add_class("hidden")
            self.action_focus_editor()
