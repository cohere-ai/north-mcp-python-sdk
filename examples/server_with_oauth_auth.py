"""
Example MCP server using OAuth authentication.

This demonstrates how to use the new OAuthAuthProvider with different
validation methods (JWT, introspection, custom validator).
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer, OAuthAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user, get_authenticated_user_optional


# Example 1: JWT-based OAuth validation
def create_jwt_oauth_server():
    """Create server with JWT-based OAuth authentication."""
    return NorthMCPServer(
        name="JWT OAuth Demo",
        auth_providers=[
            OAuthAuthProvider(
                jwt_secret="your-jwt-secret-key",
                jwt_algorithm="HS256",
                email_claim="email",  # Extract email from this JWT claim
                debug=True
            )
        ],
        debug=True
    )


# Example 2: Token introspection OAuth validation  
def create_introspection_oauth_server():
    """Create server with OAuth token introspection."""
    return NorthMCPServer(
        name="Introspection OAuth Demo",
        auth_providers=[
            OAuthAuthProvider(
                introspection_endpoint="https://your-oauth-server.com/oauth/introspect",
                client_id="your-client-id",
                client_secret="your-client-secret",
                email_claim="sub",  # Extract email from 'sub' claim
                debug=True
            )
        ],
        debug=True
    )


# Example 3: Custom OAuth validation
async def custom_token_validator(token: str) -> dict:
    """
    Custom OAuth token validator.
    
    This is called for each OAuth token and should return user info
    if the token is valid, or None if invalid.
    """
    # Example: validate against custom OAuth service
    # In real implementation, you would call your OAuth server's API
    
    # Mock validation - replace with real OAuth validation logic
    if token == "valid-oauth-token-123":
        return {
            "email": "user@oauth-example.com",
            "connector_access_tokens": {
                "google": "google-oauth-token",
                "slack": "slack-oauth-token"
            }
        }
    elif token.startswith("test-token-"):
        # Extract user ID from test token
        user_id = token.split("-")[-1]
        return {
            "email": f"test-user-{user_id}@example.com",
            "connector_access_tokens": {}
        }
    else:
        return None  # Invalid token


def create_custom_oauth_server():
    """Create server with custom OAuth validation."""
    return NorthMCPServer(
        name="Custom OAuth Demo",
        auth_providers=[
            OAuthAuthProvider(
                custom_validator=custom_token_validator,
                debug=True
            )
        ],
        debug=True
    )


# Example 4: Multi-provider setup with OAuth + API keys
def create_multi_auth_server():
    """Create server supporting both OAuth and API key authentication."""
    from north_mcp_python_sdk import APIKeyAuthProvider
    
    return NorthMCPServer(
        name="Multi-Auth Demo",
        auth_providers=[
            # Try OAuth first
            OAuthAuthProvider(
                custom_validator=custom_token_validator,
                debug=True
            ),
            # Fallback to API keys
            APIKeyAuthProvider(
                valid_keys=["fallback-api-key-123"],
                debug=True
            )
        ],
        debug=True
    )


# Choose which server to run (change this to test different examples)
mcp = create_custom_oauth_server()


@mcp.tool()
def oauth_protected_tool(message: str) -> str:
    """Tool that requires OAuth authentication"""
    user = get_authenticated_user()
    return f"OAuth user {user.email} sent: {message}"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check - works without authentication"""
    return PlainTextResponse("OK")


@mcp.custom_route("/user-info", methods=["GET"])
async def user_info(request: Request) -> JSONResponse:
    """Show user info - demonstrates optional auth in custom routes"""
    user = get_authenticated_user_optional()
    
    if user:
        return JSONResponse({
            "authenticated": True,
            "email": user.email,
            "connectors": list(user.connector_access_tokens.keys()),
            "auth_method": "OAuth"
        })
    else:
        return JSONResponse({
            "authenticated": False,
            "message": "Provide Authorization: Bearer <oauth-token>"
        })


if __name__ == "__main__":
    print("🔐 Starting MCP server with OAuth authentication...")
    print("\nTo test OAuth authentication:")
    print("  curl -H 'Authorization: Bearer valid-oauth-token-123' http://localhost:8000/user-info")
    print("  curl -H 'Authorization: Bearer test-token-456' http://localhost:8000/user-info")
    print("\nCustom routes (no auth required):")
    print("  GET /health - Health check")
    print("  GET /user-info - Shows auth status")
    print("\nMCP endpoints (OAuth required):")
    print("  POST /mcp - MCP protocol endpoint")
    print("  GET /sse - Server-sent events endpoint")
    print("\nNOTE: This example uses a mock validator. In production, implement")
    print("real OAuth validation using JWT secrets, introspection endpoints,")
    print("or integration with your OAuth provider (Dex, Auth0, etc.)")
    
    mcp.run(transport="streamable-http")