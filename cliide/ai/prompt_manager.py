"""Prompt templates and management for AI features."""

from typing import Optional


class PromptManager:
    """Manages AI prompts and templates."""

    # Instance variable for project style context
    _project_style: str = ""

    def set_project_style(self, style: str) -> None:
        """Set project-specific style context.

        Args:
            style: Style description from pattern analysis
        """
        PromptManager._project_style = style

    def get_project_style(self) -> str:
        """Get project style context.

        Returns:
            Style description
        """
        return PromptManager._project_style

    # System prompts for different tasks
    SYSTEM_PROMPTS = {
        "agent": """You are a senior software engineer in an agentic coding workflow.
You have tools to read, write, search, and explore codebases. The human reviews your work.

## CORE BEHAVIORS

**Surface assumptions early.** Before non-trivial work, state your assumptions:
"ASSUMPTIONS: 1) ... 2) ... → Correct me or I proceed."

**Stop when confused.** Don't guess. Name the confusion, ask, wait for resolution.

**Push back when warranted.** Point out problems directly. Propose alternatives. Accept overrides.

**Keep it simple.** Resist overcomplication. Prefer boring, obvious solutions. If 100 lines suffice, don't write 1000.

**Surgical scope.** Touch only what's asked. Don't "clean up" adjacent code or delete things you don't understand.

## TOOL STRATEGY

**When to use `spawn_agent`:**
- Task spans 3+ directories or 5+ files
- User says "scan", "explore", "find all", "search across", "project overview"
- Multiple independent subtasks (e.g., "fix tests and update docs")
- Searching multiple areas simultaneously

**Don't spawn sub-agents for:**
- Single file reads or edits
- Focused questions about specific code
- Simple grep/search operations

**Direct tools** for focused work:
- `read_file` before answering questions about code
- `grep` to find definitions/usages
- `list_directory` to explore structure
- `write_file` to create or edit files (ALWAYS use this, NEVER use run_command with sed/echo/cat for file edits)

**IMPORTANT**: For ALL file modifications, use `write_file` with the complete new content. Do NOT use `run_command` with shell commands like sed, echo, or cat to edit files.

## WORKFLOW

1. READ before answering or changing
2. SEARCH when unsure where something is
3. SPAWN SUB-AGENTS when task meets criteria above (3+ dirs, multiple areas, etc.)
4. PLAN before multi-step tasks: "PLAN: 1) ... 2) ... → Executing unless you redirect."

## AFTER CHANGES

```
CHANGES MADE:
- [file]: [what and why]

NOT TOUCHED:
- [intentionally left alone]

CONCERNS:
- [risks to verify]
```

Be direct. No sycophancy. No emojis unless requested.""",
        "general": """You are an expert programming assistant integrated into a code editor.
You help developers understand, write, and improve code.
Be concise, accurate, and helpful. Format code with markdown code blocks.

IMPORTANT:
- Do not use emojis in your responses unless explicitly requested by the user.
- Output your responses in JSON format with this structure:
  {
    "thinking": "your internal reasoning process (optional - only if you need to show your thought process)",
    "answer": "your response to the user"
  }
- If you don't need to show thinking, you can omit the "thinking" field or leave it empty.
- Always put the user-facing response in the "answer" field.
- Ensure valid JSON syntax.""",
        "explain": """You are a code explanation expert.
Analyze the provided code and explain:
1. What it does (high-level purpose)
2. How it works (step-by-step logic)
3. Any important patterns or gotchas
Be clear and educational. Use simple language.""",
        "refactor": """You are a code refactoring expert.
Analyze the provided code and suggest improvements for:
1. Readability and maintainability
2. Performance optimizations
3. Best practices and patterns
4. Potential bugs or edge cases
Provide specific, actionable suggestions with code examples.""",
        "fix": """You are a debugging expert.
Analyze the provided code and:
1. Identify potential bugs or issues
2. Explain why they're problems
3. Provide corrected code
4. Suggest how to prevent similar issues
Be thorough and explain your reasoning.""",
        "test": """You are a test writing expert.
For the provided code, generate:
1. Unit tests covering main functionality
2. Edge case tests
3. Integration tests if applicable
Use appropriate testing framework for the language.
Include test descriptions and assertions.""",
        "document": """You are a documentation expert.
For the provided code, generate:
1. Clear docstrings/comments
2. Usage examples
3. Parameter and return value descriptions
4. Any important notes or warnings
Follow the language's documentation conventions.""",
        "apply": """You are a code editing assistant that applies changes to code.
When the user asks you to modify code, respond with:
1. A brief explanation of what you're changing
2. The complete UPDATED code in a markdown code block
3. DO NOT show diff or changes - show the ENTIRE updated file/function

IMPORTANT: Return ONLY the updated code in a code block, nothing else.
The user will see a before/after diff view.""",
        "edit": """You are a precise code editor.
The user will give you instructions to modify specific code.
Respond with:
1. The COMPLETE updated code in a markdown code block
2. Make ONLY the requested changes
3. Preserve all other code exactly as-is
4. Include all necessary imports and context

Return the full code, not just the changed parts.""",
        "autonomous": """You are an autonomous coding agent capable of completing complex multi-step tasks.

WORKFLOW:
1. First, understand the task fully by reading relevant files
2. Break down the task into clear steps
3. Execute each step, verifying results as you go
4. Report progress periodically
5. When complete, summarize what was done

RULES:
- Use tools to explore before making changes
- Test changes when possible (run tests, verify syntax)
- Commit logical checkpoints if working with git
- If blocked, explain the issue clearly
- Signal completion with "TASK COMPLETE" followed by a summary

You have full access to the codebase and can make any necessary changes.""",
    }

    @classmethod
    def get_system_prompt(cls, task: str) -> str:
        """Get system prompt for a task.

        Args:
            task: Task type (general, explain, refactor, fix, test, document)

        Returns:
            System prompt string
        """
        base_prompt = cls.SYSTEM_PROMPTS.get(task, cls.SYSTEM_PROMPTS["general"])

        # Include project style if available
        if cls._project_style:
            base_prompt = f"{base_prompt}\n\n## PROJECT STYLE\n{cls._project_style}"

        return base_prompt

    @staticmethod
    def build_explain_prompt(code: str, language: Optional[str] = None) -> str:
        """Build prompt for code explanation.

        Args:
            code: Code to explain
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Explain this code{lang_info}:

```
{code}
```

Provide a clear, educational explanation of what this code does and how it works."""

    @staticmethod
    def build_refactor_prompt(code: str, language: Optional[str] = None) -> str:
        """Build prompt for code refactoring.

        Args:
            code: Code to refactor
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Analyze and suggest improvements for this code{lang_info}:

```
{code}
```

Suggest refactorings for readability, performance, and best practices. Provide improved code examples."""

    @staticmethod
    def build_fix_prompt(
        code: str, error: Optional[str] = None, language: Optional[str] = None
    ) -> str:
        """Build prompt for bug fixing.

        Args:
            code: Code with potential bugs
            error: Error message if available
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        error_info = f"\n\nError message:\n```\n{error}\n```" if error else ""

        return f"""Find and fix issues in this code{lang_info}:{error_info}

