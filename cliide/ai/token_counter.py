"""Token counting utility for context management."""

from typing import Callable


class TokenCounter:
    """Count tokens for context management.

    Uses tiktoken for accurate token counting, with a fallback
    to character-based estimation if tiktoken is unavailable.
    """

    def __init__(self, model: str = "gpt-4"):  # noqa: ARG002
        """Initialize token counter.

        Args:
            model: Model name for tokenizer selection (reserved for future use)
        """
        self._encoder: Callable[[str], list[int]] | None = None
        self._decoder: Callable[[list[int]], str] | None = None
        self._use_fallback = False

        try:
            import tiktoken
            # Use cl100k_base as reasonable approximation for most models
            encoding = tiktoken.get_encoding("cl100k_base")
            self._encoder = encoding.encode
            self._decoder = encoding.decode
        except ImportError:
            # Fallback to character-based estimation
            self._use_fallback = True

    def count(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count (or estimated count if using fallback)
        """
        if not text:
            return 0

        if self._use_fallback:
            # Rough estimation: ~4 chars per token on average
            return len(text) // 4

        return len(self._encoder(text))

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text
        """
        if not text or max_tokens <= 0:
            return ""

        if self._use_fallback:
            # Rough estimation
            max_chars = max_tokens * 4
            if len(text) <= max_chars:
                return text
            # Find a good break point (newline or space)
            truncated = text[:max_chars]
            last_newline = truncated.rfind('\n')
            if last_newline > max_chars * 0.8:
                return truncated[:last_newline]
            return truncated

        tokens = self._encoder(text)
        if len(tokens) <= max_tokens:
            return text

        return self._decoder(tokens[:max_tokens])

    def truncate_from_end(self, text: str, max_tokens: int) -> str:
        """Truncate text from the beginning, keeping the end.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed

        Returns:
            Truncated text (end portion preserved)
        """
        if not text or max_tokens <= 0:
            return ""

        if self._use_fallback:
            max_chars = max_tokens * 4
            if len(text) <= max_chars:
                return text
            return "..." + text[-max_chars:]

        tokens = self._encoder(text)
        if len(tokens) <= max_tokens:
            return text

        return self._decoder(tokens[-max_tokens:])

    def split_by_tokens(self, text: str, chunk_size: int) -> list[str]:
        """Split text into chunks of approximately chunk_size tokens.

        Args:
            text: Text to split
            chunk_size: Target tokens per chunk

        Returns:
            List of text chunks
        """
        if not text or chunk_size <= 0:
            return []

        if self._use_fallback:
            # Split by lines and group
            lines = text.split('\n')
            chunks = []
            current_chunk = []
            current_size = 0

            for line in lines:
                line_size = len(line) // 4  # Estimated tokens
                if current_size + line_size > chunk_size and current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                current_chunk.append(line)
                current_size += line_size

            if current_chunk:
                chunks.append('\n'.join(current_chunk))

            return chunks

        tokens = self._encoder(text)
        chunks = []

        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i:i + chunk_size]
            chunks.append(self._decoder(chunk_tokens))

        return chunks

    def fits_in_budget(self, text: str, budget: int) -> bool:
        """Check if text fits within token budget.

        Args:
            text: Text to check
            budget: Token budget

        Returns:
            True if text fits within budget
        """
        return self.count(text) <= budget

    def remaining_budget(self, text: str, total_budget: int) -> int:
        """Calculate remaining token budget after text.

        Args:
            text: Text already using budget
            total_budget: Total token budget

        Returns:
            Remaining tokens (can be negative if over budget)
        """
        return total_budget - self.count(text)


# Global instance for convenience
_global_counter: TokenCounter | None = None


def get_token_counter() -> TokenCounter:
    """Get the global token counter instance.

    Returns:
        Global TokenCounter instance
    """
    global _global_counter
    if _global_counter is None:
        _global_counter = TokenCounter()
    return _global_counter
