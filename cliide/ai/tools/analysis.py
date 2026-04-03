"""Code analysis tools using tree-sitter."""

from pathlib import Path
from typing import Any
import tree_sitter_python as tspython

try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .base import Tool, ToolResult, ToolCategory
from .safety import validate_path, is_binary_file


class ExtractSymbolsTool(Tool):
    """Tool for extracting symbols (classes, functions) from a file using AST parsing."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.ANALYSIS
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)

        # Initialize tree-sitter parser if available
        if TREE_SITTER_AVAILABLE:
            self.py_language = Language(tspython.language())
            self.parser = Parser(self.py_language)
        else:
            self.parser = None

    @property
    def name(self) -> str:
        return "extract_symbols"

    @property
    def description(self) -> str:
        return "Extract symbols (classes, functions, methods) from a source file. Currently supports Python files with tree-sitter, falls back to regex for other languages."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the source file to analyze"
                },
                "symbol_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: Types of symbols to extract (e.g., ['class', 'function']). Default: all types."
                }
            },
            "required": ["path"]
        }

    def _extract_python_symbols(self, source_code: str, symbol_types: list[str] | None) -> list[dict]:
        """Extract symbols from Python code using tree-sitter.

        Args:
            source_code: Python source code
            symbol_types: Types to extract or None for all

        Returns:
            List of symbol dicts
        """
        if not self.parser:
            return []

        symbols = []
        tree = self.parser.parse(bytes(source_code, "utf8"))

        def visit_node(node, parent_class=None):
            """Recursively visit AST nodes."""
            if node.type == "class_definition":
                # Extract class name
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = source_code[name_node.start_byte:name_node.end_byte]
                    line = node.start_point[0] + 1

                    if not symbol_types or "class" in symbol_types:
                        symbols.append({
                            "type": "class",
                            "name": class_name,
                            "line": line,
                            "parent": None
                        })

                    # Visit class body for methods
                    body = node.child_by_field_name("body")
                    if body:
                        for child in body.children:
                            visit_node(child, parent_class=class_name)

            elif node.type == "function_definition":
                # Extract function/method name
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_name = source_code[name_node.start_byte:name_node.end_byte]
                    line = node.start_point[0] + 1

                    if parent_class:
                        # It's a method
                        if not symbol_types or "method" in symbol_types:
                            symbols.append({
                                "type": "method",
                                "name": func_name,
                                "line": line,
                                "parent": parent_class
                            })
                    else:
                        # It's a function
                        if not symbol_types or "function" in symbol_types:
                            symbols.append({
                                "type": "function",
                                "name": func_name,
                                "line": line,
                                "parent": None
                            })

            # Recurse for other node types
            elif parent_class is None:  # Only recurse at module level, not inside functions
                for child in node.children:
                    visit_node(child, parent_class)

        # Start traversal
        visit_node(tree.root_node)

        return symbols

    def _extract_symbols_regex(self, source_code: str, file_ext: str, symbol_types: list[str] | None) -> list[dict]:
        """Fallback regex-based symbol extraction.

        Args:
            source_code: Source code
            file_ext: File extension
            symbol_types: Types to extract or None for all

        Returns:
            List of symbol dicts
        """
        import re

        symbols = []
        lines = source_code.split('\n')

        # Python patterns
        if file_ext == '.py':
            for i, line in enumerate(lines, start=1):
                # Class definitions
                if not symbol_types or "class" in symbol_types:
                    match = re.match(r'^\s*class\s+(\w+)', line)
                    if match:
                        symbols.append({
                            "type": "class",
                            "name": match.group(1),
                            "line": i,
                            "parent": None
                        })

                # Function/method definitions
                if not symbol_types or "function" in symbol_types or "method" in symbol_types:
                    match = re.match(r'^\s*(?:async\s+)?def\s+(\w+)', line)
                    if match:
                        # Determine if it's a method (indented) or function (top-level)
                        if line.startswith(' ') or line.startswith('\t'):
                            sym_type = "method"
                        else:
                            sym_type = "function"

                        if not symbol_types or sym_type in symbol_types:
                            symbols.append({
                                "type": sym_type,
                                "name": match.group(1),
                                "line": i,
                                "parent": None  # Can't easily determine parent with regex
                            })

        # JavaScript/TypeScript patterns
        elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
            for i, line in enumerate(lines, start=1):
                # Class definitions
                if not symbol_types or "class" in symbol_types:
                    match = re.match(r'^\s*(?:export\s+)?class\s+(\w+)', line)
                    if match:
                        symbols.append({
                            "type": "class",
                            "name": match.group(1),
                            "line": i,
                            "parent": None
                        })

                # Function definitions
                if not symbol_types or "function" in symbol_types:
                    match = re.match(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', line)
                    if match:
                        symbols.append({
                            "type": "function",
                            "name": match.group(1),
                            "line": i,
                            "parent": None
                        })

                    # Arrow functions: const name = () => {}
                    match = re.match(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', line)
                    if match:
                        symbols.append({
                            "type": "function",
                            "name": match.group(1),
                            "line": i,
                            "parent": None
                        })

        return symbols

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute symbol extraction."""
        path = args["path"]
        symbol_types = args.get("symbol_types")

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        if not normalized_path.exists():
            return ToolResult(success=False, error=f"File does not exist: {path}")

        if not normalized_path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        if is_binary_file(normalized_path):
            return ToolResult(success=False, error=f"Cannot analyze binary file: {path}")

        try:
            # Read file
            with open(normalized_path, 'r', encoding='utf-8', errors='replace') as f:
                source_code = f.read()

            file_ext = normalized_path.suffix

            # Extract symbols based on file type
            if file_ext == '.py' and TREE_SITTER_AVAILABLE and self.parser:
                symbols = self._extract_python_symbols(source_code, symbol_types)
            else:
                symbols = self._extract_symbols_regex(source_code, file_ext, symbol_types)

            # Format output
            if not symbols:
                content = f"No symbols found in {normalized_path.name}"
                summary = f"No symbols in {normalized_path.name}"
            else:
                lines = []
                for sym in symbols:
                    icon = {"class": "🔷", "function": "🔹", "method": "  🔸"}.get(sym["type"], "•")
                    parent_info = f" (in {sym['parent']})" if sym.get("parent") else ""
                    lines.append(f"{icon} {sym['name']} (line {sym['line']}){parent_info}")

                content = "\n".join(lines)
                summary = f"Found {len(symbols)} symbol{'s' if len(symbols) != 1 else ''} in {normalized_path.name}"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "path": str(normalized_path),
                    "count": len(symbols),
                    "symbols": symbols
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Symbol extraction failed: {e}")


