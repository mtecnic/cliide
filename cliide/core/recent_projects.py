"""Recent projects management for quick project switching."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cliide.utils.logger import log


@dataclass
class RecentProject:
    """A recently opened project."""

    path: str
    name: str
    last_opened: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "name": self.name,
            "last_opened": self.last_opened.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecentProject":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            name=data["name"],
            last_opened=datetime.fromisoformat(data["last_opened"]),
        )

    def time_ago(self) -> str:
        """Get human-readable time since last opened."""
        delta = datetime.now() - self.last_opened
        seconds = int(delta.total_seconds())

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days}d ago"
        else:
            weeks = seconds // 604800
            return f"{weeks}w ago"


class RecentProjectsManager:
    """Manages list of recently opened projects."""

    MAX_PROJECTS = 20

    def __init__(self):
        """Initialize recent projects manager."""
        self.config_dir = Path.home() / ".config" / "cliide"
        self.config_path = self.config_dir / "recent_projects.json"
        self._projects: list[RecentProject] = []
        self._loaded = False  # Lazy load on first access

    def _ensure_loaded(self) -> None:
        """Ensure projects are loaded (lazy load on first access)."""
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self) -> None:
        """Load recent projects from disk."""
        if not self.config_path.exists():
            log("[RECENT] No recent projects file found")
            return

        try:
            with open(self.config_path) as f:
                data = json.load(f)

            self._projects = [
                RecentProject.from_dict(p) for p in data.get("projects", [])
            ]
            log(f"[RECENT] Loaded {len(self._projects)} recent projects")
        except Exception as e:
            log(f"[RECENT] Error loading recent projects: {e}")
            self._projects = []

    def _save(self) -> None:
        """Save recent projects to disk."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "projects": [p.to_dict() for p in self._projects],
            }

            with open(self.config_path, "w") as f:
                json.dump(data, f, indent=2)

            log(f"[RECENT] Saved {len(self._projects)} recent projects")
        except Exception as e:
            log(f"[RECENT] Error saving recent projects: {e}")

    def add(self, path: Path) -> None:
        """Add or update a project in recent list.

        Args:
            path: Path to the project directory
        """
        self._ensure_loaded()
        path = Path(path).resolve()
        path_str = str(path)

        # Remove existing entry if present
        self._projects = [p for p in self._projects if p.path != path_str]

        # Add new entry at the beginning
        self._projects.insert(
            0,
            RecentProject(
                path=path_str,
                name=path.name,
                last_opened=datetime.now(),
            ),
        )

        # Limit to max projects
        self._projects = self._projects[: self.MAX_PROJECTS]

        # Save to disk
        self._save()

    def get_all(self, filter_existing: bool = True) -> list[RecentProject]:
        """Get all recent projects.

        Args:
            filter_existing: If True, filter out projects that no longer exist

        Returns:
            List of recent projects, sorted by most recent first
        """
        self._ensure_loaded()
        if filter_existing:
            valid = [p for p in self._projects if Path(p.path).exists()]
            # Update list if we filtered any
            if len(valid) != len(self._projects):
                self._projects = valid
                self._save()
            return valid
        return self._projects.copy()

    def remove(self, path: str) -> None:
        """Remove a project from recent list.

        Args:
            path: Path to remove
        """
        self._ensure_loaded()
        path_str = str(Path(path).resolve())
        self._projects = [p for p in self._projects if p.path != path_str]
        self._save()

    def clear(self) -> None:
        """Clear all recent projects."""
        self._projects = []
        self._loaded = True  # Mark as loaded (empty)
        self._save()

    def __len__(self) -> int:
        """Number of recent projects."""
        self._ensure_loaded()
        return len(self._projects)

    def __iter__(self):
        """Iterate over recent projects."""
        return iter(self._projects)
