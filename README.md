# Homelab MCP Server

MCP (Model Context Protocol) server for managing Docker containers in a homelab environment. Allows Claude to inspect and manage your Docker containers, images, volumes, and compose projects.

## What is this?

This is an MCP server that gives Claude (or other MCP clients) the ability to:
- List Docker containers and their status
- Fetch container logs
- Manage container lifecycle (start/stop/restart)
- Inspect Docker Compose projects
- Monitor resource usage
- And much more!

## Requirements

- Python 3.10+
- Docker installed and running
- `uv` (Python package manager) or `pip`

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd homelab-mcp-server
```

2. Install dependencies:
```bash
# Using uv (recommended)
uv sync --all-extras

# Or using pip
pip install -e ".[dev]"
```

3. Test Docker connection:
```bash
uv run python test_connection.py
```

## Docker Installation (Alternative)

You can run the MCP server in a Docker container instead of installing it locally. This is useful for isolation and easier deployment.

### Building the Docker Image

```bash
docker build -t homelab-mcp-server .
```

### Running the Container

The container requires access to the host Docker socket to manage containers:

```bash
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --name homelab-mcp \
  homelab-mcp-server
```

**Important Notes:**
- The `-v /var/run/docker.sock:/var/run/docker.sock` flag gives the container access to the host Docker daemon
- This gives the container full control over Docker on your host system
- On some systems, you may need to adjust Docker socket permissions or run with `--user root` for testing
- The container runs as a non-root user (`mcp`) for security

### Testing the Docker Container

Test the container with a simple ping:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
docker run -i --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  homelab-mcp-server
```

### Docker Permissions

If you encounter permission errors accessing the Docker socket, you have several options:

**Option 1: Run as root (temporary/testing only)**
```bash
docker run -i --rm --user root \
  -v /var/run/docker.sock:/var/run/docker.sock \
  homelab-mcp-server
```

**Option 2: Match host docker group GID**
Find your host's docker group GID:
```bash
getent group docker | cut -d: -f3
```

Then rebuild with that GID:
```bash
docker build --build-arg DOCKER_GID=<your-gid> -t homelab-mcp-server .
```

**Option 3: Adjust socket permissions on host (not recommended)**
```bash
sudo chmod 666 /var/run/docker.sock
```

## Configuration for Claude Code

Add this to your Claude Code MCP configuration. You can edit it through Claude Code settings or manually:

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/samuelenocsson/dev/homelab-mcp-server",
        "python",
        "src/homelab_mcp/server.py"
      ]
    }
  }
}
```

**What this configuration does:**
- `command: "uv"` - Use uv to run the server
- `--directory` - Set working directory to your project
- `python src/homelab_mcp/server.py` - Run the MCP server

### Alternative: Using Docker

If you prefer to run the server in Docker, use this configuration instead:

```json
{
  "mcpServers": {
    "homelab": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "homelab-mcp-server"
      ]
    }
  }
}
```

**Docker configuration notes:**
- Requires the Docker image to be built first (`docker build -t homelab-mcp-server .`)
- The `-i` flag enables interactive mode for stdin/stdout communication
- The `--rm` flag removes the container after each use
- Adjust Docker socket permissions if you encounter permission errors

After adding this, restart Claude Code to load the new server.

## Testing the Server

### Option 1: Test with Claude Code

1. Add the configuration above
2. Restart Claude Code
3. In a chat, ask: "Can you list my Docker containers?"
4. Claude should use the `list_containers` tool and show your containers

### Option 2: Manual Testing

Run the Docker connection test:
```bash
uv run python test_connection.py
```

## Available Tools

### `ping`
Simple test tool to verify the server is working.

**Usage:** "Ping the homelab server"

### `list_containers`
List all Docker containers with their status.

**Parameters:**
- `all` (boolean, optional): Show all containers (default: true). Set to false to show only running containers.

**Usage examples:**
- "List all my Docker containers"
- "Show me running containers only"
- "What containers are running in my homelab?"

## Development

### Project Structure
```
homelab-mcp-server/
├── src/
│   └── homelab_mcp/
│       ├── __init__.py
│       └── server.py          # Main MCP server
├── tests/                      # Tests (coming soon)
├── pyproject.toml              # Dependencies & config
├── test_connection.py          # Docker connection test
└── README.md
```

### Running the server manually
```bash
uv run python src/homelab_mcp/server.py
```

The server communicates via stdin/stdout using JSON-RPC, so running it manually won't show much output unless you send properly formatted MCP messages.

### Adding new tools

1. Add the tool metadata to `list_tools()` function in `server.py`
2. Implement the tool logic in `call_tool()` function
3. Test with Claude Code or write a unit test

## How It Works

### MCP Architecture
```
┌─────────────┐         MCP Protocol        ┌──────────────────┐
│   Claude    │ ←──────────────────────────→ │   This Server    │
│  (Client)   │    JSON-RPC over stdio      │   (homelab-mcp)  │
└─────────────┘                              └──────────────────┘
                                                      ↓
                                              ┌──────────────────┐
                                              │  Docker Engine   │
                                              │  (docker-py SDK) │
                                              └──────────────────┘
```

### Communication Flow

1. **Claude sends request** → JSON-RPC message via stdin
2. **MCP server receives** → Routes to appropriate tool handler
3. **Server calls Docker API** → Using docker-py SDK
4. **Docker responds** → Container info, logs, status, etc.
5. **Server formats response** → TextContent with results
6. **Claude receives response** → Displays to user

### Key Components

**Server (`server.py`)**
- Implements MCP protocol using official SDK
- Declares available tools via `list_tools()`
- Executes tool calls via `call_tool()`
- Manages Docker client connection

**Docker Client (`docker.from_env()`)**
- Official Python SDK for Docker
- Automatically connects to Docker daemon (socket/env)
- Provides full Docker API access

**MCP SDK (`mcp` package)**
- Handles all protocol details (JSON-RPC, validation)
- Type-safe tool definitions
- stdin/stdout communication

## Next Steps

See the [GitHub issues](https://github.com/shcizo/homelab-mcp-server/issues) for planned features:

- Container log fetching and searching
- Docker Compose project management
- Volume and storage management
- Image management and updates
- Resource monitoring (CPU, memory, network)
- Container health checks
- And 30+ more features!

## License

MIT

## Contributing

Contributions welcome! Please open an issue first to discuss what you'd like to change.