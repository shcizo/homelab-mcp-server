"""
Homelab MCP Server

This server provides tools for managing Docker containers via the Model Context Protocol.
Claude (or other MCP clients) can use these tools to inspect and manage your homelab.

Architecture:
- Tools are automatically discovered from the tools/ directory
- Each tool implements the BaseTool interface
- ToolRegistry handles discovery and routing
- Supports both stdio (local) and HTTP/SSE (remote) transports
"""

import os
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
    import logging
    logging.info(f"Tool call: {name} with arguments: {arguments}")

    # Find the tool that handles this command
    tool = registry.find_tool(name)

    if tool:
        # Execute the tool and return the result
        result = await tool.execute(arguments)
        logging.info(f"Tool {name} returned: {result[:100] if result else 'None'}...")
        return result
    else:
        # Unknown tool - this shouldn't happen if list_tools() is correct
        logging.error(f"Unknown tool requested: {name}")
        return [
            TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )
        ]


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

async def main_stdio():
    """
    Run server in stdio mode (local communication).

    stdio_server means:
    - Input comes from stdin (standard input)
    - Output goes to stdout (standard output)
    - This is how Claude communicates with the MCP server locally

    It's like running a console app that reads from stdin and writes to stdout,
    but the messages are JSON-RPC formatted.
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main_http():
    """
    Run server in HTTP/SSE mode (remote communication).

    This allows remote access to the MCP server via HTTP with Server-Sent Events.
    Useful for accessing the server from a different machine.
    """
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount

    # Get configuration from environment
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8080"))

    # Create SSE transport - use trailing slash for Mount compatibility
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    # Create Starlette app
    # Mount the handle_post_message as an ASGI app at /messages (Mount adds trailing slash)
    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=sse.handle_post_message),
        ]
    )

    print(f"🚀 Homelab MCP Server starting on http://{host}:{port}")
    print(f"📡 SSE endpoint: http://{host}:{port}/sse")
    print(f"📨 Messages endpoint: http://{host}:{port}/messages")

    # Run the server
    uvicorn.run(app, host=host, port=port)


# This is the standard Python entry point
# When you run: python -m homelab_mcp.server
if __name__ == "__main__":
    import asyncio

    # Check which mode to run in
    mode = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if mode == "http" or mode == "sse":
        # Run in HTTP/SSE mode for remote access
        main_http()
    else:
        # Run in stdio mode for local access (default)
        asyncio.run(main_stdio())
