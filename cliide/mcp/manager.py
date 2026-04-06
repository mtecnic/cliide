"""MCP server manager for multi-server support."""

from typing import Any, Optional

from cliide.mcp.client import MCPClient
from cliide.mcp.protocol import MCPTool
from cliide.mcp.transport.stdio import StdioTransport
from cliide.mcp.tools import MCPToolWrapper, wrap_mcp_tools
from cliide.utils.logger import log


class MCPServerConfig:
    """Configuration for an MCP server."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        transport: str = "stdio",
        url: str | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize server config.

        Args:
            name: Server name identifier
            command: Command to run (for stdio transport)
            args: Command arguments
            env: Environment variables
            transport: Transport type ("stdio" or "sse")
            url: URL for SSE transport
            enabled: Whether server is enabled
        """
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.transport = transport
        self.url = url
        self.enabled = enabled

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "MCPServerConfig":
        """Create from config dict.

        Args:
            name: Server name
            data: Config dict

        Returns:
            MCPServerConfig instance
        """
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            transport=data.get("transport", "stdio"),
            url=data.get("url"),
            enabled=data.get("enabled", True),
        )


class MCPManager:
    """Manager for multiple MCP server connections.

    Handles starting, stopping, and communicating with multiple MCP servers,
    and provides unified access to all available tools.
    """

    def __init__(self) -> None:
        """Initialize MCP manager."""
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
        self._tools: dict[str, MCPToolWrapper] = {}  # tool_name -> wrapper

    @property
    def connected_servers(self) -> list[str]:
        """Get list of connected server names."""
        return [name for name, client in self._clients.items() if client.is_connected]

    @property
    def all_tools(self) -> list[MCPToolWrapper]:
        """Get all available MCP tools."""
        return list(self._tools.values())

    def add_server(self, config: MCPServerConfig) -> None:
        """Add a server configuration.

        Args:
            config: Server configuration
        """
        self._servers[config.name] = config
        log(f"[MCP_MANAGER] Added server config: {config.name}")

    def remove_server(self, name: str) -> None:
        """Remove a server configuration.

        Args:
            name: Server name
        """
        self._servers.pop(name, None)
        log(f"[MCP_MANAGER] Removed server config: {name}")

    async def connect_server(self, name: str) -> bool:
        """Connect to a configured server.

        Args:
            name: Server name

        Returns:
            True if connection successful
        """
        config = self._servers.get(name)
        if not config:
            log(f"[MCP_MANAGER] Server not configured: {name}")
            return False

        if not config.enabled:
            log(f"[MCP_MANAGER] Server disabled: {name}")
            return False

        # Check if already connected
        if name in self._clients and self._clients[name].is_connected:
            log(f"[MCP_MANAGER] Server already connected: {name}")
            return True

        # Create transport based on config
        if config.transport == "stdio":
            transport = StdioTransport(
                command=config.command,
                args=config.args,
                env=config.env,
            )
        else:
            log(f"[MCP_MANAGER] Unsupported transport: {config.transport}")
            return False

        # Create and connect client
        client = MCPClient(name, transport)

        if await client.connect():
            self._clients[name] = client

            # Register tools from this server
            await self._register_server_tools(client)

            log(f"[MCP_MANAGER] Connected to server: {name}")
            return True

        log(f"[MCP_MANAGER] Failed to connect to server: {name}")
        return False

    async def disconnect_server(self, name: str) -> None:
        """Disconnect from a server.

        Args:
            name: Server name
        """
        client = self._clients.pop(name, None)
        if client:
            await client.disconnect()

            # Remove tools from this server
            self._tools = {
                k: v for k, v in self._tools.items()
                if v.server_name != name
            }

            log(f"[MCP_MANAGER] Disconnected from server: {name}")

    async def connect_all(self) -> int:
        """Connect to all configured and enabled servers.

        Returns:
            Number of successfully connected servers
        """
        connected = 0
        for name, config in self._servers.items():
            if config.enabled:
                if await self.connect_server(name):
                    connected += 1
        return connected

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for name in list(self._clients.keys()):
            await self.disconnect_server(name)

    async def _register_server_tools(self, client: MCPClient) -> None:
        """Register tools from a connected server.

        Args:
            client: Connected MCP client
        """
        # Create wrapper function for calling tools
        async def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            return await client.call_tool(tool_name, arguments)

        # Wrap all tools from this server
        wrapped = wrap_mcp_tools(client.tools, call_tool)

        for tool in wrapped:
            self._tools[tool.name] = tool
            log(f"[MCP_MANAGER] Registered tool: {tool.name}")

    def get_tool(self, name: str) -> MCPToolWrapper | None:
        """Get a tool by name.

        Args:
            name: Tool name (with mcp_ prefix)

        Returns:
            Tool wrapper or None
        """
        return self._tools.get(name)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a tool by name.

        Args:
            tool_name: Tool name (with mcp_ prefix)
            arguments: Tool arguments

        Returns:
            Tool result

        Raises:
            ValueError: If tool not found
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"MCP tool not found: {tool_name}")

        result = await tool.execute(**(arguments or {}))
        return {"success": result.success, "output": result.output, "error": result.error}

    def get_tools_for_registry(self) -> list[MCPToolWrapper]:
        """Get all tools ready to be registered with cliide's ToolRegistry.

        Returns:
            List of tool wrappers
        """
        return list(self._tools.values())


# Global instance
_mcp_manager: MCPManager | None = None


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager instance.

    Returns:
        MCPManager instance
    """
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
