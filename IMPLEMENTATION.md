# Tool Calling Implementation for Cliide

## Overview

This document describes the tool calling system implemented for Cliide, enabling the AI to interact with the filesystem, search code, analyze files, and follow coding rules.

## Implementation Status

✅ **Phase 1: Complete** - Core infrastructure and tools
✅ **Phase 2: Complete** - VLLM client integration and agent loop
✅ **Phase 3: Complete** - UI integration and display
⚠️ **Phase 4: Partial** - App integration (needs wiring in app.py)
🔜 **Phase 5: Pending** - Testing and MCP migration path

## Architecture

### Hybrid Approach

The implementation uses **OpenAI Function Calling** format for immediate compatibility with VLLM, with a design that allows future migration to **Model Context Protocol (MCP)**.

### Components

```
cliide/ai/tools/
├── base.py           # Tool base class, ToolResult, ToolRegistry
├── filesystem.py     # File operations (read, write, list, create, mkdir)
├── search.py         # Code search (find files, grep, find symbols)
├── analysis.py       # Code analysis (extract symbols, file summary)
├── rules.py          # Coding rules (apply/list rules)
└── safety.py         # Path validation and sandboxing

cliide/ai/
└── agent.py          # ToolAgent - main agent loop

cliide/ui/
└── tool_confirm.py   # Confirmation dialog widget

cliide/utils/
└── audit_log.py      # Tool execution audit logging

cliide/core/
├── config.py         # Added ToolsConfig section
└── events.py         # Added tool execution events
```

## Available Tools

### Filesystem Tools
- **read_file** - Read file contents with optional line range
- **write_file** - Write content to file (requires confirmation)
- **list_directory** - List directory contents with optional pattern filter
- **create_file** - Create new file (requires confirmation)
- **mkdir** - Create directory (requires confirmation)

### Search Tools
- **search_files** - Find files by glob pattern
- **grep** - Search file contents with regex
- **find_symbol** - Find class/function definitions by name

### Analysis Tools
- **extract_symbols** - Extract classes/functions from source file (uses tree-sitter for Python)
- **get_file_summary** - Get file stats, imports, and structure

### Rules Tools
- **follow_rule** - Analyze code against coding standards
- **list_rules** - List available built-in coding rules

### Built-in Coding Rules

- **python_pep8** - PEP 8 style guide
- **python_typing** - Type hints
- **python_docstrings** - Google-style docstrings
- **javascript_es6** - ES6+ standards
- **consistent_naming** - Naming conventions
- **no_magic_numbers** - Replace magic numbers with constants
- **error_handling** - Proper error handling
- **dry** - Don't Repeat Yourself principle
- **single_responsibility** - Single Responsibility Principle

## Configuration

### Tools Configuration (`config.toml`)

```toml
[tools]
enabled = true
confirmation_mode = "dangerous"  # Options: "auto", "all", "dangerous"
timeout_seconds = 30
max_file_size_mb = 10.0
workspace_only = true
audit_log_enabled = true
```

### Confirmation Modes

- **auto** - No confirmation, AI calls tools automatically
- **dangerous** - Confirm only write/delete operations (DEFAULT)
- **all** - Confirm every tool call

## Safety & Sandboxing

### Path Validation

- All file operations restricted to workspace directory by default
- Blocks access to sensitive directories (`/etc`, `/root`, `~/.ssh`, etc.)
- Blocks sensitive files (`.env`, `*.key`, `*.pem`, credentials, etc.)
- Prevents directory traversal attacks (`../`, symlinks)

### Resource Limits

- Configurable file size limits (default 10MB)
- Timeout for all tool operations (default 30s)
- Binary file detection and blocking for text operations

### Audit Logging

All tool executions are logged to `~/.config/cliide/audit.log`:

```
[2025-01-15 10:30:45] read_file(path='main.py') - APPROVED - SUCCESS
[2025-01-15 10:31:12] write_file(path='test.py', content='...') - APPROVED - SUCCESS
[2025-01-15 10:31:45] grep(pattern='TODO') - APPROVED - SUCCESS
```

