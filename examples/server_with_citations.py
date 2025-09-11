"""
Example shows how to return results that are interpreted as citations in the North UI
 using the `_north_metadata` field. Simulating a web search through wikipedia.
"""

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user

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
            },
        }
    ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
