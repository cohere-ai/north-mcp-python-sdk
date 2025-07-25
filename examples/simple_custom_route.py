from north_mcp_python_sdk import NorthMCPServer
from starlette.requests import Request
from starlette.responses import PlainTextResponse

# Create your North MCP server
mcp = NorthMCPServer("MyServer")

# Add a custom route - no auth middleware applied automatically!
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")

# That's it! Custom routes bypass auth, MCP routes (/mcp, /sse) require auth
if __name__ == "__main__":
    mcp.run()