## Agent Loop

### Flow

1. **User sends message** → Chat panel processes
2. **AI response requested** → ToolAgent.run() called
3. **AI may return tool_calls** in response
4. **For each tool call:**
   - Check if confirmation needed (based on confirmation_mode)
   - Execute tool with timeout
   - Log execution to audit log
   - Add results to conversation
5. **Send tool results back to AI** for final response
6. **Iterate** up to max_iterations (default: 5)

### Events Flow

```
User Message
    ↓
AIRequestStarted (chat.py)
    ↓
ToolAgent.run() (agent.py)
    ↓
ToolExecutionStarted (events)  →  ChatPanel displays "🔧 Executing..."
    ↓
Tool.execute()
    ↓
ToolExecutionCompleted (events)  →  ChatPanel updates with result
    ↓
AI processes results
    ↓
Final response to user
```

## UI Integration

### Tool Execution Display

Tool executions appear in the chat as:

```
🔧 read_file(path='main.py') [+]
   ✓ Read 145 lines from main.py
   📍 Lines 1-145

🔧 grep(pattern='TODO') [+]
   ✓ Found 3 matches for 'TODO'
```

- **Green** for success
- **Red** for errors
- **Cyan** for in-progress
- Click to expand/collapse full results
- Line numbers shown when relevant

### Confirmation Dialog

For dangerous operations (write, delete):

```
┌─────────────────────────────────────────────┐
│ 🔒 Tool Confirmation Required               │
│                                             │
│ Tool: write_file                            │
│ Execute write_file                          │
│                                             │
│ Arguments:                                  │
│ ┌─────────────────────────────────────────┐ │
│ │ path: test.py                           │ │
│ │ content: def test():\n    pass          │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ⚠️  This tool will make changes to your    │
│     system. Please review carefully.       │
│                                             │
│     [Approve (Y)]  [Deny (N)]              │
└─────────────────────────────────────────────┘
```

## Usage Examples

### Example 1: File Operations

**User**: "What Python files are in the current directory?"

**AI**:
```
🔧 list_directory(path=".", pattern="*.py")
   ✓ Listed 5 entries in .

Found 5 Python files:
- main.py
- config.py
- utils.py
- test_main.py
- setup.py
```

### Example 2: Code Search

**User**: "Find all TODO comments in the codebase"

**AI**:
```
🔧 grep(pattern="TODO", file_pattern="**/*.py")
   ✓ Found 12 matches for 'TODO'

Found TODO comments in:
- src/main.py:45: # TODO: Implement error handling
- src/utils.py:23: # TODO: Add type hints
- tests/test_main.py:67: # TODO: Add more test cases
```

### Example 3: Code Analysis

**User**: "What classes and functions are defined in main.py?"

**AI**:
```
🔧 extract_symbols(path="main.py")
   ✓ Found 8 symbols in main.py

🔷 App (line 15)
  🔸 __init__ (line 17) (in App)
  🔸 run (line 25) (in App)
🔹 main (line 45)
🔹 setup_logging (line 52)
```

### Example 4: Applying Coding Rules

**User**: "Check main.py against PEP 8"

**AI**:
```
🔧 follow_rule(rule="python_pep8", path="main.py")
   ✓ Analyzing main.py for rule: Python PEP 8 Style Guide

Analysis of main.py:

Issues found:
1. Line 23: Function name 'MyFunction' should be snake_case
2. Line 45: Line too long (95 characters, max 79)
3. Line 67: Missing space after comma in parameter list

Suggestions:
- Rename 'MyFunction' to 'my_function'
- Break long line into multiple lines
- Add space after commas
```

## Integration Points (TODO)

### code_actions.py

Update the `chat()` method to optionally use `ToolAgent`:

```python
async def chat(self, user_message: str, ..., use_tools: bool = True):
    if use_tools and config.tools.enabled:
        # Use ToolAgent
        agent = create_tool_agent(self.client, workspace_root, confirmation_callback)
        async for event in agent.chat(user_message, conversation_history):
            # Handle events
            if event["type"] == "tool_start":
                # Post ToolExecutionStarted event
            elif event["type"] == "tool_result":
                # Post ToolExecutionCompleted event
            elif event["type"] == "text":
                # Stream text chunks
    else:
        # Original streaming implementation
```

