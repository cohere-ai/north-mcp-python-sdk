import argparse
from collections import defaultdict

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import AuthenticatedNorthUser, get_authenticated_user

mcp = NorthMCPServer(name="Demo", port=5222)

counts = defaultdict(int)

default_user = AuthenticatedNorthUser(
    connector_access_tokens={}, email="default@company.com"
)


@mcp.tool()
def reset() -> str:
    """Reset the count to zero"""
    try:
        user = get_authenticated_user()
    except:
        user = default_user

    print(f"'reset' was called by: {user.email}")
    counts[user.default] = 0
    return "success"


@mcp.tool()
def count() -> int:
    """Get the current count"""
    try:
        user = get_authenticated_user()
    except:
        user = default_user

    print(f"'count' was called by: {user.email}")
    return counts[user.email]


@mcp.tool()
def increment() -> str:
    """Increment the count by 1"""
    try:
        user = get_authenticated_user()
    except:
        user = default_user

    print(f"'increment' was called by: {user.email}")
    counts[user.email] += 1
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
