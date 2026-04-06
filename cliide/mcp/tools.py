"""MCP tool wrapper for cliide's tool system."""

from typing import Any

from cliide.ai.tools.base import Tool, ToolResult
from cliide.mcp.protocol import MCPTool
from cliide.utils.logger import log


class MCPToolWrapper(Tool):
    """Wrapper that exposes an MCP tool as a cliide Tool.

    This allows MCP tools to be seamlessly integrated into cliide's
    agent tool system alongside native tools.
    """

    def __init__(
        self,
        mcp_tool: MCPTool,
        call_func,
    ) -> None:
        """Initialize MCP tool wrapper.

        Args:
            mcp_tool: MCP tool definition
            call_func: Async function to call the tool (tool_name, arguments) -> result
        """
        self._mcp_tool = mcp_tool
        self._call_func = call_func

        # Build parameters schema from MCP input_schema
        parameters = self._convert_schema(mcp_tool.input_schema)

        super().__init__(
            name=f"mcp_{mcp_tool.server_name}_{mcp_tool.name}",
            description=f"[MCP:{mcp_tool.server_name}] {mcp_tool.description}",
            parameters=parameters,
            requires_confirmation=False,  # MCP tools run externally
        )

    @property
    def server_name(self) -> str:
        """Get the MCP server name."""
        return self._mcp_tool.server_name

    @property
    def original_name(self) -> str:
        """Get the original MCP tool name."""
        return self._mcp_tool.name

    def _convert_schema(self, input_schema: dict[str, Any]) -> dict[str, Any]:
        """Convert MCP input schema to cliide parameter format.

        Args:
            input_schema: MCP tool input schema

        Returns:
            Parameter schema dict
        """
        if not input_schema:
            return {"type": "object", "properties": {}, "required": []}

        # MCP uses JSON Schema, which is compatible with our format
        return {
            "type": "object",
            "properties": input_schema.get("properties", {}),
            "required": input_schema.get("required", []),
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the MCP tool.

        Args:
            **kwargs: Tool arguments

        Returns:
            ToolResult with output or error
        """
        try:
            log(f"[MCP_TOOL] Calling {self.original_name} on {self.server_name}")

            # Call the MCP tool via the client
            result = await self._call_func(self.original_name, kwargs)

            # Extract content from result
            content = result.get("content", [])
            if isinstance(content, list):
                # Format content items
                output_parts = []
                for item in content:
                    if item.get("type") == "text":
                        output_parts.append(item.get("text", ""))
                    elif item.get("type") == "image":
                        output_parts.append(f"[Image: {item.get('mimeType', 'image')}]")
                    elif item.get("type") == "resource":
                        output_parts.append(f"[Resource: {item.get('uri', '')}]")
                output = "\n".join(output_parts)
            else:
                output = str(content)

            # Check for error flag
            if result.get("isError"):
                return ToolResult(success=False, error=output)

            return ToolResult(success=True, output=output)

        except Exception as e:
            log(f"[MCP_TOOL] Error calling {self.original_name}: {e}")
            return ToolResult(success=False, error=str(e))


def wrap_mcp_tools(
    tools: list[MCPTool],
    call_func,
) -> list[MCPToolWrapper]:
    """Wrap multiple MCP tools.

    Args:
        tools: List of MCP tool definitions
        call_func: Async function to call tools

    Returns:
        List of wrapped tools
    """
    return [MCPToolWrapper(tool, call_func) for tool in tools]
