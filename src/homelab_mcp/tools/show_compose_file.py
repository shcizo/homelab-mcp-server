"""
Show Compose File Tool

Display the docker-compose.yml file for a project.
"""

from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ShowComposeFileTool(BaseTool):
    """
    Tool for displaying Docker Compose file contents.

    Reads and displays docker-compose.yml files with support
    for override files.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'show_compose_file' command"""
        return name == "show_compose_file"

    def get_definition(self) -> Tool:
        """Define the show_compose_file tool for MCP"""
        return Tool(
            name="show_compose_file",
            description="Display the contents of a docker-compose.yml file for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Name of the compose project (will auto-detect location)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Direct path to docker-compose.yml file or directory containing it"
                    },
                    "include_override": {
                        "type": "boolean",
                        "description": "Include docker-compose.override.yml if present (default: true)",
                        "default": True
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the show_compose_file command"""
        project_name = arguments.get("project")
        file_path = arguments.get("path")
        include_override = arguments.get("include_override", True)

        try:
            compose_file_path = None

            # If project name provided, find it via container labels
            if project_name:
                containers = self.docker_client.containers.list(all=True)
                for container in containers:
                    labels = container.labels
                    if labels.get('com.docker.compose.project') == project_name:
                        # Found the project, get config files and working dir
                        working_dir = labels.get('com.docker.compose.project.working_dir')
                        config_files = labels.get('com.docker.compose.project.config_files')

                        if working_dir and config_files:
                            # config_files is usually a comma-separated list
                            main_file = config_files.split(',')[0].strip()
                            compose_file_path = Path(main_file)
                            if not compose_file_path.is_absolute():
                                compose_file_path = Path(working_dir) / main_file
                            break

                if not compose_file_path:
                    return [TextContent(
                        type="text",
                        text=f"Project '{project_name}' not found or has no running containers.\n\nTip: Use list_compose_projects to see available projects."
                    )]

            # If path provided, use it directly
            elif file_path:
                compose_file_path = Path(file_path)

                # If it's a directory, look for compose files
                if compose_file_path.is_dir():
                    # Try docker-compose.yml first, then docker-compose.yaml
                    for filename in ['docker-compose.yml', 'docker-compose.yaml']:
                        potential_file = compose_file_path / filename
                        if potential_file.exists():
                            compose_file_path = potential_file
                            break
                    else:
                        return [TextContent(
                            type="text",
                            text=f"No docker-compose.yml or docker-compose.yaml found in {file_path}"
                        )]
            else:
                return [TextContent(
                    type="text",
                    text="Error: Either 'project' or 'path' parameter is required"
                )]

            # Read the main compose file
            if not compose_file_path.exists():
                return [TextContent(
                    type="text",
                    text=f"File not found: {compose_file_path}"
                )]

            compose_content = compose_file_path.read_text(encoding='utf-8')

            # Build output
            lines = [
                f"Docker Compose File: {compose_file_path}",
                "=" * 80,
                "",
                compose_content
            ]

            # Check for override file
            if include_override:
                override_path = compose_file_path.parent / 'docker-compose.override.yml'
                if not override_path.exists():
                    override_path = compose_file_path.parent / 'docker-compose.override.yaml'

                if override_path.exists():
                    override_content = override_path.read_text(encoding='utf-8')
                    lines.extend([
                        "",
                        "",
                        "=" * 80,
                        f"Override File: {override_path}",
                        "=" * 80,
                        "",
                        override_content
                    ])

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except FileNotFoundError as e:
            return [TextContent(type="text", text=f"File not found: {str(e)}")]
        except PermissionError as e:
            return [TextContent(type="text", text=f"Permission denied: {str(e)}")]
        except DockerException as e:
            return [TextContent(type="text", text=f"Error accessing Docker: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading compose file: {str(e)}")]
