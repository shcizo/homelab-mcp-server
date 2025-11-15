"""
Volumes Tool

List and manage Docker volumes with usage statistics.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class VolumesTool(BaseTool):
    """
    Tool for managing Docker volumes.

    Shows volume name, driver, mount point, size, and identifies
    orphaned volumes not used by any container.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'volumes' command"""
        return name == "volumes"

    def get_definition(self) -> Tool:
        """Define the volumes tool for MCP"""
        return Tool(
            name="volumes",
            description="List Docker volumes with usage statistics and container associations",
            inputSchema={
                "type": "object",
                "properties": {
                    "show_usage": {
                        "type": "boolean",
                        "description": "Show detailed usage statistics (default: true)",
                        "default": True
                    },
                    "orphaned_only": {
                        "type": "boolean",
                        "description": "Show only orphaned volumes (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the volumes command"""
        show_usage = arguments.get("show_usage", True)
        orphaned_only = arguments.get("orphaned_only", False)

        try:
            # Get all volumes
            volumes = self.docker_client.volumes.list()

            if not volumes:
                return [TextContent(type="text", text="No volumes found.")]

            # Get all containers to check volume usage
            containers = self.docker_client.containers.list(all=True)

            # Build volume usage map
            volume_usage = {}  # volume_name -> list of container names
            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume':
                        vol_name = mount.get('Name', '')
                        if vol_name:
                            if vol_name not in volume_usage:
                                volume_usage[vol_name] = []
                            volume_usage[vol_name].append(container.name)

            # Build output
            lines = ["Docker Volumes:", ""]

            orphaned_count = 0
            total_volumes = 0

            for volume in volumes:
                vol_name = volume.name
                vol_attrs = volume.attrs

                # Check if orphaned
                is_orphaned = vol_name not in volume_usage
                if is_orphaned:
                    orphaned_count += 1

                # Skip if filtering for orphaned only
                if orphaned_only and not is_orphaned:
                    continue

                total_volumes += 1

                # Volume info
                driver = vol_attrs.get('Driver', 'unknown')
                mountpoint = vol_attrs.get('Mountpoint', 'N/A')
                created = vol_attrs.get('CreatedAt', 'Unknown')

                lines.append(f"Volume: {vol_name}")
                lines.append(f"  Driver: {driver}")
                lines.append(f"  Mount Point: {mountpoint}")
                lines.append(f"  Created: {created}")

                # Usage information
                if is_orphaned:
                    lines.append(f"  ⚠️  Status: ORPHANED (not used by any container)")
                else:
                    container_list = volume_usage[vol_name]
                    lines.append(f"  ✓ Used by: {', '.join(container_list)} ({len(container_list)} container(s))")

                # Size estimation (if available)
                # Note: Docker doesn't expose volume size directly, would need to check filesystem
                if show_usage:
                    # Get labels if any
                    labels = vol_attrs.get('Labels')
                    if labels:
                        lines.append(f"  Labels: {labels}")

                lines.append("")

            # Summary
            lines.append("=" * 80)
            lines.append(f"Total Volumes: {len(volumes)}")
            if orphaned_count > 0:
                lines.append(f"⚠️  Orphaned Volumes: {orphaned_count}")
                if not orphaned_only:
                    lines.append("\nTip: Run with orphaned_only=true to see only orphaned volumes")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error listing volumes: {str(e)}")]
