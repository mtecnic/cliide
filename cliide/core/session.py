"""Session management for persisting workspace state."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cliide.utils.logger import log


@dataclass
class ChatSession:
    """A single chat conversation session."""

    id: str
    name: str
    history: list[dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "history": self.history,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatSession":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            history=data.get("history", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class SessionState:
    """Complete session state for a project."""

    open_files: list[str] = field(default_factory=list)
    active_file: str | None = None
    chat_sessions: list[ChatSession] = field(default_factory=list)
    active_chat_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": 1,
            "open_files": self.open_files,
            "active_file": self.active_file,
            "chat_sessions": [s.to_dict() for s in self.chat_sessions],
            "active_chat_id": self.active_chat_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """Create from dictionary."""
        return cls(
            open_files=data.get("open_files", []),
            active_file=data.get("active_file"),
            chat_sessions=[
                ChatSession.from_dict(s) for s in data.get("chat_sessions", [])
            ],
            active_chat_id=data.get("active_chat_id"),
        )


class SessionManager:
    """Manages session persistence for a project."""

    def __init__(self, project_path: Path):
        """Initialize session manager.

        Args:
            project_path: Root path of the project
        """
        self.project_path = Path(project_path)
        self.storage_dir = self.project_path / ".cliide"
        self.session_path = self.storage_dir / "session.json"

    def save(self, state: SessionState) -> None:
        """Save session state to disk.

        Args:
            state: Session state to save
        """
        try:
            # Ensure storage directory exists
            self.storage_dir.mkdir(parents=True, exist_ok=True)

            # Write session file
            with open(self.session_path, "w") as f:
                json.dump(state.to_dict(), f, indent=2)

            log(f"[SESSION] Saved session to {self.session_path}")
        except Exception as e:
            log(f"[SESSION] Error saving session: {e}")

    def load(self) -> SessionState | None:
        """Load session state from disk.

        Returns:
            SessionState if exists and valid, None otherwise
        """
        if not self.session_path.exists():
            log(f"[SESSION] No session file at {self.session_path}")
            return None

        try:
            with open(self.session_path) as f:
                data = json.load(f)

            state = SessionState.from_dict(data)
            log(
                f"[SESSION] Loaded session: {len(state.open_files)} files, "
                f"{len(state.chat_sessions)} chats"
            )
            return state
        except Exception as e:
            log(f"[SESSION] Error loading session: {e}")
            return None

    def clear(self) -> None:
        """Delete session file."""
        try:
            if self.session_path.exists():
                self.session_path.unlink()
                log(f"[SESSION] Cleared session at {self.session_path}")
        except Exception as e:
            log(f"[SESSION] Error clearing session: {e}")
