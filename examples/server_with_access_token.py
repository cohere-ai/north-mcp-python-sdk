"""
Example: Accessing User Claims from Access Token

This example demonstrates the recommended way to access authenticated user
information in North MCP servers using `get_access_token()`.

The access token contains:
- token: The raw JWT token string
- client_id: The user's email (if available)
- scopes: List of granted scopes
- claims: Dictionary with custom claims including:
  - email: User's email address
  - connector_access_tokens: Dict of connector name -> access token
"""

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Access Token Demo")


@mcp.tool()
def whoami() -> dict[str, str | bool | list[str] | None]:
    """Get information about the authenticated user from the access token."""
    token = get_access_token()

    if token is None:
        return {"error": "No access token available"}

    return {
        "email": token.claims.get("email"),
        "client_id": token.client_id,
        "scopes": token.scopes,
        "has_token": bool(token.token),
    }


@mcp.tool()
def get_connector_token(
    connector_name: str,
) -> dict[str, str | bool | list[str] | None]:
    """
    Retrieve an OAuth access token for a specific connector.

    This is useful when your MCP tool needs to call external APIs
    on behalf of the user (e.g., Google Drive, Slack, GitHub).
    """
    token = get_access_token()

    if token is None:
        return {"error": "No access token available"}

    connector_tokens: dict[str, str] = token.claims.get(
        "connector_access_tokens", {}
    )

    if connector_name not in connector_tokens:
        return {
            "error": f"No token available for connector: {connector_name}",
            "available_connectors": list(connector_tokens.keys()),
        }

    return {
        "connector": connector_name,
        "token_available": True,
        "token_preview": connector_tokens[connector_name][:20] + "..."
        if len(connector_tokens[connector_name]) > 20
        else connector_tokens[connector_name],
    }


@mcp.tool()
def list_available_connectors() -> dict[str, str | int | list[str] | None]:
    """List all connectors the user has authorized."""
    token = get_access_token()

    if token is None:
        return {"error": "No access token available"}

    connector_tokens: dict[str, str] = token.claims.get(
        "connector_access_tokens", {}
    )

    return {
        "email": token.claims.get("email"),
        "connector_count": len(connector_tokens),
        "connectors": list(connector_tokens.keys()),
    }


if __name__ == "__main__":
    print("Starting North MCP Server with Access Token examples...")
    print()
    print("Available tools:")
    print("  - whoami: Get authenticated user info from access token")
    print("  - get_connector_token: Retrieve OAuth token for a connector")
    print("  - list_available_connectors: List all authorized connectors")
    print()
    print("The access token claims contain:")
    print("  - email: User's email address")
    print("  - connector_access_tokens: OAuth tokens for external services")

    mcp.run(transport="streamable-http", port=5222)
