"""
Cleanup Volumes Tool

Remove volumes not attached to any container.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class CleanupVolumesTool(BaseTool):
    """
    Tool for cleaning up orphaned Docker volumes.

    Identifies volumes not used by any container and optionally
    removes them to free disk space.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'cleanup_volumes' command"""
        return name == "cleanup_volumes"

    def get_definition(self) -> Tool:
        """Define the cleanup_volumes tool for MCP"""
        return Tool(
            name="cleanup_volumes",
            description="Remove orphaned volumes not attached to any container (with safety confirmation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be deleted without actually deleting (default: true)",
                        "default": True
                    },
                    "exclude": {
                        "type": "array",
                        "description": "List of volume names to exclude from cleanup",
                        "items": {"type": "string"},
                        "default": []
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the cleanup_volumes command"""
        dry_run = arguments.get("dry_run", True)
        exclude = arguments.get("exclude", [])

        try:
            # Get all volumes
            volumes = self.docker_client.volumes.list()

            if not volumes:
                return [TextContent(type="text", text="No volumes found.")]

            # Get all containers to check volume usage
            containers = self.docker_client.containers.list(all=True)

            # Build volume usage map
            volume_usage = {}
            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume':
                        vol_name = mount.get('Name', '')
                        if vol_name:
                            if vol_name not in volume_usage:
                                volume_usage[vol_name] = []
                            volume_usage[vol_name].append(container.name)

            # Find orphaned volumes
            orphaned_volumes = []
            for volume in volumes:
                vol_name = volume.name
                is_orphaned = vol_name not in volume_usage

                # Check if excluded
                if vol_name in exclude:
                    continue

                if is_orphaned:
                    orphaned_volumes.append(volume)

            if not orphaned_volumes:
                return [TextContent(
                    type="text",
                    text="No orphaned volumes found. All volumes are in use."
                )]

            # Build output
            lines = ["Orphaned Volume Cleanup", "=" * 80, ""]

            if dry_run:
                lines.append("⚠️  DRY RUN MODE - No volumes will be deleted")
                lines.append("")

            lines.append(f"Found {len(orphaned_volumes)} orphaned volume(s):")
            lines.append("")

            for volume in orphaned_volumes:
                vol_attrs = volume.attrs
                driver = vol_attrs.get('Driver', 'unknown')
                mountpoint = vol_attrs.get('Mountpoint', 'N/A')
                created = vol_attrs.get('CreatedAt', 'Unknown')

                lines.append(f"• {volume.name}")
                lines.append(f"  Driver: {driver}")
                lines.append(f"  Mount Point: {mountpoint}")
                lines.append(f"  Created: {created}")
                lines.append("")

            # Perform deletion if not dry run
            if not dry_run:
                lines.append("=" * 80)
                lines.append("Deleting volumes...")
                lines.append("")

                deleted_count = 0
                errors = []

                for volume in orphaned_volumes:
                    try:
                        volume.remove()
                        lines.append(f"✓ Deleted: {volume.name}")
                        deleted_count += 1
                    except Exception as e:
                        error_msg = f"✗ Failed to delete {volume.name}: {str(e)}"
                        lines.append(error_msg)
                        errors.append(error_msg)

                lines.append("")
                lines.append("=" * 80)
                lines.append(f"Summary: {deleted_count} volume(s) deleted")
                if errors:
                    lines.append(f"Errors: {len(errors)} volume(s) failed to delete")
            else:
                lines.append("=" * 80)
                lines.append("To actually delete these volumes, run with: dry_run=false")
                lines.append("")
                lines.append("⚠️  WARNING: This action is IRREVERSIBLE!")
                lines.append("⚠️  Make sure you have backups of any important data!")

            if exclude:
                lines.append("")
                lines.append(f"Excluded volumes: {', '.join(exclude)}")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error cleaning up volumes: {str(e)}")]