class GetFileSummaryTool(Tool):
    """Tool for getting file summary (stats, imports, etc.)."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.ANALYSIS
        self._requires_confirmation = False
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "get_file_summary"

    @property
    def description(self) -> str:
        return "Get a summary of a file including size, line count, imports, and basic structure."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to summarize"
                }
            },
            "required": ["path"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute file summary."""
        path = args["path"]

        # Validate path
        is_valid, error, normalized_path = validate_path(path, self.workspace_root)
        if not is_valid:
            return ToolResult(success=False, error=error)

        if not normalized_path.exists():
            return ToolResult(success=False, error=f"File does not exist: {path}")

        if not normalized_path.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")

        try:
            # Get file stats
            stats = normalized_path.stat()
            size_bytes = stats.st_size
            size_kb = size_bytes / 1024

            # Check if binary
            if is_binary_file(normalized_path):
                return ToolResult(
                    success=True,
                    data=f"Binary file: {normalized_path.name}\nSize: {size_kb:.1f} KB",
                    summary=f"{normalized_path.name}: Binary file ({size_kb:.1f} KB)",
                    metadata={"path": str(normalized_path), "binary": True, "size_kb": size_kb}
                )

            # Read and analyze text file
            with open(normalized_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            line_count = len(lines)
            non_empty_lines = sum(1 for line in lines if line.strip())

            # Extract imports for common languages
            imports = []
            file_ext = normalized_path.suffix

            if file_ext == '.py':
                import re
                for line in lines[:100]:  # Check first 100 lines
                    # import x, from x import y
                    match = re.match(r'^\s*(?:from\s+[\w.]+\s+)?import\s+(.+)', line)
                    if match:
                        imports.append(line.strip())

            elif file_ext in ['.js', '.ts', '.jsx', '.tsx']:
                import re
                for line in lines[:100]:
                    # import x from 'y', const x = require('y')
                    if re.match(r'^\s*import\s+', line) or re.match(r'^\s*(?:const|let|var)\s+\w+\s*=\s*require\(', line):
                        imports.append(line.strip())

            # Build summary
            lines_output = [
                f"📄 {normalized_path.name}",
                f"Size: {size_kb:.1f} KB",
                f"Lines: {line_count} ({non_empty_lines} non-empty)",
                f"Type: {file_ext or 'no extension'}"
            ]

            if imports:
                lines_output.append(f"\nImports ({len(imports)}):")
                for imp in imports[:10]:  # Limit to 10 imports
                    lines_output.append(f"  {imp}")
                if len(imports) > 10:
                    lines_output.append(f"  ... and {len(imports) - 10} more")

            content = "\n".join(lines_output)
            summary = f"{normalized_path.name}: {line_count} lines, {size_kb:.1f} KB"

            return ToolResult(
                success=True,
                data=content,
                summary=summary,
                metadata={
                    "path": str(normalized_path),
                    "size_kb": size_kb,
                    "line_count": line_count,
                    "non_empty_lines": non_empty_lines,
                    "imports": imports,
                    "binary": False
                }
            )

        except Exception as e:
            return ToolResult(success=False, error=f"File summary failed: {e}")
