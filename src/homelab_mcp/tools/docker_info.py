"""
Docker Info Tool

Show overall Docker system information.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class DockerInfoTool(BaseTool):
    """
    Tool for displaying Docker system information.

    Shows Docker version, total containers, images, volumes,
    storage driver info, and available storage space.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'docker_info' command"""
        return name == "docker_info"

    def get_definition(self) -> Tool:
        """Define the docker_info tool for MCP"""
        return Tool(
            name="docker_info",
            description="Display Docker system information including version, containers, images, and storage",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the docker_info command"""
        try:
            # Get Docker system info
            info = self.docker_client.info()
            version = self.docker_client.version()

            # Get counts
            containers = self.docker_client.containers.list(all=True)
            running_containers = sum(1 for c in containers if c.status == 'running')
            stopped_containers = len(containers) - running_containers

            images = self.docker_client.images.list(all=True)
            volumes = self.docker_client.volumes.list()

            # Build output
            lines = ["Docker System Information", "=" * 80, ""]

            # Version info
            lines.append("## Version Information")
            lines.append(f"Docker Version: {version.get('Version', 'Unknown')}")
            lines.append(f"API Version: {version.get('ApiVersion', 'Unknown')}")
            lines.append(f"OS/Arch: {info.get('OperatingSystem', 'Unknown')} / {info.get('Architecture', 'Unknown')}")
            lines.append(f"Kernel Version: {info.get('KernelVersion', 'Unknown')}")
            lines.append("")

            # Container stats
            lines.append("## Containers")
            lines.append(f"Total: {info.get('Containers', 0)}")
            lines.append(f"  Running: {running_containers}")
            lines.append(f"  Stopped: {stopped_containers}")
            lines.append(f"  Paused: {info.get('ContainersPaused', 0)}")
            lines.append("")

            # Image stats
            lines.append("## Images")
            lines.append(f"Total: {len(images)}")
            lines.append("")

            # Volume stats
            lines.append("## Volumes")
            lines.append(f"Total: {len(volumes)}")
            lines.append("")

            # Storage info
            lines.append("## Storage")
            lines.append(f"Storage Driver: {info.get('Driver', 'Unknown')}")

            # Docker Root Dir
            docker_root_dir = info.get('DockerRootDir', 'Unknown')
            lines.append(f"Docker Root Dir: {docker_root_dir}")

            # System resources
            lines.append("")
            lines.append("## System Resources")
            lines.append(f"CPUs: {info.get('NCPU', 'Unknown')}")

            total_memory = info.get('MemTotal', 0)
            total_memory_gb = total_memory / (1024 ** 3) if total_memory else 0
            lines.append(f"Total Memory: {total_memory_gb:.2f} GB")

            # Server version and experimental features
            lines.append("")
            lines.append("## Server Configuration")
            lines.append(f"Server Version: {info.get('ServerVersion', 'Unknown')}")
            lines.append(f"Experimental: {info.get('ExperimentalBuild', False)}")
            lines.append(f"Live Restore Enabled: {info.get('LiveRestoreEnabled', False)}")

            # Registry info
            if 'RegistryConfig' in info and 'IndexConfigs' in info['RegistryConfig']:
                lines.append("")
                lines.append("## Registry Configuration")
                for registry_name, registry_info in info['RegistryConfig']['IndexConfigs'].items():
                    lines.append(f"  {registry_name}: {registry_info.get('Official', False) and 'Official' or 'Custom'}")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error getting Docker info: {str(e)}")]
