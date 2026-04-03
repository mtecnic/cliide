"""Search and grep tools for code exploration."""

import re
import asyncio
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult, ToolCategory
from .safety import validate_path, is_binary_file


class SearchFilesTool(Tool):
    """Tool for finding files by name or pattern."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.SEARCH
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Find files by name pattern. Supports glob patterns like '*.py', '*test*', 'src/**/*.js'."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '*.py', '**/test_*.py', 'src/**/*.js')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Optional: Maximum number of results to return (default: 100)"
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute file search."""
        pattern = args["pattern"]
        max_results = args.get("max_results", 100)

        try:
            # Use rglob for ** patterns, glob otherwise
            if "**" in pattern:
                matches = list(self.workspace_root.rglob(pattern))
            else:
                matches = list(self.workspace_root.glob(pattern))

            # Filter to only files
            file_matches = [m for m in matches if m.is_file()]

            # Limit results
            if len(file_matches) > max_results:
                file_matches = file_matches[:max_results]
                truncated = True
            else:
                truncated = False

            # Build result
            if not file_matches:
                content = f"No files found matching '{pattern}'"
                summary = f"No matches for '{pattern}'"
            else:
                lines = []
                for match in file_matches:
                    rel_path = match.relative_to(self.workspace_root)
                    lines.append(f"📄 {rel_path}")

                content = "\n".join(lines)
                summary = f"Found {len(file_matches)} file{'s' if len(file_matches) != 1 else ''} matching '{pattern}'"
                if truncated:
                    summary += f" (showing first {max_results})"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "pattern": pattern,
                    "count": len(file_matches),
                    "truncated": truncated,
                    "files": [str(m.relative_to(self.workspace_root)) for m in file_matches]
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {e}")


class GrepTool(Tool):
    """Tool for searching file contents with regex."""

    def __init__(self, workspace_root: str | Path, max_file_size_mb: float = 10.0):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
            max_file_size_mb: Maximum file size to search in MB
        """
        super().__init__()
        self._category = ToolCategory.SEARCH
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)
        self.max_file_size_mb = max_file_size_mb

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Search for text pattern in files. Supports regex patterns. Returns matching lines with line numbers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for (e.g., 'def.*test', 'class\\s+\\w+', 'TODO:')"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional: Glob pattern for files to search in (e.g., '*.py', '**/*.js'). Default: search all text files."
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Optional: Whether search is case-sensitive (default: false)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Optional: Maximum number of matching lines to return (default: 100)"
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute grep search."""
        pattern = args["pattern"]
        file_pattern = args.get("file_pattern", "**/*")
        case_sensitive = args.get("case_sensitive", False)
        max_results = args.get("max_results", 100)

        try:
            # Compile regex
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            # Find files to search
            if "**" in file_pattern:
                files = list(self.workspace_root.rglob(file_pattern))
            else:
                files = list(self.workspace_root.glob(file_pattern))

            # Filter to only files
            files = [f for f in files if f.is_file()]

            # Search files
            matches = []
            total_matches = 0

            for file_path in files:
                # Skip binary files
                if is_binary_file(file_path):
                    continue

                # Skip large files
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    continue

                try:
                    # Read and search file
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_no, line in enumerate(f, start=1):
                            if regex.search(line):
                                total_matches += 1
                                if len(matches) < max_results:
                                    rel_path = file_path.relative_to(self.workspace_root)
                                    matches.append({
                                        "file": str(rel_path),
                                        "line": line_no,
                                        "content": line.rstrip()
                                    })

                                    # Stop if we've hit the limit
                                    if len(matches) >= max_results:
                                        break

                        # Break outer loop if we've hit the limit
                        if len(matches) >= max_results:
                            break

                except Exception:
                    # Skip files we can't read
                    continue

            # Format results
            if not matches:
                content = f"No matches found for pattern '{pattern}'"
                summary = f"No matches for '{pattern}'"
            else:
                lines = []
                current_file = None
                for match in matches:
                    if match["file"] != current_file:
                        if current_file is not None:
                            lines.append("")  # Blank line between files
                        lines.append(f"📄 {match['file']}")
                        current_file = match["file"]

                    lines.append(f"  {match['line']}: {match['content']}")

                content = "\n".join(lines)

                summary = f"Found {len(matches)} match{'es' if len(matches) != 1 else ''} for '{pattern}'"
                if total_matches > max_results:
                    summary += f" (showing first {max_results} of {total_matches})"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "pattern": pattern,
                    "count": len(matches),
                    "total_matches": total_matches,
                    "truncated": total_matches > max_results,
                    "matches": matches
                }
            )

        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex pattern: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Grep failed: {e}")


