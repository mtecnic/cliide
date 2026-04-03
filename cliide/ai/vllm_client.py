"""VLLM client for AI-powered features."""

import asyncio
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI, OpenAIError

from cliide.core.config import get_config


class VLLMClient:
    """Client for interacting with VLLM server via OpenAI-compatible API."""

    def __init__(self, config=None) -> None:
        """Initialize VLLM client.

        Args:
            config: Optional Config instance. If None, uses get_config()
        """
        self.config = config if config is not None else get_config()
        self.client: Optional[AsyncOpenAI] = None
        self.connected = False
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the OpenAI client with VLLM endpoint."""
        from cliide.utils.logger import log

        try:
            # Use configured API key, or "EMPTY" if not set
            api_key = self.config.vllm.api_key if self.config.vllm.api_key else "EMPTY"
            log(f"[VLLM_CLIENT] Initializing with URL: {self.config.vllm.base_url}, API key: {'***' if self.config.vllm.api_key else 'EMPTY'}")

            self.client = AsyncOpenAI(
                base_url=self.config.vllm.base_url,
                api_key=api_key,
                timeout=self.config.vllm.timeout,
            )
            self.connected = True
            log("[VLLM_CLIENT] Client initialized successfully")
        except Exception as e:
            log(f"[VLLM_CLIENT] Failed to initialize: {e}")
            print(f"Failed to initialize VLLM client: {e}")
            self.connected = False

    async def check_connection(self) -> bool:
        """Check if VLLM server is reachable.

        Returns:
            True if server is reachable, False otherwise
        """
        if not self.client:
            return False

        try:
            # Try to list models as a health check
            await self.client.models.list()
            self.connected = True
            return True
        except Exception:
            self.connected = False
            return False

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
    ) -> str | AsyncIterator[str] | dict:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
            temperature: Sampling temperature (overrides config)
            max_tokens: Max tokens to generate (overrides config)
            tools: Optional list of tool definitions (OpenAI function format)
            tool_choice: Tool choice strategy: "auto", "none", or specific tool

        Returns:
            Complete response string or async iterator of chunks or dict (if tools used)

        Raises:
            OpenAIError: If API request fails
        """
        if not self.client:
            raise OpenAIError("VLLM client not initialized")

        temp = temperature if temperature is not None else self.config.vllm.temperature
        max_tok = max_tokens if max_tokens is not None else self.config.vllm.max_tokens

        try:
            # Build request parameters
            request_params = {
                "model": self.config.vllm.model,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tok,
                "stream": stream,
            }

            # Add tools if provided
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice

            response = await self.client.chat.completions.create(**request_params)

            if stream:
                return self._stream_response(response)
            else:
                # If tools were provided, return full response dict for tool_calls
                if tools:
                    return response.model_dump()
                else:
                    return response.choices[0].message.content or ""

        except Exception as e:
            raise OpenAIError(f"Chat completion failed: {e}")

    async def _stream_response(self, response: AsyncIterator) -> AsyncIterator[str]:
        """Stream response chunks.

        Args:
            response: OpenAI streaming response

        Yields:
            Response chunks
        """
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete(self, prompt: str, **kwargs: dict) -> str:
        """Simple completion helper.

        Args:
            prompt: User prompt
            **kwargs: Additional arguments for chat_completion

        Returns:
            AI response
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat_completion(messages, stream=False, **kwargs)
        return response if isinstance(response, str) else ""

    async def complete_with_system(
        self, system_prompt: str, user_prompt: str, **kwargs: dict
    ) -> str:
        """Completion with system prompt.

        Args:
            system_prompt: System prompt to set context
            user_prompt: User prompt
            **kwargs: Additional arguments for chat_completion

        Returns:
            AI response
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await self.chat_completion(messages, stream=False, **kwargs)
        return response if isinstance(response, str) else ""

    async def stream_complete(self, prompt: str, **kwargs: dict) -> AsyncIterator[str]:
        """Stream a completion.

        Args:
            prompt: User prompt
            **kwargs: Additional arguments for chat_completion

        Yields:
            Response chunks
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat_completion(messages, stream=True, **kwargs)

        if isinstance(response, str):
            yield response
        else:
            async for chunk in response:
                yield chunk

    async def stream_with_system(
        self, system_prompt: str, user_prompt: str, **kwargs: dict
    ) -> AsyncIterator[str]:
        """Stream completion with system prompt.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional arguments for chat_completion

        Yields:
            Response chunks
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await self.chat_completion(messages, stream=True, **kwargs)

        if isinstance(response, str):
            yield response
        else:
            async for chunk in response:
                yield chunk


# Global client instance
_client: Optional[VLLMClient] = None


def get_client() -> VLLMClient:
    """Get the global VLLM client instance.

    Returns:
        VLLMClient instance
    """
    global _client
    if _client is None:
        _client = VLLMClient()
    return _client


def reset_client() -> None:
    """Reset the global VLLM client instance.

    This forces a new client to be created on the next get_client() call,
    which will use the latest configuration.
    """
    from cliide.utils.logger import log

    global _client
    log("[VLLM_CLIENT] Resetting global client instance")
    _client = None
