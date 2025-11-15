"""
List Containers Tool

Lists all Docker containers with their status.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ListContainersTool(BaseTool):
    """
    Tool for listing Docker containers.

    Shows container name, image, and status (running/stopped/exited).
    Can filter to show only running containers or all containers.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'list_containers' command"""
        return name == "list_containers"

    def get_definition(self) -> Tool:
        """Define the list_containers tool for MCP"""
        return Tool(
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
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the list_containers command"""
        # Get the 'all' parameter, default to True if not provided
        show_all = arguments.get("all", True)

        try:
            # Call Docker API to get containers
            # This is similar to: docker ps (show_all=False) or docker ps -a (show_all=True)
            containers = self.docker_client.containers.list(all=show_all)

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
