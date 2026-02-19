"""
Example: Server Secret for Additional Security

Configure a server_secret to add an additional layer of authentication.
Requests must include the correct secret in addition to user credentials.

This is useful for:
- Restricting which North deployments can access this server
- Adding defense-in-depth beyond user authentication
- Environment-specific access control

Note: The server_secret is deprecated in favor of trusted_issuers
for new deployments. Use trusted_issuers for cryptographic verification.
"""

import os

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

SERVER_SECRET = os.getenv("MCP_SERVER_SECRET", "development-secret")

mcp = NorthMCPServer(
    "Secret Protected Server",
    port=5222,
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
    print("Starting MCP Server with server secret protection...")
    print()
    print("Requests must include the server secret in the auth payload.")
    print("Set MCP_SERVER_SECRET environment variable to configure.")
    print()
    print("Generate a test token with:")
    print(f'  python create_bearer_token.py --server-secret "{SERVER_SECRET}"')

    mcp.run(transport="streamable-http")
