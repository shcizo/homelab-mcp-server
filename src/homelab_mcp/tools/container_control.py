"""
Container Control Tool

Start, stop, restart, pause, and unpause Docker containers.
"""

from docker.errors import DockerException, NotFound, APIError
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerControlTool(BaseTool):
    """
    Tool for controlling Docker container lifecycle.

    Supports start, stop, restart, pause, and unpause operations.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_control' command"""
        return name == "container_control"

    def get_definition(self) -> Tool:
        """Define the container_control tool for MCP"""
        return Tool(
            name="container_control",
            description="Start, stop, restart, pause, or unpause Docker containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of the container"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["start", "stop", "restart", "pause", "unpause"]
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds for stop operation (default: 10)",
                        "default": 10
                    }
                },
                "required": ["container", "action"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the container_control command"""
        container_name = arguments.get("container")
        action = arguments.get("action")
        timeout = arguments.get("timeout", 10)

        if not container_name or not action:
            return [TextContent(type="text", text="Error: container and action are required")]

        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)

            # Perform the action
            if action == "start":
                container.start()
                result = f"✅ Container '{container.name}' started successfully"

            elif action == "stop":
                container.stop(timeout=timeout)
                result = f"✅ Container '{container.name}' stopped successfully (timeout: {timeout}s)"

            elif action == "restart":
                container.restart(timeout=timeout)
                result = f"✅ Container '{container.name}' restarted successfully"

            elif action == "pause":
                container.pause()
                result = f"✅ Container '{container.name}' paused successfully"

            elif action == "unpause":
                container.unpause()
                result = f"✅ Container '{container.name}' unpaused successfully"

            else:
                result = f"❌ Unknown action: {action}"

            # Reload and show new status
            container.reload()
            result += f"\nCurrent Status: {container.status}"

            return [TextContent(type="text", text=result)]

        except NotFound:
            return [TextContent(type="text", text=f"Error: Container '{container_name}' not found")]
        except APIError as e:
            # Container might already be in desired state
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        except DockerException as e:
            return [TextContent(type="text", text=f"Error controlling container: {str(e)}")]
