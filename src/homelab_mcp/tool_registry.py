"""
Tool Registry

Automatically discovers and registers all available tools.
This uses Python's introspection to find all tool classes.
"""

import importlib
import pkgutil
from typing import List, Optional
from .base_tool import BaseTool
from mcp.types import Tool
import docker


class ToolRegistry:
    """
    Registry for managing all MCP tools.

    This class:
    1. Automatically discovers all tool classes in the tools/ directory
    2. Instantiates them with the Docker client
    3. Provides methods to get tool definitions and find tools by name

    Think of this as a service locator or dependency injection container.
    """

    def __init__(self, docker_client: docker.DockerClient):
        """
        Initialize the registry and discover all tools.

        Args:
            docker_client: Docker client instance to pass to all tools
        """
        self.docker_client = docker_client
        self.tools: List[BaseTool] = []
        self._discover_tools()

    def _discover_tools(self):
        """
        Automatically discover and load all tools.

        This uses Python's pkgutil to find all modules in the tools package,
        then uses introspection to find classes that inherit from BaseTool.

        It's like scanning a directory for plugins - any new .py file in tools/
        with a BaseTool subclass will automatically be registered.
        """
        # Import the tools package
        import homelab_mcp.tools as tools_package

        # Iterate through all modules in the tools package
        for _, module_name, _ in pkgutil.iter_modules(tools_package.__path__):
            # Skip __init__.py
            if module_name.startswith('_'):
                continue

            # Import the module
            module = importlib.import_module(f'homelab_mcp.tools.{module_name}')

            # Find all classes in the module
            for item_name in dir(module):
                item = getattr(module, item_name)

                # Check if it's a class that inherits from BaseTool
                # (but not BaseTool itself)
                if (isinstance(item, type) and
                    issubclass(item, BaseTool) and
                    item != BaseTool):
                    # Instantiate and register the tool
                    tool_instance = item(self.docker_client)
                    self.tools.append(tool_instance)

    def get_tool_definitions(self) -> list[Tool]:
        """
        Get all tool definitions for MCP.

        This is called by the MCP server's list_tools() handler
        to tell Claude what tools are available.

        Returns:
            List of Tool definitions
        """
        return [tool.get_definition() for tool in self.tools]

    def find_tool(self, name: str) -> Optional[BaseTool]:
        """
        Find the tool that handles the given command.

        This is called by the MCP server's call_tool() handler
        to route commands to the right tool.

        Args:
            name: The command name (e.g., "ping", "list_containers")

        Returns:
            The tool that handles this command, or None if not found
        """
        for tool in self.tools:
            if tool.handles(name):
                return tool
        return None

    def get_tool_count(self) -> int:
        """
        Get the number of registered tools.

        Useful for debugging and verification.

        Returns:
            Number of tools in the registry
        """
        return len(self.tools)
