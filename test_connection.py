"""
Quick test to verify Docker connection works before configuring MCP
"""
import docker

try:
    client = docker.from_env()
    print("✓ Successfully connected to Docker daemon")

    # Try to list containers
    containers = client.containers.list(all=True)
    print(f"✓ Found {len(containers)} containers")

    for container in containers[:5]:  # Show first 5
        print(f"  - {container.name} ({container.status})")

    # Show Docker info
    info = client.info()
    print(f"\n✓ Docker version: {info.get('ServerVersion')}")
    print(f"✓ Running containers: {info.get('ContainersRunning')}")

except docker.errors.DockerException as e:
    print(f"✗ Error connecting to Docker: {e}")
    print("\nMake sure Docker is running!")
