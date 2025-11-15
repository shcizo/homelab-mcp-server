"""
Container Health Tool

Show health check status for Docker containers.
"""

from datetime import datetime
from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerHealthTool(BaseTool):
    """
    Tool for checking Docker container health status.

    Shows health check results, timestamps, failure counts, and
    identifies containers without health checks configured.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_health' command"""
        return name == "container_health"

    def get_definition(self) -> Tool:
        """Define the container_health tool for MCP"""
        return Tool(
            name="container_health",
            description="Check health status of Docker containers with health checks configured",
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
        """Execute the container_health command"""
        container_name = arguments.get("container")
        show_all = arguments.get("all", False)

        try:
            # Get containers
            if container_name:
                # Get specific container
                containers = [self.docker_client.containers.get(container_name)]
            else:
                # Get all containers (running or all based on parameter)
                containers = self.docker_client.containers.list(all=show_all)

            if not containers:
                return [
                    TextContent(
                        type="text",
                        text="No containers found."
                    )
                ]

            # Build health status report
            lines = ["Docker Container Health Status:", ""]

            for container in containers:
                # Reload to get latest state
                container.reload()

                # Get container basic info
                name = container.name
                status = container.status

                # Get health status from container state
                state = container.attrs.get('State', {})
                health = state.get('Health', None)

                lines.append(f"Container: {name}")
                lines.append(f"  Status: {status}")

                if health:
                    # Container has health checks configured
                    health_status = health.get('Status', 'unknown')
                    failing_streak = health.get('FailingStreak', 0)

                    # Status with symbol
                    status_symbols = {
                        'healthy': '✓',
                        'unhealthy': '✗',
                        'starting': '⏳',
                        'none': '○'
                    }
                    symbol = status_symbols.get(health_status.lower(), '?')

                    lines.append(f"  Health: {symbol} {health_status.upper()}")

                    if failing_streak > 0:
                        lines.append(f"  ⚠️  Consecutive Failures: {failing_streak}")

                    # Get last health check log
                    health_log = health.get('Log', [])
                    if health_log:
                        last_check = health_log[-1]

                        # Parse timestamp
                        start_time = last_check.get('Start', '')
                        if start_time:
                            try:
                                # Parse ISO format timestamp
                                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                                lines.append(f"  Last Check: {formatted_time}")
                            except:
                                lines.append(f"  Last Check: {start_time}")

                        # Show exit code
                        exit_code = last_check.get('ExitCode', 'N/A')
                        output = last_check.get('Output', '').strip()

                        if exit_code != 0 and output:
                            lines.append(f"  Last Output: {output[:100]}...")
                else:
                    # No health check configured
                    lines.append(f"  Health: ○ NO HEALTH CHECK CONFIGURED")

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
                    text=f"Error checking health status: {str(e)}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Unexpected error: {str(e)}"
                )
            ]
