"""Base classes and infrastructure for the tool system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from enum import Enum

from cliide.core.agent_mode import AgentMode, get_agent_mode, is_tool_allowed_in_mode


class ToolCategory(str, Enum):
    """Categories of tools for organization."""
    FILESYSTEM = "filesystem"
    SEARCH = "search"
    ANALYSIS = "analysis"
    RULES = "rules"
    COMMAND = "command"
    AGENT = "agent"
    OTHER = "other"


class RiskLevel(str, Enum):
    """Risk level for tool operations.

    LOW: Read-only operations that don't modify anything
    MEDIUM: Write operations to code files
    HIGH: Potentially dangerous operations (shell, git commit, config files)
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SubAgentTrustLevel(str, Enum):
    """Trust levels for sub-agents.

    READ_ONLY: Can only read, never needs approval for reads but cannot write
    WRITE_SAFE: Can write code files, main agent approves medium risk
    WRITE_ALL: Can write any file, user approves high risk
    FULL: Same permissions as main agent
    """
    READ_ONLY = "read_only"
    WRITE_SAFE = "write_safe"
    WRITE_ALL = "write_all"
    FULL = "full"


# Approval routing matrix for sub-agents
# Maps (trust_level, risk_level) -> approval target
# "auto" = automatic approval, "main_agent" = main agent decides, "user" = user decides, "denied" = not allowed
SUBAGENT_APPROVAL_MATRIX: dict[tuple[SubAgentTrustLevel, RiskLevel], str] = {
    # READ_ONLY: Can only do low-risk operations
    (SubAgentTrustLevel.READ_ONLY, RiskLevel.LOW): "auto",
    (SubAgentTrustLevel.READ_ONLY, RiskLevel.MEDIUM): "denied",
    (SubAgentTrustLevel.READ_ONLY, RiskLevel.HIGH): "denied",

    # WRITE_SAFE: Auto for low, main agent for medium, user for high
    (SubAgentTrustLevel.WRITE_SAFE, RiskLevel.LOW): "auto",
    (SubAgentTrustLevel.WRITE_SAFE, RiskLevel.MEDIUM): "main_agent",
    (SubAgentTrustLevel.WRITE_SAFE, RiskLevel.HIGH): "user",

    # WRITE_ALL: Same as WRITE_SAFE
    (SubAgentTrustLevel.WRITE_ALL, RiskLevel.LOW): "auto",
    (SubAgentTrustLevel.WRITE_ALL, RiskLevel.MEDIUM): "main_agent",
    (SubAgentTrustLevel.WRITE_ALL, RiskLevel.HIGH): "user",

    # FULL: Auto for low/medium, user for high
    (SubAgentTrustLevel.FULL, RiskLevel.LOW): "auto",
    (SubAgentTrustLevel.FULL, RiskLevel.MEDIUM): "auto",
    (SubAgentTrustLevel.FULL, RiskLevel.HIGH): "user",
}


def get_approval_target(trust_level: SubAgentTrustLevel, risk_level: RiskLevel) -> str:
    """Get the approval target for a sub-agent operation.

    Args:
        trust_level: Trust level of the sub-agent
        risk_level: Risk level of the operation

    Returns:
        Approval target: "auto", "main_agent", "user", or "denied"
    """
    return SUBAGENT_APPROVAL_MATRIX.get(
        (trust_level, risk_level),
        "user"  # Default to user approval for unknown combinations
    )


# File extensions considered "code files" for MEDIUM risk auto-approval
CODE_FILE_EXTENSIONS = {
    ".py", ".pyi", ".pyx",  # Python
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",  # JavaScript/TypeScript
    ".rs",  # Rust
    ".go",  # Go
    ".java", ".kt", ".scala",  # JVM
    ".c", ".cpp", ".cc", ".h", ".hpp",  # C/C++
    ".rb",  # Ruby
    ".php",  # PHP
    ".swift",  # Swift
    ".cs",  # C#
    ".lua",  # Lua
    ".sh", ".bash", ".zsh",  # Shell scripts
    ".sql",  # SQL
    ".r", ".R",  # R
    ".md", ".rst", ".txt",  # Documentation
    ".css", ".scss", ".less",  # Styles
    ".html", ".htm", ".vue", ".svelte",  # Templates
}

# File extensions/names that are HIGH risk (config files)
CONFIG_FILE_PATTERNS = {
    ".env", ".env.local", ".env.production",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    "Dockerfile", "docker-compose.yml",
    ".gitignore", ".gitattributes",
    "Makefile", "CMakeLists.txt",
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
}


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any = None
    error: str | None = None
    summary: str = ""  # Human-readable summary for UI display
    metadata: dict[str, Any] = field(default_factory=dict)  # e.g., line numbers, file paths

    def to_message(self) -> str:
        """Convert result to message format for AI."""
        if not self.success:
            return f"Error: {self.error}"

        # Return actual data content, not just summary
        # Summary is for UI display; data has the real content AI needs
        if isinstance(self.data, str) and self.data:
            return self.data
        if self.data is not None:
            return str(self.data)
        # Fall back to summary only if no data
        if self.summary:
            return self.summary
        return "Success (no output)"


