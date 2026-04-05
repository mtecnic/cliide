"""Inline code suggestions (ghost text)."""

import asyncio
from typing import Optional

from cliide.ai.vllm_client import get_client
from cliide.utils.logger import log


class InlineSuggest:
    """Generates inline code suggestions (ghost text) as you type."""

    def __init__(self, debounce_ms: int = 300, max_tokens: int = 50) -> None:
        """Initialize inline suggest.

        Args:
            debounce_ms: Debounce delay in milliseconds
            max_tokens: Maximum tokens to generate for suggestion
        """
        self.client = get_client()
        self.debounce_ms = debounce_ms
        self.max_tokens = max_tokens
        self._pending_task: Optional[asyncio.Task] = None
        self._last_request_id: int = 0

    async def get_suggestion(
        self,
        code_before: str,
        code_after: str,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Optional[str]:
        """Get inline completion suggestion.

        Args:
            code_before: Code before cursor
            code_after: Code after cursor
            language: Programming language
            file_path: Current file path for context

        Returns:
            Suggested completion or None
        """
        # Cancel any pending request
        self._last_request_id += 1
        request_id = self._last_request_id

        # Build FIM-style prompt (Fill In the Middle)
        # This format works well with code completion models
        prompt = self._build_fim_prompt(code_before, code_after, language)

        try:
            # Non-streaming request for speed
            suggestion = ""
            async for chunk in self.client.stream_with_system(
                system_prompt=self._get_system_prompt(language),
                user_prompt=prompt,
            ):
                # Check if this request is still relevant
                if request_id != self._last_request_id:
                    log(f"[SUGGEST] Request {request_id} cancelled")
                    return None

                suggestion += chunk

                # Stop early if we hit certain patterns
                if self._should_stop(suggestion):
                    break

                # Limit length
                if len(suggestion) > 200:
                    break

            # Clean up suggestion
            suggestion = self._clean_suggestion(suggestion, code_after)

            if suggestion and len(suggestion.strip()) > 0:
                log(f"[SUGGEST] Generated: {suggestion[:50]}...")
                return suggestion

            return None

        except Exception as e:
            log(f"[SUGGEST] Error: {e}")
            return None

    def _build_fim_prompt(
        self,
        code_before: str,
        code_after: str,
        language: Optional[str] = None,
    ) -> str:
        """Build Fill-In-the-Middle style prompt.

        Args:
            code_before: Code before cursor
            code_after: Code after cursor
            language: Programming language

        Returns:
            Formatted prompt
        """
        # Get last N lines for context (avoid sending huge files)
        lines_before = code_before.split("\n")
        context_before = "\n".join(lines_before[-20:]) if len(lines_before) > 20 else code_before

        # Get first few lines after cursor
        lines_after = code_after.split("\n")
        context_after = "\n".join(lines_after[:5]) if len(lines_after) > 5 else code_after

        lang_hint = f" ({language})" if language else ""

        return f"""Complete the code at <CURSOR>. Return ONLY the completion, nothing else.

```{language or ''}
{context_before}<CURSOR>{context_after}
```

Continue from <CURSOR>. Do not repeat existing code. Return only new code to insert."""

    def _get_system_prompt(self, language: Optional[str] = None) -> str:
        """Get system prompt for code completion.

        Args:
            language: Programming language

        Returns:
            System prompt
        """
        lang_hint = f" {language}" if language else ""
        return f"""You are a{lang_hint} code completion assistant.
Given code with <CURSOR>, return ONLY the code that should be inserted at that position.
Rules:
- Return just the completion, no explanations
- Don't repeat existing code
- Keep completions short (1-2 lines max)
- Match the code style
- Don't add closing brackets if they exist after cursor"""

    def _should_stop(self, suggestion: str) -> bool:
        """Check if we should stop generating.

        Args:
            suggestion: Current suggestion

        Returns:
            True if should stop
        """
        # Stop patterns
        stop_patterns = [
            "\n\n",  # Double newline
            "```",   # Code fence
            "# ",    # Comment (often means explanation)
            "//",    # Comment
        ]

        for pattern in stop_patterns:
            if pattern in suggestion:
                return True

        # Count newlines - stop if too many
        if suggestion.count("\n") > 2:
            return True

        return False

    def _clean_suggestion(self, suggestion: str, code_after: str) -> str:
        """Clean up the suggestion.

        Args:
            suggestion: Raw suggestion
            code_after: Code that exists after cursor

        Returns:
            Cleaned suggestion
        """
        # Remove any markdown artifacts
        suggestion = suggestion.strip()
        if suggestion.startswith("```"):
            lines = suggestion.split("\n")
            if len(lines) > 1:
                suggestion = "\n".join(lines[1:])
        if suggestion.endswith("```"):
            suggestion = suggestion[:-3]

        # Remove duplicate content that already exists after cursor
        if code_after:
            first_line_after = code_after.split("\n")[0].strip()
            if first_line_after and suggestion.strip().endswith(first_line_after):
                suggestion = suggestion[:suggestion.rfind(first_line_after)]

        # Trim trailing whitespace but keep leading for indentation
        suggestion = suggestion.rstrip()

        return suggestion

    def cancel(self) -> None:
        """Cancel any pending suggestion request."""
        self._last_request_id += 1
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
            self._pending_task = None
