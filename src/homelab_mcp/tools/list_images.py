"""
List Images Tool

Show all Docker images on the system.
"""

from datetime import datetime
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ListImagesTool(BaseTool):
    """
    Tool for listing Docker images.

    Shows image ID, repository, tag, size, creation date, and
    identifies dangling/unused images.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'list_images' command"""
        return name == "list_images"

    def get_definition(self) -> Tool:
        """Define the list_images tool for MCP"""
        return Tool(
            name="list_images",
            description="List all Docker images with size, tags, and usage information",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Show all images including dangling (default: true)",
                        "default": True
                    },
                    "show_dangling_only": {
                        "type": "boolean",
                        "description": "Show only dangling images (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the list_images command"""
        show_all = arguments.get("all", True)
        show_dangling_only = arguments.get("show_dangling_only", False)

        try:
            # Get all images
            if show_dangling_only:
                images = self.docker_client.images.list(filters={"dangling": True})
            else:
                images = self.docker_client.images.list(all=show_all)

            if not images:
                return [TextContent(type="text", text="No images found.")]

            # Get all containers to check image usage
            containers = self.docker_client.containers.list(all=True)
            used_images = set()
            for container in containers:
                used_images.add(container.image.id)

            # Build output
            lines = ["Docker Images:", ""]

            total_size = 0
            dangling_count = 0
            unused_count = 0

            for image in images:
                # Get image details
                image_id = image.id.split(':')[1][:12]  # Short ID
                tags = image.tags if image.tags else ["<none>:<none>"]
                size_mb = image.attrs.get('Size', 0) / (1024 ** 2)
                total_size += size_mb

                # Creation date
                created = image.attrs.get('Created', '')
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        created_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        created_str = created
                else:
                    created_str = 'Unknown'

                # Check if dangling or unused
                is_dangling = not image.tags or image.tags == []
                is_unused = image.id not in used_images

                if is_dangling:
                    dangling_count += 1
                if is_unused:
                    unused_count += 1

                # Format each tag as a separate line for multi-tag images
                for tag in tags:
                    repo_tag = tag if tag != "<none>:<none>" else "<none>"

                    # Build status indicators
                    status = []
                    if is_dangling:
                        status.append("⚠️ DANGLING")
                    if is_unused:
                        status.append("○ UNUSED")

                    status_str = f" ({', '.join(status)})" if status else ""

                    lines.append(f"• {repo_tag}")
                    lines.append(f"  ID: {image_id}")
                    lines.append(f"  Size: {size_mb:.2f} MB")
                    lines.append(f"  Created: {created_str}{status_str}")
                    lines.append("")

            # Summary
            lines.append("=" * 80)
            lines.append(f"Total Images: {len(images)}")
            lines.append(f"Total Size: {total_size:.2f} MB ({total_size / 1024:.2f} GB)")
            if dangling_count > 0:
                lines.append(f"⚠️  Dangling Images: {dangling_count}")
            if unused_count > 0:
                lines.append(f"○ Unused Images: {unused_count}")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error listing images: {str(e)}")]
