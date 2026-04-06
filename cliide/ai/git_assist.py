"""AI-powered git assistance for commit messages and more."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from cliide.utils.logger import log


# Marker to identify commits made by cliide
CLIIDE_MARKER = "(cliide)"


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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return False, "Staging timed out"
        except Exception as e:
            log(f"[GIT] Error staging changes: {e}")
            return False, str(e)

    async def get_last_commit_info(self) -> Optional[dict]:
        """Get information about the last commit.

        Returns:
            Dict with 'hash', 'message', 'author' or None if error
        """
        if not self._is_git_repo:
            return None

        process = None
        try:
            # Get the last commit hash, subject, and author
            process = await asyncio.create_subprocess_exec(
                "git", "log", "-1", "--format=%H%n%s%n%an",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                lines = stdout.decode("utf-8", errors="replace").strip().split("\n")
                if len(lines) >= 3:
                    return {
                        "hash": lines[0],
                        "message": lines[1],
                        "author": lines[2],
                    }
            return None

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting last commit info")
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return None
        except Exception as e:
            log(f"[GIT] Error getting last commit info: {e}")
            return None

    def is_cliide_commit(self, message: str) -> bool:
        """Check if a commit message was made by cliide.

        Args:
            message: Commit message to check

        Returns:
            True if the commit was made by cliide
        """
        return CLIIDE_MARKER in message

    async def reset_last_commit(self, soft: bool = True) -> tuple[bool, str]:
        """Reset (undo) the last commit.

        Args:
            soft: If True, keep changes staged (--soft). If False, unstage (--mixed).

        Returns:
            Tuple of (success, message)
        """
        if not self._is_git_repo:
            return False, "Not a git repository"

        process = None
        try:
            reset_mode = "--soft" if soft else "--mixed"
            process = await asyncio.create_subprocess_exec(
                "git", "reset", reset_mode, "HEAD~1",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                log("[GIT] Reset last commit successful")
                return True, "Last commit undone. Changes are now staged."
            else:
                error = stderr.decode("utf-8", errors="replace").strip()
                log(f"[GIT] Reset failed: {error}")
                return False, error or "Failed to reset commit"

        except asyncio.TimeoutError:
            log("[GIT] Timeout resetting commit")
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return False, "Reset timed out"
        except Exception as e:
            log(f"[GIT] Error resetting commit: {e}")
            return False, str(e)

    async def get_status(self) -> Optional[str]:
        """Get git status output.

        Returns:
            Git status string or None if error
        """
        if not self._is_git_repo:
            return None

        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "status", "-s",
                cwd=str(self.workspace_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)

            if process.returncode == 0:
                return stdout.decode("utf-8", errors="replace").strip()
            return None

        except asyncio.TimeoutError:
            log("[GIT] Timeout getting status")
            if process:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return None
        except Exception as e:
            log(f"[GIT] Error getting status: {e}")
            return None

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
- End the message with " {CLIIDE_MARKER}" on the same line as the summary

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
