"""Simple file logger for debugging."""

import os
import stat
import time
from pathlib import Path


def _get_secure_log_path() -> Path:
    """Get secure log file path in user's home directory.

    Returns:
        Path to log file with proper directory structure
    """
    log_dir = Path.home() / ".cliide" / "logs"

    # Create directory with restricted permissions (owner only)
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        # Set directory permissions to 700 (owner only)
        os.chmod(log_dir, stat.S_IRWXU)

    return log_dir / "debug.log"


class DebugLogger:
    """Simple file logger for debugging."""

    def __init__(self, log_file: str | None = None):
        """Initialize logger.

        Args:
            log_file: Path to log file (defaults to ~/.cliide/logs/debug.log)
        """
        self.log_file = Path(log_file) if log_file else _get_secure_log_path()
        self.enabled = True

        # Ensure parent directory exists with proper permissions
        if not self.log_file.parent.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(self.log_file.parent, stat.S_IRWXU)

        # Clear log on init
        if self.log_file.exists():
            self.log_file.unlink()

    def log(self, message: str) -> None:
        """Log a message.

        Args:
            message: Message to log
        """
        if not self.enabled:
            return

        timestamp = time.strftime("%H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
            f.flush()


# Global logger
_logger = DebugLogger()


def log(message: str) -> None:
    """Log a debug message.

    Args:
        message: Message to log
    """
    _logger.log(message)
