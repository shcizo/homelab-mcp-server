"""
Export Logs Tool

Export container logs to files for further analysis.
"""

import json
import gzip
from datetime import datetime
from pathlib import Path
from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class ExportLogsTool(BaseTool):
    """
    Tool for exporting Docker container logs to files.

    Supports multiple formats (text, JSON) and optional compression.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'export_logs' command"""
        return name == "export_logs"

    def get_definition(self) -> Tool:
        """Define the export_logs tool for MCP"""
        return Tool(
            name="export_logs",
            description="Export container logs to a file with optional compression and metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of the container to export logs from"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path where to save the log file (default: ./logs/<container>_<timestamp>.log)"
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'text' or 'json' (default: text)",
                        "enum": ["text", "json"],
                        "default": "text"
                    },
                    "compress": {
                        "type": "boolean",
                        "description": "Compress the output file with gzip (default: false)",
                        "default": False
                    },
                    "timestamps": {
                        "type": "boolean",
                        "description": "Include timestamps in logs (default: true)",
                        "default": True
                    },
                    "since": {
                        "type": "string",
                        "description": "Export logs since this time (e.g., '1h', '30m', ISO 8601)"
                    },
                    "until": {
                        "type": "string",
                        "description": "Export logs until this time"
                    }
                },
                "required": ["container"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the export_logs command"""
        container_name = arguments.get("container")
        output_path = arguments.get("output_path")
        format_type = arguments.get("format", "text")
        compress = arguments.get("compress", False)
        timestamps = arguments.get("timestamps", True)
        since = arguments.get("since")
        until = arguments.get("until")

        if not container_name:
            return [TextContent(type="text", text="Error: container name or ID is required")]

        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)

            # Build logs parameters
            log_params = {
                "stdout": True,
                "stderr": True,
                "timestamps": timestamps,
                "stream": False
            }

            if since:
                log_params["since"] = since
            if until:
                log_params["until"] = until

            # Fetch logs
            logs = container.logs(**log_params)
            log_text = logs.decode('utf-8', errors='replace')

            # Generate default output path if not provided
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                logs_dir = Path('./logs')
                logs_dir.mkdir(exist_ok=True)

                extension = '.log'
                if format_type == 'json':
                    extension = '.json'
                if compress:
                    extension += '.gz'

                output_path = str(logs_dir / f"{container.name}_{timestamp}{extension}")

            # Prepare content based on format
            if format_type == 'json':
                # JSON format with metadata
                metadata = {
                    "container_name": container.name,
                    "container_id": container.id[:12],
                    "image": container.image.tags[0] if container.image.tags else container.image.id[:12],
                    "export_time": datetime.now().isoformat(),
                    "since": since,
                    "until": until,
                    "timestamps_included": timestamps
                }

                # Split logs into lines
                log_lines = [line for line in log_text.split('\n') if line.strip()]

                content = json.dumps({
                    "metadata": metadata,
                    "logs": log_lines
                }, indent=2)
            else:
                # Plain text format with header
                header = f"""Container Log Export
================================================================================
Container: {container.name}
Image: {container.image.tags[0] if container.image.tags else container.image.id[:12]}
Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                if since:
                    header += f"Since: {since}\n"
                if until:
                    header += f"Until: {until}\n"
                header += "================================================================================\n\n"

                content = header + log_text

            # Write to file (with optional compression)
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if compress:
                with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                    f.write(content)
            else:
                output_file.write_text(content, encoding='utf-8')

            # Calculate file size
            file_size = output_file.stat().st_size
            size_mb = file_size / (1024 * 1024)

            result = f"""✅ Logs exported successfully!

Output File: {output_path}
Format: {format_type.upper()}
Compressed: {'Yes' if compress else 'No'}
File Size: {size_mb:.2f} MB
Container: {container.name}
Log Lines: {len(log_text.splitlines())}
"""

            return [TextContent(type="text", text=result)]

        except NotFound:
            return [TextContent(type="text", text=f"Error: Container '{container_name}' not found")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error exporting logs: {str(e)}")]
