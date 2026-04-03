"""Build context for AI requests from editor state."""

from pathlib import Path
from typing import Optional


class ContextBuilder:
    """Builds context information for AI requests."""

    @staticmethod
    def build_code_context(
        code: str,
        file_path: Optional[str] = None,
        selection: Optional[str] = None,
        cursor_line: Optional[int] = None,
    ) -> dict[str, str | int | None]:
        """Build context from code and editor state.

        Args:
            code: Full file content
            file_path: Path to current file
            selection: Selected text (if any)
            cursor_line: Current cursor line number

        Returns:
            Context dictionary
        """
        context = {
            "file_path": file_path,
            "file_name": Path(file_path).name if file_path else None,
            "language": ContextBuilder._detect_language(file_path) if file_path else None,
            "full_code": code,
            "selection": selection,
            "cursor_line": cursor_line,
            "line_count": len(code.split("\n")) if code else 0,
        }

        return context

    @staticmethod
    def _detect_language(file_path: str) -> Optional[str]:
        """Detect programming language from file extension.

        Args:
            file_path: Path to file

        Returns:
            Language name or None
        """
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".ps1": "powershell",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".xml": "xml",
        }

        suffix = Path(file_path).suffix.lower()
        return extension_map.get(suffix)

    @staticmethod
    def format_context_for_prompt(context: dict, include_full_code: bool = False) -> str:
        """Format context as a string for AI prompts.

        Args:
            context: Context dictionary
            include_full_code: Whether to include full file content

        Returns:
            Formatted context string
        """
        parts = []

        if context.get("file_name"):
            parts.append(f"File: {context['file_name']}")

        if context.get("language"):
            parts.append(f"Language: {context['language']}")

        if context.get("cursor_line"):
            parts.append(f"Line: {context['cursor_line']}")

        if context.get("selection"):
            parts.append(f"\nSelected code:\n```\n{context['selection']}\n```")
        elif include_full_code and context.get("full_code"):
            parts.append(f"\nFull file:\n```\n{context['full_code']}\n```")

        return "\n".join(parts)

    @staticmethod
    def get_context_summary(context: dict) -> str:
        """Get a brief summary of the context.

        Args:
            context: Context dictionary

        Returns:
            Summary string
        """
        parts = []

        if context.get("file_name"):
            parts.append(context["file_name"])

        if context.get("language"):
            parts.append(f"({context['language']})")

        if context.get("selection"):
            sel_len = len(context["selection"])
            parts.append(f"{sel_len} chars selected")
        elif context.get("line_count"):
            parts.append(f"{context['line_count']} lines")

        return " ".join(parts) if parts else "No context"

    @staticmethod
    def extract_relevant_code(
        full_code: str, cursor_line: int, context_lines: int = 10
    ) -> str:
        """Extract relevant code around cursor position.

        Args:
            full_code: Full file content
            cursor_line: Current cursor line (0-indexed)
            context_lines: Number of lines to include before/after

        Returns:
            Extracted code snippet
        """
        lines = full_code.split("\n")
        start = max(0, cursor_line - context_lines)
        end = min(len(lines), cursor_line + context_lines + 1)

        return "\n".join(lines[start:end])

    @staticmethod
    def build_conversation_context(
        messages: list[dict[str, str]], max_messages: int = 10
    ) -> list[dict[str, str]]:
        """Build conversation context from message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_messages: Maximum number of messages to include

        Returns:
            Trimmed message list
        """
        # Keep system message + last N messages
        if not messages:
            return []

        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]

        # Keep last max_messages
        trimmed_messages = other_messages[-max_messages:]

        return system_messages + trimmed_messages

    @staticmethod
    def format_mentioned_files(mentioned_files: dict[str, str]) -> str:
        """Format @mentioned files for inclusion in prompt.

        Args:
            mentioned_files: Dict mapping file path to file content

        Returns:
            Formatted string with file contents
        """
        if not mentioned_files:
            return ""

        parts = ["\n\nReferenced files:"]
        for file_path, content in mentioned_files.items():
            # Detect language for syntax highlighting
            language = ContextBuilder._detect_language(file_path) or ""
            parts.append(f"\n@{file_path}:")
            parts.append(f"```{language}\n{content}\n```")

        return "\n".join(parts)
