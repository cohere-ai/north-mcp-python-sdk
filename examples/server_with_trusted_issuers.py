"""
Example: JWT Signature Verification with Trusted Issuers

When `trusted_issuers` is configured, the server cryptographically verifies
JWT signatures against the specified OAuth/OIDC providers' public keys.

This provides stronger security by ensuring tokens were actually issued
by your identity provider, not just validly formatted.

Without trusted_issuers: Tokens are decoded but signatures aren't verified
With trusted_issuers: Tokens must be signed by a trusted identity provider
"""

from fastmcp.server.dependencies import get_access_token

from north_mcp_python_sdk import NorthMCPServer

TRUSTED_ISSUERS = [
    "https://accounts.google.com",
    "https://login.microsoftonline.com/common/v2.0",
]

mcp = NorthMCPServer(
    "Verified Auth Demo",
    trusted_issuers=TRUSTED_ISSUERS,
    debug=True,
)


@mcp.tool()
def secure_operation() -> dict[str, str | bool | None]:
    """
    Perform an operation that requires cryptographically verified identity.

    Only tokens signed by a trusted issuer can call this tool.
    """
    token = get_access_token()

    if token is None:
        return {"error": "No access token"}

    return {
        "email": token.claims.get("email"),
        "verified": True,
        "message": "Your JWT signature was cryptographically verified",
    }


@mcp.tool()
def get_verified_identity() -> dict[str, str | bool | None]:
    """Get the verified user identity from the access token."""
    token = get_access_token()

    if token is None:
        return {"error": "No access token"}

    return {
        "email": token.claims.get("email"),
        "client_id": token.client_id,
        "signature_verified": True,
    }


if __name__ == "__main__":
    print("Starting MCP Server with JWT signature verification...")
    print()
    print("Trusted issuers:")
    for issuer in TRUSTED_ISSUERS:
        print(f"  - {issuer}")
    print()
    print("Only tokens signed by these identity providers will be accepted.")
    print("Server running on port 5224...")

    mcp.run(transport="streamable-http", port=5224)
