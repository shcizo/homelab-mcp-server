"""
Homelab MCP Server

This server provides tools for managing Docker containers via the Model Context Protocol.
Claude (or other MCP clients) can use these tools to inspect and manage your homelab.

Architecture:
- Tools are automatically discovered from the tools/ directory
- Each tool implements the BaseTool interface
- ToolRegistry handles discovery and routing
"""

import docker
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tool_registry import ToolRegistry

# ============================================================================
# INITIALIZATION
# ============================================================================

# Create the MCP server instance
# Think of this like creating a WebAPI service in C#
server = Server("homelab-mcp-server")

# Create Docker client
# This connects to your local Docker daemon (usually via /var/run/docker.sock)
# Similar to creating a HttpClient - it's reused across requests
docker_client = docker.from_env()

# Create the tool registry
# This automatically discovers and loads all tools from the tools/ directory
registry = ToolRegistry(docker_client)


# ============================================================================
# SERVER CAPABILITIES - What can this server do?
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    This function tells Claude what tools are available.

    In MCP, the client (Claude) first asks "what can you do?"
    This function returns the list of available tools.

    The registry automatically discovers all tools, so adding a new tool
    is as simple as creating a new file in tools/ that inherits from BaseTool.
    """
    return registry.get_tool_definitions()


# ============================================================================
# TOOL EXECUTION - Route commands to the right tool
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    This function is called when Claude wants to use a tool.

    Flow:
    1. Claude calls a tool (e.g., "list_containers")
    2. MCP routes the request to this function
    3. We ask the registry to find the tool that handles this command
    4. The tool executes and returns the result
    5. We return the result to Claude

    The registry uses the handles() method on each tool to determine
    which tool should handle the command.
    """
    # Find the tool that handles this command
    tool = registry.find_tool(name)

    if tool:
        # Execute the tool and return the result
        return await tool.execute(arguments)
    else:
        # Unknown tool - this shouldn't happen if list_tools() is correct
        return [
            TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )
        ]


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

async def main():
    """
    Main entry point for the server.

    stdio_server means:
    - Input comes from stdin (standard input)
    - Output goes to stdout (standard output)
    - This is how Claude communicates with the MCP server

    It's like running a console app that reads from stdin and writes to stdout,
    but the messages are JSON-RPC formatted.
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


# This is the standard Python entry point
# When you run: python server.py
if __name__ == "__main__":
    import asyncio

    # Run the async main function
    # This is like Program.Main() in C#, but for async
    asyncio.run(main())
