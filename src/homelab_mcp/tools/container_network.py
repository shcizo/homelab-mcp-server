"""
Container Network Tool

Show network configuration and connectivity for Docker containers.
"""

from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ContainerNetworkTool(BaseTool):
    """
    Tool for showing Docker container network information.

    Displays networks, IP addresses, port mappings, network drivers,
    and identifies orphaned networks.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'container_network' command"""
        return name == "container_network"

    def get_definition(self) -> Tool:
        """Define the container_network tool for MCP"""
        return Tool(
            name="container_network",
            description="Show network configuration, IP addresses, and port mappings for containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of specific container (optional, shows all if not specified)"
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Show all containers including stopped (default: false, running only)",
                        "default": False
                    },
                    "show_orphaned": {
                        "type": "boolean",
                        "description": "Also show orphaned networks not attached to any container (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the container_network command"""
        container_name = arguments.get("container")
        show_all = arguments.get("all", False)
        show_orphaned = arguments.get("show_orphaned", False)

        try:
            lines = []

            # Container network info
            if container_name:
                containers = [self.docker_client.containers.get(container_name)]
            else:
                containers = self.docker_client.containers.list(all=show_all)

            if containers:
                lines.append("Docker Container Network Information:")
                lines.append("")

                for container in containers:
                    container.reload()

                    name = container.name
                    status = container.status
                    attrs = container.attrs

                    lines.append(f"Container: {name}")
                    lines.append(f"  Status: {status}")

                    # Network settings
                    network_settings = attrs.get('NetworkSettings', {})
                    networks = network_settings.get('Networks', {})

                    if networks:
                        lines.append(f"  Networks: {len(networks)} connected")

                        for network_name, network_info in networks.items():
                            lines.append(f"    • {network_name}")

                            # IP Address
                            ip_address = network_info.get('IPAddress', '')
                            if ip_address:
                                lines.append(f"      IP: {ip_address}")

                            # Gateway
                            gateway = network_info.get('Gateway', '')
                            if gateway:
                                lines.append(f"      Gateway: {gateway}")

                            # MAC Address
                            mac_address = network_info.get('MacAddress', '')
                            if mac_address:
                                lines.append(f"      MAC: {mac_address}")

                            # Network ID
                            network_id = network_info.get('NetworkID', '')
                            if network_id:
                                lines.append(f"      Network ID: {network_id[:12]}")
                    else:
                        lines.append("  Networks: None")

                    # Port mappings
                    ports = network_settings.get('Ports', {})
                    if ports and any(ports.values()):
                        lines.append("  Port Mappings:")
                        for container_port, host_bindings in ports.items():
                            if host_bindings:
                                for binding in host_bindings:
                                    host_ip = binding.get('HostIp', '0.0.0.0')
                                    host_port = binding.get('HostPort', '')
                                    lines.append(f"    {host_ip}:{host_port} → {container_port}")
                            else:
                                lines.append(f"    {container_port} (not published)")
                    else:
                        lines.append("  Port Mappings: None")

                    lines.append("")

            # Orphaned networks
            if show_orphaned:
                lines.append("=" * 80)
                lines.append("Orphaned Networks Check:")
                lines.append("")

                all_networks = self.docker_client.networks.list()
                all_containers = self.docker_client.containers.list(all=True)

                # Get all network IDs used by containers
                used_networks = set()
                for container in all_containers:
                    container.reload()
                    networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
                    for network_name, network_info in networks.items():
                        network_id = network_info.get('NetworkID', '')
                        if network_id:
                            used_networks.add(network_id)

                # Find orphaned networks
                orphaned = []
                for network in all_networks:
                    # Skip built-in networks
                    if network.name in ['bridge', 'host', 'none']:
                        continue

                    if network.id not in used_networks:
                        orphaned.append(network)

                if orphaned:
                    lines.append(f"Found {len(orphaned)} orphaned network(s):")
                    for network in orphaned:
                        lines.append(f"  ⚠️  {network.name}")
                        lines.append(f"      ID: {network.id[:12]}")
                        lines.append(f"      Driver: {network.attrs.get('Driver', 'unknown')}")
                        lines.append(f"      Scope: {network.attrs.get('Scope', 'unknown')}")
                        lines.append("")
                else:
                    lines.append("No orphaned networks found.")

            result = "\n".join(lines)

            return [
                TextContent(
                    type="text",
                    text=result
                )
            ]

        except NotFound:
            return [
                TextContent(
                    type="text",
                    text=f"Error: Container '{container_name}' not found"
                )
            ]
        except DockerException as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error checking network info: {str(e)}"
                )
            ]
        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Unexpected error: {str(e)}"
                )
            ]
