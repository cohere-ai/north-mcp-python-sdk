"""
Example shows how to return results that are interpreted as citations in the North UI
 using the `_north_metadata` field. Simulating a web search through wikipedia.
"""

from north_mcp_python_sdk import NorthMCPServer

from datetime import datetime

mcp = NorthMCPServer("Demo", port=5222)


@mcp.tool()
def canada_knowledge(query: str) -> list[dict]:
    """Search for information about Canada"""

    return [
        {
            "text": "Canada is a country in North America. Its ten provinces and three territories extend from the Atlantic Ocean to the Pacific Ocean and northward into the Arctic Ocean, making it the world's second-largest country by total area, with the world's longest coastline.",
            "_north_metadata": {
                "title": "Canada - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Canada",
                "author_name": "Dave Smith",
                "last_updated": str(datetime(2020, 1, 2).timestamp()),
                "page_number": str(1),
            },
        },
    ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
