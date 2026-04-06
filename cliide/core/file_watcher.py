"""File system watcher using watchdog for auto-refresh."""

import asyncio
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from cliide.utils.logger import log

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
}

# Debounce interval in seconds
DEBOUNCE_INTERVAL = 0.3


class DebouncedEventHandler(FileSystemEventHandler):
    """File system event handler with debouncing."""

    def __init__(self, callback: Callable[[list[str], str], None]) -> None:
        """Initialize the handler.

        Args:
            callback: Function to call with (paths, event_type) when events occur
        """
        super().__init__()
        self._callback = callback
        self._pending_events: dict[str, str] = {}  # path -> event_type
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored.

        Args:
            path: File path to check

        Returns:
            True if path should be ignored
        """
        path_obj = Path(path)
        for part in path_obj.parts:
            if part in IGNORE_DIRS:
                return True
            # Handle patterns like *.egg-info
            for pattern in IGNORE_DIRS:
                if "*" in pattern and path_obj.match(pattern):
                    return True
        return False

    def _schedule_callback(self) -> None:
        """Schedule the callback after debounce interval."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_INTERVAL, self._fire_callback)
            self._timer.start()

    def _fire_callback(self) -> None:
        """Fire the callback with pending events."""
        with self._lock:
            if not self._pending_events:
                return
            events = self._pending_events.copy()
            self._pending_events.clear()

        # Group by event type
        by_type: dict[str, list[str]] = {}
        for path, event_type in events.items():
            by_type.setdefault(event_type, []).append(path)

        # Fire callbacks
        for event_type, paths in by_type.items():
            try:
                self._callback(paths, event_type)
            except Exception as e:
                log(f"[FileWatcher] Error in callback: {e}")

    def _handle_event(self, event: FileSystemEvent, event_type: str) -> None:
        """Handle a file system event.

        Args:
            event: The watchdog event
            event_type: Type of event (created, deleted, modified, moved)
        """
        if event.is_directory and event_type == "modified":
            return  # Ignore directory modifications (contents change handles this)

        path = event.src_path
        if self._should_ignore(path):
            return

        with self._lock:
            self._pending_events[path] = event_type

        self._schedule_callback()

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle_event(event, "created")

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle_event(event, "deleted")

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle_event(event, "modified")

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle_event(event, "moved")


class FileWatcher:
    """Watches a directory for file system changes."""

    def __init__(
        self,
        path: Path,
        callback: Callable[[list[str], str], None],
    ) -> None:
        """Initialize the file watcher.

        Args:
            path: Directory to watch
            callback: Function to call when changes detected
        """
        self._path = path
        self._callback = callback
        self._observer: Observer | None = None
        self._handler: DebouncedEventHandler | None = None

    def start(self) -> None:
        """Start watching the directory."""
        if self._observer:
            return  # Already watching

        log(f"[FileWatcher] Starting watch on {self._path}")
        self._handler = DebouncedEventHandler(self._callback)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._path), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stop watching the directory."""
        if self._observer:
            log("[FileWatcher] Stopping watch")
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
            self._handler = None

    @property
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._observer is not None and self._observer.is_alive()
