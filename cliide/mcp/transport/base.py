"""Base transport interface for MCP communication."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class Transport(ABC):
    """Abstract base class for MCP transports.

    Transports handle the low-level communication with MCP servers,
    including sending requests and receiving responses.
    """

    @abstractmethod
    async def start(self) -> bool:
        """Start the transport connection.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport and clean up resources."""
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message.

        Args:
            message: JSON-RPC message dict
        """
        pass

    @abstractmethod
    async def receive(self) -> dict[str, Any] | None:
        """Receive a JSON-RPC message.

        Returns:
            JSON-RPC message dict or None if connection closed
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass

    async def receive_stream(self) -> AsyncIterator[dict[str, Any]]:
        """Stream messages from the transport.

        Yields:
            JSON-RPC message dicts
        """
        while self.is_connected:
            message = await self.receive()
            if message is None:
                break
            yield message