class Tool(ABC):
    """Base class for all tools available to the AI agent."""

    def __init__(self):
        """Initialize the tool."""
        self._category = ToolCategory.OTHER
        self._requires_confirmation = False
        self._risk_level = RiskLevel.LOW

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters.

        Returns:
            Dictionary with JSON Schema format for OpenAI function calling:
            {
                "type": "object",
                "properties": {
                    "param_name": {
                        "type": "string",
                        "description": "What this parameter does"
                    }
                },
                "required": ["param_name"]
            }
        """
        pass

    @property
    def category(self) -> ToolCategory:
        """Category this tool belongs to."""
        return self._category

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool requires user confirmation before execution."""
        return self._requires_confirmation

    @property
    def risk_level(self) -> RiskLevel:
        """Base risk level for this tool."""
        return self._risk_level

    def classify_risk(self, args: dict[str, Any]) -> RiskLevel:
        """Classify risk level for specific operation with given arguments.

        Override in subclasses for dynamic risk classification based on arguments.

        Args:
            args: Operation arguments

        Returns:
            Risk level for this specific operation
        """
        return self._risk_level

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format.

        Returns:
            Dictionary in OpenAI function format:
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": {...}
                }
            }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def validate(self, args: dict[str, Any]) -> tuple[bool, str]:
        """Validate arguments before execution.

        Args:
            args: Dictionary of arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation - check required parameters
        required = self.parameters.get("required", [])
        for param in required:
            if param not in args:
                return False, f"Missing required parameter: {param}"
        return True, ""

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            args: Dictionary of arguments matching the parameters schema

        Returns:
            ToolResult with execution outcome
        """
        pass

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        """Initialize the registry."""
        self._tools: dict[str, Tool] = {}
        self._confirmation_callback: Callable[[str, dict], Awaitable[bool]] | None = None

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        """Unregister a tool.

        Args:
            tool_name: Name of tool to unregister
        """
        self._tools.pop(tool_name, None)

    def get(self, tool_name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools.

        Returns:
            List of all tool instances
        """
        return list(self._tools.values())

    def get_by_category(self, category: ToolCategory) -> list[Tool]:
        """Get all tools in a category.

        Args:
            category: Category to filter by

        Returns:
            List of tools in the category
        """
        return [tool for tool in self._tools.values() if tool.category == category]

    def to_openai_functions(self, filter_by_mode: bool = True) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function format.

        Args:
            filter_by_mode: If True, only include tools allowed in current agent mode

        Returns:
            List of function definitions for OpenAI API
        """
        mode = get_agent_mode()
        return [
            tool.to_openai_function()
            for tool in self._tools.values()
            if not filter_by_mode or is_tool_allowed_in_mode(tool.name, mode)
        ]

    def set_confirmation_callback(self, callback: Callable[[str, dict], Awaitable[bool]]) -> None:
        """Set callback for tool confirmation.

        Args:
            callback: Async function that takes (tool_name, args) and returns bool
        """
        self._confirmation_callback = callback

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        skip_confirmation: bool = False,
        confirmation_mode: str = "moderate",
        enforce_mode: bool = True,
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool
            skip_confirmation: Skip confirmation even if tool requires it
            confirmation_mode: 'conservative', 'moderate', or 'aggressive'
            enforce_mode: If True, block tools not allowed in current agent mode

        Returns:
            ToolResult from execution
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}"
            )

        # Check agent mode restrictions
        if enforce_mode:
            mode = get_agent_mode()
            if not is_tool_allowed_in_mode(tool_name, mode):
                return ToolResult(
                    success=False,
                    error=f"Tool '{tool_name}' is not allowed in {mode.value.upper()} mode. Switch to ACT mode to use write/execute operations."
                )

        # Validate arguments
        is_valid, error = tool.validate(args)
        if not is_valid:
            return ToolResult(
                success=False,
                error=f"Validation failed: {error}"
            )

        # Determine if confirmation is needed based on risk level and mode
        needs_confirmation = False
        if not skip_confirmation and self._confirmation_callback:
            risk = tool.classify_risk(args)

            if confirmation_mode == "conservative":
                # Confirm all writes and commands
                needs_confirmation = risk in (RiskLevel.MEDIUM, RiskLevel.HIGH)
            elif confirmation_mode == "moderate":
                # Auto-approve LOW and MEDIUM (code writes), confirm HIGH
                needs_confirmation = risk == RiskLevel.HIGH
            elif confirmation_mode == "aggressive":
                # Only confirm HIGH risk (shell commands, git commits)
                needs_confirmation = risk == RiskLevel.HIGH and tool.requires_confirmation
            else:
                # Fallback to legacy behavior
                needs_confirmation = tool.requires_confirmation

        if needs_confirmation:
            confirmed = await self._confirmation_callback(tool_name, args)
            if not confirmed:
                return ToolResult(
                    success=False,
                    error="User denied execution"
                )

        # Execute the tool
        try:
            result = await tool.execute(args)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Execution failed: {str(e)}"
            )

    def __len__(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def __contains__(self, tool_name: str) -> bool:
        """Check if a tool is registered."""
        return tool_name in self._tools


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry.

    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> None:
    """Reset the global tool registry."""
    global _global_registry
    _global_registry = None
