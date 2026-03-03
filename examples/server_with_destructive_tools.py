"""
Example: Tool Annotations for Destructive Operations

Use ToolAnnotations to mark tools that perform destructive operations.
This helps clients warn users before executing dangerous actions.

Available annotations:
- destructiveHint: Tool may modify or delete data
- idempotentHint: Tool can be safely retried
- openWorldHint: Tool interacts with external systems
"""

from mcp.types import ToolAnnotations

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Annotated Tools Demo", port=5222)


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def delete_item(item_id: str) -> str:
    """Delete an item by ID. This action cannot be undone."""
    return f"Deleted item: {item_id}"


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
def get_item(item_id: str) -> dict[str, str]:
    """Get an item by ID. Safe to retry."""
    return {"id": item_id, "name": "Example Item"}


@mcp.tool(annotations=ToolAnnotations(openWorldHint=True))
def fetch_external_data(url: str) -> str:
    """Fetch data from an external URL."""
    return f"Would fetch: {url}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
