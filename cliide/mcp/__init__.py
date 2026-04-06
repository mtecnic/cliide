"""MCP (Model Context Protocol) client implementation for cliide.

MCP is a protocol for connecting AI models to external tools and services.
This module provides a client implementation that can connect to MCP servers
and expose their tools to the cliide agent system.
"""

from cliide.mcp.client import MCPClient
from cliide.mcp.manager import MCPManager, get_mcp_manager
from cliide.mcp.protocol import MCPRequest, MCPResponse, MCPTool, MCPError

__all__ = [
    "MCPClient",
    "MCPManager",
    "get_mcp_manager",
    "MCPRequest",
    "MCPResponse",
    "MCPTool",
    "MCPError",
]
