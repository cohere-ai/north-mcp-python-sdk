"""
Example: Returning Citations with Tool Results

Use the `_north_metadata` field to provide citation information
that the North UI will display alongside results.

Document citation metadata requires:
- renderer: "document"
- content: Text displayed in the citation

Optional document fields include `title`, `url`, `label`, and `meta`.
Author, update time, and page number belong inside `meta`.

Keep `title` and `url` at the top level too. North uses those fields when
labelling the tool result in the thinking UI.
"""

from datetime import datetime
from typing import Any

from north_mcp_python_sdk import NorthMCPServer

mcp = NorthMCPServer("Citations Demo")


@mcp.tool()
def search_knowledge_base(query: str) -> list[dict[str, Any]]:
    """Search the knowledge base and return results with citations."""
    python_text = (
        "Python is a high-level programming language known for its "
        "clear syntax and readability. It supports multiple programming "
        "paradigms including procedural, object-oriented, and functional."
    )
    python_title = "Python (programming language) - Wikipedia"
    python_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"

    zen_text = (
        "The Zen of Python emphasizes code readability and simplicity. "
        "Key principles include 'Beautiful is better than ugly' and "
        "'Simple is better than complex'."
    )
    zen_title = "PEP 20 – The Zen of Python"
    zen_url = "https://peps.python.org/pep-0020/"

    return [
        {
            "text": python_text,
            "title": python_title,
            "url": python_url,
            "_north_metadata": {
                "renderer": "document",
                "content": python_text,
                "title": python_title,
                "url": python_url,
                "meta": {
                    "author_name": "Wikipedia Contributors",
                    "last_updated": str(
                        int(datetime(2024, 1, 15).timestamp())
                    ),
                },
            },
        },
        {
            "text": zen_text,
            "title": zen_title,
            "url": zen_url,
            "_north_metadata": {
                "renderer": "document",
                "content": zen_text,
                "title": zen_title,
                "url": zen_url,
                "meta": {
                    "author_name": "Tim Peters",
                    "last_updated": str(
                        int(datetime(2004, 8, 23).timestamp())
                    ),
                },
            },
        },
    ]


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=5222)
