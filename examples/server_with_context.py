"""
Example: Accessing North Context Headers

North can pass additional context to MCP servers via X-North-Context-* headers.
Use `get_north_context()` to access these values in your tools.

This is useful for passing tenant IDs, feature flags, or other
request-scoped context from the North platform to your MCP server.
"""

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer, get_north_context

mcp = NorthMCPServer("Context Demo")


@mcp.tool()
def process_with_context(data: str) -> dict[str, str | dict[str, str] | None]:
    """
    Process data using context from North headers.

    Context is passed via X-North-Context-* headers:
    - X-North-Context-Tenant-ID → {"tenant-id": "..."}
    - X-North-Context-Feature-Flags → {"feature-flags": "..."}
    """
    token = get_access_token()
    context = get_north_context()

    return {
        "email": token.claims.get("email") if token else None,
        "data": data,
        "context": context,
        "tenant_id": context.get("tenant-id"),
        "feature_flags": context.get("feature-flags"),
    }


@mcp.tool()
def get_context() -> dict[str, str]:
    """Return all available North context headers."""
    return get_north_context()


if __name__ == "__main__":
    print("Starting MCP Server with context support...")
    print()
    print("Pass context via headers:")
    print("  X-North-Context-Tenant-ID: your-tenant-id")
    print("  X-North-Context-Feature-Flags: flag1,flag2")

    mcp.run(transport="streamable-http", port=5222)