### app.py

Wire up tool confirmation flow:

```python
def on_tool_confirmation_required(self, event: ToolConfirmationRequired):
    """Show confirmation dialog for tool execution."""
    dialog = ToolConfirmationDialog(event.tool_name, event.args)

    def on_result(approved: bool):
        event.callback(approved)

    self.push_screen(dialog, on_result)
```

## Testing

### Unit Tests (TODO)

```python
# tests/ai/test_tools.py
async def test_read_file_tool():
    tool = ReadFileTool(workspace_root)
    result = await tool.execute({"path": "test.txt"})
    assert result.success
    assert "test content" in result.data

async def test_path_validation():
    is_valid, error, path = validate_path("../etc/passwd", workspace_root)
    assert not is_valid
    assert "outside workspace" in error
```

### Integration Tests (TODO)

1. Test agent loop with mock AI responses
2. Test tool confirmation flow
3. Test UI updates for tool executions
4. Test audit logging

## Future: MCP Migration Path

The architecture is designed to support MCP:

### Phase 5.1: MCP Abstraction

```python
class Tool(ABC):
    def to_openai_function(self) -> dict:
        # Current implementation

    def to_mcp_tool(self) -> dict:
        # NEW: Convert to MCP format
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters
        }
```

### Phase 5.2: MCP Server

```python
# cliide/ai/mcp_server.py
class CliideMCPServer:
    """Expose Cliide tools via MCP protocol."""

    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry

    async def handle_tools_list(self):
        return [tool.to_mcp_tool() for tool in self.registry.get_all()]

    async def handle_tool_call(self, name: str, arguments: dict):
        result = await self.registry.execute_tool(name, arguments)
        return result.to_message()
```

### Phase 5.3: MCP Client Support

- Connect to external MCP servers (databases, APIs, etc.)
- Merge external tools into registry
- UI for managing MCP connections

## Dependencies

All required dependencies already in `pyproject.toml`:

- `textual>=0.50.0` - TUI framework
- `openai>=1.12.0` - OpenAI API (VLLM compatible)
- `tree-sitter>=0.21.0` - Code parsing
- `aiofiles>=23.2.0` - Async file I/O
- `pydantic>=2.6.0` - Configuration

## Troubleshooting

### Tools Not Working

1. Check `config.toml`: `tools.enabled = true`
2. Verify VLLM model supports function calling
3. Check audit log for errors: `~/.config/cliide/audit.log`

### Permission Errors

1. Verify workspace_only setting
2. Check sensitive file patterns in `tools/safety.py`
3. Review audit log for denied operations

### Timeout Errors

1. Increase `tools.timeout_seconds` in config
2. Check network connectivity for remote operations
3. Reduce `max_file_size_mb` for large files

## Performance Considerations

- Binary file detection prevents wasted parsing
- File size limits prevent memory issues
- Timeouts prevent hanging operations
- Lazy tool registration for faster startup
- Audit logging runs asynchronously

## Security Considerations

✅ Path traversal protection
✅ Sensitive file blocking
✅ Workspace sandboxing
✅ User confirmation for dangerous ops
✅ Audit logging for accountability
✅ Resource limits (size, timeout)
⚠️ Command execution NOT implemented (intentional - too dangerous)

## Next Steps

1. ✅ Core tool system implemented
2. ✅ VLLM client tool support added
3. ✅ UI display for tool executions
4. ⏭️ Wire up confirmation dialog in app.py
5. ⏭️ Update code_actions.py to use ToolAgent
6. ⏭️ Write unit tests
7. ⏭️ End-to-end testing
8. ⏭️ Add more tools as needed
9. ⏭️ MCP migration (future)

## Conclusion

The tool calling system provides a robust, safe, and extensible foundation for AI-powered file operations and code analysis in Cliide. The hybrid approach ensures immediate usability with VLLM while maintaining a clear path to MCP adoption in the future.
