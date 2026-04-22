"""
Example: Basic Authentication with North MCP Server

This is the simplest example of an authenticated MCP server.
All MCP protocol endpoints (/mcp, /sse) require authentication automatically.
"""

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Auth Demo")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers. Only authenticated users can call this tool."""
    token = get_access_token()
    email = token.claims.get("email") if token else "unknown"
    print(f"Add tool called by: {email}")
    return a + b


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=5222)
