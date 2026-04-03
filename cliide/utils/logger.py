"""Simple file logger for debugging."""

import time
from pathlib import Path


class DebugLogger:
    """Simple file logger for debugging."""

    def __init__(self, log_file: str = "/tmp/cliide_debug.log"):
        """Initialize logger.

        Args:
            log_file: Path to log file
        """
        self.log_file = Path(log_file)
        self.enabled = True

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
