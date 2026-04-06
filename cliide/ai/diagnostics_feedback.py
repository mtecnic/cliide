"""LSP diagnostics feedback loop for AI agent self-correction."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from cliide.core.config import get_config
from cliide.utils.logger import log


@dataclass
class DiagnosticsSnapshot:
    """Snapshot of diagnostics for a file at a point in time."""
    file_path: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0

    def get_error_count(self) -> int:
        """Count errors (severity 1) in diagnostics."""
        return sum(1 for d in self.diagnostics if d.get("severity", 4) == 1)

    def get_warning_count(self) -> int:
        """Count warnings (severity 2) in diagnostics."""
        return sum(1 for d in self.diagnostics if d.get("severity", 4) == 2)


class DiagnosticsFeedbackManager:
    """Manages LSP diagnostics feedback loop for AI agent self-correction.

    After the agent edits a file, this manager:
    1. Captures diagnostics before the edit
    2. Waits for LSP to process the change
    3. Compares before/after diagnostics
    4. If new errors appeared, formats a feedback prompt for the agent
    """

    def __init__(self) -> None:
        """Initialize the diagnostics feedback manager."""
        self._config = get_config().diagnostics_feedback
        self._snapshots: dict[str, DiagnosticsSnapshot] = {}
        self._current_diagnostics: dict[str, list[dict[str, Any]]] = {}
        self._diagnostic_event = asyncio.Event()
        self._retry_counts: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        """Check if diagnostics feedback is enabled."""
        return self._config.enabled and self._config.mode != "off"

    def register_diagnostic_handler(self) -> Callable[[str, list[dict]], None]:
        """Get a diagnostic handler to register with LSP manager.

        Returns:
            Callback function for diagnostic updates
        """
        def handler(file_path: str, diagnostics: list[dict[str, Any]]) -> None:
            self._current_diagnostics[file_path] = diagnostics
            self._diagnostic_event.set()
            log(f"[DIAG_FEEDBACK] Received {len(diagnostics)} diagnostics for {file_path}")

        return handler

    def capture_before_edit(self, file_path: str) -> DiagnosticsSnapshot:
        """Capture diagnostics snapshot before editing a file.

        Args:
            file_path: Path to the file being edited

        Returns:
            DiagnosticsSnapshot of current state
        """
        import time

        diagnostics = self._current_diagnostics.get(file_path, [])
        snapshot = DiagnosticsSnapshot(
            file_path=file_path,
            diagnostics=diagnostics.copy(),
            timestamp=time.monotonic(),
        )
        self._snapshots[file_path] = snapshot
        log(f"[DIAG_FEEDBACK] Captured snapshot for {file_path}: {snapshot.get_error_count()} errors, {snapshot.get_warning_count()} warnings")
        return snapshot

    async def wait_for_diagnostics(
        self,
        file_path: str,
        timeout_ms: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Wait for LSP to publish diagnostics for a file.

        Args:
            file_path: Path to wait for diagnostics
            timeout_ms: Timeout in milliseconds (uses config default if None)

        Returns:
            List of diagnostics for the file
        """
        timeout_ms = timeout_ms or self._config.wait_timeout_ms
        timeout_s = timeout_ms / 1000.0

        # Clear event and wait
        self._diagnostic_event.clear()

        try:
            await asyncio.wait_for(self._diagnostic_event.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            log(f"[DIAG_FEEDBACK] Timeout waiting for diagnostics for {file_path}")

        return self._current_diagnostics.get(file_path, [])

    def check_for_new_errors(
        self,
        before: DiagnosticsSnapshot,
        after: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Compare before/after diagnostics and return new errors.

        Args:
            before: Snapshot from before edit
            after: Current diagnostics

        Returns:
            List of new errors/warnings that appeared after the edit
        """
        threshold = self._config.severity_threshold

        # Get diagnostics that meet severity threshold
        before_issues = {
            (d.get("range", {}).get("start", {}).get("line", 0), d.get("message", ""))
            for d in before.diagnostics
            if d.get("severity", 4) <= threshold
        }

        new_errors = [
            d for d in after
            if d.get("severity", 4) <= threshold
            and (d.get("range", {}).get("start", {}).get("line", 0), d.get("message", ""))
            not in before_issues
        ]

        log(f"[DIAG_FEEDBACK] Found {len(new_errors)} new errors (threshold: severity <= {threshold})")
        return new_errors

    def should_auto_fix(self, file_path: str) -> bool:
        """Check if auto-fix should be attempted for a file.

        Args:
            file_path: Path to the file

        Returns:
            True if auto-fix should be attempted
        """
        if self._config.mode != "auto":
            return False

        retry_count = self._retry_counts.get(file_path, 0)
        if retry_count >= self._config.max_retries:
            log(f"[DIAG_FEEDBACK] Max retries ({self._config.max_retries}) reached for {file_path}")
            return False

        return True

    def increment_retry(self, file_path: str) -> int:
        """Increment retry count for a file.

        Args:
            file_path: Path to the file

        Returns:
            New retry count
        """
        count = self._retry_counts.get(file_path, 0) + 1
        self._retry_counts[file_path] = count
        return count

    def reset_retry(self, file_path: str) -> None:
        """Reset retry count for a file (call when errors are resolved).

        Args:
            file_path: Path to the file
        """
        self._retry_counts.pop(file_path, None)

    def format_feedback_prompt(
        self,
        file_path: str,
        new_errors: list[dict[str, Any]],
        file_content: str,
    ) -> str:
        """Format a feedback prompt for the AI agent.

        Args:
            file_path: Path to the file with errors
            new_errors: List of new diagnostic errors
            file_content: Current file content

        Returns:
            Formatted prompt for the agent
        """
        file_name = Path(file_path).name

        # Format errors
        error_lines = []
        for error in new_errors[:10]:  # Limit to first 10 errors
            severity = error.get("severity", 4)
            severity_label = {1: "ERROR", 2: "WARNING", 3: "INFO", 4: "HINT"}.get(severity, "ISSUE")
            line = error.get("range", {}).get("start", {}).get("line", 0) + 1  # 1-indexed
            message = error.get("message", "Unknown error")
            source = error.get("source", "")
            source_label = f" ({source})" if source else ""

            error_lines.append(f"  Line {line}: [{severity_label}]{source_label} {message}")

        errors_text = "\n".join(error_lines)
        retry_count = self._retry_counts.get(file_path, 0)

        # Include relevant context from the file
        lines = file_content.split("\n")
        error_line_nums = {
            error.get("range", {}).get("start", {}).get("line", 0)
            for error in new_errors[:10]
        }

        context_lines = []
        for line_num in sorted(error_line_nums):
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 3)
            context_lines.append(f"Lines {start + 1}-{end}:")
            for i in range(start, end):
                marker = ">>>" if i == line_num else "   "
                context_lines.append(f"{marker} {i + 1}: {lines[i]}")
            context_lines.append("")

        context_text = "\n".join(context_lines)

        return f"""The file `{file_name}` has new errors after your recent edit (attempt {retry_count + 1}/{self._config.max_retries}):

{errors_text}

Relevant code context:
```
{context_text}
```

Please fix these errors. Focus on the specific issues reported above."""

    def clear_all(self) -> None:
        """Clear all snapshots and retry counts."""
        self._snapshots.clear()
        self._retry_counts.clear()
        self._current_diagnostics.clear()


# Global instance
_feedback_manager: Optional[DiagnosticsFeedbackManager] = None


def get_diagnostics_feedback_manager() -> DiagnosticsFeedbackManager:
    """Get the global diagnostics feedback manager.

    Returns:
        DiagnosticsFeedbackManager instance
    """
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = DiagnosticsFeedbackManager()
    return _feedback_manager
