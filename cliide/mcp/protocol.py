"""MCP protocol message types and constants.

Based on the Model Context Protocol specification:
https://modelcontextprotocol.io/
"""

from dataclasses import dataclass, field
from typing import Any


# Protocol version
MCP_VERSION = "2024-11-05"


@dataclass
class MCPRequest:
    """JSON-RPC 2.0 request message."""
    method: str
    id: int | str
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class MCPResponse:
    """JSON-RPC 2.0 response message."""
    id: int | str
    result: Any = None
    error: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPResponse":
        """Create from JSON dict."""
        return cls(
            id=data.get("id", 0),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class MCPNotification:
    """JSON-RPC 2.0 notification (no id, no response expected)."""
    method: str
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": self.method,
        }
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class MCPError:
    """MCP error with code and message."""
    code: int
    message: str
    data: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPError":
        """Create from JSON dict."""
        return cls(
            code=data.get("code", -1),
            message=data.get("message", "Unknown error"),
            data=data.get("data"),
        )


# Standard JSON-RPC error codes
class ErrorCode:
    """Standard JSON-RPC and MCP error codes."""
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_ERROR = -32001


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""  # Which server provides this tool

    @classmethod
    def from_dict(cls, data: dict[str, Any], server_name: str = "") -> "MCPTool":
        """Create from JSON dict."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {}),
            server_name=server_name,
        )


@dataclass
class MCPResource:
    """MCP resource definition."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPResource":
        """Create from JSON dict."""
        return cls(
            uri=data.get("uri", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            mime_type=data.get("mimeType", ""),
        )


@dataclass
class MCPPrompt:
    """MCP prompt template definition."""
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MCPPrompt":
        """Create from JSON dict."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", []),
        )


@dataclass
class ServerCapabilities:
    """MCP server capabilities."""
    tools: bool = False
    resources: bool = False
    prompts: bool = False
    logging: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerCapabilities":
        """Create from JSON dict."""
        return cls(
            tools="tools" in data,
            resources="resources" in data,
            prompts="prompts" in data,
            logging="logging" in data,
        )


@dataclass
class ClientCapabilities:
    """MCP client capabilities."""
    roots: bool = True
    sampling: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        caps: dict[str, Any] = {}
        if self.roots:
            caps["roots"] = {"listChanged": True}
        if self.sampling:
            caps["sampling"] = {}
        return caps


@dataclass
class InitializeParams:
    """Parameters for initialize request."""
    protocol_version: str = MCP_VERSION
    client_info: dict[str, str] = field(default_factory=lambda: {
        "name": "cliide",
        "version": "0.1.0"
    })
    capabilities: ClientCapabilities = field(default_factory=ClientCapabilities)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "protocolVersion": self.protocol_version,
            "clientInfo": self.client_info,
            "capabilities": self.capabilities.to_dict(),
        }


@dataclass
class InitializeResult:
    """Result of initialize request."""
    protocol_version: str
    server_info: dict[str, str]
    capabilities: ServerCapabilities

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InitializeResult":
        """Create from JSON dict."""
        return cls(
            protocol_version=data.get("protocolVersion", ""),
            server_info=data.get("serverInfo", {}),
            capabilities=ServerCapabilities.from_dict(data.get("capabilities", {})),
        )
