import os

from north_mcp_python_sdk import NorthMCPServer


from mcp.types import (
    Annotations,
    ContentBlock,
    EmbeddedResource,
    Role,
    TextResourceContents,
)
from pydantic import AnyUrl

mcp = NorthMCPServer("UI as MCP Results", port=5566)  # pyright: ignore[reportUnknownVariableType]


def generate_html(*, theme: str, quote: str, author: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{theme}</title>
        <style>
            body {{
                margin: 0;
                padding: 40px;
                min-height: 100vh;
                background: linear-gradient(135deg, #ffeaa7, #fab1a0, #fd79a8, #a29bfe);
                background-size: 400% 400%;
                animation: gradientShift 8s ease infinite;
            }}
            @keyframes gradientShift {{
                0% {{ background-position: 0% 50%; }}
                50% {{ background-position: 100% 50%; }}
                100% {{ background-position: 0% 50%; }}
            }}
            .content {{
                position: relative;
                z-index: 1;
                color: #2d3436;
                text-align: center;
                max-width: 600px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.8);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                text-transform: uppercase;
                font-size: 2.5em;
                margin-bottom: 30px;
                color: #6c5ce7;
            }}
            .subtext {{
                font-size: 0.8em;
                color: #636e72;
                font-style: italic;
                text-transform: uppercase;
            }}
            button {{
                padding: 10px 20px;
                background: linear-gradient(45deg, #a29bfe, #fd79a8);
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                margin: 10px 0;
                transition: transform 0.2s ease;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 15px rgba(162, 155, 254, 0.4);
            }}
            p {{
                font-size: 1.2em;
                line-height: 1.6;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="content">
            <h1>{theme}</h1>
            <button onclick="changeGradient()">Change Colors</button>
            <p>{quote}</p>
            <p class="subtext">— {author}</p>
        </div>
        <script>
            let gradientIndex = 0;
            const gradients = [
                'linear-gradient(135deg, #ffeaa7, #fab1a0, #fd79a8, #a29bfe)',
                'linear-gradient(135deg, #81ecec, #74b9ff, #a29bfe, #fd79a8)',
                'linear-gradient(135deg, #fdcb6e, #e17055, #fd79a8, #6c5ce7)',
                'linear-gradient(135deg, #55efc4, #81ecec, #74b9ff, #a29bfe)'
            ];
            function changeGradient() {{
                gradientIndex = (gradientIndex + 1) % gradients.length;
                document.body.style.background = gradients[gradientIndex];
                document.body.style.backgroundSize = '400% 400%';
            }}
        </script>
    </body>
    </html>
    """


def get_resource(
    html_text: str, audience: list[Role] | None
) -> EmbeddedResource:
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            text=html_text,
            uri=AnyUrl("file:///dynamic-quote.html"),
            mimeType="text/html",
        ),
        annotations=Annotations(audience=audience),
    )


@mcp.resource("file://static-quote.html")
def get_quote() -> EmbeddedResource:
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            text=generate_html(
                theme="Motivation",
                quote="Hello, this is Patrick",
                author="Patrick Star",
            ),
            uri=AnyUrl("file:///static-quote.html"),
            mimeType="text/html",
        ),
        annotations=Annotations(audience=["user"]),
    )


@mcp.tool()
def html_demo_fast_mcp(
    theme: str, author: str, inspirational_quote: str
) -> list[ContentBlock]:
    """Displays an inspirational quote in html. The quote, theme, and its author must be provided by the model."""

    return [
        get_resource(
            generate_html(
                theme=theme, quote=inspirational_quote, author=author
            ),
            ["user"],
        )
    ]


@mcp.tool()
def html_demo_fast_mcp_show_model(
    theme: str, author: str, inspirational_quote: str
) -> list[ContentBlock]:
    """Displays an inspirational quote in html. The quote, theme, and its author must be provided by the model."""

    return [
        get_resource(
            generate_html(
                theme=theme, quote=inspirational_quote, author=author
            ),
            ["user", "assistant"],
        )
    ]


if __name__ == "__main__":
    mcp.run("streamable-http")
