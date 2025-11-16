"""
Monitor Events Tool

Monitor Docker events with filtering and alerting capabilities.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from docker.errors import DockerException
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class MonitorEventsTool(BaseTool):
    """
    Tool for monitoring Docker events.

    Fetches recent Docker events with filtering by type, container,
    and alert conditions. Can optionally log events to file.

    Note: MCP doesn't support true streaming, so this fetches recent events
    rather than providing real-time streaming.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'monitor_events' command"""
        return name == "monitor_events"

    def get_definition(self) -> Tool:
        """Define the monitor_events tool for MCP"""
        return Tool(
            name="monitor_events",
            description="Monitor Docker events with filtering and alerting (fetches recent events)",
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Get events since this time (e.g., '5m', '1h', '30s'). Default: '5m'"
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Filter by event type: 'container', 'image', 'volume', 'network', or 'all'",
                        "enum": ["all", "container", "image", "volume", "network"],
                        "default": "all"
                    },
                    "container": {
                        "type": "string",
                        "description": "Filter events for specific container name"
                    },
                    "alert_on": {
                        "type": "array",
                        "description": "Alert on specific event actions (e.g., ['die', 'stop', 'kill'])",
                        "items": {"type": "string"}
                    },
                    "log_to_file": {
                        "type": "string",
                        "description": "Path to log file (optional). If provided, events will be appended to this file."
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'text' or 'json'",
                        "enum": ["text", "json"],
                        "default": "text"
                    }
                },
                "required": []
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the monitor_events command"""
        since = arguments.get("since", "5m")
        event_type = arguments.get("event_type", "all")
        container_filter = arguments.get("container")
        alert_on = arguments.get("alert_on", [])
        log_file = arguments.get("log_to_file")
        output_format = arguments.get("format", "text")

        try:
            # Build event filters
            filters = {}

            if event_type != "all":
                filters["type"] = event_type

            if container_filter:
                filters["container"] = container_filter

            # Get events
            # Note: Docker Python SDK's events() method is a generator for streaming,
            # but we'll use it with since/until to get recent events
            events = []

            try:
                # Fetch events from the last time period
                event_generator = self.docker_client.events(
                    since=since,
                    decode=True,
                    filters=filters
                )

                # Collect events (this will get all events since the specified time)
                # We need to be careful not to hang, so we'll use a timeout approach
                import time
                start_time = time.time()
                timeout = 2  # 2 second timeout for collecting events

                for event in event_generator:
                    events.append(event)
                    # Break if we've been collecting for too long
                    if time.time() - start_time > timeout:
                        break

            except Exception as e:
                # If streaming fails, try getting events another way
                # This is a fallback
                pass

            if not events:
                return [TextContent(
                    type="text",
                    text=f"No events found in the last {since}"
                )]

            # Process events
            alert_events = []
            regular_events = []

            for event in events:
                # Check for alerts
                action = event.get("Action") or event.get("status")
                if action in alert_on:
                    alert_events.append(event)
                else:
                    regular_events.append(event)

            # Build output
            if output_format == "json":
                result = {
                    "total_events": len(events),
                    "alert_events": alert_events,
                    "regular_events": regular_events,
                    "filters": {
                        "since": since,
                        "type": event_type,
                        "container": container_filter
                    }
                }
                output_text = json.dumps(result, indent=2)

            else:
                # Text format
                lines = ["Docker Event Monitor", "=" * 80, ""]
                lines.append(f"Time Range: Last {since}")
                lines.append(f"Event Type Filter: {event_type}")
                if container_filter:
                    lines.append(f"Container Filter: {container_filter}")
                if alert_on:
                    lines.append(f"Alert Actions: {', '.join(alert_on)}")
                lines.append(f"Total Events: {len(events)}")
                lines.append("")

                # Show alert events first
                if alert_events:
                    lines.append(f"🚨 ALERT EVENTS ({len(alert_events)}):")
                    lines.append("-" * 80)
                    for event in alert_events:
                        lines.extend(self._format_event(event, alert=True))
                    lines.append("")

                # Show regular events
                if regular_events:
                    lines.append(f"Regular Events ({len(regular_events)}):")
                    lines.append("-" * 80)
                    # Limit display to last 20 events
                    display_events = regular_events[-20:] if len(regular_events) > 20 else regular_events

                    if len(regular_events) > 20:
                        lines.append(f"(Showing last 20 of {len(regular_events)} events)")
                        lines.append("")

                    for event in display_events:
                        lines.extend(self._format_event(event))
                    lines.append("")

                output_text = "\n".join(lines)

            # Log to file if requested
            if log_file:
                try:
                    log_path = Path(log_file)
                    log_path.parent.mkdir(parents=True, exist_ok=True)

                    # Append events to log file
                    with open(log_path, 'a', encoding='utf-8') as f:
                        timestamp = datetime.now().isoformat()
                        f.write(f"\n--- Event Log Entry: {timestamp} ---\n")
                        if output_format == "json":
                            f.write(output_text)
                        else:
                            for event in events:
                                f.write(json.dumps(event) + "\n")
                        f.write("\n")

                    output_text += f"\n\n✅ Events logged to: {log_file}"

                except Exception as e:
                    output_text += f"\n\n⚠️  Failed to log to file: {str(e)}"

            return [TextContent(type="text", text=output_text)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error monitoring events: {str(e)}")]

    def _format_event(self, event: dict, alert: bool = False) -> list[str]:
        """Format a single event for text output"""
        lines = []

        # Extract event details
        event_type = event.get("Type", "unknown")
        action = event.get("Action") or event.get("status", "unknown")
        timestamp = event.get("time") or event.get("timeNano")

        # Format timestamp
        if timestamp:
            try:
                if isinstance(timestamp, int):
                    # Unix timestamp (could be seconds or nanoseconds)
                    if timestamp > 10000000000:  # Likely nanoseconds
                        timestamp = timestamp / 1000000000
                    dt = datetime.fromtimestamp(timestamp)
                else:
                    # ISO format or string
                    dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                time_str = str(timestamp)
        else:
            time_str = "Unknown"

        # Build event description
        icon = "🚨" if alert else "•"

        # Get actor info
        actor = event.get("Actor", {})
        attributes = actor.get("Attributes", {})

        if event_type == "container":
            container_name = attributes.get("name", actor.get("ID", "unknown")[:12])
            image = attributes.get("image", "unknown")
            lines.append(f"{icon} [{time_str}] Container '{container_name}' - {action}")
            lines.append(f"  Image: {image}")

        elif event_type == "image":
            image_name = attributes.get("name", actor.get("ID", "unknown")[:12])
            lines.append(f"{icon} [{time_str}] Image - {action}")
            lines.append(f"  Name: {image_name}")

        elif event_type == "volume":
            volume_name = attributes.get("name", actor.get("ID", "unknown"))
            lines.append(f"{icon} [{time_str}] Volume '{volume_name}' - {action}")

        elif event_type == "network":
            network_name = attributes.get("name", actor.get("ID", "unknown")[:12])
            network_type = attributes.get("type", "unknown")
            lines.append(f"{icon} [{time_str}] Network '{network_name}' - {action}")
            lines.append(f"  Type: {network_type}")

        else:
            resource_id = actor.get("ID", "unknown")[:12] if actor.get("ID") else "unknown"
            lines.append(f"{icon} [{time_str}] {event_type} '{resource_id}' - {action}")

        lines.append("")
        return lines
