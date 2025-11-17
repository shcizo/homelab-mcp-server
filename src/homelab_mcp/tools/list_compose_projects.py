"""
List Compose Projects Tool

Discover and list all Docker Compose projects on the server.
"""

from collections import defaultdict
from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ListComposeProjectsTool(BaseTool):
    """
    Tool for listing Docker Compose projects.

    Identifies compose projects by examining container labels,
    groups containers by project, and shows project status.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'list_compose_projects' command"""
        return name == "list_compose_projects"

    def get_definition(self) -> Tool:
        """Define the list_compose_projects tool for MCP"""
        return Tool(
            name="list_compose_projects",
            description="List all Docker Compose projects with their services and status",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {
                        "type": "boolean",
                        "description": "Include projects with all containers stopped (default: true)",
                        "default": True
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the list_compose_projects command"""
        show_all = arguments.get("all", True)

        try:
            # Get all containers
            containers = self.docker_client.containers.list(all=show_all)

            # Group containers by compose project
            projects = defaultdict(list)

            for container in containers:
                labels = container.labels
                # Docker Compose adds a 'com.docker.compose.project' label
                project_name = labels.get('com.docker.compose.project')

                if project_name:
                    service_name = labels.get('com.docker.compose.service', 'unknown')
                    config_files = labels.get('com.docker.compose.project.config_files', 'N/A')
                    working_dir = labels.get('com.docker.compose.project.working_dir', 'N/A')

                    projects[project_name].append({
                        'container': container,
                        'service_name': service_name,
                        'config_files': config_files,
                        'working_dir': working_dir,
                        'status': container.status
                    })

            if not projects:
                return [TextContent(
                    type="text",
                    text="No Docker Compose projects found.\n\nTip: Docker Compose projects are identified by the 'com.docker.compose.project' label."
                )]

            # Build output
            lines = ["Docker Compose Projects:", ""]

            for project_name in sorted(projects.keys()):
                services = projects[project_name]

                # Determine project status
                statuses = [s['status'] for s in services]
                running_count = sum(1 for s in statuses if s == 'running')
                total_count = len(services)

                if running_count == total_count:
                    status_icon = "✓"
                    status_text = "All running"
                elif running_count == 0:
                    status_icon = "✗"
                    status_text = "All stopped"
                else:
                    status_icon = "⚠"
                    status_text = f"{running_count}/{total_count} running"

                # Check if paths exist
                working_dir = services[0]['working_dir']
                config_files = services[0]['config_files']

                dir_exists = working_dir != 'N/A' and Path(working_dir).exists()
                file_exists = False
                if config_files != 'N/A':
                    # config_files might be comma-separated list, check first one
                    main_config = config_files.split(',')[0].strip()
                    config_path = Path(main_config)
                    if not config_path.is_absolute() and working_dir != 'N/A':
                        config_path = Path(working_dir) / main_config
                    file_exists = config_path.exists()

                # Mark as stale if paths don't exist
                is_stale = working_dir != 'N/A' and not (dir_exists and file_exists)

                if is_stale:
                    lines.append(f"⚠️  Project: {project_name} (STALE)")
                else:
                    lines.append(f"{status_icon} Project: {project_name}")

                lines.append(f"  Status: {status_text}")

                # Get location from first service (all should have same working_dir)
                if working_dir != 'N/A':
                    if dir_exists:
                        lines.append(f"  Location: {working_dir}")
                    else:
                        lines.append(f"  Location: {working_dir} ⚠️  (NOT FOUND)")

                # Get config files from first service
                if config_files != 'N/A':
                    if file_exists:
                        lines.append(f"  Config: {config_files}")
                    else:
                        lines.append(f"  Config: {config_files} ⚠️  (NOT FOUND)")

                # Add warning if stale
                if is_stale:
                    lines.append(f"  ⚠️  Warning: Compose files missing - operations may fail")
                    lines.append(f"  💡 Tip: Use direct container operations instead of compose operations")

                # List services
                lines.append(f"  Services ({len(services)}):")
                for service in sorted(services, key=lambda x: x['service_name']):
                    service_icon = "✓" if service['status'] == 'running' else "✗"
                    lines.append(f"    {service_icon} {service['service_name']} ({service['container'].name}) - {service['status']}")

                lines.append("")

            # Summary
            lines.append("=" * 80)
            lines.append(f"Total Projects: {len(projects)}")
            total_services = sum(len(services) for services in projects.values())
            lines.append(f"Total Services: {total_services}")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error listing compose projects: {str(e)}")]
