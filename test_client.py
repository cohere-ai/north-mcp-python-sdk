import asyncio

from mcp import ClientSession
from mcp.client.sse import sse_client

from examples.create_bearer_token import create_bearer_token


async def run(url: str, bearer_token: str):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
    }
    async with sse_client(url=url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
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
            url="http://0.0.0.0:5222/sse",
            bearer_token=create_bearer_token(email="matthias.hericks@cohere.com"),
        )
    )