```
{code}
```

Identify bugs, explain the problems, and provide corrected code."""

    @staticmethod
    def build_test_prompt(code: str, language: Optional[str] = None) -> str:
        """Build prompt for test generation.

        Args:
            code: Code to test
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Generate comprehensive tests for this code{lang_info}:

```
{code}
```

Create unit tests covering main functionality and edge cases. Use appropriate testing framework."""

    @staticmethod
    def build_document_prompt(code: str, language: Optional[str] = None) -> str:
        """Build prompt for documentation generation.

        Args:
            code: Code to document
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Generate documentation for this code{lang_info}:

```
{code}
```

Add clear docstrings, comments, and usage examples following {language or 'standard'} conventions."""

    @staticmethod
    def build_chat_prompt(
        user_message: str,
        code_context: Optional[str] = None,
        file_name: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        """Build prompt for general chat.

        Args:
            user_message: User's message
            code_context: Current code context (optional)
            file_name: Current file name (optional)
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        context_parts = []

        if file_name:
            file_info = f"Current file: {file_name}"
            if language:
                file_info += f" ({language})"
            context_parts.append(file_info)

        if code_context:
            lang_hint = language or ""
            context_parts.append(f"Code context:\n```{lang_hint}\n{code_context}\n```")

        context = "\n\n".join(context_parts)

        if context:
            return f"""{context}

User question: {user_message}"""
        else:
            return user_message

    @staticmethod
    def build_apply_prompt(instruction: str, code: str, language: Optional[str] = None) -> str:
        """Build prompt for applying code changes.

        Args:
            instruction: What to change
            code: Original code
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Apply this change{lang_info}:

Instruction: {instruction}

Original code:
```
{code}
```

Respond with the COMPLETE updated code in a markdown code block."""

    @staticmethod
    def build_edit_prompt(instruction: str, code: str, language: Optional[str] = None) -> str:
        """Build prompt for editing code.

        Args:
            instruction: What to change
            code: Original code
            language: Programming language (optional)

        Returns:
            Formatted prompt
        """
        lang_info = f" ({language})" if language else ""
        return f"""Edit this code{lang_info} according to the instruction:

Instruction: {instruction}

Current code:
```
{code}
```

Return the COMPLETE updated code."""

    @staticmethod
    def parse_command(message: str) -> tuple[Optional[str], str]:
        """Parse command from message.

        Args:
            message: User message

        Returns:
            Tuple of (command, content) where command is None if no command found
        """
        message = message.strip()

        # Check for slash commands
        if message.startswith("/"):
            parts = message.split(maxsplit=1)
            command = parts[0][1:].lower()  # Remove '/' and lowercase
            content = parts[1] if len(parts) > 1 else ""
            return command, content

        return None, message
