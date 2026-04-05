"""Shell command execution tool."""

import asyncio
import shlex
from pathlib import Path
from typing import Any

from cliide.ai.tools.base import Tool, ToolCategory, ToolResult, RiskLevel


class RunCommandTool(Tool):
    """Execute shell commands with safety controls."""

    # Commands that are generally safe to run
    ALLOWED_COMMANDS = {
        # Python
        "python", "python3", "pip", "pip3", "pytest", "mypy", "ruff", "black", "isort",
        # JavaScript/Node
        "node", "npm", "npx", "yarn", "pnpm", "jest", "vitest", "eslint", "prettier",
        # Rust
        "cargo", "rustc", "rustfmt", "clippy",
        # Go
        "go", "gofmt",
        # General tools
        "git", "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq",
        "echo", "pwd", "which", "env", "make", "cmake",
        # File tools (read-only)
        "file", "stat", "du", "diff",
    }

    # Patterns that are blocked for safety
    BLOCKED_PATTERNS = [
        "rm -rf /", "rm -rf ~", "rm -rf $HOME",
        "sudo", "su ",
        "> /dev/", ">> /dev/",
        "| sh", "| bash", "| zsh",
        "curl | ", "wget | ",
        ":(){", "fork bomb",
        "chmod 777", "chmod -R 777",
        "mkfs", "dd if=",
        ":(){ :|:& };:",
    ]

    def __init__(
        self,
        workspace_root: str | Path,
        timeout: int = 30,
        max_output_size: int = 50000,
    ):
        """Initialize the shell tool.

        Args:
            workspace_root: Root directory to run commands in
            timeout: Command timeout in seconds
            max_output_size: Maximum output size in characters
        """
        super().__init__()
        self._category = ToolCategory.COMMAND
        self._requires_confirmation = True  # Always require confirmation for shell
        self._risk_level = RiskLevel.HIGH  # Shell commands are always high risk
        self.workspace_root = Path(workspace_root).resolve()
        self.timeout = timeout
        self.max_output_size = max_output_size

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return """Execute a shell command in the workspace directory.
Use this to run tests, linters, build commands, git operations, and other CLI tools.
Commands run in the project root directory.
Common uses: pytest, npm test, cargo build, git status, etc."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute (e.g., 'pytest -v', 'npm run build')"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional subdirectory to run command in (relative to workspace root)"
                },
            },
            "required": ["command"]
        }

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """Check if a command is allowed to run.

        Args:
            command: The command string

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check for blocked patterns
        command_lower = command.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in command_lower:
                return False, f"Command contains blocked pattern: {pattern}"

        # Extract the base command
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"
            base_cmd = parts[0]
        except ValueError as e:
            return False, f"Invalid command syntax: {e}"

        # Check if base command is in allowlist
        # Also allow commands with paths like ./script.sh or /usr/bin/python
        if base_cmd.startswith("./") or base_cmd.startswith("/"):
            # Allow scripts in the workspace - but verify they exist
            if base_cmd.startswith("./"):
                script_path = self.workspace_root / base_cmd[2:]  # Remove "./" prefix
                if not script_path.exists():
                    return False, f"Script does not exist: {base_cmd}"
                if not script_path.is_file():
                    return False, f"Not a file: {base_cmd}"
                return True, ""
            # Be cautious with absolute paths
            return False, f"Absolute paths not allowed for safety: {base_cmd}"

        if base_cmd not in self.ALLOWED_COMMANDS:
            return False, f"Command '{base_cmd}' not in allowlist. Allowed: {', '.join(sorted(self.ALLOWED_COMMANDS))}"

        return True, ""

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute the shell command.

        Args:
            args: Dictionary with 'command' and optional 'working_dir'

        Returns:
            ToolResult with command output
        """
        command = args.get("command", "")
        working_dir = args.get("working_dir", "")

        if not command:
            return ToolResult(
                success=False,
                error="No command provided"
            )

        # Validate command
        is_allowed, reason = self._is_command_allowed(command)
        if not is_allowed:
            return ToolResult(
                success=False,
                error=f"Command not allowed: {reason}"
            )

        # Determine working directory
        if working_dir:
            cwd = self.workspace_root / working_dir
            if not cwd.exists():
                return ToolResult(
                    success=False,
                    error=f"Working directory does not exist: {working_dir}"
                )
            # Security: ensure we stay within workspace
            try:
                cwd.resolve().relative_to(self.workspace_root)
            except ValueError:
                return ToolResult(
                    success=False,
                    error="Working directory must be within workspace"
                )
        else:
            cwd = self.workspace_root

        # Execute command using subprocess_exec to avoid shell injection
        try:
            # Parse command into arguments (already validated via shlex.split earlier)
            cmd_args = shlex.split(command)
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=None,  # Use current environment
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {self.timeout} seconds"
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate if needed
            if len(stdout_str) > self.max_output_size:
                stdout_str = stdout_str[:self.max_output_size] + f"\n... (truncated, {len(stdout_str)} total chars)"
            if len(stderr_str) > self.max_output_size:
                stderr_str = stderr_str[:self.max_output_size] + f"\n... (truncated, {len(stderr_str)} total chars)"

            # Build result
            output_parts = []
            if stdout_str.strip():
                output_parts.append(f"STDOUT:\n{stdout_str}")
            if stderr_str.strip():
                output_parts.append(f"STDERR:\n{stderr_str}")

            output = "\n\n".join(output_parts) if output_parts else "(no output)"
            exit_code = process.returncode

            return ToolResult(
                success=exit_code == 0,
                data={
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": exit_code,
                },
                summary=f"Exit code: {exit_code}\n\n{output}",
                error=f"Command failed with exit code {exit_code}" if exit_code != 0 else None,
                metadata={
                    "command": command,
                    "working_dir": str(cwd),
                    "exit_code": exit_code,
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute command: {str(e)}"
            )
