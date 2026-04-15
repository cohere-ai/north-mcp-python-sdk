"""
Example: Custom Routes for Kubernetes Health Checks

MCP servers deployed in Kubernetes need health check endpoints that
work without authentication. Custom routes automatically bypass auth,
making them perfect for:
- Liveness probes (/health)
- Readiness probes (/ready)
- Metrics endpoints (/metrics)

MCP protocol endpoints (/mcp, /sse) still require authentication.
"""

from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("K8s Ready Server", port=5222)


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> JSONResponse:
    """Kubernetes readiness probe - no auth required."""
    return JSONResponse({"status": "ready", "checks": {"mcp": "ok"}})


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(request: Request) -> PlainTextResponse:
    """Prometheus metrics endpoint - no auth required."""
    return PlainTextResponse(
        (
            "# HELP mcp_requests_total Total MCP requests\n"
            "# TYPE mcp_requests_total counter\n"
            "mcp_requests_total 0\n"
        ),
        media_type="text/plain",
    )


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers - requires authentication."""
    token = get_access_token()
    email = token.claims.get("email") if token else "unknown"
    print(f"Add called by: {email}")
    return a + b


if __name__ == "__main__":
    print("MCP Server with Kubernetes endpoints")
    print()
    print("Public endpoints (no auth):")
    print("  GET /ready   - Readiness probe")
    print("  GET /metrics - Prometheus metrics")
    print()
    print("Protected endpoints (auth required):")
    print("  POST /mcp    - MCP protocol")

    mcp.run(transport="streamable-http")
