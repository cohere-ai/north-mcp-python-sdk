import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from examples.create_bearer_token import create_bearer_token


async def run(url: str, bearer_token: str, user_id: str):
    headers = {"Authorization": f"Bearer {bearer_token}", "x-north-user-id": user_id}
    async with streamablehttp_client("http://localhost:5222/mcp", headers=headers) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            # initialize the connection
            await session.initialize()

            # get available tools
            tools = await session.list_tools()
            print("Available tools:", tools)

            # call tools
            result = await session.call_tool("count")
            print(result)
            result = await session.call_tool("increment")
            print(result)
            result = await session.call_tool("count")
            print(result)


if __name__ == "__main__":
    asyncio.run(
        run(
            url="https://c9fb-2001-a61-3501-6301-1577-a846-2914-7060.ngrok-free.app/sse",
            bearer_token=create_bearer_token(email="abcd@company.com"),
            user_id="63599fde-49f8-4ce5-a46a-75337f07a950",
        )
    )
