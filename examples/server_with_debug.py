"""
Example: Debug Mode for Troubleshooting Authentication

Enable debug mode to see detailed logs about:
- Incoming request headers
- Token parsing and validation
- Authentication decisions
- User context extraction

Useful when troubleshooting authentication issues.
"""

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Debug Demo", debug=True)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers with debug logging."""
    token = get_access_token()

    if token:
        print(f"Tool called by: {token.claims.get('email')}")
        connectors: dict[str, str] = token.claims.get(
            "connector_access_tokens", {}
        )
        print(f"Available connectors: {list(connectors.keys())}")
    else:
        print("No access token available")

    result = a + b
    print(f"Computed: {a} + {b} = {result}")
    return result


@mcp.tool()
def inspect_token() -> dict[str, str | int | list[str] | None]:
    """Inspect the full access token for debugging purposes."""
    token = get_access_token()

    if token is None:
        return {"error": "No access token"}

    connectors: dict[str, str] = token.claims.get(
        "connector_access_tokens", {}
    )

    return {
        "client_id": token.client_id,
        "email": token.claims.get("email"),
        "scopes": token.scopes,
        "token_length": len(token.token) if token.token else 0,
        "connector_count": len(connectors),
        "connectors": list(connectors.keys()),
    }


if __name__ == "__main__":
    print("Starting North MCP Server in DEBUG mode...")
    print()
    print("Debug logging will show:")
    print("  - Incoming request headers")
    print("  - Token parsing details")
    print("  - Authentication decisions")
    print("  - User context information")
    print()
    print("Server running on port 5223...")

    mcp.run(transport="streamable-http", port=5223)
