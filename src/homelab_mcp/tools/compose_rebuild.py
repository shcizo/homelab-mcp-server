"""
Compose Rebuild Tool

Rebuild images and restart services for a compose project.
"""

import subprocess
from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ComposeRebuildTool(BaseTool):
    """
    Tool for rebuilding and restarting Docker Compose services.

    Implements docker compose up -d --build equivalent.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'compose_rebuild' command"""
        return name == "compose_rebuild"

    def get_definition(self) -> Tool:
        """Define the compose_rebuild tool for MCP"""
        return Tool(
            name="compose_rebuild",
            description="Rebuild images and restart services for a Docker Compose project",
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
                        "description": "Specific service to rebuild (omit to rebuild all)"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Show what would be done without executing (default: true)",
                        "default": True
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the compose_rebuild command"""
        project_name = arguments.get("project")
        compose_path = arguments.get("path")
        service = arguments.get("service")
        dry_run = arguments.get("dry_run", True)

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
                return [TextContent(
                    type="text",
                    text=f"Error: Directory not found: {compose_path}"
                )]

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
            cmd = ['docker', 'compose', '-f', str(compose_file), 'up', '-d', '--build']
            if service:
                cmd.append(service)

            # Build output
            lines = ["Compose Rebuild", "=" * 80, ""]
            lines.append(f"Project: {project_name or compose_path}")
            lines.append(f"Compose File: {compose_file}")
            if service:
                lines.append(f"Service: {service}")
            else:
                lines.append("Service: All services")
            lines.append("")

            if dry_run:
                lines.append("⚠️  DRY RUN MODE - No changes will be made")
                lines.append("")
                lines.append("Command that would be executed:")
                lines.append(f"  {' '.join(cmd)}")
                lines.append("")
                lines.append("To actually rebuild, run with: dry_run=false")
                lines.append("")
                lines.append("⚠️  WARNING: This will rebuild images and restart containers!")
            else:
                lines.append("Executing rebuild...")
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
                        timeout=300  # 5 minute timeout
                    )

                    # Add output
                    if result.stdout:
                        lines.append(result.stdout)
                    if result.stderr:
                        lines.append(result.stderr)

                    lines.append("-" * 80)
                    lines.append("")

                    if result.returncode == 0:
                        lines.append("✅ Rebuild completed successfully!")
                    else:
                        lines.append(f"❌ Rebuild failed with exit code {result.returncode}")

                except subprocess.TimeoutExpired:
                    lines.append("❌ Command timed out after 5 minutes")
                except Exception as e:
                    lines.append(f"❌ Error executing command: {str(e)}")

            result_text = "\n".join(lines)
            return [TextContent(type="text", text=result_text)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
