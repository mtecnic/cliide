"""Git operation tools."""

import asyncio
from pathlib import Path
from typing import Any

from cliide.ai.tools.base import Tool, ToolCategory, ToolResult, RiskLevel


class GitBaseTool(Tool):
    """Base class for git tools."""

    def __init__(self, workspace_root: str | Path):
        super().__init__()
        self._category = ToolCategory.COMMAND
        self.workspace_root = Path(workspace_root).resolve()

    async def _run_git(self, *args: str, timeout: int = 30) -> tuple[int, str, str]:
        """Run a git command.

        Args:
            *args: Git command arguments
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = ["git"] + list(args)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.workspace_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return -1, "", f"Git command timed out after {timeout}s"

        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )


class GitStatusTool(GitBaseTool):
    """Get git repository status."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = False  # Read-only, safe

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Get the current git status showing modified, staged, and untracked files."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        exit_code, stdout, stderr = await self._run_git("status", "--porcelain=v2", "--branch")

        if exit_code != 0:
            # Try without porcelain for non-git directories
            exit_code2, stdout2, stderr2 = await self._run_git("status")
            if exit_code2 != 0:
                return ToolResult(
                    success=False,
                    error=f"Not a git repository or git error: {stderr or stderr2}"
                )
            stdout = stdout2

        return ToolResult(
            success=True,
            data=stdout,
            summary=f"Git Status:\n{stdout}" if stdout.strip() else "Working tree clean",
        )


class GitDiffTool(GitBaseTool):
    """Show git diff for changes."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = False  # Read-only, safe

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Show git diff for unstaged changes, or staged changes if --staged is specified."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Optional specific file to diff"
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged changes instead of unstaged (default: false)"
                }
            },
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        file_path = args.get("file", "")
        staged = args.get("staged", False)

        git_args = ["diff"]
        if staged:
            git_args.append("--staged")
        if file_path:
            git_args.append("--")
            git_args.append(file_path)

        exit_code, stdout, stderr = await self._run_git(*git_args)

        if exit_code != 0:
            return ToolResult(
                success=False,
                error=f"Git diff failed: {stderr}"
            )

        diff_type = "staged" if staged else "unstaged"
        return ToolResult(
            success=True,
            data=stdout,
            summary=f"Git Diff ({diff_type}):\n{stdout}" if stdout.strip() else f"No {diff_type} changes",
        )


class GitLogTool(GitBaseTool):
    """Show git commit history."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = False  # Read-only, safe

    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "Show recent git commit history."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of commits to show (default: 10, max: 50)"
                },
                "oneline": {
                    "type": "boolean",
                    "description": "Use one-line format (default: true)"
                }
            },
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        count = min(args.get("count", 10), 50)  # Cap at 50
        oneline = args.get("oneline", True)

        git_args = ["log", f"-{count}"]
        if oneline:
            git_args.append("--oneline")
        else:
            git_args.extend(["--format=%h %an %ad %s", "--date=short"])

        exit_code, stdout, stderr = await self._run_git(*git_args)

        if exit_code != 0:
            return ToolResult(
                success=False,
                error=f"Git log failed: {stderr}"
            )

        return ToolResult(
            success=True,
            data=stdout,
            summary=f"Git Log (last {count} commits):\n{stdout}" if stdout.strip() else "No commits yet",
        )


class GitCommitTool(GitBaseTool):
    """Create a git commit."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = True  # Modifies repo, requires confirmation
        self._risk_level = RiskLevel.HIGH  # Git commits are high risk

    @property
    def name(self) -> str:
        return "git_commit"

    @property
    def description(self) -> str:
        return "Create a git commit with the staged changes. Use git_status first to see what will be committed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message"
                },
                "add_all": {
                    "type": "boolean",
                    "description": "Stage all modified files before committing (git add -A)"
                }
            },
            "required": ["message"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        message = args.get("message", "")
        add_all = args.get("add_all", False)

        if not message:
            return ToolResult(
                success=False,
                error="Commit message is required"
            )

        # Optionally stage all files
        if add_all:
            exit_code, _, stderr = await self._run_git("add", "-A")
            if exit_code != 0:
                return ToolResult(
                    success=False,
                    error=f"Failed to stage files: {stderr}"
                )

        # Check if there are staged changes
        exit_code, stdout, _ = await self._run_git("diff", "--staged", "--name-only")
        if exit_code == 0 and not stdout.strip():
            return ToolResult(
                success=False,
                error="No staged changes to commit. Use add_all=true or stage files first."
            )

        # Create commit
        exit_code, stdout, stderr = await self._run_git("commit", "-m", message)

        if exit_code != 0:
            return ToolResult(
                success=False,
                error=f"Commit failed: {stderr}"
            )

        return ToolResult(
            success=True,
            data=stdout,
            summary=f"Committed successfully:\n{stdout}",
            metadata={"message": message}
        )


class GitAddTool(GitBaseTool):
    """Stage files for commit."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = False  # Staging is reversible and safe

    @property
    def name(self) -> str:
        return "git_add"

    @property
    def description(self) -> str:
        return "Stage files for the next commit."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files to stage, or use ['.'] to stage all"
                }
            },
            "required": ["files"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        files = args.get("files", [])

        if not files:
            return ToolResult(
                success=False,
                error="No files specified to stage"
            )

        git_args = ["add"] + files
        exit_code, stdout, stderr = await self._run_git(*git_args)

        if exit_code != 0:
            return ToolResult(
                success=False,
                error=f"Failed to stage files: {stderr}"
            )

        # Get status to show what was staged
        _, status_out, _ = await self._run_git("status", "--short")

        return ToolResult(
            success=True,
            data=status_out,
            summary=f"Staged files:\n{status_out}" if status_out.strip() else "Files staged",
        )


class GitBranchTool(GitBaseTool):
    """List or create git branches."""

    def __init__(self, workspace_root: str | Path):
        super().__init__(workspace_root)
        self._requires_confirmation = False  # Listing is safe, creating is minimal risk

    @property
    def name(self) -> str:
        return "git_branch"

    @property
    def description(self) -> str:
        return "List branches or create a new branch."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of new branch to create (optional - omit to list branches)"
                },
                "checkout": {
                    "type": "boolean",
                    "description": "Switch to the new branch after creating it"
                }
            },
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        name = args.get("name", "")
        checkout = args.get("checkout", False)

        if not name:
            # List branches
            exit_code, stdout, stderr = await self._run_git("branch", "-a", "-v")
            if exit_code != 0:
                return ToolResult(
                    success=False,
                    error=f"Failed to list branches: {stderr}"
                )
            return ToolResult(
                success=True,
                data=stdout,
                summary=f"Branches:\n{stdout}",
            )

        # Create branch
        if checkout:
            exit_code, stdout, stderr = await self._run_git("checkout", "-b", name)
        else:
            exit_code, stdout, stderr = await self._run_git("branch", name)

        if exit_code != 0:
            return ToolResult(
                success=False,
                error=f"Failed to create branch: {stderr}"
            )

        return ToolResult(
            success=True,
            data=stdout or f"Created branch: {name}",
            summary=f"Created branch '{name}'" + (" and switched to it" if checkout else ""),
        )
