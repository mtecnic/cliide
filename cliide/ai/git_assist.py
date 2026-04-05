"""AI-powered git assistance for commit messages and more."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from cliide.utils.logger import log


class GitAssist:
    """AI-powered git assistance."""

    def __init__(self, workspace_path: Path) -> None:
        """Initialize git assist.

        Args:
            workspace_path: Root workspace path
        """
        self.workspace_path = workspace_path
        self._is_git_repo = (workspace_path / ".git").exists()

    @property
    def is_git_repo(self) -> bool:
        """Check if workspace is a git repo."""
        return self._is_git_repo

    async def get_staged_diff(self) -> Optional[str]:
        """Get diff of staged changes.

        Returns:
            Staged diff or None if no staged changes
        """
        if not self._is_git_repo:
            return None

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "diff", "--staged",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                diff = stdout.decode("utf-8", errors="replace").strip()
                return diff if diff else None
            return None

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting staged diff")
            if process:
                process.kill()
            return None
        except Exception as e:
            log(f"[GIT] Error getting staged diff: {e}")
            return None

    async def get_unstaged_diff(self) -> Optional[str]:
        """Get diff of unstaged changes.

        Returns:
            Unstaged diff or None if no changes
        """
        if not self._is_git_repo:
            return None

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "diff",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                diff = stdout.decode("utf-8", errors="replace").strip()
                return diff if diff else None
            return None

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting unstaged diff")
            if process:
                process.kill()
            return None
        except Exception as e:
            log(f"[GIT] Error getting unstaged diff: {e}")
            return None

    async def get_all_changes_diff(self) -> Optional[str]:
        """Get diff of all changes (staged + unstaged).

        Returns:
            Combined diff or None if no changes
        """
        if not self._is_git_repo:
            return None

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                diff = stdout.decode("utf-8", errors="replace").strip()
                return diff if diff else None
            return None

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting all changes diff")
            if process:
                process.kill()
            return None
        except Exception as e:
            log(f"[GIT] Error getting all changes diff: {e}")
            return None

    async def get_staged_files(self) -> list[str]:
        """Get list of staged files.

        Returns:
            List of staged file paths
        """
        if not self._is_git_repo:
            return []

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "diff", "--staged", "--name-only",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                files = stdout.decode("utf-8", errors="replace").strip()
                return files.split("\n") if files else []
            return []

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting staged files")
            if process:
                process.kill()
            return []
        except Exception as e:
            log(f"[GIT] Error getting staged files: {e}")
            return []

    async def commit(self, message: str) -> tuple[bool, str]:
        """Create a commit with the given message.

        Args:
            message: Commit message

        Returns:
            Tuple of (success, output_message)
        """
        if not self._is_git_repo:
            return False, "Not a git repository"

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", message,
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode == 0:
                log(f"[GIT] Commit successful: {output}")
                return True, output or "Commit created successfully"
            else:
                log(f"[GIT] Commit failed: {error}")
                return False, error or "Commit failed"

        except asyncio.TimeoutError:
            log("[GIT] Timeout creating commit")
            if process:
                process.kill()
            return False, "Commit timed out"
        except Exception as e:
            log(f"[GIT] Error creating commit: {e}")
            return False, str(e)

    async def stage_all(self) -> tuple[bool, str]:
        """Stage all changes.

        Returns:
            Tuple of (success, output_message)
        """
        if not self._is_git_repo:
            return False, "Not a git repository"

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "add", "-A",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                return True, "All changes staged"
            else:
                error = stderr.decode("utf-8", errors="replace").strip()
                return False, error or "Failed to stage changes"

        except asyncio.TimeoutError:
            log("[GIT] Timeout staging changes")
            if process:
                process.kill()
            return False, "Staging timed out"
        except Exception as e:
            log(f"[GIT] Error staging changes: {e}")
            return False, str(e)

    def generate_commit_prompt(self, diff: str, staged_files: list[str]) -> str:
        """Generate prompt for AI commit message.

        Args:
            diff: Git diff content
            staged_files: List of staged file names

        Returns:
            Prompt for AI
        """
        # Truncate diff if too long
        max_diff_length = 8000
        if len(diff) > max_diff_length:
            diff = diff[:max_diff_length] + "\n\n[... diff truncated ...]"

        files_list = "\n".join(f"  - {f}" for f in staged_files)

        return f"""Write a concise git commit message for the following changes.

Files changed:
{files_list}

Diff:
```diff
{diff}
```

Guidelines:
- First line: imperative mood, max 50 chars (e.g., "Add user authentication")
- If needed, add a blank line then bullet points for details
- Focus on WHAT changed and WHY, not HOW
- Be specific but concise

Respond with ONLY the commit message, nothing else."""

    def generate_review_prompt(self, diff: str) -> str:
        """Generate prompt for AI code review.

        Args:
            diff: Git diff content

        Returns:
            Prompt for AI
        """
        # Truncate diff if too long
        max_diff_length = 12000
        if len(diff) > max_diff_length:
            diff = diff[:max_diff_length] + "\n\n[... diff truncated ...]"

        return f"""Review the following code changes and provide constructive feedback.

```diff
{diff}
```

Please analyze:
1. **Potential Issues**: Bugs, edge cases, or logic errors
2. **Security**: Any security concerns (injection, auth, etc.)
3. **Code Quality**: Naming, structure, readability
4. **Best Practices**: Language-specific idioms and patterns
5. **Performance**: Any obvious performance concerns

Format your response as a structured review with clear sections.
Be constructive and specific. If the code looks good, say so briefly.
Focus on the most important issues first."""
