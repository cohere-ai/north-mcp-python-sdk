# North MCP Python SDK

This SDK builds on top of the original SDK. Please refer to the [original repository's README](https://github.com/modelcontextprotocol/python-sdk) for general information. This README focuses on North-specific details.


## Installation

```
uv pip install git+ssh://git@github.com/cohere-ai/north-mcp-python-sdk.git
```


## Why this repository
This repository provides code to enable your server to use authentication with North, a custom extension to the original specification. Other than that, no changes are made to the SDK; this builds on top of it.


## Main differences

* North only supports the StreamableHTTP transport. The sse transport is deprecated, it will work for backwards compatibility, but you shouldn't use it if you are creating new servers
* You can protect all requests to your server with a secret.
* You can access the user's OAuth token to interact with third-party services on their behalf.
* You can access the user's identity (from the identity provider used with North).
* **Debug mode** for detailed authentication logging and troubleshooting.

## FastMCP Integration

If you are building on top of `FastMCP` directly, you can install the lightweight middleware shipped with this SDK to capture North-specific context without enabling full authentication:

```python
from fastmcp import FastMCP
from north_mcp_python_sdk.middleware import (
    FastMCPNorthMiddleware,
    get_north_request_context,
)

mcp = FastMCP("Demo")
app = mcp.streamable_http_app()
app.add_middleware(FastMCPNorthMiddleware)


@mcp.tool()
def echo(_: dict) -> dict:
    ctx = get_north_request_context()
    return {
        "user_id_token": ctx.user_id_token,
        "connector_tokens": ctx.connector_tokens,
    }
```

The middleware reads the `X-North-ID-Token` header (if present) and parses Base64-encoded JSON from `X-North-Connector-Tokens`. It never returns a 401—it simply exposes these values through a context variable and `request.state.north_context` for downstream handlers.

## Examples

This repository contains example servers that you can use as a quickstart. You can find them in the [examples directory](https://github.com/cohere-ai/north-mcp-python-sdk/tree/main/examples).

There are 2 examples, one that uses the auth to get the user making the tool call, and the other one shows how to send the right metadata so that the North UI can display the tool call results correctly.


## Authentication

This SDK offers several strategies for authenticating users and authorizing their requests.


#### I only want north to be able to send requests to my server
```python
mcp = NorthMCPServer(name="Demo", port=5222, server_secret="secret")
```

#### I want to get the identity of the north user that is calling my server
Refer to `examples/server_with_auth.py`. During your request call the following:
```python
user = get_authenticated_user()
print(user.email)
```


#### I need access to a third party service via oauth (e.g.: google drive, slack, etc...)
Similar as above:
```
user = get_authenticated_user()
print(user.connector_access_tokens)
```

## Debug Mode

The North MCP SDK includes a comprehensive debug mode that provides detailed logging of authentication processes, incoming requests, and token validation. This is invaluable when troubleshooting authentication issues.

### Enabling Debug Mode

There are several ways to enable debug mode:

#### 1. Environment Variable (Recommended)
```bash
export DEBUG=true
python your_server.py
```

#### 2. Constructor Parameter
```python
mcp = NorthMCPServer(name="Demo", port=5222, debug=True)
```

### What Gets Logged in Debug Mode

When debug mode is enabled, you'll see detailed logs including:

- **Request Headers**: All incoming HTTP headers (including Authorization)
- **Token Parsing**: Base64 decoding and JSON parsing of auth tokens
- **JWT Validation**: User ID token decoding and validation steps
- **Authentication Details**: User email, available connectors, token counts
- **Error Context**: Detailed error messages with troubleshooting context

### Example Debug Output

```
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Authenticating request from ('127.0.0.1', 54321)
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Request headers: {'authorization': 'Bearer eyJ...', 'content-type': 'application/json'}
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Authorization header present (length: 248)
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Successfully decoded base64 auth header
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Successfully parsed auth tokens. Has server_secret: True, Has user_id_token: True, Connector count: 2
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Available connectors: ['google', 'slack']
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Successfully decoded user ID token. Email: user@example.com
2024-01-15 10:30:45 - NorthMCP.AuthContext - DEBUG - Setting authenticated user in context: email=user@example.com, connectors=['google', 'slack']
```

### Debug Mode Examples

See the - `examples/server_with_debug.py` for a debug mode for an example:

### Security Note

Debug mode logs sensitive information including request headers and token metadata. **Never enable debug mode in production environments** as it may expose authentication details in logs.

## Local Development without North

This guide describes how to test your MCP server locally without connecting it to North. For this, we will use the MCP Inspector. You can run it with:
```
npx @modelcontextprotocol/inspector
```

If authentication is not required and you just want to run it locally, you can choose the stdio transport. Navigate to the [MCP Inspector](http://127.0.0.1:6274) and configure it as follows:
* Transport Type: stdio
* Command: uv
* Arguments: run examples/server_with_auth.py --transport stdio

From here:
* Click "Connect"
* Select "Tools" on the top of the screen.
* Click "List Tools" -> "add"
* Add the numbers and click "Run". You should see the sum.


### Adding authentication

If you want to test the authentication mechanism locally you can do the following. First start the server with the streamable http transport:

```
uv run examples/server_with_auth.py --transport streamable-http
```

Next, create a bearer token. You can generate one using `examples/create_bearer_token.py` or use a pre-made one.

Navigate to the MCP Inspector and configure it like this:
* Transport Type: Streamable HTTP
* URL: http://localhost:5222/mcp
* Authentication -> Bearer token: eyJzZXJ2ZXJfc2VjcmV0IjogInNlcnZlcl9zZWNyZXQiLCAidXNlcl9pZF90b2tlbiI6ICJleUpoYkdjaU9pSklVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKbGJXRnBiQ0k2SW5SbGMzUkFZMjl0Y0dGdWVTNWpiMjBpZlEuV0pjckVUUi1MZnFtX2xrdE9vdjd0Q1ktTmZYR2JuYTVUMjhaeFhTaEZ4SSIsICJjb25uZWN0b3JfYWNjZXNzX3Rva2VucyI6IHsiZ29vZ2xlIjogImFiYyJ9fQ==

Follow the same process as before. When you call the tool, you should see the following log in the terminal where you started the server:

```
This tool was called by: test@company.com
```

## Development

### Prerequisites

To contribute to this project, you'll need:

- **Python 3.11+**: Required for the SDK
- **uv >= 0.8.13**: Used for dependency management, formatting, and CI checks

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/cohere-ai/north-mcp-python-sdk.git
   cd north-mcp-python-sdk
   ```

2. Install dependencies:
   ```bash
   uv sync --dev
   ```

### Code Formatting

This project uses `uv format` for consistent code formatting. The CI pipeline enforces these standards:

```bash
# Check formatting (same as CI)
uv format --preview-features format --check

# Apply formatting
uv format --preview-features format
```

### Running Tests

```bash
uv run pytest
```

### Contributing

Before submitting a PR:
1. Ensure your code passes formatting checks: `uv format --preview-features format --check`
2. Run the test suite: `uv run pytest`
3. Follow the existing code style and patterns
