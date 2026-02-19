"""
Example: MCP Client Connecting to North MCP Server

This example shows how to connect to a North MCP server and call tools.
The client must provide a valid Bearer token in the Authorization header.

To generate a test token, run:
    python create_bearer_token.py --email user@example.com
"""

import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    # Generate this token using: python create_bearer_token.py
    bearer_token = (
        "eyJzZXJ2ZXJfc2VjcmV0IjogbnVsbCwgInVzZXJfaWRfdG9rZW4iOiAiZXlKaGJHY2"
        "lPaUpJVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SmxiV0ZwYkNJNkluUmxjM1JB"
        "WlhoaGJYQnNaUzVqYjIwaWZRLkVrb2dQSzVfclBUSWxsRXM4bEhIaWRRdTZrckM2NVVO"
        "N0ZwWUxPTXFTMlEiLCAiY29ubmVjdG9yX2FjY2Vzc190b2tlbnMiOiB7fX0="
    )

    headers = {"Authorization": f"Bearer {bearer_token}"}

    async with httpx.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(
            url="http://localhost:5222/mcp",
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List available tools
                tools = await session.list_tools()
                print("Available tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Call a tool
                result = await session.call_tool("add", {"a": 5, "b": 3})
                print(f"\nResult of add(5, 3): {result}")


if __name__ == "__main__":
    asyncio.run(main())
