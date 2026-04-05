"""Audit logging for tool executions."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles


class AuditLogger:
    """Logger for tool execution audits."""

    def __init__(self, log_file: Path | None = None, enabled: bool = True):
        """Initialize audit logger.

        Args:
            log_file: Path to audit log file. If None, uses default location.
            enabled: Whether logging is enabled
        """
        self.enabled = enabled

        if log_file is None:
            # Default to ~/.config/cliide/audit.log
            log_file = Path.home() / ".config" / "cliide" / "audit.log"

        self.log_file = log_file
        self._lock = asyncio.Lock()

        # Ensure directory exists
        if self.enabled:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    async def log_execution(
        self,
        tool_name: str,
        args: dict[str, Any],
        result_success: bool,
        approved: bool = True,
        error: str | None = None,
    ) -> None:
        """Log a tool execution.

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            result_success: Whether execution succeeded
            approved: Whether user approved the execution
            error: Error message if execution failed
        """
        if not self.enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build log entry
        status = "SUCCESS" if result_success else "FAILED"
        approval = "APPROVED" if approved else "DENIED"

        # Format args for logging (truncate large values)
        args_str = self._format_args(args)

        log_entry = f"[{timestamp}] {tool_name}({args_str}) - {approval} - {status}"

        if error:
            log_entry += f" - Error: {error}"

        log_entry += "\n"

        # Write to file asynchronously (non-blocking)
        async with self._lock:
            try:
                async with aiofiles.open(self.log_file, 'a', encoding='utf-8') as f:
                    await f.write(log_entry)
            except Exception:
                # Silently fail if logging fails
                pass

    def _format_args(self, args: dict[str, Any], max_length: int = 100) -> str:
        """Format arguments for logging.

        Args:
            args: Arguments dictionary
            max_length: Maximum length for each argument value

        Returns:
            Formatted string
        """
        formatted = []
        for key, value in args.items():
            value_str = str(value)
            if len(value_str) > max_length:
                value_str = value_str[:max_length] + "..."
            # Escape newlines
            value_str = value_str.replace("\n", "\\n")
            formatted.append(f"{key}={value_str!r}")

        return ", ".join(formatted)

    async def get_recent_logs(self, lines: int = 100) -> list[str]:
        """Get recent audit log entries.

        Args:
            lines: Number of recent lines to retrieve

        Returns:
            List of log entry strings
        """
        if not self.enabled or not self.log_file.exists():
            return []

        try:
            async with self._lock:
                async with aiofiles.open(self.log_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    all_lines = content.splitlines(keepends=True)

            # Return last N lines
            return all_lines[-lines:] if lines < len(all_lines) else all_lines

        except Exception:
            return []

    async def clear_logs(self) -> None:
        """Clear all audit logs."""
        if not self.enabled:
            return

        async with self._lock:
            try:
                if self.log_file.exists():
                    self.log_file.unlink()
            except Exception:
                pass


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger(enabled: bool = True) -> AuditLogger:
    """Get the global audit logger instance.

    Args:
        enabled: Whether logging should be enabled

    Returns:
        Global AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(enabled=enabled)
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger."""
    global _audit_logger
    _audit_logger = None
