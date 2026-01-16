from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

from database import DATABASE

# MCP server with operational endpoints for container orchestration
mcp = NorthMCPServer("MCP Server with K8s Endpoints", port=5222)

@mcp.tool()
def fetch_knowledge(key: str) -> str:
    """This tool retrieves official stc internal knowledge stored in a simple key–value format. Each key corresponds to a specific category of corporate information.

You MUST call this tool whenever the user's request relies on or implies internal stc-specific knowledge, even if the user does not mention “stc” explicitly.
The tool should be used instead of general world knowledge whenever the query touches any of the domains covered by the available keys.

## When to call the Tool
You must call the tool if any of the following are true:
    - The user requests writing, editing, or generating any content (call the tool with the style key).
    - The user assumes the assistant already knows stc-specific information or asks a question framed from an internal perspective (e.g., "What is our strategy?", “How do we communicate X?”).
    - The user asks a question that cannot be correctly answered without internal stc facts, even if the need is implicit and not directly stated.
    - The user asks about, references, or implies information tied to one of the keys (definitions, summaries, explanations, examples, guidance, etc.).

Available Keys:
    - strategy — stc's high-level strategic direction and priorities
    - ai_strategy — stc’s AI vision, roadmap, and guiding principles
    - style — communication guidelines for written communication like: email, messages, web page, branding marterials, end of year reports, etc. should be called then the user askes for writing or editing content,
    - hierarchy — Reporting structure or organizational hierarchy
    - subsidiaries — List of stc subsidiaries
    - diversity_and_inclusion — DEI principles and commitments
"""
    
    return DATABASE.get(key, "Knowledge not found.")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Kubernetes liveness probe endpoint - automatically bypasses authentication"""
    return PlainTextResponse("OK")


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> JSONResponse:
    """Kubernetes readiness probe - checks if server is ready to accept traffic"""
    # In a real implementation, you might check database connections,
    # external service availability, etc.
    return JSONResponse(
        {
            "status": "ready",
            "server": "MCP Server with K8s Endpoints",
            "checks": {"mcp_protocol": "ok", "tools_loaded": "ok"},
        }
    )


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
    try:
        user = get_authenticated_user()
    except Exception:
        user = None

    # This endpoint works without auth but can show auth info if provided
    status_data = {
        "status": "running",
        "server": "MCP Server with K8s Endpoints",
        "version": "1.0.0",
        "uptime_seconds": 3600,  # In real implementation, track actual uptime
        "authenticated_request": user is not None,
    }

    if user:
        status_data["user_email"] = user.email
        status_data["available_connectors"] = list(
            user.connector_access_tokens.keys()
        )

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