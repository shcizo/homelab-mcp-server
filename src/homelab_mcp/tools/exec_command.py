"""
Exec Command Tool

Run commands inside running containers.
"""

from docker.errors import DockerException, NotFound, APIError
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ExecCommandTool(BaseTool):
    """
    Tool for executing commands in running containers.

    Implements docker exec equivalent with support for working directory,
    environment variables, and user specification.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'exec_command' command"""
        return name == "exec_command"

    def get_definition(self) -> Tool:
        """Define the exec_command tool for MCP"""
        return Tool(
            name="exec_command",
            description="Execute commands inside running containers (docker exec equivalent)",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of the running container"
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute (will be split into shell args)"
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Working directory for the command (optional)"
                    },
                    "user": {
                        "type": "string",
                        "description": "User to run command as (optional, default: container's default user)"
                    },
                    "environment": {
                        "type": "object",
                        "description": "Environment variables to set (optional)",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["container", "command"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the exec_command command"""
        container_name = arguments.get("container")
        command = arguments.get("command")
        workdir = arguments.get("workdir")
        user = arguments.get("user")
        environment = arguments.get("environment", {})

        if not container_name or not command:
            return [TextContent(type="text", text="Error: container and command are required")]

        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)

            # Check if container is running
            if container.status != 'running':
                return [TextContent(
                    type="text",
                    text=f"Error: Container '{container.name}' is not running (status: {container.status})"
                )]

            # Build exec options
            exec_options = {
                'stdout': True,
                'stderr': True,
                'stream': False,
            }

            if workdir:
                exec_options['workdir'] = workdir

            if user:
                exec_options['user'] = user

            if environment:
                # Convert dict to list of "KEY=VALUE" strings
                env_list = [f"{key}={value}" for key, value in environment.items()]
                exec_options['environment'] = env_list

            # Execute the command
            # Note: MCP doesn't support true interactive mode
            exit_code, output = container.exec_run(command, **exec_options)

            # Decode output
            output_text = output.decode('utf-8', errors='replace') if output else ''

            # Build result
            lines = [f"Command Execution: {container.name}", "=" * 80, ""]
            lines.append(f"Command: {command}")
            if workdir:
                lines.append(f"Working Dir: {workdir}")
            if user:
                lines.append(f"User: {user}")
            if environment:
                lines.append(f"Environment: {environment}")
            lines.append(f"Exit Code: {exit_code}")
            lines.append("")
            lines.append("Output:")
            lines.append("-" * 80)
            lines.append(output_text if output_text else "(No output)")
            lines.append("-" * 80)

            if exit_code != 0:
                lines.append("")
                lines.append(f"⚠️  Command failed with exit code {exit_code}")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except NotFound:
            return [TextContent(type="text", text=f"Error: Container '{container_name}' not found")]
        except APIError as e:
            return [TextContent(type="text", text=f"Error executing command: {str(e)}")]
        except DockerException as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
