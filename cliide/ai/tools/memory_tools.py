"""Memory tools for agent memory management."""

from typing import Any

from cliide.ai.tools.base import Tool, ToolCategory, ToolResult, RiskLevel
from cliide.ai.memory import AgentMemory, MemoryCategory


class StoreMemoryTool(Tool):
    """Tool to store information in persistent memory."""

    def __init__(self, memory: AgentMemory):
        """Initialize the tool.

        Args:
            memory: AgentMemory instance
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.memory = memory

    @property
    def name(self) -> str:
        return "store_memory"

    @property
    def description(self) -> str:
        return """Store information in persistent per-project memory.
Use this to remember important discoveries, decisions, or context for future reference.
Categories: discovery (facts about codebase), decision (choices made), context (user preferences), error (issues encountered)."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Unique identifier for this memory (e.g., 'project_uses_pytest', 'user_prefers_tabs')"
                },
                "value": {
                    "type": "string",
                    "description": "The information to store"
                },
                "category": {
                    "type": "string",
                    "enum": ["discovery", "decision", "context", "error"],
                    "description": "Category of memory (default: discovery)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for searching later"
                }
            },
            "required": ["key", "value"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Store a memory."""
        key = args.get("key", "")
        value = args.get("value", "")
        category = args.get("category", "discovery")
        tags = args.get("tags", [])

        if not key or not value:
            return ToolResult(success=False, error="Both key and value are required")

        # Map category string to MemoryCategory
        category_map = {
            "discovery": MemoryCategory.DISCOVERY,
            "decision": MemoryCategory.DECISION,
            "context": MemoryCategory.CONTEXT,
            "error": MemoryCategory.ERROR,
        }
        mem_category = category_map.get(category, MemoryCategory.DISCOVERY)

        try:
            self.memory.store(
                key=key,
                value=value,
                category=mem_category,
                source="main",
                tags=tags,
            )

            return ToolResult(
                success=True,
                data=f"Stored memory: {key}",
                summary=f"Remembered: {key}",
                metadata={"key": key, "category": category}
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to store memory: {e}")


class RecallMemoryTool(Tool):
    """Tool to recall information from persistent memory."""

    def __init__(self, memory: AgentMemory):
        """Initialize the tool.

        Args:
            memory: AgentMemory instance
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.memory = memory

    @property
    def name(self) -> str:
        return "recall_memory"

    @property
    def description(self) -> str:
        return """Recall information from persistent per-project memory.
Search by key, category, or keywords to find previously stored information."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Specific memory key to recall (exact match)"
                },
                "category": {
                    "type": "string",
                    "enum": ["discovery", "decision", "context", "error"],
                    "description": "Category to filter by"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to search for in memories"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return (default: 10)"
                }
            },
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Recall memories."""
        key = args.get("key")
        category = args.get("category")
        keywords = args.get("keywords", [])
        limit = args.get("limit", 10)

        try:
            # Recall by specific key
            if key:
                entry = self.memory.recall_entry(key)
                if entry:
                    return ToolResult(
                        success=True,
                        data=f"[{entry.category}] {entry.key}: {entry.value}",
                        summary=f"Recalled: {key}",
                        metadata=entry.to_dict()
                    )
                else:
                    return ToolResult(
                        success=True,
                        data=f"No memory found for key: {key}",
                        summary="Memory not found"
                    )

            # Recall by category
            if category:
                category_map = {
                    "discovery": MemoryCategory.DISCOVERY,
                    "decision": MemoryCategory.DECISION,
                    "context": MemoryCategory.CONTEXT,
                    "error": MemoryCategory.ERROR,
                }
                mem_category = category_map.get(category, MemoryCategory.DISCOVERY)
                entries = self.memory.recall_by_category(mem_category, limit=limit)
            # Recall by keywords
            elif keywords:
                entries = self.memory.recall_context(keywords, limit=limit)
            # Recall recent
            else:
                entries = self.memory.recall_recent(limit=limit)

            if not entries:
                return ToolResult(
                    success=True,
                    data="No memories found matching criteria.",
                    summary="No memories found"
                )

            # Format output
            lines = []
            for entry in entries:
                lines.append(f"[{entry.category}] {entry.key}: {entry.value}")

            output = "\n".join(lines)

            return ToolResult(
                success=True,
                data=output,
                summary=f"Found {len(entries)} memories",
                metadata={"count": len(entries)}
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to recall memory: {e}")


class ForgetMemoryTool(Tool):
    """Tool to remove information from memory."""

    def __init__(self, memory: AgentMemory):
        """Initialize the tool.

        Args:
            memory: AgentMemory instance
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = True  # Requires confirmation since it deletes data
        self._risk_level = RiskLevel.MEDIUM
        self.memory = memory

    @property
    def name(self) -> str:
        return "forget_memory"

    @property
    def description(self) -> str:
        return """Remove a specific memory from persistent storage.
Use this to delete outdated or incorrect information."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The memory key to remove"
                }
            },
            "required": ["key"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Remove a memory."""
        key = args.get("key", "")

        if not key:
            return ToolResult(success=False, error="Key is required")

        try:
            removed = self.memory.forget(key)

            if removed:
                return ToolResult(
                    success=True,
                    data=f"Removed memory: {key}",
                    summary=f"Forgot: {key}"
                )
            else:
                return ToolResult(
                    success=True,
                    data=f"Memory not found: {key}",
                    summary="Memory not found"
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to remove memory: {e}")


class MemorySummaryTool(Tool):
    """Tool to get a summary of stored memories."""

    def __init__(self, memory: AgentMemory):
        """Initialize the tool.

        Args:
            memory: AgentMemory instance
        """
        super().__init__()
        self._category = ToolCategory.AGENT
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.memory = memory

    @property
    def name(self) -> str:
        return "memory_summary"

    @property
    def description(self) -> str:
        return """Get a summary of all stored memories including counts by category."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Get memory summary."""
        _ = args  # Unused but required by interface

        try:
            summary = self.memory.get_summary()

            lines = [
                f"Total memories: {summary['total']}",
                "",
                "By category:",
            ]

            for category, count in summary.get("by_category", {}).items():
                lines.append(f"  {category}: {count}")

            lines.extend([
                "",
                "By source:",
            ])

            for source, count in summary.get("by_source", {}).items():
                lines.append(f"  {source}: {count}")

            output = "\n".join(lines)

            return ToolResult(
                success=True,
                data=output,
                summary=f"Memory summary: {summary['total']} total",
                metadata=summary
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get memory summary: {e}")
