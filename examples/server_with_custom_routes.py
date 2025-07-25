from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user, get_authenticated_user_optional

mcp = NorthMCPServer("Demo with Custom Routes", port=5222)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers - this tool requires authentication"""
    try:
        user = get_authenticated_user()
        print(f"Tool called by authenticated user: {user.email}")
    except Exception:
        print("Tool called by unauthenticated user (shouldn't happen)")
    
    return a + b


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint - no authentication required"""
    return PlainTextResponse("OK")


@mcp.custom_route("/status", methods=["GET"])
async def status_check(request: Request) -> JSONResponse:
    """Status endpoint - no authentication required"""
    return JSONResponse({
        "status": "running",
        "server": "NorthMCP Demo",
        "authenticated": False
    })


@mcp.custom_route("/user-info", methods=["GET"])
async def user_info(request: Request) -> JSONResponse:
    """User info endpoint that shows auth is optional for custom routes"""
    user = get_authenticated_user_optional()
    
    if user:
        return JSONResponse({
            "authenticated": True,
            "email": user.email,
            "connectors": list(user.connector_access_tokens.keys())
        })
    else:
        return JSONResponse({
            "authenticated": False,
            "message": "This custom route works without authentication!"
        })


if __name__ == "__main__":
    print("Starting server with custom routes...")
    print("Try these endpoints:")
    print("  GET /health - Simple health check")
    print("  GET /status - Status information")
    print("  GET /user-info - Shows authentication is optional")
    print("  POST /mcp - MCP protocol endpoint (requires auth)")
    print("  GET /sse - Server-sent events endpoint (requires auth)")
    
    mcp.run(transport="streamable-http")
