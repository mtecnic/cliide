"""Filesystem operation tools."""

import aiofiles
import os
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult, ToolCategory, RiskLevel, CODE_FILE_EXTENSIONS, CONFIG_FILE_PATTERNS
from .safety import validate_path, validate_file_size, is_binary_file
from cliide.ai.token_counter import get_token_counter


class ReadFileTool(Tool):
    """Tool for reading file contents with smart token-aware truncation."""

    def __init__(
        self,
        workspace_root: str | Path,
        max_file_size_mb: float = 10.0,
        max_context_tokens: int = 8000,
    ):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
            max_file_size_mb: Maximum file size in MB
            max_context_tokens: Maximum tokens for file content in context
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)
        self.max_file_size_mb = max_file_size_mb
        self.max_context_tokens = max_context_tokens
        self.token_counter = get_token_counter()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Can optionally read a specific line range."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to workspace or absolute)"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: Starting line number (1-indexed). If provided, only read from this line."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional: Ending line number (1-indexed, inclusive). If provided with start_line, read only this range."
                },
                "focus": {
                    "type": "string",
                    "description": "Optional: Search term to focus on specific sections. If the file is too large, only sections containing this term (with context) will be returned."
                }
            },
            "required": ["path"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute file read with smart token-aware truncation."""
        path = args["path"]
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        focus = args.get("focus")

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check if file exists
        if not normalized_path.exists():
            return ToolResult(success=False, error=f"File does not exist: {path}")

        if not normalized_path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        # Check file size
        is_valid, error = validate_file_size(normalized_path, self.max_file_size_mb)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check if binary
        if is_binary_file(normalized_path):
            return ToolResult(
                success=False,
                error=f"Cannot read binary file: {path}"
            )

        try:
            # Read file
            async with aiofiles.open(normalized_path, 'r', encoding='utf-8', errors='replace') as f:
                content = await f.read()

            # Handle line range if specified (takes priority over token limits)
            if start_line is not None or end_line is not None:
                lines = content.splitlines()
                total_lines = len(lines)

                # Convert to 0-indexed
                start_idx = (start_line - 1) if start_line is not None else 0
                end_idx = end_line if end_line is not None else total_lines

                # Validate range
                if start_idx < 0 or start_idx >= total_lines:
                    return ToolResult(
                        success=False,
                        error=f"Invalid start_line: {start_line} (file has {total_lines} lines)"
                    )

                if end_idx < start_idx or end_idx > total_lines:
                    return ToolResult(
                        success=False,
                        error=f"Invalid end_line: {end_line} (must be >= start_line and <= {total_lines})"
                    )

                # Extract range
                selected_lines = lines[start_idx:end_idx]
                content = "\n".join(selected_lines)

                summary = f"Read {len(selected_lines)} lines ({start_line}-{end_line}) from {normalized_path.name}"
                return ToolResult(
                    success=True,
                    data=content,
                    summary=summary,
                    metadata={
                        "path": str(normalized_path),
                        "start_line": start_line,
                        "end_line": end_line,
                        "line_count": len(selected_lines)
                    }
                )

            # Check token count for context management
            token_count = self.token_counter.count(content)
            line_count = len(content.splitlines())

            # If within budget, return full content
            if token_count <= self.max_context_tokens:
                return ToolResult(
                    success=True,
                    data=content,
                    summary=f"Read {line_count} lines ({token_count} tokens) from {normalized_path.name}",
                    metadata={
                        "path": str(normalized_path),
                        "line_count": line_count,
                        "token_count": token_count
                    }
                )

            # File is too large - try smart extraction
            if focus:
                # Search for relevant sections
                relevant = self._extract_relevant_sections(content, focus)
                relevant_tokens = self.token_counter.count(relevant)

                return ToolResult(
                    success=True,
                    data=relevant,
                    summary=f"Extracted {relevant_tokens} tokens focused on '{focus}' from {normalized_path.name} ({token_count} total tokens)",
                    metadata={
                        "path": str(normalized_path),
                        "line_count": line_count,
                        "token_count": token_count,
                        "extracted_tokens": relevant_tokens,
                        "focus": focus,
                        "truncated": True
                    }
                )

            # No focus - return summary + truncated content
            file_summary = self._get_file_summary(content, normalized_path.name)
            summary_tokens = self.token_counter.count(file_summary)

            # Allocate remaining budget to content
            content_budget = self.max_context_tokens - summary_tokens - 100  # Reserve some tokens
            truncated = self.token_counter.truncate_to_tokens(content, content_budget)

            result_data = f"{file_summary}\n\n[CONTENT TRUNCATED - {token_count} tokens total, showing first {content_budget}]\n\n{truncated}"

            return ToolResult(
                success=True,
                data=result_data,
                summary=f"File too large ({token_count} tokens), showing summary + first {content_budget} tokens from {normalized_path.name}",
                metadata={
                    "path": str(normalized_path),
                    "line_count": line_count,
                    "token_count": token_count,
                    "truncated": True,
                    "truncated_tokens": content_budget
                }
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"File encoding error: {path} (not valid UTF-8)"
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read file: {e}")

    def _extract_relevant_sections(
        self,
        content: str,
        query: str,
        context_lines: int = 5,
    ) -> str:
        """Extract sections relevant to search query.

        Args:
            content: Full file content
            query: Search term to find
            context_lines: Number of lines to include before/after matches

        Returns:
            Extracted sections with context
        """
        lines = content.split('\n')
        query_lower = query.lower()

        # Find matching lines
        matches: list[tuple[int, int, int]] = []  # (start, end, match_line)
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Include context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                matches.append((start, end, i))

        if not matches:
            # No matches found - return first portion with a note
            truncated = self.token_counter.truncate_to_tokens(
                content,
                self.max_context_tokens
            )
            return f"[No matches for '{query}' - showing beginning of file]\n\n{truncated}"

        # Merge overlapping ranges
        merged: list[tuple[int, int]] = []
        for start, end, _ in sorted(matches):
            if merged and start <= merged[-1][1]:
                # Overlaps with previous - extend
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Build result with context
        result_parts: list[str] = []
        for start, end in merged:
            section_lines = []
            for i in range(start, end):
                # Add line number prefix
                section_lines.append(f"{i + 1:4d}: {lines[i]}")

            section = '\n'.join(section_lines)
            result_parts.append(f"[Lines {start + 1}-{end}]\n{section}")

            # Check token budget
            current = '\n\n---\n\n'.join(result_parts)
            if self.token_counter.count(current) > self.max_context_tokens:
                result_parts.pop()
                break

        if not result_parts:
            # Even one section was too large, truncate it
            return self.token_counter.truncate_to_tokens(
                f"[Lines {merged[0][0] + 1}-{merged[0][1]}]\n" +
                '\n'.join(f"{i + 1:4d}: {lines[i]}" for i in range(merged[0][0], merged[0][1])),
                self.max_context_tokens
            )

        return '\n\n---\n\n'.join(result_parts)

    def _get_file_summary(self, content: str, filename: str) -> str:
        """Generate a structural summary of the file.

        Args:
            content: File content
            filename: Name of the file

        Returns:
            Structural summary string
        """
        lines = content.split('\n')
        total_lines = len(lines)

        # Detect file type from filename
        ext = Path(filename).suffix.lower()

        summary_parts = [f"## File: {filename}", f"Total lines: {total_lines}"]

        # For Python files, extract class and function definitions
        if ext == '.py':
            classes = []
            functions = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('class '):
                    # Extract class name
                    match = stripped[6:].split('(')[0].split(':')[0].strip()
                    classes.append(f"  - {match} (line {i + 1})")
                elif stripped.startswith('def ') or stripped.startswith('async def '):
                    # Extract function name
                    prefix = 'async def ' if 'async def ' in stripped else 'def '
                    match = stripped[len(prefix):].split('(')[0].strip()
                    # Skip private methods in class summary
                    if not line.startswith(' ') or not match.startswith('_'):
                        functions.append(f"  - {match}() (line {i + 1})")

            if classes:
                summary_parts.append("\nClasses:")
                summary_parts.extend(classes[:20])  # Limit to 20
                if len(classes) > 20:
                    summary_parts.append(f"  ... and {len(classes) - 20} more")

            if functions:
                summary_parts.append("\nFunctions:")
                summary_parts.extend(functions[:30])  # Limit to 30
                if len(functions) > 30:
                    summary_parts.append(f"  ... and {len(functions) - 30} more")

        # For JS/TS files
        elif ext in ('.js', '.jsx', '.ts', '.tsx'):
            exports = []
            functions = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                if 'export ' in stripped:
                    exports.append(f"  - line {i + 1}: {stripped[:60]}...")
                elif stripped.startswith('function ') or 'const ' in stripped and '=>' in stripped:
                    functions.append(f"  - line {i + 1}")

            if exports:
                summary_parts.append("\nExports (first 15):")
                summary_parts.extend(exports[:15])

        return '\n'.join(summary_parts)


class WriteFileTool(Tool):
    """Tool for writing to files."""

    def __init__(self, workspace_root: str | Path, max_file_size_mb: float = 10.0):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
            max_file_size_mb: Maximum file size in MB
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = True  # Writing requires confirmation
        self._risk_level = RiskLevel.MEDIUM  # Default to MEDIUM
        self.workspace_root = Path(workspace_root)
        self.max_file_size_mb = max_file_size_mb

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to workspace or absolute)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }

    def classify_risk(self, args: dict[str, Any]) -> RiskLevel:
        """Classify risk based on file path.

        Code files (.py, .js, .ts, etc.) = MEDIUM (auto-approve in moderate mode)
        Config files (.env, .json, .toml, etc.) = HIGH (always confirm)
        """
        path_str = args.get("path", "")
        path = Path(path_str)
        suffix = path.suffix.lower()
        name = path.name

        # Check if it's a config file (HIGH risk)
        if suffix in CONFIG_FILE_PATTERNS or name in CONFIG_FILE_PATTERNS:
            return RiskLevel.HIGH

        # Check if it's a code file (MEDIUM risk)
        if suffix in CODE_FILE_EXTENSIONS:
            return RiskLevel.MEDIUM

        # Default to HIGH for unknown file types
        return RiskLevel.HIGH

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute file write."""
        path = args["path"]
        content = args["content"]

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check content size
        content_size_mb = len(content.encode('utf-8')) / (1024 * 1024)
        if content_size_mb > self.max_file_size_mb:
            return ToolResult(
                success=False,
                error=f"Content too large: {content_size_mb:.1f}MB (max: {self.max_file_size_mb}MB)"
            )

        try:
            # Create parent directories if needed
            normalized_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            async with aiofiles.open(normalized_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            line_count = len(content.splitlines())
            file_existed = normalized_path.exists()
            action = "Updated" if file_existed else "Created"

            return ToolResult(
                success=True,
                data=str(normalized_path),
                summary=f"{action} {normalized_path.name} ({line_count} lines)",
                metadata={
                    "path": str(normalized_path),
                    "line_count": line_count,
                    "action": action.lower()
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to write file: {e}")


class ListDirectoryTool(Tool):
    """Tool for listing directory contents."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List contents of a directory. Returns files and subdirectories."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list (relative to workspace or absolute). Use '.' for current directory."
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional: Filter pattern (e.g., '*.py' for Python files, '*test*' for files with 'test' in name)"
                }
            },
            "required": ["path"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute directory listing."""
        path = args["path"]
        pattern = args.get("pattern", "*")

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check if directory exists
        if not normalized_path.exists():
            return ToolResult(success=False, error=f"Directory does not exist: {path}")

        if not normalized_path.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")

        try:
            # List entries
            entries = []
            for entry in sorted(normalized_path.glob(pattern)):
                entry_type = "dir" if entry.is_dir() else "file"
                size = entry.stat().st_size if entry.is_file() else 0
                entries.append({
                    "name": entry.name,
                    "type": entry_type,
                    "size": size,
                    "path": str(entry.relative_to(self.workspace_root))
                })

            # Format output
            if not entries:
                content = f"No entries found in {normalized_path.name}"
            else:
                lines = []
                for entry in entries:
                    marker = "📁" if entry["type"] == "dir" else "📄"
                    size_str = f" ({entry['size']} bytes)" if entry["type"] == "file" else ""
                    lines.append(f"{marker} {entry['name']}{size_str}")
                content = "\n".join(lines)

            summary = f"Listed {len(entries)} entries in {normalized_path.name}"
            if pattern != "*":
                summary += f" (pattern: {pattern})"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "path": str(normalized_path),
                    "count": len(entries),
                    "entries": entries
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list directory: {e}")


class CreateFileTool(Tool):
    """Tool for creating new files."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = True
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return "Create a new empty file. Fails if file already exists."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to create (relative to workspace or absolute)"
                },
                "content": {
                    "type": "string",
                    "description": "Optional: Initial content for the file (default: empty)"
                }
            },
            "required": ["path"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute file creation."""
        path = args["path"]
        content = args.get("content", "")

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check if file already exists
        if normalized_path.exists():
            return ToolResult(
                success=False,
                error=f"File already exists: {path} (use write_file to overwrite)"
            )

        try:
            # Create parent directories if needed
            normalized_path.parent.mkdir(parents=True, exist_ok=True)

            # Create file
            async with aiofiles.open(normalized_path, 'w', encoding='utf-8') as f:
                await f.write(content)

            line_count = len(content.splitlines()) if content else 0

            return ToolResult(
                success=True,
                data=str(normalized_path),
                summary=f"Created {normalized_path.name}" + (f" ({line_count} lines)" if content else ""),
                metadata={
                    "path": str(normalized_path),
                    "line_count": line_count
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create file: {e}")


class MkdirTool(Tool):
    """Tool for creating directories."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = True
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "mkdir"

    @property
    def description(self) -> str:
        return "Create a new directory. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to create (relative to workspace or absolute)"
                }
            },
            "required": ["path"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute directory creation."""
        path = args["path"]

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        # Check if already exists
        if normalized_path.exists():
            if normalized_path.is_dir():
                return ToolResult(
                    success=True,
                    data=str(normalized_path),
                    summary=f"Directory already exists: {normalized_path.name}",
                    metadata={"path": str(normalized_path), "existed": True}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Path exists but is not a directory: {path}"
                )

        try:
            # Create directory and parents
            normalized_path.mkdir(parents=True, exist_ok=True)

            return ToolResult(
                success=True,
                data=str(normalized_path),
                summary=f"Created directory: {normalized_path.name}",
                metadata={"path": str(normalized_path), "existed": False}
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create directory: {e}")


class BatchWriteTool(Tool):
    """Tool for writing multiple files atomically."""

    def __init__(self, workspace_root: str | Path, max_file_size_mb: float = 10.0):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
            max_file_size_mb: Maximum file size in MB per file
        """
        super().__init__()
        self._category = ToolCategory.FILESYSTEM
        self._requires_confirmation = True
        self._risk_level = RiskLevel.HIGH  # Multi-file edits are high risk
        self.workspace_root = Path(workspace_root)
        self.max_file_size_mb = max_file_size_mb

    @property
    def name(self) -> str:
        return "batch_write"

    @property
    def description(self) -> str:
        return """Write multiple files in a single atomic operation.
Use this for coordinated changes across multiple files (e.g., refactoring).
All files are validated before any writes occur. If any validation fails, no files are written."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "description": "List of file operations to perform",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the file (relative to workspace or absolute)"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write to the file"
                            },
                            "action": {
                                "type": "string",
                                "enum": ["write", "create", "append"],
                                "description": "Action: 'write' (overwrite), 'create' (fail if exists), 'append' (add to end)"
                            }
                        },
                        "required": ["path", "content"]
                    }
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, validate but don't write (default: false)"
                }
            },
            "required": ["files"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute batch file write."""
        files = args.get("files", [])
        dry_run = args.get("dry_run", False)

        if not files:
            return ToolResult(success=False, error="No files specified")

        if len(files) > 20:
            return ToolResult(success=False, error="Too many files (max 20 per batch)")

        # Phase 1: Validate all files
        validated_files = []
        errors = []

        for i, file_op in enumerate(files):
            path = file_op.get("path", "")
            content = file_op.get("content", "")
            action = file_op.get("action", "write")

            # Validate path
            is_valid, error, normalized_path = validate_path(path, self.workspace_root)
            if not is_valid:
                errors.append(f"[{i}] {path}: {error}")
                continue

            # Check content size
            content_size_mb = len(content.encode('utf-8')) / (1024 * 1024)
            if content_size_mb > self.max_file_size_mb:
                errors.append(f"[{i}] {path}: Content too large ({content_size_mb:.1f}MB)")
                continue

            # Check action-specific conditions
            if action == "create" and normalized_path.exists():
                errors.append(f"[{i}] {path}: File already exists (action='create')")
                continue

            if action == "append" and normalized_path.exists() and not normalized_path.is_file():
                errors.append(f"[{i}] {path}: Not a file (cannot append)")
                continue

            validated_files.append({
                "path": normalized_path,
                "content": content,
                "action": action,
                "original_path": path,
            })

        if errors:
            return ToolResult(
                success=False,
                error=f"Validation failed for {len(errors)} file(s):\n" + "\n".join(errors)
            )

        if dry_run:
            return ToolResult(
                success=True,
                data=f"Dry run: {len(validated_files)} files validated successfully",
                summary=f"Dry run passed for {len(validated_files)} files",
                metadata={
                    "files": [str(f["path"]) for f in validated_files],
                    "dry_run": True
                }
            )

        # Phase 2: Write all files
        written = []
        write_errors = []

        for file_op in validated_files:
            normalized_path = file_op["path"]
            content = file_op["content"]
            action = file_op["action"]

            try:
                # Create parent directories if needed
                normalized_path.parent.mkdir(parents=True, exist_ok=True)

                # Determine write mode
                if action == "append":
                    mode = 'a'
                else:
                    mode = 'w'

                # Write file
                async with aiofiles.open(normalized_path, mode, encoding='utf-8') as f:
                    await f.write(content)

                written.append({
                    "path": str(normalized_path),
                    "action": action,
                    "lines": len(content.splitlines())
                })

            except Exception as e:
                write_errors.append(f"{file_op['original_path']}: {e}")

        if write_errors:
            # Some writes failed - report partial success
            return ToolResult(
                success=False,
                error=f"Partial failure: {len(write_errors)} file(s) failed:\n" + "\n".join(write_errors),
                data=f"Successfully wrote {len(written)} file(s)",
                metadata={"written": written, "errors": write_errors}
            )

        # Build summary
        summary_lines = []
        for w in written:
            action_word = {"write": "Updated", "create": "Created", "append": "Appended to"}.get(w["action"], "Wrote")
            summary_lines.append(f"{action_word} {Path(w['path']).name} ({w['lines']} lines)")

        return ToolResult(
            success=True,
            data="\n".join(summary_lines),
            summary=f"Batch write: {len(written)} files updated",
            metadata={"written": written}
        )
