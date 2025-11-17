"""
Check Image Updates Tool

Check if newer versions of images are available in registries.
"""

from docker.errors import DockerException, APIError
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class CheckImageUpdatesTool(BaseTool):
    """
    Tool for checking if image updates are available.

    Compares local image digests with registry versions
    to identify available updates.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'check_image_updates' command"""
        return name == "check_image_updates"

    def get_definition(self) -> Tool:
        """Define the check_image_updates tool for MCP"""
        return Tool(
            name="check_image_updates",
            description="Check if newer versions of Docker images are available in registries",
            inputSchema={
                "type": "object",
                "properties": {
                    "image": {
                        "type": "string",
                        "description": "Specific image to check (repository:tag format). Omit to check all local images."
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the check_image_updates command"""
        specific_image = arguments.get("image")

        try:
            # Get images to check
            if specific_image:
                # Check specific image
                try:
                    local_image = self.docker_client.images.get(specific_image)
                    images_to_check = [local_image]
                except Exception:
                    return [TextContent(
                        type="text",
                        text=f"Error: Image '{specific_image}' not found locally"
                    )]
            else:
                # Check all tagged images
                all_images = self.docker_client.images.list()
                # Filter out images without tags (dangling)
                images_to_check = [img for img in all_images if img.tags]

            if not images_to_check:
                return [TextContent(type="text", text="No images to check")]

            # Build output
            lines = ["Image Update Check", "=" * 80, ""]
            lines.append(f"Checking {len(images_to_check)} image(s) for updates...")
            lines.append("")

            updates_available = []
            up_to_date = []
            errors = []

            for image in images_to_check:
                for tag in image.tags:
                    try:
                        # Get local image digest
                        local_digest = image.id

                        if not local_digest:
                            errors.append(f"{tag}: Unable to retrieve local image digest")
                            lines.append("  ✗ Error: Unable to retrieve local image digest")
                            continue

                        # Try to get registry digest by pulling the image metadata
                        # This uses Docker's registry API to check without downloading
                        lines.append(f"Checking: {tag}")

                        try:
                            # Pull the latest metadata from registry
                            # Note: This doesn't download layers, just checks the manifest
                            registry_image = self.docker_client.images.get_registry_data(tag)

                            # Compare digests
                            if registry_image.id and registry_image.id != local_digest:
                                updates_available.append({
                                    'tag': tag,
                                    'local': local_digest[:12],
                                    'registry': registry_image.id[:12],
                                    'status': 'UPDATE AVAILABLE'
                                })
                                lines.append("  ⚠️  Update   available!")
                            else:
                                up_to_date.append(tag)
                                lines.append(f"  ✓ Up to date")

                        except APIError as e:
                            # Image might not be in a public registry or auth required
                            if "404" in str(e) or "not found" in str(e).lower():
                                errors.append(f"{tag}: Not found in registry (might be local-only or private)")
                                lines.append("  ⚠️  Not found in registry")
                            elif "unauthorized" in str(e).lower() or "authentication" in str(e).lower():
                                errors.append(f"{tag}: Authentication required")
                                lines.append(f"  ⚠️  Authentication required")  # noqa: F541
                            else:
                                errors.append(f"{tag}: {str(e)}")
                                lines.append(f"  ✗ Error: {str(e)}")

                    except Exception as e:
                        errors.append(f"{tag}: {str(e)}")
                        lines.append(f"  ✗ Error: {str(e)}")

                    lines.append("")

            # Summary
            lines.append("=" * 80)
            lines.append("Summary:")
            lines.append("")

            if updates_available:
                lines.append(f"⚠️  {len(updates_available)} image(s) with updates available:")
                for update in updates_available:
                    lines.append(f"  • {update['tag']}")
                    lines.append(f"    Local: {update['local']}")
                    lines.append(f"    Registry: {update['registry']}")
                lines.append("")

            if up_to_date:
                lines.append(f"✓ {len(up_to_date)} image(s) up to date")
                lines.append("")

            if errors:
                lines.append(f"⚠️  {len(errors)} error(s) occurred:")
                for error in errors[:5]:  # Show first 5 errors
                    lines.append(f"  • {error}")
                if len(errors) > 5:
                    lines.append(f"  ... and {len(errors) - 5} more")
                lines.append("")

            lines.append("Note: To update an image, use: docker pull <image:tag>")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error checking for updates: {str(e)}")]
