"""
Container Stats Tool

Shows resource usage (CPU, memory, network, disk I/O) for Docker containers.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerStatsTool(BaseTool):
    """
    Tool for showing Docker container resource usage.

    Displays CPU, memory, network I/O, and disk I/O statistics.
    Can show stats for all running containers or a specific container.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_stats' command"""
        return name == "container_stats"

    def get_definition(self) -> Tool:
        """Define the container_stats tool for MCP"""
        return Tool(
            name="container_stats",
            description="Show resource usage (CPU, memory, network, disk I/O) for Docker containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Show all containers (default shows just running)",
                        "default": True
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the container to get stats for"
                    }
                },
                "required": []  # No required parameters
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the container_stats command"""
        # Get parameters
        show_all = arguments.get("all", True)
        container_name = arguments.get("name", None)

        try:
            # Get containers
            containers = self.docker_client.containers.list(all=show_all)

            if container_name:
                # Filter to the specified container
                containers = [c for c in containers if c.name == container_name]
                if not containers:
                    return [
                        TextContent(
                            type="text",
                            text=f"No container found with name: {container_name}"
                        )
                    ]

            # Filter to only running containers (stats only work on running containers)
            containers = [c for c in containers if c.status == 'running']

            if not containers:
                return [
                    TextContent(
                        type="text",
                        text="No running containers found to get stats for."
                    )
                ]

            # Gather stats
            lines = ["Docker Container Stats:", ""]
            for container in containers:
                stats = container.stats(stream=False)

                # Calculate CPU percentage (properly accounting for multiple cores)
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']
                num_cpus = stats['cpu_stats'].get('online_cpus', 1)

                cpu_percent = 0.0
                if system_delta > 0 and cpu_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0

                # Memory stats
                mem_usage = stats['memory_stats']['usage']
                mem_limit = stats['memory_stats']['limit']
                mem_percent = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

                # Network I/O
                networks = stats.get('networks', {})
                total_rx = sum(net.get('rx_bytes', 0) for net in networks.values())
                total_tx = sum(net.get('tx_bytes', 0) for net in networks.values())

                # Disk I/O
                blkio_stats = stats.get('blkio_stats', {})
                io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
                read_bytes = sum(entry.get('value', 0) for entry in io_service_bytes if entry.get('op') == 'read')
                write_bytes = sum(entry.get('value', 0) for entry in io_service_bytes if entry.get('op') == 'write')

                lines.append(f"Container: {container.name}")
                lines.append(f"  CPU Usage: {cpu_percent:.2f}%")
                lines.append(f"  Memory Usage: {mem_usage / (1024 ** 2):.2f} MiB / {mem_limit / (1024 ** 2):.2f} MiB ({mem_percent:.2f}%)")
                lines.append(f"  Network I/O: RX {total_rx / (1024 ** 2):.2f} MiB / TX {total_tx / (1024 ** 2):.2f} MiB")
                lines.append(f"  Disk I/O: Read {read_bytes / (1024 ** 2):.2f} MiB / Write {write_bytes / (1024 ** 2):.2f} MiB")
                lines.append("")

            result = "\n".join(lines)

            return [
                TextContent(
                    type="text",
                    text=result
                )
            ]
        except DockerException as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error connecting to Docker: {str(e)}"
                )
            ]
