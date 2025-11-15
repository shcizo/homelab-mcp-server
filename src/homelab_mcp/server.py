"""
Homelab MCP Server

This server provides tools for managing Docker containers via the Model Context Protocol.
Claude (or other MCP clients) can use these tools to inspect and manage your homelab.
"""

import docker
from docker.errors import DockerException
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

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


# ============================================================================
# SERVER CAPABILITIES - What can this server do?
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    This function tells Claude what tools are available.

    In MCP, the client (Claude) first asks "what can you do?"
    This function returns the list of available tools.

    It's like registering endpoints in a REST API - you're declaring
    what operations are available and what parameters they accept.
    """
    return [
        Tool(
            name="list_containers",
            description="List all Docker containers with their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Show all containers (default shows just running)",
                        "default": True
                    }
                },
                "required": []  # No required parameters
            }
        ),
        Tool(
            name="ping",
            description="Simple test tool to verify the server is working",
            inputSchema={
                "type": "object",
                "properties": {},  # No parameters
                "required": []
            }
        )
    ]


# ============================================================================
# TOOL IMPLEMENTATIONS - What do the tools actually do?
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    This function is called when Claude wants to use a tool.

    Flow:
    1. Claude calls a tool (e.g., "list_containers")
    2. MCP routes the request to this function
    3. We check which tool was called (name parameter)
    4. We extract the arguments and execute the logic
    5. We return the result as TextContent

    Think of this as your controller action in C# MVC.
    """

    if name == "ping":
        # Simple test tool
        return [
            TextContent(
                type="text",
                text="Pong! Server is running correctly."
            )
        ]

    elif name == "list_containers":
        # Get the 'all' parameter, default to True if not provided
        show_all = arguments.get("all", True)

        try:
            # Call Docker API to get containers
            # This is similar to: docker ps (show_all=False) or docker ps -a (show_all=True)
            containers = docker_client.containers.list(all=show_all)

            # Format the output
            if not containers:
                result = "No containers found."
            else:
                # Build a nice formatted list
                lines = ["Docker Containers:", ""]
                for container in containers:
                    status = container.status  # running, exited, etc.
                    name = container.name
                    image = container.image.tags[0] if container.image.tags else container.image.id[:12]

                    # Format: ✓/✗ name (image) - status
                    symbol = "✓" if status == "running" else "✗"
                    lines.append(f"{symbol} {name} ({image}) - {status}")

                result = "\n".join(lines)

            return [
                TextContent(
                    type="text",
                    text=result
                )
            ]
        except DockerException as e:
            # If Docker isn't running or there's an error, return a helpful message
            return [
                TextContent(
                    type="text",
                    text=f"Error connecting to Docker: {str(e)}"
                )
            ]

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
