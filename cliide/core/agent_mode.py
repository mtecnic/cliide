"""Agent mode definitions for Plan vs Act mode."""

from enum import Enum


class AgentMode(str, Enum):
    """Agent operating modes.

    PLAN: Read-only mode - agent can only read, search, and analyze
    ACT: Full access mode - agent can edit, write, execute commands
    """
    PLAN = "plan"
    ACT = "act"


# Tools allowed in Plan mode (read-only operations)
PLAN_MODE_ALLOWED_TOOLS = {
    # Filesystem read operations
    "read_file",
    "list_directory",
    "file_info",

    # Search operations
    "search_files",
    "grep",
    "find_symbol",
    "find_definition",
    "find_references",

    # Git read operations
    "git_status",
    "git_diff",
    "git_log",
    "git_show",

    # Memory operations (read-only)
    "recall_memory",
    "memory_summary",

    # Analysis
    "analyze_code",
    "explain_code",
}


def is_tool_allowed_in_mode(tool_name: str, mode: AgentMode) -> bool:
    """Check if a tool is allowed in the given mode.

    Args:
        tool_name: Name of the tool
        mode: Current agent mode

    Returns:
        True if tool is allowed, False otherwise
    """
    if mode == AgentMode.ACT:
        return True
    return tool_name in PLAN_MODE_ALLOWED_TOOLS


# Global agent mode state
_current_mode: AgentMode = AgentMode.ACT


def get_agent_mode() -> AgentMode:
    """Get the current agent mode.

    Returns:
        Current AgentMode
    """
    return _current_mode


def set_agent_mode(mode: AgentMode) -> None:
    """Set the agent mode.

    Args:
        mode: New agent mode
    """
    global _current_mode
    _current_mode = mode


def toggle_agent_mode() -> AgentMode:
    """Toggle between Plan and Act modes.

    Returns:
        New agent mode after toggle
    """
    global _current_mode
    if _current_mode == AgentMode.ACT:
        _current_mode = AgentMode.PLAN
    else:
        _current_mode = AgentMode.ACT
    return _current_mode
