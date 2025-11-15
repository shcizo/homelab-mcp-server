"""
Container Lifecycle Tool

Show container start/restart times and restart history.
"""

from datetime import datetime
from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerLifecycleTool(BaseTool):
    """
    Tool for showing Docker container lifecycle information.

    Displays creation time, start time, restart count, restart policy,
    and identifies containers that restart frequently.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_lifecycle' command"""
        return name == "container_lifecycle"

    def get_definition(self) -> Tool:
        """Define the container_lifecycle tool for MCP"""
        return Tool(
            name="container_lifecycle",
            description="Show container creation, start times, restart history and policies",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of specific container (optional, shows all if not specified)"
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Show all containers including stopped (default: false, running only)",
                        "default": False
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the container_lifecycle command"""
        container_name = arguments.get("container")
        show_all = arguments.get("all", False)

        try:
            # Get containers
            if container_name:
                containers = [self.docker_client.containers.get(container_name)]
            else:
                containers = self.docker_client.containers.list(all=show_all)

            if not containers:
                return [
                    TextContent(
                        type="text",
                        text="No containers found."
                    )
                ]

            # Build lifecycle report
            lines = ["Docker Container Lifecycle Information:", ""]

            for container in containers:
                container.reload()

                name = container.name
                status = container.status

                # Get container attributes
                attrs = container.attrs
                state = attrs.get('State', {})
                host_config = attrs.get('HostConfig', {})

                lines.append(f"Container: {name}")
                lines.append(f"  Status: {status}")

                # Creation time
                created = attrs.get('Created', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        formatted = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                        lines.append(f"  Created: {formatted}")
                    except:
                        lines.append(f"  Created: {created}")

                # Start time
                started_at = state.get('StartedAt', '')
                if started_at and started_at != '0001-01-01T00:00:00Z':
                    try:
                        dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        formatted = dt.strftime('%Y-%m-%d %H:%M:%S UTC')

                        # Calculate uptime if running
                        if status == 'running':
                            now = datetime.now(dt.tzinfo)
                            uptime = now - dt
                            days = uptime.days
                            hours, remainder = divmod(uptime.seconds, 3600)
                            minutes, seconds = divmod(remainder, 60)

                            uptime_str = []
                            if days > 0:
                                uptime_str.append(f"{days}d")
                            if hours > 0:
                                uptime_str.append(f"{hours}h")
                            if minutes > 0:
                                uptime_str.append(f"{minutes}m")
                            if not uptime_str:  # Less than a minute
                                uptime_str.append(f"{seconds}s")

                            lines.append(f"  Started: {formatted} (Uptime: {' '.join(uptime_str)})")
                        else:
                            lines.append(f"  Last Started: {formatted}")
                    except:
                        lines.append(f"  Started: {started_at}")

                # Finished time (if stopped)
                finished_at = state.get('FinishedAt', '')
                if finished_at and finished_at != '0001-01-01T00:00:00Z' and status != 'running':
                    try:
                        dt = datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
                        formatted = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                        lines.append(f"  Finished: {formatted}")
                    except:
                        lines.append(f"  Finished: {finished_at}")

                # Restart count
                restart_count = state.get('RestartCount', 0)
                if restart_count > 0:
                    # Identify frequent restarts (more than 5 is concerning)
                    warning = " ⚠️  FREQUENT RESTARTS" if restart_count > 5 else ""
                    lines.append(f"  Restart Count: {restart_count}{warning}")
                else:
                    lines.append(f"  Restart Count: {restart_count}")

                # Restart policy
                restart_policy = host_config.get('RestartPolicy', {})
                policy_name = restart_policy.get('Name', 'no')
                max_retry = restart_policy.get('MaximumRetryCount', 0)

                policy_display = policy_name
                if policy_name == 'on-failure' and max_retry > 0:
                    policy_display = f"{policy_name} (max: {max_retry})"

                lines.append(f"  Restart Policy: {policy_display}")

                lines.append("")

            result = "\n".join(lines)

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
                    text=f"Error checking lifecycle info: {str(e)}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Unexpected error: {str(e)}"
                )
            ]
