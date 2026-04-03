"""Checkpoint management for agent state recovery."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cliide.ai.memory import AgentMemory


@dataclass
class Checkpoint:
    """A saved checkpoint of agent state."""
    checkpoint_id: str
    task_id: str  # "main" or sub-agent task_id
    timestamp: str  # ISO format
    iteration: int
    messages: list[dict[str, Any]]  # Conversation state
    tool_results: list[dict[str, Any]]  # Recent tool outputs
    memory_snapshot: dict[str, Any]  # Relevant memories at time of checkpoint
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(**data)

    def get_age_seconds(self) -> float:
        """Get age of checkpoint in seconds."""
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds()


class CheckpointManager:
    """Manage state checkpoints for recovery.

    Checkpoints allow agents to save their state periodically and resume
    from a known good state if interrupted or encountering errors.
    """

    def __init__(
        self,
        project_root: Path,
        max_checkpoints: int = 20,
        max_age_hours: int = 48,
    ):
        """Initialize checkpoint manager.

        Args:
            project_root: Root directory of the project
            max_checkpoints: Maximum checkpoints to keep per task
            max_age_hours: Maximum age before auto-pruning
        """
        self.project_root = Path(project_root)
        self.max_checkpoints = max_checkpoints
        self.max_age_hours = max_age_hours

        # Create storage directory
        self.storage_dir = self.project_root / ".cliide" / "checkpoints"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Index file for quick lookup
        self.index_path = self.storage_dir / "index.json"
        self._index: dict[str, list[str]] = {}  # task_id -> [checkpoint_ids]
        self._load_index()

    async def create_checkpoint(
        self,
        task_id: str,
        iteration: int,
        messages: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        memory: AgentMemory | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a checkpoint.

        Args:
            task_id: Task identifier ("main" or sub-agent task_id)
            iteration: Current iteration number
            messages: Conversation messages to save
            tool_results: Recent tool results (usually last 10)
            memory: Optional AgentMemory to snapshot relevant entries
            metadata: Optional additional metadata

        Returns:
            Checkpoint ID
        """
        checkpoint_id = str(uuid.uuid4())[:12]

        # Snapshot memory if provided
        memory_snapshot = {}
        if memory:
            # Get recent memories relevant to this task
            recent = memory.recall_recent(limit=20)
            memory_snapshot = {
                entry.key: entry.to_dict()
                for entry in recent
            }

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            iteration=iteration,
            messages=messages,
            tool_results=tool_results[-10:] if tool_results else [],  # Keep last 10
            memory_snapshot=memory_snapshot,
            metadata=metadata or {},
        )

        # Save checkpoint file
        checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, indent=2, default=str)
        except IOError:
            raise RuntimeError(f"Failed to save checkpoint: {checkpoint_path}")

        # Update index
        if task_id not in self._index:
            self._index[task_id] = []
        self._index[task_id].append(checkpoint_id)
        self._save_index()

        # Prune if needed
        await self._prune_task_checkpoints(task_id)

        return checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """Restore state from a checkpoint.

        Args:
            checkpoint_id: The checkpoint to restore

        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Checkpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError, IOError):
            return None

    def list_checkpoints(
        self,
        task_id: str | None = None,
        limit: int = 10,
    ) -> list[Checkpoint]:
        """List available checkpoints.

        Args:
            task_id: Optional filter by task
            limit: Maximum checkpoints to return

        Returns:
            List of checkpoints, most recent first
        """
        checkpoints = []

        if task_id:
            checkpoint_ids = self._index.get(task_id, [])
        else:
            checkpoint_ids = [
                cid for ids in self._index.values() for cid in ids
            ]

        for checkpoint_id in checkpoint_ids:
            checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"
            if checkpoint_path.exists():
                try:
                    with open(checkpoint_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoints.append(Checkpoint.from_dict(data))
                except (json.JSONDecodeError, KeyError, IOError):
                    continue

        # Sort by timestamp descending
        checkpoints.sort(key=lambda c: c.timestamp, reverse=True)

        return checkpoints[:limit]

    def get_latest_checkpoint(self, task_id: str) -> Checkpoint | None:
        """Get the most recent checkpoint for a task.

        Args:
            task_id: Task identifier

        Returns:
            Latest checkpoint or None
        """
        checkpoints = self.list_checkpoints(task_id=task_id, limit=1)
        return checkpoints[0] if checkpoints else None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: The checkpoint to delete

        Returns:
            True if deleted, False if not found
        """
        checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return False

        try:
            checkpoint_path.unlink()
        except IOError:
            return False

        # Update index
        for _, ids in self._index.items():
            if checkpoint_id in ids:
                ids.remove(checkpoint_id)
                break

        self._save_index()
        return True

    async def prune_old_checkpoints(self) -> int:
        """Remove old checkpoints to save space.

        Returns:
            Number of checkpoints removed
        """
        max_age_seconds = self.max_age_hours * 3600
        removed = 0

        for task_id in list(self._index.keys()):
            checkpoint_ids = self._index.get(task_id, []).copy()

            for checkpoint_id in checkpoint_ids:
                checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"

                if not checkpoint_path.exists():
                    # Clean up stale index entry
                    if checkpoint_id in self._index.get(task_id, []):
                        self._index[task_id].remove(checkpoint_id)
                    continue

                try:
                    with open(checkpoint_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoint = Checkpoint.from_dict(data)

                    if checkpoint.get_age_seconds() > max_age_seconds:
                        checkpoint_path.unlink()
                        self._index[task_id].remove(checkpoint_id)
                        removed += 1

                except (json.JSONDecodeError, KeyError, IOError):
                    # Remove corrupted checkpoint
                    try:
                        checkpoint_path.unlink()
                    except IOError:
                        pass
                    if checkpoint_id in self._index.get(task_id, []):
                        self._index[task_id].remove(checkpoint_id)
                    removed += 1

        self._save_index()
        return removed

    async def _prune_task_checkpoints(self, task_id: str) -> None:
        """Prune checkpoints for a specific task to stay under limit.

        Args:
            task_id: Task identifier
        """
        checkpoint_ids = self._index.get(task_id, [])

        if len(checkpoint_ids) <= self.max_checkpoints:
            return

        # Load all checkpoints for sorting
        checkpoints_with_ids = []
        for checkpoint_id in checkpoint_ids:
            checkpoint_path = self.storage_dir / f"{checkpoint_id}.json"
            if checkpoint_path.exists():
                try:
                    with open(checkpoint_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoints_with_ids.append((checkpoint_id, data["timestamp"]))
                except (json.JSONDecodeError, KeyError, IOError):
                    pass

        # Sort by timestamp ascending (oldest first)
        checkpoints_with_ids.sort(key=lambda x: x[1])

        # Remove oldest until under limit
        num_to_remove = len(checkpoints_with_ids) - self.max_checkpoints
        for checkpoint_id, _ in checkpoints_with_ids[:num_to_remove]:
            self.delete_checkpoint(checkpoint_id)

    def clear_task_checkpoints(self, task_id: str) -> int:
        """Clear all checkpoints for a task.

        Args:
            task_id: Task identifier

        Returns:
            Number of checkpoints removed
        """
        checkpoint_ids = self._index.get(task_id, []).copy()
        removed = 0

        for checkpoint_id in checkpoint_ids:
            if self.delete_checkpoint(checkpoint_id):
                removed += 1

        return removed

    def get_summary(self) -> dict[str, Any]:
        """Get checkpoint manager summary.

        Returns:
            Summary dict
        """
        total_checkpoints = sum(len(ids) for ids in self._index.values())
        total_size = sum(
            f.stat().st_size
            for f in self.storage_dir.glob("*.json")
            if f.name != "index.json"
        )

        return {
            "total_checkpoints": total_checkpoints,
            "tasks_with_checkpoints": len(self._index),
            "storage_path": str(self.storage_dir),
            "total_size_bytes": total_size,
            "max_checkpoints_per_task": self.max_checkpoints,
            "max_age_hours": self.max_age_hours,
        }

    def _load_index(self) -> None:
        """Load index from disk."""
        if not self.index_path.exists():
            return

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)
        except (json.JSONDecodeError, IOError):
            self._index = {}

    def _save_index(self) -> None:
        """Save index to disk."""
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self._index, f, indent=2)
        except IOError:
            pass  # Fail silently


