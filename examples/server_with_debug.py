from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

# Create server with debug mode enabled
mcp = NorthMCPServer("Debug Demo", port=5223, debug=True)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""

    try:
        user = get_authenticated_user()
        print(f"Tool called by authenticated user: {user.email}")
        print(
            f"Available connectors: {list(user.connector_access_tokens.keys())}"
        )
    except Exception as e:
        print(f"Unauthenticated user or error: {e}")

    result = a + b
    print(f"Adding {a} + {b} = {result}")
    return result


@mcp.tool()
def get_user_info() -> dict:
    """Get information about the authenticated user"""

    try:
        user = get_authenticated_user()
        return {
            "email": user.email,
            "available_connectors": list(user.connector_access_tokens.keys()),
            "connector_count": len(user.connector_access_tokens),
        }
    except Exception as e:
        return {"error": str(e), "authenticated": False}


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""

    try:
        user = get_authenticated_user()
        print(f"Multiply tool accessed by: {user.email}")
    except Exception:
        print("Multiply tool accessed by unauthenticated user")

    result = a * b
    print(f"Multiplying {a} * {b} = {result}")
    return result


if __name__ == "__main__":
    print("Starting North MCP Server in DEBUG mode...")
    print("Debug logging will show:")
    print("- Incoming request headers")
    print("- Authentication token parsing details")
    print("- User context information")
    print("- Connector access token details")
    print("- Any authentication errors with detailed context")
    print()
    print("Use this mode when troubleshooting authentication issues.")
    print("Server running on port 5223...")

    mcp.run(transport="streamable-http")
