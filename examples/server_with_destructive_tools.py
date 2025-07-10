from mcp.types import ToolAnnotations
from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Demo", port=5222)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
