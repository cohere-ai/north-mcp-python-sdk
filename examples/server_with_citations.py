"""
Example: Returning Citations with Tool Results

Use the `_north_metadata` field to provide citation information
that the North UI will display alongside results.

Supported metadata fields:
- title: Document or page title
- url: Source URL
- author_name: Author of the content
- last_updated: Unix timestamp of last update
- page_number: Page number in document
"""

from datetime import datetime

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Citations Demo")


@mcp.tool()
def search_knowledge_base(query: str) -> list[dict[str, str | dict[str, str]]]:
    """Search the knowledge base and return results with citations."""
    return [
        {
            "text": (
                "Python is a high-level programming language known for its "
                "clear syntax and readability. It supports multiple programming "
                "paradigms including procedural, object-oriented, and functional."
            ),
            "_north_metadata": {
                "title": "Python (programming language) - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
                "author_name": "Wikipedia Contributors",
                "last_updated": str(int(datetime(2024, 1, 15).timestamp())),
            },
        },
        {
            "text": (
                "The Zen of Python emphasizes code readability and simplicity. "
                "Key principles include 'Beautiful is better than ugly' and "
                "'Simple is better than complex'."
            ),
            "_north_metadata": {
                "title": "PEP 20 – The Zen of Python",
                "url": "https://peps.python.org/pep-0020/",
                "author_name": "Tim Peters",
                "last_updated": str(int(datetime(2004, 8, 23).timestamp())),
            },
        },
    ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=5222)
