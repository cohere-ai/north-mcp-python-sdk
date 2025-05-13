import argparse
from collections import defaultdict

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

mcp = NorthMCPServer(name="Demo", port=5222)

counts = defaultdict(int)


@mcp.tool()
def count() -> int:
    """Get current count"""

    try:
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
        return counts[user.email]
    except:
        print("unauthenticated user")
        return counts["default"]


@mcp.tool()
def increment() -> str:
    """Increment the count for the authenticated user"""

    try:
        user = get_authenticated_user()
        print(f"This tool was called by: {user.email}")
        counts[user.email] += 1
    except:
        print("unauthenticated user")
        counts["default"] += 1

    return "success"


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
