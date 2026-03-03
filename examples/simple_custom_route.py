"""
Example: Minimal Custom Route for Health Checks

The simplest way to add a health check endpoint for Kubernetes.
Custom routes bypass authentication automatically.
"""

from starlette.requests import Request
from starlette.responses import PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Simple Server")


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> PlainTextResponse:
    """Health check endpoint - no authentication required."""
    return PlainTextResponse("OK")


@mcp.tool()
def echo(message: str) -> str:
    """Echo the message back - requires authentication."""
    return f"Echo: {message}"


if __name__ == "__main__":
    mcp.run()
