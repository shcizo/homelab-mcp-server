"""
Cleanup Images Tool

Remove unused and dangling images to free disk space.
"""

from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class CleanupImagesTool(BaseTool):
    """
    Tool for cleaning up unused and dangling Docker images.

    Shows space that will be freed and removes images with
    safety confirmation.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'cleanup_images' command"""
        return name == "cleanup_images"

    def get_definition(self) -> Tool:
        """Define the cleanup_images tool for MCP"""
        return Tool(
            name="cleanup_images",
            description="Remove unused and dangling images to free disk space (with safety confirmation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be deleted without actually deleting (default: true)",
                        "default": True
                    },
                    "dangling_only": {
                        "type": "boolean",
                        "description": "Remove only dangling images (untagged) (default: false)",
                        "default": False
                    },
                    "all_unused": {
                        "type": "boolean",
                        "description": "Remove all unused images, not just dangling (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the cleanup_images command"""
        dry_run = arguments.get("dry_run", True)
        dangling_only = arguments.get("dangling_only", False)
        all_unused = arguments.get("all_unused", False)

        try:
            # Get all images
            all_images = self.docker_client.images.list(all=True)

            if not all_images:
                return [TextContent(type="text", text="No images found.")]

            # Get all containers to check image usage
            containers = self.docker_client.containers.list(all=True)
            used_images = set()
            for container in containers:
                used_images.add(container.image.id)

            # Find images to remove
            images_to_remove = []
            total_size = 0

            for image in all_images:
                is_dangling = not image.tags or image.tags == []
                is_unused = image.id not in used_images

                # Determine if image should be removed based on criteria
                should_remove = False
                if dangling_only and is_dangling:
                    should_remove = True
                elif all_unused and is_unused:
                    should_remove = True
                elif not dangling_only and not all_unused and is_dangling:
                    # Default behavior: remove dangling images only
                    should_remove = True

                if should_remove:
                    images_to_remove.append(image)
                    size = image.attrs.get('Size', 0)
                    total_size += size

            if not images_to_remove:
                mode = "dangling" if dangling_only else ("all unused" if all_unused else "dangling")
                return [TextContent(
                    type="text",
                    text=f"No {mode} images found to clean up."
                )]

            # Build output
            lines = ["Image Cleanup", "=" * 80, ""]

            if dry_run:
                lines.append("⚠️  DRY RUN MODE - No images will be deleted")
                lines.append("")

            mode_desc = "dangling" if dangling_only else ("all unused" if all_unused else "dangling")
            lines.append(f"Found {len(images_to_remove)} {mode_desc} image(s):")
            lines.append(f"Total space to be freed: {total_size / (1024**3):.2f} GB")
            lines.append("")

            for image in images_to_remove:
                image_id = image.id.split(':')[1][:12]
                tags = image.tags if image.tags else ["<none>"]
                size_mb = image.attrs.get('Size', 0) / (1024 ** 2)

                is_dangling = not image.tags or image.tags == []
                is_unused = image.id not in used_images

                status = []
                if is_dangling:
                    status.append("DANGLING")
                if is_unused:
                    status.append("UNUSED")

                status_str = f" [{', '.join(status)}]" if status else ""

                lines.append(f"• {', '.join(tags)}")
                lines.append(f"  ID: {image_id}")
                lines.append(f"  Size: {size_mb:.2f} MB{status_str}")
                lines.append("")

            # Perform deletion if not dry run
            if not dry_run:
                lines.append("=" * 80)
                lines.append("Deleting images...")
                lines.append("")

                deleted_count = 0
                freed_space = 0
                errors = []

                for image in images_to_remove:
                    image_id = image.id.split(':')[1][:12]
                    size = image.attrs.get('Size', 0)

                    try:
                        self.docker_client.images.remove(image.id, force=False)
                        lines.append(f"✓ Deleted: {image_id}")
                        deleted_count += 1
                        freed_space += size
                    except Exception as e:
                        error_msg = f"✗ Failed to delete {image_id}: {str(e)}"
                        lines.append(error_msg)
                        errors.append(error_msg)

                lines.append("")
                lines.append("=" * 80)
                lines.append(f"Summary: {deleted_count} image(s) deleted")
                lines.append(f"Space freed: {freed_space / (1024**3):.2f} GB")
                if errors:
                    lines.append(f"Errors: {len(errors)} image(s) failed to delete")
            else:
                lines.append("=" * 80)
                lines.append("To actually delete these images, run with: dry_run=false")
                lines.append("")
                lines.append("⚠️  WARNING: This action is IRREVERSIBLE!")
                lines.append("⚠️  Deleted images will need to be pulled again if needed!")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error cleaning up images: {str(e)}")]
