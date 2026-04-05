"""Pattern analyzer for learning codebase conventions."""

import asyncio
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from cliide.utils.logger import log


class PatternAnalyzer:
    """Analyzes codebase to learn coding patterns and conventions."""

    # Common file extensions to analyze
    ANALYZABLE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
    }

    def __init__(self, workspace_root: Path) -> None:
        """Initialize pattern analyzer.

        Args:
            workspace_root: Root directory of the workspace
        """
        self.workspace_root = workspace_root
        self.patterns: dict[str, Any] = {}
        self._analyzed = False

    async def analyze(self, max_files: int = 50) -> dict[str, Any]:
        """Analyze the codebase for patterns.

        Args:
            max_files: Maximum number of files to analyze

        Returns:
            Dict of detected patterns
        """
        log(f"[PATTERNS] Starting analysis of {self.workspace_root}")

        # Find source files (in thread pool to avoid blocking)
        files = await asyncio.to_thread(self._find_source_files, max_files)
        log(f"[PATTERNS] Found {len(files)} files to analyze")

        if not files:
            return {}

        # Analyze files
        results = await asyncio.gather(
            *[self._analyze_file(f) for f in files],
            return_exceptions=True,
        )

        # Aggregate results
        self.patterns = self._aggregate_patterns(
            [r for r in results if isinstance(r, dict)]
        )
        self._analyzed = True

        log(f"[PATTERNS] Analysis complete: {len(self.patterns)} pattern types detected")
        return self.patterns

    def _find_source_files(self, max_files: int) -> list[Path]:
        """Find source files in workspace.

        Args:
            max_files: Maximum files to return

        Returns:
            List of file paths
        """
        files = []

        try:
            for ext in self.ANALYZABLE_EXTENSIONS:
                for f in self.workspace_root.rglob(f"*{ext}"):
                    # Skip common ignored directories
                    parts = f.parts
                    if any(p in parts for p in [
                        "node_modules", ".git", "__pycache__", "venv",
                        ".venv", "dist", "build", ".tox", "eggs",
                    ]):
                        continue

                    files.append(f)
                    if len(files) >= max_files:
                        return files

        except Exception as e:
            log(f"[PATTERNS] Error finding files: {e}")

        return files

    async def _analyze_file(self, file_path: Path) -> dict[str, Any]:
        """Analyze a single file for patterns.

        Args:
            file_path: Path to file

        Returns:
            Dict of patterns found in file
        """
        try:
            # Read file in thread pool to avoid blocking
            content = await asyncio.to_thread(
                file_path.read_text, encoding="utf-8", errors="ignore"
            )
            lines = content.split("\n")

            ext = file_path.suffix.lower()

            return {
                "extension": ext,
                "naming": self._analyze_naming(content, ext),
                "imports": self._analyze_imports(lines, ext),
                "comments": self._analyze_comments(lines, ext),
                "indentation": self._analyze_indentation(lines),
                "line_length": self._analyze_line_length(lines),
                "error_handling": self._analyze_error_handling(content, ext),
            }

        except Exception as e:
            log(f"[PATTERNS] Error analyzing {file_path}: {e}")
            return {}

    def _analyze_naming(self, content: str, ext: str) -> dict[str, int]:
        """Analyze naming conventions.

        Args:
            content: File content
            ext: File extension

        Returns:
            Dict of naming pattern counts
        """
        patterns = Counter()

        # Find identifiers (simplified)
        if ext == ".py":
            # Python: look for function and variable definitions
            snake_case = len(re.findall(r'\bdef ([a-z][a-z0-9_]*)\(', content))
            camel_case = len(re.findall(r'\bdef ([a-z][a-zA-Z0-9]*)\(', content)) - snake_case
            patterns["snake_case"] = snake_case
            patterns["camelCase"] = camel_case

            # Class names
            pascal = len(re.findall(r'\bclass ([A-Z][a-zA-Z0-9]*)', content))
            patterns["PascalCase"] = pascal

        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            # JavaScript/TypeScript
            camel = len(re.findall(r'\b(?:function|const|let|var)\s+([a-z][a-zA-Z0-9]*)\b', content))
            patterns["camelCase"] = camel

            pascal = len(re.findall(r'\bclass\s+([A-Z][a-zA-Z0-9]*)', content))
            patterns["PascalCase"] = pascal

        return dict(patterns)

    def _analyze_imports(self, lines: list[str], ext: str) -> dict[str, int]:
        """Analyze import patterns.

        Args:
            lines: File lines
            ext: File extension

        Returns:
            Dict of import pattern counts
        """
        patterns = Counter()

        for line in lines[:50]:  # Only check top of file
            line = line.strip()

            if ext == ".py":
                if line.startswith("import "):
                    patterns["absolute_import"] += 1
                elif line.startswith("from ") and "import" in line:
                    if line.startswith("from ."):
                        patterns["relative_import"] += 1
                    else:
                        patterns["from_import"] += 1

            elif ext in (".js", ".ts", ".jsx", ".tsx"):
                if line.startswith("import "):
                    if "from './" in line or 'from "./' in line:
                        patterns["relative_import"] += 1
                    else:
                        patterns["absolute_import"] += 1
                elif line.startswith("const ") and "require(" in line:
                    patterns["require"] += 1

        return dict(patterns)

    def _analyze_comments(self, lines: list[str], ext: str) -> dict[str, int]:
        """Analyze comment style.

        Args:
            lines: File lines
            ext: File extension

        Returns:
            Dict of comment style counts
        """
        patterns = Counter()

        for line in lines:
            stripped = line.strip()

            if ext == ".py":
                if stripped.startswith("#"):
                    patterns["hash_comment"] += 1
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    patterns["docstring"] += 1

            elif ext in (".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".c", ".cpp"):
                if stripped.startswith("//"):
                    patterns["slash_comment"] += 1
                if stripped.startswith("/*"):
                    patterns["block_comment"] += 1
                if stripped.startswith("/**"):
                    patterns["jsdoc"] += 1

        return dict(patterns)

    def _analyze_indentation(self, lines: list[str]) -> dict[str, int]:
        """Analyze indentation style.

        Args:
            lines: File lines

        Returns:
            Dict of indentation counts
        """
        patterns = Counter()

        for line in lines:
            if not line.strip():
                continue

            leading = len(line) - len(line.lstrip())
            if leading == 0:
                continue

            if line.startswith("\t"):
                patterns["tabs"] += 1
            elif leading == 2:
                patterns["2_spaces"] += 1
            elif leading == 4:
                patterns["4_spaces"] += 1

        return dict(patterns)

    def _analyze_line_length(self, lines: list[str]) -> dict[str, Any]:
        """Analyze line length patterns.

        Args:
            lines: File lines

        Returns:
            Line length statistics
        """
        lengths = [len(l) for l in lines if l.strip()]

        if not lengths:
            return {}

        return {
            "avg": sum(lengths) // len(lengths),
            "max": max(lengths),
            "over_80": sum(1 for l in lengths if l > 80),
            "over_120": sum(1 for l in lengths if l > 120),
        }

    def _analyze_error_handling(self, content: str, ext: str) -> dict[str, int]:
        """Analyze error handling patterns.

        Args:
            content: File content
            ext: File extension

        Returns:
            Dict of error handling counts
        """
        patterns = Counter()

        if ext == ".py":
            patterns["try_except"] = len(re.findall(r'\btry:', content))
            patterns["raise"] = len(re.findall(r'\braise\b', content))
            patterns["assert"] = len(re.findall(r'\bassert\b', content))

        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            patterns["try_catch"] = len(re.findall(r'\btry\s*{', content))
            patterns["throw"] = len(re.findall(r'\bthrow\b', content))
            patterns["promise_catch"] = len(re.findall(r'\.catch\(', content))

        elif ext == ".go":
            patterns["if_err"] = len(re.findall(r'if\s+err\s*!=\s*nil', content))
            patterns["panic"] = len(re.findall(r'\bpanic\(', content))

        return dict(patterns)

    def _aggregate_patterns(self, results: list[dict]) -> dict[str, Any]:
        """Aggregate patterns from multiple files.

        Args:
            results: List of per-file pattern results

        Returns:
            Aggregated patterns
        """
        if not results:
            return {}

        aggregated = {
            "naming": Counter(),
            "imports": Counter(),
            "comments": Counter(),
            "indentation": Counter(),
            "error_handling": Counter(),
            "line_length": {"avg": 0, "max": 0},
            "extensions": Counter(),
        }

        for r in results:
            if "extension" in r:
                aggregated["extensions"][r["extension"]] += 1

            for key in ["naming", "imports", "comments", "indentation", "error_handling"]:
                if key in r and isinstance(r[key], dict):
                    for k, v in r[key].items():
                        aggregated[key][k] += v

            if "line_length" in r and r["line_length"]:
                aggregated["line_length"]["avg"] += r["line_length"].get("avg", 0)
                aggregated["line_length"]["max"] = max(
                    aggregated["line_length"]["max"],
                    r["line_length"].get("max", 0),
                )

        # Average line length
        if results:
            aggregated["line_length"]["avg"] //= len(results)

        # Convert Counters to dicts for JSON serialization
        return {
            k: dict(v) if isinstance(v, Counter) else v
            for k, v in aggregated.items()
        }

    def get_style_prompt(self) -> str:
        """Generate a prompt section describing the codebase style.

        Returns:
            Style description for AI prompts
        """
        if not self._analyzed or not self.patterns:
            return ""

        parts = ["The codebase follows these patterns:"]

        # Naming
        naming = self.patterns.get("naming", {})
        if naming:
            dominant = max(naming, key=naming.get, default=None)
            if dominant:
                parts.append(f"- Naming: primarily {dominant}")

        # Indentation
        indent = self.patterns.get("indentation", {})
        if indent:
            dominant = max(indent, key=indent.get, default=None)
            if dominant:
                parts.append(f"- Indentation: {dominant.replace('_', ' ')}")

        # Comments
        comments = self.patterns.get("comments", {})
        if comments.get("docstring", 0) > 5:
            parts.append("- Uses docstrings for documentation")
        if comments.get("jsdoc", 0) > 5:
            parts.append("- Uses JSDoc comments")

        # Line length
        line_len = self.patterns.get("line_length", {})
        avg = line_len.get("avg", 0)
        if avg:
            parts.append(f"- Average line length: ~{avg} chars")

        # Error handling
        errors = self.patterns.get("error_handling", {})
        if errors.get("try_except", 0) > 3:
            parts.append("- Uses try/except for error handling")
        if errors.get("if_err", 0) > 3:
            parts.append("- Uses Go-style 'if err != nil' error checking")

        if len(parts) == 1:
            return ""

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Export patterns for persistence.

        Returns:
            Dict representation of patterns
        """
        return {
            "patterns": self.patterns,
            "analyzed": self._analyzed,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Import patterns from saved data.

        Args:
            data: Saved pattern data
        """
        self.patterns = data.get("patterns", {})
        self._analyzed = data.get("analyzed", False)
