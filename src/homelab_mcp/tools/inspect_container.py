"""
Inspect Container Tool

Deep dive into container configuration and state.
"""

import json
from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class InspectContainerTool(BaseTool):
    """
    Tool for inspecting container configuration and state.

    Shows full container configuration, environment variables,
    mounted volumes, network settings, and labels/metadata.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'inspect_container' command"""
        return name == "inspect_container"

    def get_definition(self) -> Tool:
        """Define the inspect_container tool for MCP"""
        return Tool(
            name="inspect_container",
            description="Deep inspection of container configuration, environment, volumes, network, and metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of the container to inspect"
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'detailed' (human-readable) or 'json' (raw JSON)",
                        "enum": ["detailed", "json"],
                        "default": "detailed"
                    },
                    "section": {
                        "type": "string",
                        "description": "Show specific section only: 'config', 'env', 'volumes', 'network', 'labels', or 'all'",
                        "enum": ["all", "config", "env", "volumes", "network", "labels"],
                        "default": "all"
                    }
                },
                "required": ["container"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the inspect_container command"""
        container_name = arguments.get("container")
        format_type = arguments.get("format", "detailed")
        section = arguments.get("section", "all")

        if not container_name:
            return [TextContent(type="text", text="Error: container name or ID is required")]

        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)
            attrs = container.attrs

            # If JSON format requested, return raw JSON
            if format_type == "json":
                result = json.dumps(attrs, indent=2)
                return [TextContent(type="text", text=result)]

            # Build detailed human-readable output
            lines = [f"Container Inspection: {container.name}", "=" * 80, ""]

            # Configuration section
            if section in ["all", "config"]:
                lines.append("## Configuration")
                lines.append(f"ID: {container.id[:12]}")
                lines.append(f"Name: {container.name}")
                lines.append(f"Image: {container.image.tags[0] if container.image.tags else container.image.id[:12]}")
                lines.append(f"Status: {container.status}")

                state = attrs.get('State', {})
                lines.append(f"Running: {state.get('Running', False)}")
                lines.append(f"Paused: {state.get('Paused', False)}")
                lines.append(f"Restarting: {state.get('Restarting', False)}")
                lines.append(f"Exit Code: {state.get('ExitCode', 'N/A')}")

                if state.get('StartedAt'):
                    lines.append(f"Started At: {state.get('StartedAt')}")
                if state.get('FinishedAt') and state.get('FinishedAt') != '0001-01-01T00:00:00Z':
                    lines.append(f"Finished At: {state.get('FinishedAt')}")

                config = attrs.get('Config', {})
                lines.append(f"Hostname: {config.get('Hostname', 'N/A')}")
                lines.append(f"User: {config.get('User', 'root')}")
                lines.append(f"Working Dir: {config.get('WorkingDir', '/')}")

                if config.get('Entrypoint'):
                    lines.append(f"Entrypoint: {' '.join(config.get('Entrypoint', []))}")
                if config.get('Cmd'):
                    lines.append(f"Command: {' '.join(config.get('Cmd', []))}")

                lines.append("")

            # Environment variables section
            if section in ["all", "env"]:
                lines.append("## Environment Variables")
                env_vars = attrs.get('Config', {}).get('Env', [])
                if env_vars:
                    for env in sorted(env_vars):
                        # Mask potential secrets (values with SECRET, PASSWORD, TOKEN, KEY in name)
                        if any(keyword in env.upper() for keyword in ['SECRET', 'PASSWORD', 'TOKEN', 'KEY', 'CREDENTIAL']):
                            key = env.split('=')[0]
                            lines.append(f"  {key}=***MASKED***")
                        else:
                            lines.append(f"  {env}")
                else:
                    lines.append("  (No environment variables)")
                lines.append("")

            # Volumes section
            if section in ["all", "volumes"]:
                lines.append("## Volumes & Mounts")
                mounts = attrs.get('Mounts', [])
                if mounts:
                    for mount in mounts:
                        mount_type = mount.get('Type', 'unknown')
                        lines.append(f"  {mount_type.upper()}: {mount.get('Source', 'N/A')} → {mount.get('Destination', 'N/A')}")
                        lines.append(f"    Mode: {mount.get('Mode', 'N/A')}")
                        lines.append(f"    RW: {mount.get('RW', 'N/A')}")
                        lines.append("")
                else:
                    lines.append("  (No mounts)")
                lines.append("")

            # Network section
            if section in ["all", "network"]:
                lines.append("## Network Settings")
                network_settings = attrs.get('NetworkSettings', {})
                networks = network_settings.get('Networks', {})

                if networks:
                    for network_name, network_info in networks.items():
                        lines.append(f"  Network: {network_name}")
                        lines.append(f"    IP Address: {network_info.get('IPAddress', 'N/A')}")
                        lines.append(f"    Gateway: {network_info.get('Gateway', 'N/A')}")
                        lines.append(f"    MAC Address: {network_info.get('MacAddress', 'N/A')}")
                        lines.append("")

                # Port bindings
                ports = attrs.get('NetworkSettings', {}).get('Ports', {})
                if ports:
                    lines.append("  Port Bindings:")
                    for container_port, host_bindings in ports.items():
                        if host_bindings:
                            for binding in host_bindings:
                                host_ip = binding.get('HostIp', '0.0.0.0')
                                host_port = binding.get('HostPort', 'N/A')
                                lines.append(f"    {host_ip}:{host_port} → {container_port}")
                        else:
                            lines.append(f"    {container_port} (not bound)")
                    lines.append("")

            # Labels section
            if section in ["all", "labels"]:
                lines.append("## Labels & Metadata")
                labels = attrs.get('Config', {}).get('Labels', {})
                if labels:
                    for key, value in sorted(labels.items()):
                        # Truncate long values
                        display_value = value if len(value) < 100 else value[:97] + "..."
                        lines.append(f"  {key}: {display_value}")
                else:
                    lines.append("  (No labels)")
                lines.append("")

            # Restart policy
            if section == "all":
                lines.append("## Restart Policy")
                restart_policy = attrs.get('HostConfig', {}).get('RestartPolicy', {})
                lines.append(f"  Name: {restart_policy.get('Name', 'no')}")
                if restart_policy.get('MaximumRetryCount'):
                    lines.append(f"  Max Retry Count: {restart_policy.get('MaximumRetryCount')}")
                lines.append("")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except NotFound:
            return [TextContent(type="text", text=f"Error: Container '{container_name}' not found")]
        except DockerException as e:
            return [TextContent(type="text", text=f"Error inspecting container: {str(e)}")]
