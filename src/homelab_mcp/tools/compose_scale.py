"""
Compose Scale Tool

Adjust the number of replicas for compose services.
"""

import subprocess
from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ComposeScaleTool(BaseTool):
    """
    Tool for scaling Docker Compose services.

    Adjusts the number of container replicas for services.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'compose_scale' command"""
        return name == "compose_scale"

    def get_definition(self) -> Tool:
        """Define the compose_scale tool for MCP"""
        return Tool(
            name="compose_scale",
            description="Scale Docker Compose services to specified number of replicas",
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
                        "description": "Service name to scale"
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Number of replicas to run",
                        "minimum": 0
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be done without executing (default: true)",
                        "default": True
                    }
                },
                "required": ["service", "replicas"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the compose_scale command"""
        project_name = arguments.get("project")
        compose_path = arguments.get("path")
        service = arguments.get("service")
        replicas = arguments.get("replicas")
        dry_run = arguments.get("dry_run", True)

        if service is None or replicas is None:
            return [TextContent(
                type="text",
                text="Error: service and replicas parameters are required"
            )]

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

            # Get current scale
            current_scale = 0
            try:
                containers = self.docker_client.containers.list(all=True)
                for container in containers:
                    labels = container.labels
                    if (labels.get('com.docker.compose.project') == project_name and
                        labels.get('com.docker.compose.service') == service):
                        current_scale += 1
            except Exception:
                pass  # If we can't determine current scale, proceed anyway

            # Build command
            cmd = ['docker', 'compose', '-f', str(compose_file), 'up', '-d', '--scale', f'{service}={replicas}', '--no-recreate']

            # Build output
            lines = ["Compose Scale Service", "=" * 80, ""]
            lines.append(f"Project: {project_name or compose_path}")
            lines.append(f"Compose File: {compose_file}")
            lines.append(f"Service: {service}")
            lines.append(f"Current Replicas: {current_scale}")
            lines.append(f"Target Replicas: {replicas}")
            lines.append("")

            if dry_run:
                lines.append("⚠️  DRY RUN MODE - No changes will be made")
                lines.append("")
                lines.append("Command that would be executed:")
                lines.append(f"  {' '.join(cmd)}")
                lines.append("")

                if replicas > current_scale:
                    lines.append(f"This would START {replicas - current_scale} new container(s)")
                elif replicas < current_scale:
                    lines.append(f"This would STOP {current_scale - replicas} container(s)")
                else:
                    lines.append("No change (already at target replicas)")

                lines.append("")
                lines.append("To actually scale, run with: dry_run=false")
            else:
                lines.append("Executing scale operation...")
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
                        timeout=120  # 2 minute timeout
                    )

                    # Add output
                    if result.stdout:
                        lines.append(result.stdout)
                    if result.stderr:
                        lines.append(result.stderr)

                    lines.append("-" * 80)
                    lines.append("")

                    if result.returncode == 0:
                        lines.append(f"✅ Service '{service}' scaled to {replicas} replica(s) successfully!")
                    else:
                        lines.append(f"❌ Scale operation failed with exit code {result.returncode}")

                except subprocess.TimeoutExpired:
                    lines.append("❌ Command timed out after 2 minutes")
                except Exception as e:
                    lines.append(f"❌ Error executing command: {str(e)}")

            result_text = "\n".join(lines)
            return [TextContent(type="text", text=result_text)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
