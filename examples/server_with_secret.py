"""Deprecated compatibility example for legacy server_secret deployments.

Do not use this for new MCP servers. Use `examples/server_with_trusted_issuers.py`
so the server validates `X-North-ID-Token` signatures from trusted issuers.
"""

import os

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

SERVER_SECRET = os.getenv("MCP_SERVER_SECRET", "development-secret")

mcp = NorthMCPServer(
    "Secret Protected Server",
    server_secret=SERVER_SECRET,
)


@mcp.tool()
def protected_operation() -> dict[str, str | None]:
    """
    This operation requires both:
    1. Valid user authentication (email/ID token)
    2. Correct server secret in the request
    """
    token = get_access_token()

    return {
        "email": token.claims.get("email") if token else None,
        "message": "Access granted - server secret verified",
    }


if __name__ == "__main__":
    print("Starting deprecated server_secret compatibility example...")
    print()
    print("server_secret is deprecated. Prefer server_with_trusted_issuers.py.")
    print()

    mcp.run(transport="streamable-http", port=5222)
