from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

mcp = NorthMCPServer("Demo", port=5222)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""

    try:
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
    except Exception:
        print("unauthenticated user")

    return a + b


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
