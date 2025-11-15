"""
Base Tool Interface

All MCP tools should inherit from this base class.
This provides a consistent interface for tool discovery and execution.
"""

from abc import ABC, abstractmethod
from mcp.types import Tool, TextContent
import docker


class BaseTool(ABC):
    """
    Base class for all MCP tools.

    This is the interface that all tools must implement.
    Think of this like an interface in C# - it defines the contract.
    """

    def __init__(self, docker_client: docker.DockerClient):
        """
        Initialize the tool with a Docker client.

        Args:
            docker_client: The Docker client instance to use for Docker operations
        """
        self.docker_client = docker_client

    @abstractmethod
    def handles(self, name: str) -> bool:
        """
        Check if this tool handles the given command name.

        Args:
            name: The command name to check (e.g., "ping", "list_containers")

        Returns:
            True if this tool handles the command, False otherwise
        """
        pass

    @abstractmethod
    def get_definition(self) -> Tool:
        """
        Get the MCP Tool definition for this tool.

        This defines what the tool is called, what it does, and what parameters it accepts.
        Claude uses this information to know how to call the tool.

        Returns:
            Tool definition with name, description, and input schema
        """
        pass

    @abstractmethod
    async def execute(self, arguments: dict) -> list[TextContent]:
        """
        Execute the tool with the given arguments.

        This is where the actual work happens - calling Docker API, formatting results, etc.

        Args:
            arguments: Dictionary of arguments passed by Claude

        Returns:
            List of TextContent objects containing the results
        """
        pass
