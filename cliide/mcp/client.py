"""MCP client for connecting to MCP servers."""

import asyncio
from typing import Any

from cliide.mcp.protocol import (
    MCPRequest,
    MCPResponse,
    MCPNotification,
    MCPTool,
    MCPResource,
    MCPPrompt,
    MCPError,
    InitializeParams,
    InitializeResult,
    ServerCapabilities,
)
from cliide.mcp.transport.base import Transport
from cliide.utils.logger import log


class MCPClient:
    """Client for communicating with an MCP server."""

    def __init__(self, name: str, transport: Transport) -> None:
        """Initialize MCP client.

        Args:
            name: Name identifier for this server connection
            transport: Transport implementation to use
        """
        self.name = name
        self._transport = transport
        self._request_id = 0
        self._pending_requests: dict[int | str, asyncio.Future] = {}
        self._receive_task: asyncio.Task | None = None

        # Server info after initialization
        self._initialized = False
        self._server_info: dict[str, str] = {}
        self._capabilities: ServerCapabilities | None = None

        # Cached capabilities
        self._tools: list[MCPTool] = []
        self._resources: list[MCPResource] = []
        self._prompts: list[MCPPrompt] = []

    @property
    def is_connected(self) -> bool:
        """Check if client is connected and initialized."""
        return self._transport.is_connected and self._initialized

    @property
    def capabilities(self) -> ServerCapabilities | None:
        """Get server capabilities."""
        return self._capabilities

    @property
    def tools(self) -> list[MCPTool]:
        """Get cached tools from server."""
        return self._tools

    async def connect(self) -> bool:
        """Connect to the MCP server and initialize.

        Returns:
            True if connection and initialization successful
        """
        # Start transport
        if not await self._transport.start():
            return False

        # Start receive loop
        self._receive_task = asyncio.create_task(self._receive_loop())

        # Initialize protocol
        try:
            result = await self._initialize()
            if result:
                self._initialized = True
                self._server_info = result.server_info
                self._capabilities = result.capabilities
                log(f"[MCP_CLIENT:{self.name}] Initialized with server: {result.server_info}")

                # Fetch tools if supported
                if self._capabilities and self._capabilities.tools:
                    await self._fetch_tools()

                return True
            else:
                log(f"[MCP_CLIENT:{self.name}] Initialization failed")
                await self.disconnect()
                return False

        except Exception as e:
            log(f"[MCP_CLIENT:{self.name}] Initialization error: {e}")
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._initialized = False

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(ConnectionError("Client disconnected"))
        self._pending_requests.clear()

        # Stop transport
        await self._transport.stop()

    async def _initialize(self) -> InitializeResult | None:
        """Send initialize request to server.

        Returns:
            InitializeResult or None if failed
        """
        params = InitializeParams()
        response = await self._request("initialize", params.to_dict())

        if response and response.result:
            # Send initialized notification
            await self._notify("notifications/initialized", {})
            return InitializeResult.from_dict(response.result)

        return None

    async def _fetch_tools(self) -> None:
        """Fetch available tools from server."""
        response = await self._request("tools/list", {})
        if response and response.result:
            tools_data = response.result.get("tools", [])
            self._tools = [
                MCPTool.from_dict(t, server_name=self.name)
                for t in tools_data
            ]
            log(f"[MCP_CLIENT:{self.name}] Loaded {len(self._tools)} tools")

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a tool on the server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result dict

        Raises:
            MCPError: If tool call fails
        """
        params = {
            "name": tool_name,
            "arguments": arguments or {},
        }

        response = await self._request("tools/call", params)

        if response and response.error:
            error = MCPError.from_dict(response.error)
            raise Exception(f"MCP tool error: {error.message} (code {error.code})")

        if response and response.result:
            return response.result

        raise Exception("No result from tool call")

    async def list_resources(self) -> list[MCPResource]:
        """List available resources from server.

        Returns:
            List of MCPResource
        """
        if not self._capabilities or not self._capabilities.resources:
            return []

        response = await self._request("resources/list", {})
        if response and response.result:
            resources_data = response.result.get("resources", [])
            self._resources = [MCPResource.from_dict(r) for r in resources_data]
            return self._resources

        return []

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource from the server.

        Args:
            uri: Resource URI

        Returns:
            Resource content dict
        """
        response = await self._request("resources/read", {"uri": uri})

        if response and response.error:
            error = MCPError.from_dict(response.error)
            raise Exception(f"MCP resource error: {error.message}")

        if response and response.result:
            return response.result

        raise Exception("No result from resource read")

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> MCPResponse | None:
        """Send a request and wait for response.

        Args:
            method: RPC method name
            params: Request parameters
            timeout: Timeout in seconds

        Returns:
            MCPResponse or None if failed
        """
        self._request_id += 1
        request_id = self._request_id

        request = MCPRequest(
            method=method,
            id=request_id,
            params=params,
        )

        # Create future for response
        future: asyncio.Future[MCPResponse] = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Send request
            await self._transport.send(request.to_dict())

            # Wait for response
            return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            log(f"[MCP_CLIENT:{self.name}] Request {method} timed out")
            return None
        except Exception as e:
            log(f"[MCP_CLIENT:{self.name}] Request {method} failed: {e}")
            return None
        finally:
            self._pending_requests.pop(request_id, None)

    async def _notify(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification (no response expected).

        Args:
            method: RPC method name
            params: Notification parameters
        """
        notification = MCPNotification(method=method, params=params)
        await self._transport.send(notification.to_dict())

    async def _receive_loop(self) -> None:
        """Background task to receive and dispatch messages."""
        try:
            async for message in self._transport.receive_stream():
                await self._handle_message(message)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log(f"[MCP_CLIENT:{self.name}] Receive loop error: {e}")

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle an incoming JSON-RPC message.

        Args:
            message: JSON-RPC message dict
        """
        # Check if this is a response to a pending request
        if "id" in message and message["id"] in self._pending_requests:
            request_id = message["id"]
            future = self._pending_requests.get(request_id)
            if future and not future.done():
                response = MCPResponse.from_dict(message)
                future.set_result(response)
            return

        # Handle notifications from server
        method = message.get("method", "")
        if method:
            log(f"[MCP_CLIENT:{self.name}] Received notification: {method}")
            # Could handle specific notifications here (e.g., tool updates)
