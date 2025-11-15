"""
Container Logs Tool

Retrieve and display logs from Docker containers.
"""

from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerLogsTool(BaseTool):
    """
    Tool for fetching Docker container logs.

    Supports:
    - Fetching logs from specific containers by name
    - Limiting number of lines (tail)
    - Including timestamps
    - Streaming mode (follow)
    - Both stdout and stderr
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_logs' command"""
        return name == "container_logs"

    def get_definition(self) -> Tool:
        """Define the container_logs tool for MCP"""
        return Tool(
            name="container_logs",
            description="Retrieve and display logs from a specific Docker container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of the container to get logs from"
                    },
                    "tail": {
                        "type": "integer",
                        "description": "Number of lines to show from the end of logs (default: 100)",
                        "default": 100
                    },
                    "timestamps": {
                        "type": "boolean",
                        "description": "Include timestamps in log output (default: true)",
                        "default": True
                    },
                    "follow": {
                        "type": "boolean",
                        "description": "Stream logs in real-time (default: false). Note: MCP doesn't support true streaming, so this fetches recent logs.",
                        "default": False
                    },
                    "stdout": {
                        "type": "boolean",
                        "description": "Include stdout in logs (default: true)",
                        "default": True
                    },
                    "stderr": {
                        "type": "boolean",
                        "description": "Include stderr in logs (default: true)",
                        "default": True
                    }
                },
                "required": ["container"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the container_logs command"""
        # Get parameters
        container_name = arguments.get("container")
        tail = arguments.get("tail", 100)
        timestamps = arguments.get("timestamps", True)
        follow = arguments.get("follow", False)
        stdout = arguments.get("stdout", True)
        stderr = arguments.get("stderr", True)

        # Validate parameters
        if not container_name:
            return [
                TextContent(
                    type="text",
                    text="Error: container name or ID is required"
                )
            ]

        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)

            # Fetch logs
            # Note: MCP doesn't support true streaming, so even with follow=True,
            # we're just getting a snapshot. For true streaming, you'd need to
            # run this in a background process and poll it.
            logs = container.logs(
                stdout=stdout,
                stderr=stderr,
                timestamps=timestamps,
                tail=tail,
                stream=False  # We don't stream in MCP
            )

            # Decode the logs (they come as bytes)
            log_text = logs.decode('utf-8', errors='replace')

            # Format the output
            if not log_text.strip():
                result = f"No logs found for container: {container.name}"
            else:
                # Build header
                header_parts = [
                    f"Logs for container: {container.name}",
                    f"Image: {container.image.tags[0] if container.image.tags else container.image.id[:12]}",
                    f"Status: {container.status}"
                ]

                if tail:
                    header_parts.append(f"Showing last {tail} lines")

                header = "\n".join(header_parts)
                separator = "=" * 80

                result = f"{header}\n{separator}\n\n{log_text}"

            return [
                TextContent(
                    type="text",
                    text=result
                )
            ]

        except NotFound:
            return [
                TextContent(
                    type="text",
                    text=f"Error: Container '{container_name}' not found"
                )
            ]
        except DockerException as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error fetching logs: {str(e)}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Unexpected error: {str(e)}"
                )
            ]
