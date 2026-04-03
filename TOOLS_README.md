# Cliide AI Tool Calling System

## Quick Start

### 1. Enable Tools

Add to your `~/.config/cliide/config.toml`:

```toml
[tools]
enabled = true
confirmation_mode = "dangerous"  # Confirm writes/deletes only
```

### 2. Chat with AI

The AI can now:
- Read and write files
- Search code with grep
- Find symbols (classes/functions)
- Analyze code structure
- Apply coding rules

### 3. Example Interactions

**"What Python files are here?"**
```
🔧 list_directory(path=".", pattern="*.py")
   ✓ Listed 5 entries in .

📄 main.py
📄 config.py
📄 utils.py
```

**"Find all TODOs in the code"**
```
🔧 grep(pattern="TODO")
   ✓ Found 3 matches for 'TODO'

📄 main.py:45: # TODO: Add error handling
📄 utils.py:23: # TODO: Add type hints
```

**"Read lines 10-20 from main.py"**
```
🔧 read_file(path="main.py", start_line=10, end_line=20)
   ✓ Read 11 lines (10-20) from main.py
   📍 Lines 10-20
```

**"What classes are in main.py?"**
```
🔧 extract_symbols(path="main.py")
   ✓ Found 3 symbols in main.py

🔷 App (line 15)
  🔸 __init__ (line 17)
  🔸 run (line 25)
```

## Available Tools

### File Operations
- `read_file` - Read file with optional line range
- `write_file` - Write to file (needs confirmation)
- `create_file` - Create new file (needs confirmation)
- `list_directory` - List files/directories
- `mkdir` - Create directory (needs confirmation)

### Code Search
- `search_files` - Find files by pattern (*.py, etc.)
- `grep` - Search file contents with regex
- `find_symbol` - Find class/function definitions

### Code Analysis
- `extract_symbols` - Get classes/functions from file
- `get_file_summary` - File stats, imports, structure

### Coding Rules
- `follow_rule` - Check code against standards
- `list_rules` - Show available coding rules

## Built-in Coding Rules

- `python_pep8` - PEP 8 style guide
- `python_typing` - Type hints
- `python_docstrings` - Docstrings
- `javascript_es6` - ES6+ standards
- `consistent_naming` - Naming conventions
- `no_magic_numbers` - No magic numbers
- `error_handling` - Error handling
- `dry` - Don't Repeat Yourself
- `single_responsibility` - Single Responsibility

Example:
```
User: "Check main.py for PEP 8 issues"

AI:
🔧 follow_rule(rule="python_pep8", path="main.py")
   ✓ Analyzing main.py for PEP 8

Issues:
- Line 23: Use snake_case for function names
- Line 45: Line too long (95 chars, max 79)
```

## Safety Features

✅ **Workspace Sandboxing** - Operations restricted to workspace directory
✅ **Sensitive File Blocking** - Blocks `.env`, `*.key`, credentials, etc.
✅ **User Confirmation** - Confirms writes/deletes/dangerous operations
✅ **Audit Logging** - All operations logged to `~/.config/cliide/audit.log`
✅ **Resource Limits** - File size limits, timeouts
✅ **Binary File Detection** - Skips binary files automatically

## Configuration Options

```toml
[tools]
# Enable/disable tool system
enabled = true

# Confirmation mode:
# - "auto" = no confirmation (AI decides)
# - "dangerous" = confirm writes/deletes only (RECOMMENDED)
# - "all" = confirm everything
confirmation_mode = "dangerous"

# Operation timeout (seconds)
timeout_seconds = 30

# Max file size for read/write (MB)
max_file_size_mb = 10.0

# Restrict to workspace only
workspace_only = true

# Enable audit logging
audit_log_enabled = true
```

## Security

### Blocked Paths
- `/etc`, `/root`, `/sys`, `/proc`, `/dev`
- `~/.ssh`, `~/.gnupg`, `~/.aws`

### Blocked Files
- `.env`, `.env.*`
- `*.key`, `*.pem`, `*.p12`
- `*_rsa`, `*_dsa`, `credentials.json`
- SSH keys, GPG keys, AWS credentials

### Path Traversal Protection
- `../` blocked
- Symlinks resolved and validated
- All paths normalized to absolute

## Audit Log

Location: `~/.config/cliide/audit.log`

Format:
```
[2025-01-15 10:30:45] read_file(path='main.py') - APPROVED - SUCCESS
[2025-01-15 10:31:12] write_file(path='test.py', ...) - APPROVED - SUCCESS
[2025-01-15 10:31:45] grep(pattern='TODO') - APPROVED - SUCCESS
```

## Troubleshooting

### Tools Not Working

1. Check config: `tools.enabled = true`
2. Verify VLLM model supports function calling
3. Check audit log for errors

### Permission Denied

1. File outside workspace? Set `workspace_only = false` (not recommended)
2. Sensitive file? Check patterns in `cliide/ai/tools/safety.py`
3. Check audit log for details

### Timeout Errors

1. Increase `timeout_seconds` in config
2. Reduce `max_file_size_mb` for large files
3. Check network/disk performance

## Advanced Usage

### Custom Rules

You can pass custom coding rules:

```
User: "Check if all functions have type hints"

AI:
🔧 follow_rule(rule="All functions must have type hints", path="main.py")
```

### Complex Searches

```
User: "Find all class definitions that inherit from BaseModel"

AI:
🔧 grep(pattern="class \\w+\\(.*BaseModel.*\\)", file_pattern="**/*.py")
```

### Line-Range Reading

```
User: "Show me the handle_request function implementation"

AI:
🔧 find_symbol(symbol_name="handle_request")
   → Found at main.py:145

🔧 read_file(path="main.py", start_line=145, end_line=175)
```

## Future Features (MCP Migration)

The system is designed to support Model Context Protocol (MCP):

- Connect to external MCP servers
- Share tools across different AI systems
- Standard protocol for tool communication
- Community ecosystem of tools

## API Reference

See `IMPLEMENTATION.md` for detailed technical documentation.

## Examples

See `examples/` directory for:
- Code review workflows
- Refactoring examples
- Rule enforcement
- Automated code generation

## Support

- GitHub Issues: https://github.com/anthropics/cliide/issues
- Documentation: See `IMPLEMENTATION.md`
- Config Example: See `config.example.toml`

---

**Note**: Tool calling requires a VLLM model that supports OpenAI function calling format. Most modern instruction-tuned models support this.
