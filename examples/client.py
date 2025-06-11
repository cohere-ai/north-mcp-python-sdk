import asyncio

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession


async def main():
    sample_token = "eyJzZXJ2ZXJfc2VjcmV0IjogInNlcnZlcl9zZWNyZXQiLCAidXNlcl9pZF90b2tlbiI6ICJleUpoYkdjaU9pSklVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKbGJXRnBiQ0k2SW5SbGMzUkFZMjl0Y0dGdWVTNWpiMjBpZlEuV0pjckVUUi1MZnFtX2xrdE9vdjd0Q1ktTmZYR2JuYTVUMjhaeFhTaEZ4SSIsICJjb25uZWN0b3JfYWNjZXNzX3Rva2VucyI6IHsiZ29vZ2xlIjogImFiYyJ9fQ=="
    headers = {"Authorization": sample_token}
    async with streamablehttp_client("http://localhost:5222/mcp", headers=headers) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_result = await session.call_tool("add", {"a": 5, "b": 3})
            print(tool_result)


if __name__ == "__main__":
    asyncio.run(main())
