"""Project management tools for switching directories."""

from pathlib import Path
from typing import Any

from cliide.ai.event_bus import AgentEvent, AgentEventBus, AgentEventType, get_event_bus
from cliide.ai.tools.base import Tool, ToolCategory, ToolResult, RiskLevel


class ChangeDirectoryTool(Tool):
    """Tool for switching to a different project directory."""

    def __init__(self, event_bus: AgentEventBus | None = None):
        """Initialize the tool.

        Args:
            event_bus: Event bus for emitting project change events
        """
        super().__init__()
        self._category = ToolCategory.OTHER
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW
        self.event_bus = event_bus or get_event_bus()

    @property
    def name(self) -> str:
        """Tool name."""
        return "change_directory"

    @property
    def description(self) -> str:
        """Tool description for AI."""
        return (
            "Switch to a different project directory. Use when the user asks to "
            "open, switch to, or change to another project or folder. This will "
            "update the file tree, reset the workspace, and load any saved session "
            "for that project."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the project directory. Can be absolute "
                        "(e.g., /home/user/projects/myapp) or relative to home "
                        "(e.g., ~/projects/myapp)"
                    ),
                }
            },
            "required": ["path"],
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute the directory change.

        Args:
            args: Tool arguments with 'path' key

        Returns:
            ToolResult indicating success or failure
        """
        path_str = args.get("path", "")

        if not path_str:
            return ToolResult(
                success=False,
                error="No path provided",
            )

        # Expand user home and resolve to absolute path
        try:
            path = Path(path_str).expanduser().resolve()
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Invalid path: {e}",
            )

        # Validate path exists
        if not path.exists():
            return ToolResult(
                success=False,
                error=f"Path does not exist: {path}",
            )

        # Validate it's a directory
        if not path.is_dir():
            return ToolResult(
                success=False,
                error=f"Not a directory: {path}",
            )

        # Emit project changed event for app to handle
        await self.event_bus.emit(
            AgentEvent(
                event_type=AgentEventType.PROJECT_CHANGED,
                source_id="main",
                data={
                    "path": str(path),
                    "name": path.name,
                    "message": f"Switching to project: {path.name}",
                },
            )
        )

        return ToolResult(
            success=True,
            data=f"Switched to project: {path.name} ({path})",
            summary=f"Opened {path.name}",
            metadata={"path": str(path), "name": path.name},
        )
