"""Custom themes for cliide."""

from textual.theme import Theme

# Custom cliide theme with modern, professional colors
CLIIDE_THEME = Theme(
    name="cliide",
    # Primary palette
    primary="#5ccfe6",  # Cyan blue - primary actions, selections
    secondary="#bae67e",  # Lime green - secondary elements
    accent="#ffd580",  # Warm gold - highlights, accents

    # Status colors
    warning="#ffae57",  # Orange - warnings
    error="#ff6b6b",  # Coral red - errors
    success="#73d0ff",  # Light blue - success states

    # Background layers (from dark to light)
    background="#0d1117",  # Deep dark - main background
    surface="#161b22",  # Slightly lighter - panels
    panel="#21262d",  # Panel backgrounds
    boost="#30363d",  # Hover/focus states

    # Enable dark mode
    dark=True,
)

# Additional semantic color definitions for use in CSS
# These can be used in widgets with inline CSS
SEMANTIC_COLORS = {
    # Diagnostic colors
    "error_bg": "#2d1f1f",  # Subtle red background for error lines
    "error_border": "#ff6b6b",
    "warning_bg": "#2d2a1f",  # Subtle yellow background for warning lines
    "warning_border": "#ffae57",
    "info_bg": "#1f2937",  # Subtle blue background for info
    "info_border": "#5ccfe6",
    "hint_bg": "#1f2d27",  # Subtle green background for hints
    "hint_border": "#bae67e",

    # Tool execution colors
    "tool_pending": "#ffae57",  # Orange for pending
    "tool_running": "#5ccfe6",  # Cyan for running
    "tool_success": "#73d0ff",  # Light blue for success
    "tool_error": "#ff6b6b",  # Red for error

    # Git status colors
    "git_added": "#bae67e",  # Green for added
    "git_modified": "#ffd580",  # Gold for modified
    "git_deleted": "#ff6b6b",  # Red for deleted
    "git_renamed": "#5ccfe6",  # Cyan for renamed

    # Syntax highlighting enhancements
    "comment": "#6e7681",  # Muted gray for comments
    "string": "#a5d6ff",  # Light blue for strings
    "keyword": "#ff7b72",  # Coral for keywords
    "function": "#d2a8ff",  # Light purple for functions
    "variable": "#79c0ff",  # Blue for variables
    "number": "#ffa657",  # Orange for numbers
    "type": "#7ee787",  # Green for types
}
