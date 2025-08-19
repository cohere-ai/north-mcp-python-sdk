from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user, get_authenticated_user_optional

# MCP server with operational endpoints for container orchestration
mcp = NorthMCPServer("MCP Server with K8s Endpoints", port=5222)


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
    """Kubernetes liveness probe endpoint - automatically bypasses authentication"""
    return PlainTextResponse("OK")


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> JSONResponse:
    """Kubernetes readiness probe - checks if server is ready to accept traffic"""
    # In a real implementation, you might check database connections,
    # external service availability, etc.
    return JSONResponse({
        "status": "ready",
        "server": "MCP Server with K8s Endpoints",
        "checks": {
            "mcp_protocol": "ok",
            "tools_loaded": "ok"
        }
    })


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics_endpoint(request: Request) -> PlainTextResponse:
    """Prometheus metrics endpoint for monitoring"""
    # In a real implementation, you would return actual Prometheus metrics
    metrics = """# HELP mcp_requests_total Total number of MCP requests
# TYPE mcp_requests_total counter
mcp_requests_total 42

# HELP mcp_tools_total Number of available MCP tools
# TYPE mcp_tools_total gauge
mcp_tools_total 1
"""
    return PlainTextResponse(metrics, media_type="text/plain")


@mcp.custom_route("/status", methods=["GET"])
async def status_check(request: Request) -> JSONResponse:
    """General status endpoint for monitoring dashboards"""
    user = get_authenticated_user_optional()
    
    # This endpoint works without auth but can show auth info if provided
    status_data = {
        "status": "running",
        "server": "MCP Server with K8s Endpoints",
        "version": "1.0.0",
        "uptime_seconds": 3600,  # In real implementation, track actual uptime
        "authenticated_request": user is not None
    }
    
    if user:
        status_data["user_email"] = user.email
        status_data["available_connectors"] = list(user.connector_access_tokens.keys())
    
    return JSONResponse(status_data)


if __name__ == "__main__":
    print("Starting MCP server with Kubernetes operational endpoints...")
    print("\nOperational endpoints (no authentication required):")
    print("  GET /health  - Liveness probe for Kubernetes")
    print("  GET /ready   - Readiness probe for Kubernetes")
    print("  GET /metrics - Prometheus metrics for monitoring")
    print("  GET /status  - General status for dashboards")
    print("\nMCP protocol endpoints (authentication required):")
    print("  POST /mcp    - JSON-RPC MCP communication")
    print("  GET /sse     - Server-sent events for streaming")
    print("\nPerfect for deployment in Kubernetes with proper health checks!")
    
    mcp.run(transport="streamable-http")
