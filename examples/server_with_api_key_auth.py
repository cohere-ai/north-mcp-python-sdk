"""
Example MCP server using API key authentication.

This demonstrates how to use the new modular auth system with API keys
instead of the default Bearer token authentication.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer, APIKeyAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user, get_authenticated_user_optional

# Create server with API key authentication
mcp = NorthMCPServer(
    name="API Key Auth Demo",
    auth_providers=[
        APIKeyAuthProvider(
            valid_keys=["demo-key-123", "another-key-456"],
            debug=True
        )
    ],
    debug=True
)


@mcp.tool()
def process_data(input_text: str) -> str:
    """Process some data - requires API key authentication"""
    user = get_authenticated_user()
    return f"Processed '{input_text}' for user: {user.email}"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check - works without authentication"""
    return PlainTextResponse("OK")


@mcp.custom_route("/user-status", methods=["GET"])
async def user_status(request: Request) -> JSONResponse:
    """Show user status - demonstrates optional auth in custom routes"""
    user = get_authenticated_user_optional()
    
    if user:
        return JSONResponse({
            "authenticated": True,
            "user_id": user.email,
            "auth_method": "API Key"
        })
    else:
        return JSONResponse({
            "authenticated": False,
            "message": "Provide X-API-Key header or Authorization: Bearer <api-key>"
        })


if __name__ == "__main__":
    print("🔑 Starting MCP server with API key authentication...")
    print("\nTo test API key authentication, use one of these methods:")
    print("  curl -H 'X-API-Key: demo-key-123' http://localhost:8000/user-status")
    print("  curl -H 'Authorization: Bearer demo-key-123' http://localhost:8000/user-status")
    print("\nValid API keys: demo-key-123, another-key-456")
    print("\nCustom routes (no auth required):")
    print("  GET /health - Health check")
    print("  GET /user-status - Shows auth status")
    print("\nMCP endpoints (API key required):")
    print("  POST /mcp - MCP protocol endpoint")
    print("  GET /sse - Server-sent events endpoint")
    
    mcp.run(transport="streamable-http")