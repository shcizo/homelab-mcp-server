# Homelab MCP Server Dockerfile
# Provides Docker management capabilities with access to host Docker daemon

FROM python:3.14-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy dependency files and source code (needed for editable install)
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# Install Python dependencies (editable install requires source code)
RUN uv pip install --system -e .

# Create a non-root user for running the server (security best practice)
# Note: This user needs to be part of a group with Docker socket access
# The GID 999 is commonly used for the docker group, but may vary by system
RUN groupadd -g 999 docker || true && \
    useradd -m -u 1000 -G 999 mcp && \
    chown -R mcp:mcp /app

# Switch to non-root user
USER mcp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DOCKER_HOST=unix:///var/run/docker.sock

# Expose MCP server via stdin/stdout
# The server communicates using JSON-RPC over stdio, not HTTP
ENTRYPOINT ["python", "-m", "homelab_mcp.server"]

# Health check (optional - checks if server process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python -m homelab_mcp.server" || exit 1

# ============================================================================
# Docker Run Instructions:
# ============================================================================
#
# RECOMMENDED: Use the pre-built image from GitHub Container Registry:
#
# docker pull ghcr.io/shcizo/homelab-mcp-server:latest
# docker run -it --rm \
#   -v /var/run/docker.sock:/var/run/docker.sock \
#   ghcr.io/shcizo/homelab-mcp-server:latest
#
# Or if you built this image locally:
#
# docker build -t homelab-mcp-server .
# docker run -it --rm \
#   -v /var/run/docker.sock:/var/run/docker.sock \
#   homelab-mcp-server
#
# Important notes:
# - The -v flag mounts the host Docker socket into the container
# - This gives the container full access to manage Docker on the host
# - The container user must have permissions to access the Docker socket
# - On Linux, you may need to add the user to the docker group or adjust socket permissions
#
# For use with Claude Code MCP configuration:
# {
#   "mcpServers": {
#     "homelab": {
#       "command": "docker",
#       "args": [
#         "run",
#         "-i",
#         "--rm",
#         "-v", "/var/run/docker.sock:/var/run/docker.sock",
#         "ghcr.io/shcizo/homelab-mcp-server:latest"
#       ]
#     }
#   }
# }
# ============================================================================