class FindSymbolTool(Tool):
    """Tool for finding symbols (classes, functions) by name."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.SEARCH
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "find_symbol"

    @property
    def description(self) -> str:
        return "Find definitions of classes, functions, or methods by name. Searches Python, JavaScript, TypeScript, and other common languages."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Name of the symbol to find (class, function, method, etc.)"
                },
                "symbol_type": {
                    "type": "string",
                    "description": "Optional: Type of symbol ('class', 'function', 'method', 'any'). Default: 'any'"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional: Glob pattern for files to search in (e.g., '*.py'). Default: common code files."
                }
            },
            "required": ["symbol_name"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute symbol search."""
        symbol_name = args["symbol_name"]
        symbol_type = args.get("symbol_type", "any")
        file_pattern = args.get("file_pattern")

        # Build regex patterns based on symbol type and common languages
        patterns = []

        if symbol_type in ("class", "any"):
            # Python: class ClassName
            patterns.append(rf"^\s*class\s+{re.escape(symbol_name)}\s*[\(:]")
            # JavaScript/TypeScript: class ClassName
            patterns.append(rf"^\s*(?:export\s+)?class\s+{re.escape(symbol_name)}\s*[{{<]")

        if symbol_type in ("function", "any"):
            # Python: def function_name
            patterns.append(rf"^\s*(?:async\s+)?def\s+{re.escape(symbol_name)}\s*\(")
            # JavaScript/TypeScript: function functionName, const functionName = function
            patterns.append(rf"^\s*(?:export\s+)?(?:async\s+)?function\s+{re.escape(symbol_name)}\s*\(")
            patterns.append(rf"^\s*(?:const|let|var)\s+{re.escape(symbol_name)}\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)")

        if symbol_type in ("method", "any"):
            # Python: def method_name (inside class)
            patterns.append(rf"^\s+(?:async\s+)?def\s+{re.escape(symbol_name)}\s*\(")
            # JavaScript/TypeScript: methodName() or async methodName()
            patterns.append(rf"^\s+(?:async\s+)?{re.escape(symbol_name)}\s*\([^)]*\)\s*{{")

        # Default file patterns if not specified
        if file_pattern is None:
            file_patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", "**/*.jsx", "**/*.java", "**/*.go", "**/*.rs"]
        else:
            file_patterns = [file_pattern]

        try:
            matches = []

            for fp in file_patterns:
                files = list(self.workspace_root.rglob(fp) if "**" in fp else self.workspace_root.glob(fp))
                files = [f for f in files if f.is_file()]

                for file_path in files:
                    if is_binary_file(file_path):
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_no, line in enumerate(f, start=1):
                                for pattern in patterns:
                                    if re.search(pattern, line):
                                        rel_path = file_path.relative_to(self.workspace_root)
                                        matches.append({
                                            "file": str(rel_path),
                                            "line": line_no,
                                            "content": line.strip()
                                        })
                                        break  # Only match once per line

                    except Exception:
                        continue

            # Format results
            if not matches:
                content = f"No definitions found for symbol '{symbol_name}'"
                summary = f"Symbol '{symbol_name}' not found"
            else:
                lines = []
                for match in matches:
                    lines.append(f"📄 {match['file']}:{match['line']}")
                    lines.append(f"  {match['content']}")
                    lines.append("")

                content = "\n".join(lines).rstrip()
                summary = f"Found {len(matches)} definition{'s' if len(matches) != 1 else ''} of '{symbol_name}'"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "symbol_name": symbol_name,
                    "symbol_type": symbol_type,
                    "count": len(matches),
                    "matches": matches
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Symbol search failed: {e}")
