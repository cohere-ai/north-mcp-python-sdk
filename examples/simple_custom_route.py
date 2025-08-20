from north_mcp_python_sdk import NorthMCPServer
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Create MCP server ready for Kubernetes deployment
mcp = NorthMCPServer("MyMCPServer")

# Add health check for Kubernetes liveness probe
# Custom routes automatically bypass authentication - perfect for operational endpoints!
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Kubernetes liveness probe endpoint"""
    return PlainTextResponse("OK")

@mcp.tool()
def my_tool(message: str) -> str:
    """Example MCP tool - accessible via authenticated /mcp endpoint"""
    return f"Processed: {message}"

# Deploy with confidence: /health works without auth, /mcp requires auth
if __name__ == "__main__":
    print("MCP server ready for Kubernetes deployment!")
    print("Health check: GET /health (no auth)")
    print("MCP protocol: POST /mcp (requires auth)")
    mcp.run()
