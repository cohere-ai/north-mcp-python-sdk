"""
Example MCP server using multiple authentication methods.

This demonstrates how to configure multiple auth providers that are tried in order:
1. Bearer token authentication (North's original format)
2. API key authentication
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer, BearerTokenAuthProvider, APIKeyAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user, get_authenticated_user_optional

# Create server with multiple authentication methods
mcp = NorthMCPServer(
    name="Multi-Auth Demo",
    auth_providers=[
        # Try Bearer tokens first (North's original format)
        BearerTokenAuthProvider(server_secret="demo-secret", debug=True),
        # Fall back to API keys
        APIKeyAuthProvider(valid_keys=["api-key-123", "backup-key-456"], debug=True),
    ],
    debug=True
)


@mcp.tool()
def analyze_text(text: str) -> str:
    """Analyze text - supports both Bearer token and API key auth"""
    user = get_authenticated_user()
    return f"Analysis of '{text}' completed for {user.email}"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check - no authentication required"""
    return PlainTextResponse("OK - Multi-auth server running")


@mcp.custom_route("/auth-test", methods=["GET"])
async def auth_test(request: Request) -> JSONResponse:
    """Test endpoint that shows which auth method was used"""
    user = get_authenticated_user_optional()
    
    if user:
        # Determine auth method based on user properties
        if user.connector_access_tokens:
            auth_method = "Bearer Token (North format)"
        else:
            auth_method = "API Key"
            
        return JSONResponse({
            "authenticated": True,
            "user_email": user.email,
            "auth_method": auth_method,
            "available_connectors": list(user.connector_access_tokens.keys()) if user.connector_access_tokens else []
        })
    else:
        return JSONResponse({
            "authenticated": False,
            "supported_methods": [
                "Bearer token (Base64 JSON with server_secret)",
                "API key (X-API-Key header or Authorization: Bearer <key>)"
            ]
        })


if __name__ == "__main__":
    print("🔐 Starting MCP server with multiple authentication methods...")
    print("\nAuthentication methods (tried in order):")
    print("1. Bearer Token (North format):")
    print("   - Requires Base64-encoded JSON with server_secret")
    print("   - Server secret: demo-secret")
    print("2. API Key:")
    print("   - X-API-Key: api-key-123")
    print("   - Authorization: Bearer api-key-123")
    print("\nTest endpoints:")
    print("  GET /health - No auth required")
    print("  GET /auth-test - Shows which auth method was used")
    print("\nExamples:")
    print("  # API key via header")
    print("  curl -H 'X-API-Key: api-key-123' http://localhost:8000/auth-test")
    print("  # API key via Authorization")
    print("  curl -H 'Authorization: Bearer api-key-123' http://localhost:8000/auth-test")
    print("  # Bearer token (use create_bearer_token.py to generate)")
    
    mcp.run(transport="streamable-http")