"""Rule-following tool for applying coding standards and patterns."""

from pathlib import Path
from typing import Any

from .base import Tool, ToolResult, ToolCategory
from .safety import validate_path, is_binary_file


# Built-in coding rules
BUILTIN_RULES = {
    "python_pep8": {
        "name": "Python PEP 8 Style Guide",
        "description": "Follow PEP 8 Python style guide: use snake_case for functions/variables, CamelCase for classes, 4-space indentation, max line length 79 chars.",
        "language": "python",
    },
    "python_typing": {
        "name": "Python Type Hints",
        "description": "Add type hints to all function parameters and return values. Use typing module for complex types.",
        "language": "python",
    },
    "python_docstrings": {
        "name": "Python Docstrings",
        "description": "Add Google-style docstrings to all classes and functions. Include Args, Returns, and Raises sections.",
        "language": "python",
    },
    "javascript_es6": {
        "name": "JavaScript ES6+ Standards",
        "description": "Use modern ES6+ features: const/let instead of var, arrow functions, template literals, destructuring, async/await.",
        "language": "javascript",
    },
    "consistent_naming": {
        "name": "Consistent Naming Conventions",
        "description": "Use consistent naming: camelCase for variables/functions, PascalCase for classes, UPPER_CASE for constants.",
        "language": "any",
    },
    "no_magic_numbers": {
        "name": "No Magic Numbers",
        "description": "Replace magic numbers with named constants. Extract numbers into well-named constant variables.",
        "language": "any",
    },
    "error_handling": {
        "name": "Proper Error Handling",
        "description": "Add proper error handling: use try/catch blocks, validate inputs, handle edge cases, provide meaningful error messages.",
        "language": "any",
    },
    "dry": {
        "name": "DRY Principle",
        "description": "Don't Repeat Yourself: extract repeated code into reusable functions or methods.",
        "language": "any",
    },
    "single_responsibility": {
        "name": "Single Responsibility Principle",
        "description": "Each function/class should have a single, well-defined responsibility. Split large functions into smaller, focused ones.",
        "language": "any",
    },
}


class FollowRuleTool(Tool):
    """Tool for applying coding rules and standards to code."""

    def __init__(self, workspace_root: str | Path):
        """Initialize the tool.

        Args:
            workspace_root: Root directory of workspace
        """
        super().__init__()
        self._category = ToolCategory.RULES
        self._requires_confirmation = False  # Just analyzing, not modifying
        self.workspace_root = Path(workspace_root)

    @property
    def name(self) -> str:
        return "follow_rule"

    @property
    def description(self) -> str:
        return "Analyze code and suggest how to apply a specific coding rule or standard. Returns guidance for improving code quality."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "rule": {
                    "type": "string",
                    "description": f"Rule to apply. Built-in rules: {', '.join(BUILTIN_RULES.keys())}. Or provide custom rule description."
                },
                "path": {
                    "type": "string",
                    "description": "Optional: Path to file to analyze. If not provided, returns rule description."
                },
                "code_snippet": {
                    "type": "string",
                    "description": "Optional: Code snippet to analyze instead of file. Overrides path if both provided."
                }
            },
            "required": ["rule"]
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute rule application."""
        rule_name = args["rule"]
        path = args.get("path")
        code_snippet = args.get("code_snippet")

        # Get rule info
        if rule_name in BUILTIN_RULES:
            rule_info = BUILTIN_RULES[rule_name]
            rule_description = rule_info["description"]
            rule_display_name = rule_info["name"]
        else:
            # Custom rule
            rule_description = rule_name
            rule_display_name = rule_name

        # If no code provided, just return rule description
        if not path and not code_snippet:
            content = f"Rule: {rule_display_name}\n\nDescription:\n{rule_description}\n\nTo apply this rule, provide either a file path or code snippet."
            return ToolResult(
                success=True,
                data=content,
                summary=f"Rule: {rule_display_name}",
                metadata={"rule": rule_name, "description": rule_description}
            )

        # Get code to analyze
        code = None
        source_info = ""

        if code_snippet:
            code = code_snippet
            source_info = "provided code snippet"
        elif path:
            # Validate and read file
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
                with open(normalized_path, 'r', encoding='utf-8', errors='replace') as f:
                    code = f.read()
                source_info = normalized_path.name
            except Exception as e:
                return ToolResult(success=False, error=f"Failed to read file: {e}")

        # Build analysis prompt guidance
        # This tool provides context for the AI to analyze the code
        # The actual analysis happens in the AI response, not here

        line_count = len(code.splitlines())

        content = [
            f"Rule: {rule_display_name}",
            f"Source: {source_info}",
            f"Lines: {line_count}",
            "",
            "Rule Description:",
            rule_description,
            "",
            "Code to analyze:",
            "```",
            code,
            "```",
            "",
            "Please analyze this code and provide specific suggestions for applying this rule.",
        ]

        summary = f"Analyzing {source_info} for rule: {rule_display_name}"

        return ToolResult(
            success=True,
            data="\n".join(content),
            summary=summary,
            metadata={
                "rule": rule_name,
                "rule_description": rule_description,
                "source": source_info,
                "line_count": line_count,
                "code": code
            }
        )


class ListRulesTool(Tool):
    """Tool for listing available coding rules."""

    def __init__(self):
        """Initialize the tool."""
        super().__init__()
        self._category = ToolCategory.RULES
        self._requires_confirmation = False

    @property
    def name(self) -> str:
        return "list_rules"

    @property
    def description(self) -> str:
        return "List all available built-in coding rules and standards."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Optional: Filter rules by language (e.g., 'python', 'javascript', 'any')"
                }
            }
        }

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute rule listing."""
        language_filter = args.get("language")

        # Filter rules by language if specified
        filtered_rules = {}
        for rule_id, rule_info in BUILTIN_RULES.items():
            if language_filter:
                if rule_info["language"] == language_filter or rule_info["language"] == "any":
                    filtered_rules[rule_id] = rule_info
            else:
                filtered_rules[rule_id] = rule_info

        # Format output
        if not filtered_rules:
            content = f"No rules found for language: {language_filter}"
            summary = f"No rules for {language_filter}"
        else:
            lines = ["Available Coding Rules:", ""]

            # Group by language
            by_language = {}
            for rule_id, rule_info in filtered_rules.items():
                lang = rule_info["language"]
                if lang not in by_language:
                    by_language[lang] = []
                by_language[lang].append((rule_id, rule_info))

            # Output grouped by language
            for lang in sorted(by_language.keys()):
                lang_display = lang.capitalize() if lang != "any" else "Language-Agnostic"
                lines.append(f"## {lang_display}")
                lines.append("")

                for rule_id, rule_info in by_language[lang]:
                    lines.append(f"**{rule_id}**: {rule_info['name']}")
                    lines.append(f"  {rule_info['description']}")
                    lines.append("")

            content = "\n".join(lines)
            summary = f"Found {len(filtered_rules)} coding rule{'s' if len(filtered_rules) != 1 else ''}"

        return ToolResult(
            success=True,
            data=content,
            summary=summary,
            metadata={
                "count": len(filtered_rules),
                "language_filter": language_filter,
                "rules": list(filtered_rules.keys())
            }
        )
