"""
Ping Tool

Simple test tool to verify the MCP server is working correctly.
"""

from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class PingTool(BaseTool):
    """
    Simple ping tool for server health check.

    This is the simplest possible tool - it just returns a success message.
    Useful for testing that the MCP server is running and responding.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'ping' command"""
        return name == "ping"

    def get_definition(self) -> Tool:
        """Define the ping tool for MCP"""
        return Tool(
            name="ping",
            description="Simple test tool to verify the server is working",
            inputSchema={
                "type": "object",
                "properties": {},  # No parameters needed
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the ping command - just return success"""
        return [
            TextContent(
                type="text",
                text="Pong! Server is running correctly."
            )
        ]
