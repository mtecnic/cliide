"""Persistent per-project agent memory system."""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryCategory:
    """Memory categories for organization."""
    DISCOVERY = "discovery"      # Facts learned about codebase
    DECISION = "decision"        # Decisions made during execution
    CONTEXT = "context"          # User preferences and context
    TOOL_RESULT = "tool_result"  # Important tool outputs
    ERROR = "error"              # Errors encountered


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: Any
    category: str
    timestamp: str  # ISO format for JSON serialization
    source: str  # "main" or task_id
    ttl: int | None = None  # seconds until expiry, None = permanent
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if this memory has expired."""
        if self.ttl is None:
            return False
        created = datetime.fromisoformat(self.timestamp)
        age_seconds = (datetime.now() - created).total_seconds()
        return age_seconds > self.ttl

    def matches_keywords(self, keywords: list[str]) -> bool:
        """Check if memory matches any keywords."""
        searchable = f"{self.key} {self.value} {' '.join(self.tags)}".lower()
        return any(kw.lower() in searchable for kw in keywords)


class AgentMemory:
    """Persistent per-project memory for agents.

    Stores discoveries, decisions, and context that persists across sessions.
    Memory is stored in the project's .cliide directory.
    """

    def __init__(self, project_root: Path, max_entries: int = 1000):
        """Initialize agent memory.

        Args:
            project_root: Root directory of the project
            max_entries: Maximum number of entries to store
        """
        self.project_root = Path(project_root)
        self.max_entries = max_entries

        # Create storage directory
        self.storage_dir = self.project_root / ".cliide"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = self.storage_dir / "memory.json"

        # In-memory cache
        self._memory: dict[str, MemoryEntry] = {}
        self._load()

    def store(
        self,
        key: str,
        value: Any,
        category: str = MemoryCategory.DISCOVERY,
        source: str = "main",
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Store a memory entry.

        Args:
            key: Unique identifier for this memory
            value: The value to store (must be JSON-serializable)
            category: Category of memory (discovery, decision, context, tool_result)
            source: Source agent ("main" or sub-agent task_id)
            ttl: Time-to-live in seconds (None = permanent)
            tags: Optional tags for search
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            category=category,
            timestamp=datetime.now().isoformat(),
            source=source,
            ttl=ttl,
            tags=tags or [],
        )

        self._memory[key] = entry

        # Enforce max entries
        if len(self._memory) > self.max_entries:
            self._prune_oldest()

        self._save()

    def recall(self, key: str) -> Any | None:
        """Recall a specific memory by key.

        Args:
            key: The memory key

        Returns:
            The stored value or None if not found/expired
        """
        entry = self._memory.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            self.forget(key)
            return None

        return entry.value

    def recall_entry(self, key: str) -> MemoryEntry | None:
        """Recall a full memory entry by key.

        Args:
            key: The memory key

        Returns:
            The full MemoryEntry or None
        """
        entry = self._memory.get(key)
        if entry is None or entry.is_expired():
            return None
        return entry

    def recall_by_category(
        self,
        category: str,
        limit: int = 10,
        source: str | None = None,
    ) -> list[MemoryEntry]:
        """Recall memories by category.

        Args:
            category: Category to filter by
            limit: Maximum entries to return
            source: Optional source filter

        Returns:
            List of matching entries, most recent first
        """
        entries = [
            e for e in self._memory.values()
            if e.category == category
            and not e.is_expired()
            and (source is None or e.source == source)
        ]

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[:limit]

    def recall_context(
        self,
        keywords: list[str],
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search memories by keywords.

        Args:
            keywords: Keywords to search for
            limit: Maximum entries to return

        Returns:
            List of matching entries, most recent first
        """
        entries = [
            e for e in self._memory.values()
            if not e.is_expired() and e.matches_keywords(keywords)
        ]

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[:limit]

    def recall_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Recall most recent memories.

        Args:
            limit: Maximum entries to return

        Returns:
            List of recent entries
        """
        entries = [e for e in self._memory.values() if not e.is_expired()]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def forget(self, key: str) -> bool:
        """Remove a memory.

        Args:
            key: The memory key to remove

        Returns:
            True if removed, False if not found
        """
        if key in self._memory:
            del self._memory[key]
            self._save()
            return True
        return False

    def forget_by_source(self, source: str) -> int:
        """Remove all memories from a source.

        Args:
            source: The source to remove memories for

        Returns:
            Number of entries removed
        """
        keys_to_remove = [
            k for k, v in self._memory.items()
            if v.source == source
        ]

        for key in keys_to_remove:
            del self._memory[key]

        if keys_to_remove:
            self._save()

        return len(keys_to_remove)

    def prune_expired(self) -> int:
        """Remove all expired memories.

        Returns:
            Number of entries removed
        """
        keys_to_remove = [
            k for k, v in self._memory.items()
            if v.is_expired()
        ]

        for key in keys_to_remove:
            del self._memory[key]

        if keys_to_remove:
            self._save()

        return len(keys_to_remove)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of stored memories.

        Returns:
            Summary dict with counts by category
        """
        self.prune_expired()

        by_category: dict[str, int] = {}
        by_source: dict[str, int] = {}

        for entry in self._memory.values():
            by_category[entry.category] = by_category.get(entry.category, 0) + 1
            by_source[entry.source] = by_source.get(entry.source, 0) + 1

        return {
            "total": len(self._memory),
            "by_category": by_category,
            "by_source": by_source,
            "storage_path": str(self.storage_path),
        }

    def get_context_for_prompt(self, max_entries: int = 10) -> str:
        """Get memory context formatted for inclusion in system prompt.

        Args:
            max_entries: Maximum entries to include

        Returns:
            Formatted string for prompt injection
        """
        entries = self.recall_recent(max_entries)

        if not entries:
            return ""

        lines = ["## Remembered Context"]
        for entry in entries:
            category_icon = {
                MemoryCategory.DISCOVERY: "📝",
                MemoryCategory.DECISION: "✅",
                MemoryCategory.CONTEXT: "💡",
                MemoryCategory.TOOL_RESULT: "🔧",
                MemoryCategory.ERROR: "⚠️",
            }.get(entry.category, "•")

            lines.append(f"{category_icon} [{entry.category}] {entry.key}: {entry.value}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all memories."""
        self._memory.clear()
        self._save()

    def _prune_oldest(self) -> None:
        """Remove oldest entries to stay under max_entries."""
        # First, remove expired
        self.prune_expired()

        if len(self._memory) <= self.max_entries:
            return

        # Sort by timestamp and remove oldest
        entries = sorted(
            self._memory.items(),
            key=lambda x: x[1].timestamp
        )

        num_to_remove = len(entries) - self.max_entries
        for key, _ in entries[:num_to_remove]:
            del self._memory[key]

    def _load(self) -> None:
        """Load memory from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._memory = {
                k: MemoryEntry.from_dict(v)
                for k, v in data.items()
            }

            # Prune expired on load
            self.prune_expired()

        except (json.JSONDecodeError, KeyError) as e:
            # Corrupted file, start fresh
            self._memory = {}

    def _save(self) -> None:
        """Persist memory to disk."""
        data = {k: v.to_dict() for k, v in self._memory.items()}

        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except IOError:
            pass  # Fail silently on write errors


class ReadOnlyMemory:
    """Read-only view of agent memory for sub-agents."""

    def __init__(self, memory: AgentMemory):
        """Initialize read-only memory view.

        Args:
            memory: The underlying agent memory
        """
        self._memory = memory

    def recall(self, key: str) -> Any | None:
        """Recall a specific memory."""
        return self._memory.recall(key)

    def recall_entry(self, key: str) -> MemoryEntry | None:
        """Recall a full memory entry."""
        return self._memory.recall_entry(key)

    def recall_by_category(
        self,
        category: str,
        limit: int = 10,
        source: str | None = None,
    ) -> list[MemoryEntry]:
        """Recall memories by category."""
        return self._memory.recall_by_category(category, limit, source)

    def recall_context(self, keywords: list[str], limit: int = 10) -> list[MemoryEntry]:
        """Search memories by keywords."""
        return self._memory.recall_context(keywords, limit)

    def recall_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Recall most recent memories."""
        return self._memory.recall_recent(limit)

    def get_summary(self) -> dict[str, Any]:
        """Get memory summary."""
        return self._memory.get_summary()

    def get_context_for_prompt(self, max_entries: int = 10) -> str:
        """Get memory context for prompt."""
        return self._memory.get_context_for_prompt(max_entries)


class MemoryProposal:
    """A proposed memory entry from a sub-agent.

    Sub-agents can propose memories that the main agent can approve/store.
    """

    def __init__(
        self,
        key: str,
        value: Any,
        category: str,
        source: str,
        tags: list[str] | None = None,
    ):
        self.key = key
        self.value = value
        self.category = category
        self.source = source
        self.tags = tags or []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "source": self.source,
            "tags": self.tags,
            "timestamp": self.timestamp,
        }