class CheckpointRestoreContext:
    """Context for restoring from a checkpoint.

    Provides a clean interface for resuming agent execution from a checkpoint.
    """

    def __init__(self, checkpoint: Checkpoint, memory: AgentMemory | None = None):
        """Initialize restore context.

        Args:
            checkpoint: The checkpoint to restore from
            memory: Optional memory to restore snapshot into
        """
        self.checkpoint = checkpoint
        self.memory = memory
        self._restored = False

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Get restored conversation messages."""
        return self.checkpoint.messages

    @property
    def iteration(self) -> int:
        """Get iteration to resume from."""
        return self.checkpoint.iteration

    @property
    def task_id(self) -> str:
        """Get task ID."""
        return self.checkpoint.task_id

    @property
    def tool_results(self) -> list[dict[str, Any]]:
        """Get recent tool results."""
        return self.checkpoint.tool_results

    def restore_memory(self) -> None:
        """Restore memory snapshot if memory provided."""
        if self._restored or not self.memory:
            return

        # Restore each memory entry from snapshot
        for _, entry_data in self.checkpoint.memory_snapshot.items():
            self.memory.store(
                key=entry_data["key"],
                value=entry_data["value"],
                category=entry_data["category"],
                source=entry_data["source"],
                ttl=entry_data.get("ttl"),
                tags=entry_data.get("tags", []),
            )

        self._restored = True

    def get_resume_prompt(self) -> str:
        """Get a prompt to inject when resuming.

        Returns:
            Resume context prompt
        """
        return f"""Resuming from checkpoint (iteration {self.iteration}).

Previous context:
- Task: {self.checkpoint.metadata.get('task_description', 'Unknown')}
- Iteration: {self.iteration}
- Checkpoint created: {self.checkpoint.timestamp}

Recent tool results available. Continue from where you left off."""
