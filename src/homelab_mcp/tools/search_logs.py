"""
Search Logs Tool

Search container logs for specific error messages or patterns.
"""

import re
from docker.errors import DockerException, NotFound
from ..base_tool import BaseTool
from mcp.types import Tool, TextContent


class SearchLogsTool(BaseTool):
    """
    Tool for searching container logs for patterns.

    Supports regex patterns, case-sensitive/insensitive search,
    context lines, and searching across multiple containers.
    """

    def handles(self, name: str) -> bool:
        """Check if this tool handles the 'search_logs' command"""
        return name == "search_logs"

    def get_definition(self) -> Tool:
        """Define the search_logs tool for MCP"""
        return Tool(
            name="search_logs",
            description="Search container logs for specific patterns or error messages with regex support",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Name or ID of container to search (omit to search all containers)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (supports regex)"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search (default: false)",
                        "default": False
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines to show before/after match (default: 2)",
                        "default": 2
                    },
                    "max_matches": {
                        "type": "integer",
                        "description": "Maximum number of matches to return per container (default: 50)",
                        "default": 50
                    },
                    "tail": {
                        "type": "integer",
                        "description": "Only search last N lines of logs (default: 1000)",
                        "default": 1000
                    }
                },
                "required": ["pattern"]
            }
        )

    async def execute(self, arguments: dict) -> list[TextContent]:
        """Execute the search_logs command"""
        container_name = arguments.get("container")
        pattern = arguments.get("pattern")
        case_sensitive = arguments.get("case_sensitive", False)
        context_lines = arguments.get("context_lines", 2)
        max_matches = arguments.get("max_matches", 50)
        tail = arguments.get("tail", 1000)

        if not pattern:
            return [TextContent(type="text", text="Error: pattern is required")]

        try:
            # Compile regex pattern
            regex_flags = 0 if case_sensitive else re.IGNORECASE
            try:
                compiled_pattern = re.compile(pattern, regex_flags)
            except re.error as e:
                return [TextContent(type="text", text=f"Error: Invalid regex pattern: {str(e)}")]

            # Get containers to search
            if container_name:
                try:
                    containers = [self.docker_client.containers.get(container_name)]
                except NotFound:
                    return [TextContent(type="text", text=f"Error: Container '{container_name}' not found")]
            else:
                # Search all running containers
                containers = self.docker_client.containers.list()

            if not containers:
                return [TextContent(type="text", text="No containers found to search")]

            # Build output
            lines = ["Log Search Results", "=" * 80, ""]
            lines.append(f"Pattern: {pattern}")
            lines.append(f"Case Sensitive: {case_sensitive}")
            lines.append(f"Searching {len(containers)} container(s)")
            lines.append("")

            total_matches = 0

            for container in containers:
                # Get logs
                try:
                    logs = container.logs(tail=tail, timestamps=True).decode('utf-8', errors='replace')
                except Exception as e:
                    lines.append(f"⚠ {container.name}: Error reading logs - {str(e)}")
                    lines.append("")
                    continue

                log_lines = logs.split('\n')

                # Search for matches
                matches = []
                for i, line in enumerate(log_lines):
                    if compiled_pattern.search(line):
                        matches.append((i, line))

                if matches:
                    # Limit matches
                    if len(matches) > max_matches:
                        matches = matches[:max_matches]
                        truncated = True
                    else:
                        truncated = False

                    lines.append(f"## {container.name}")
                    lines.append(f"Found {len(matches)} match(es){' (truncated to ' + str(max_matches) + ')' if truncated else ''}")
                    lines.append("")

                    total_matches += len(matches)

                    # Show matches with context
                    for match_idx, (line_num, match_line) in enumerate(matches):
                        lines.append(f"Match {match_idx + 1}:")

                        # Show context before
                        context_start = max(0, line_num - context_lines)
                        for ctx_idx in range(context_start, line_num):
                            if ctx_idx < len(log_lines):
                                lines.append(f"  {ctx_idx + 1:6d} | {log_lines[ctx_idx]}")

                        # Show matching line with highlight
                        highlighted = compiled_pattern.sub(lambda m: f">>> {m.group()} <<<", match_line)
                        lines.append(f"  {line_num + 1:6d} * {highlighted}")

                        # Show context after
                        context_end = min(len(log_lines), line_num + context_lines + 1)
                        for ctx_idx in range(line_num + 1, context_end):
                            if ctx_idx < len(log_lines):
                                lines.append(f"  {ctx_idx + 1:6d} | {log_lines[ctx_idx]}")

                        lines.append("")

                    lines.append("")

            # Summary
            lines.append("=" * 80)
            lines.append(f"Total Matches: {total_matches}")

            if total_matches == 0:
                lines.append("")
                lines.append("No matches found.")

            result = "\n".join(lines)
            return [TextContent(type="text", text=result)]

        except DockerException as e:
            return [TextContent(type="text", text=f"Error searching logs: {str(e)}")]
