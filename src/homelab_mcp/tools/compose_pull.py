"""
Compose Pull Tool

Pull new images for compose services without restarting.
"""

import subprocess
from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ComposePullTool(BaseTool):
    """
    Tool for pulling updated images for Docker Compose services.

    Implements docker compose pull equivalent.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'compose_pull' command"""
        return name == "compose_pull"

    def get_definition(self) -> Tool:
        """Define the compose_pull tool for MCP"""
        return Tool(
            name="compose_pull",
            description="Pull new images for Docker Compose services without restarting containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Name of the compose project (will auto-detect location)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Direct path to directory containing docker-compose.yml"
                    },
                    "service": {
                        "type": "string",
                        "description": "Specific service to pull (omit to pull all)"
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the compose_pull command"""
        project_name = arguments.get("project")
        compose_path = arguments.get("path")
        service = arguments.get("service")

        try:
            # Find compose file location
            if project_name:
                # Find project via container labels
                containers = self.docker_client.containers.list(all=True)
                for container in containers:
                    labels = container.labels
                    if labels.get('com.docker.compose.project') == project_name:
                        working_dir = labels.get('com.docker.compose.project.working_dir')
                        if working_dir:
                            compose_path = working_dir
                            break

                if not compose_path:
                    return [TextContent(
                        type="text",
                        text=f"Project '{project_name}' not found or has no running containers"
                    )]
            elif not compose_path:
                return [TextContent(
                    type="text",
                    text="Error: Either 'project' or 'path' parameter is required"
                )]

            # Verify path exists
            compose_dir = Path(compose_path)
            if not compose_dir.exists():
                error_msg = [
                    "❌ Compose project directory not found",
                    "",
                    f"The project '{project_name or 'unknown'}' was created from this location:",
                    f"  {compose_path}",
                    "",
                    "However, this directory no longer exists. This typically happens when:",
                    "  • The compose file was moved or deleted after container creation",
                    "  • The container was created from a different filesystem/mount",
                    "  • The project directory was renamed",
                    "",
                    "The containers are still running and can be managed directly, but",
                    "compose-based operations require the original compose file.",
                    "",
                    "💡 Suggestions:",
                    "  • Use direct container operations instead (container_control, etc.)",
                    "  • Use 'list_compose_projects' to see which projects have missing files",
                    "  • If you know where the compose file is now, use the 'path' parameter",
                    "  • Recreate the project if the compose file is available elsewhere"
                ]
                return [TextContent(type="text", text="\n".join(error_msg))]

            # Check for compose file
            compose_file = None
            for filename in ['docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml']:
                potential_file = compose_dir / filename
                if potential_file.exists():
                    compose_file = potential_file
                    break

            if not compose_file:
                return [TextContent(
                    type="text",
                    text=f"Error: No compose file found in {compose_path}"
                )]

            # Build command
            cmd = ['docker', 'compose', '-f', str(compose_file), 'pull']
            if service:
                cmd.append(service)

            # Build output
            lines = ["Compose Pull Images", "=" * 80, ""]
            lines.append(f"Project: {project_name or compose_path}")
            lines.append(f"Compose File: {compose_file}")
            if service:
                lines.append(f"Service: {service}")
            else:
                lines.append("Service: All services")
            lines.append("")
            lines.append("Pulling images...")
            lines.append(f"Command: {' '.join(cmd)}")
            lines.append("")
            lines.append("-" * 80)

            try:
                # Execute command
                result = subprocess.run(
                    cmd,
                    cwd=str(compose_dir),
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout for large images
                )

                # Add output
                if result.stdout:
                    lines.append(result.stdout)
                if result.stderr:
                    lines.append(result.stderr)

                lines.append("-" * 80)
                lines.append("")

                if result.returncode == 0:
                    lines.append("✅ Images pulled successfully!")
                    lines.append("")
                    lines.append("Note: Containers are still running with old images.")
                    lines.append("To use the new images, restart the services with:")
                    lines.append("  docker compose up -d")
                else:
                    lines.append(f"❌ Pull failed with exit code {result.returncode}")

            except subprocess.TimeoutExpired:
                lines.append("❌ Command timed out after 10 minutes")
            except Exception as e:
                lines.append(f"❌ Error executing command: {str(e)}")

            result_text = "\n".join(lines)
            return [TextContent(type="text", text=result_text)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
