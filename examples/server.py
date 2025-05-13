import argparse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

mcp = NorthMCPServer(name="Demo", port=5222)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""

    try:
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
    except:
        print("unauthenticated user")

    return a + b


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the MCP server with configurable transport."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport method to use (default: sse)",
    )
    args = parser.parse_args()

    mcp.run(transport=args.transport)
