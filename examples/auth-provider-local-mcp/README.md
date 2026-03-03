# Example MCP Server with OAuth (Dex)

This project demonstrates an MCP server with multiple authentication options using [FastMCP](https://github.com/jlowin/fastmcp), including OAuth via [Dex](https://dexidp.io/) and North platform authentication.

## Prerequisites

- Docker and Docker Compose (for Dex OAuth)
- [uv](https://github.com/astral-sh/uv)

## Project Structure

```
├── main.py               # MCP server with configurable auth
├── .env                  # Environment variables
├── config.yaml.template  # Dex configuration template
├── docker-compose.yaml   # Dex container setup
└── pyproject.toml        # Python dependencies
```

## Setup

### 1. Configure Environment

Create a `.env` file with your configuration:

```bash
DEX_ISSUER="http://localhost:5886/dex"
DEX_JWKS_URI="http://localhost:5886/dex/keys"
DEX_AUTH_ENDPOINT="http://localhost:5886/dex/auth"
DEX_TOKEN_ENDPOINT="http://localhost:5886/dex/token"
CLIENT_ID="example-app"
CLIENT_SECRET="ZXhhbXBsZS1hcHAtc2VjcmV0"
SERVER_BASE_URL="http://localhost:5885"
SERVER_HOST="localhost"
SERVER_PORT=5885

# North auth configuration (for north mode)
# NORTH_TRUSTED_ISSUERS=""      # Comma-separated list of trusted issuers (optional)
# NORTH_SERVER_SECRET=""        # Server secret for server-to-server auth (optional)
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Start the Dex Identity Provider (for OAuth modes)

> **Note:** Dex is only required for `--auth oauth-proxy` and `--auth jwt` modes. Skip this step if using `--auth none` or `--auth north`.

Start the Dex container using Docker Compose:

```bash
docker compose up -d
```

This starts Dex on `http://localhost:5886`. You can verify it's running:

```bash
docker compose ps
```

To view logs:

```bash
docker compose logs -f dex
```

To stop Dex:

```bash
docker compose down
```

### 4. Run the MCP Server

Start the MCP server:

```bash
uv run python main.py
```

The MCP server will start on `http://localhost:5885` with the MCP endpoint at `http://localhost:5885/mcp`.

By default, the server runs with no authentication. Use the `--auth` flag to enable authentication (see CLI Options below).

#### CLI Options

```bash
uv run --env-file .env python main.py --help
```

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--auth` | `none`, `jwt`, `oauth-proxy`, `north` | `none` | Authentication type |
| `--host` | string | `localhost` | Host to bind the server to |
| `--port` | int | `5885` | Port to bind the server to |

**Authentication modes:**

- `--auth none` - No authentication (open access, default)
- `--auth jwt` - JWT verification only (requires pre-obtained token from Dex)
- `--auth oauth-proxy` - Full OAuth flow through Dex
- `--auth north` - North platform authentication

Examples:

```bash
# Run with no authentication (default)
uv run --env-file .env python main.py

# Run with OAuth proxy (Dex)
uv run --env-file .env python main.py --auth oauth-proxy

# Run with North authentication
uv run --env-file .env python main.py --auth north

# Run with JWT verification only
uv run --env-file .env python main.py --auth jwt

# Run on a different port
uv run --env-file .env python main.py --port 8080
```

### 5. Connect with MCP Inspector

Run the MCP Inspector to test the server:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI:

1. Set the **Transport Type** to `Streamable HTTP`
2. Set the **URL** to `http://localhost:5885/mcp`
3. Click **Connect**

If running with `--auth oauth-proxy`, you'll be redirected to the Dex login page for authentication.

## Test Credentials

Use these credentials to log in via Dex:

| Field    | Value              |
|----------|-------------------|
| Email    | admin@example.com |
| Password | password          |

## Configuration Details

### Ports

| Service    | Port |
|------------|------|
| Dex        | 5886 |
| MCP Server | 5885 |

### OAuth Flow

1. MCP Inspector connects to the MCP server
2. Server returns OAuth metadata with authorization endpoint
3. Inspector redirects to Dex for authentication
4. User logs in with test credentials
5. Dex redirects back to the MCP server's callback URL
6. Server exchanges the code for tokens
7. Inspector receives access token and can make authenticated requests

## Available Tools

The example MCP server provides the following tools:

- **add(a, b)** - Adds two numbers together
- **whoami()** - Returns information about the authenticated user's access token

## Obtaining an Upstream JWT Token

The `oauth-proxy` mode wraps the upstream Dex JWT in a FastMCP-issued token. If you want to use the raw upstream JWT directly (e.g., for testing with `--auth jwt` mode), follow these steps:

### 1. Run the Server with OAuth Proxy

Start the server with oauth-proxy authentication:

```bash
uv run --env-file .env python main.py --auth oauth-proxy
```

### 2. Connect and Authenticate

Use MCP Inspector to connect and complete the OAuth flow:

```bash
npx @modelcontextprotocol/inspector
```

1. Set **Transport Type** to `Streamable HTTP`
2. Set **URL** to `http://localhost:5885/mcp`
3. Click **Connect**
4. Log in with test credentials (`admin@example.com` / `password`)
5. Call any tool (e.g., the `add` tool)

### 3. Copy the Upstream Token from Logs

When you make an authenticated request, the server logs the upstream token:

```
[UPSTREAM TOKEN] access_token:
eyJhbGciOiJSUzI1NiIsImtpZCI6...
```

Copy the `access_token` value.

### 4. Stop the OAuth Proxy Server

Stop the server with `Ctrl+C`.

### 5. Restart with JWT Authentication

Start the server in JWT-only mode:

```bash
uv run --env-file .env python main.py --auth jwt
```

### 6. Use the Token in MCP Inspector

Connect using MCP Inspector with the upstream JWT:

1. Set **Transport Type** to `Streamable HTTP`
2. Set **URL** to `http://localhost:5885/mcp`
3. Expand **Request Headers** and add:
   - **Header Name:** `Authorization`
   - **Header Value:** `Bearer <your-upstream-access-token>`
4. Click **Connect**

You should now be authenticated using the upstream Dex JWT directly.

> **Note:** The upstream JWT has a limited lifetime (typically 1 hour). You'll need to repeat the oauth-proxy flow to obtain a fresh token when it expires.

## North Authentication

For North platform authentication, the server uses `NorthTokenVerifier` from the `north-mcp-python-sdk`. This is a minimal example of using North auth with FastMCP:

```python
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from north_mcp_python_sdk.auth import NorthTokenVerifier

# Configure North authentication
auth = NorthTokenVerifier(
    trusted_issuers=["https://auth.north.app"],  # Optional: restrict to specific issuers
    server_secret="your-server-secret",          # Optional: for server-to-server auth
)

# Create the MCP server with North auth
mcp = FastMCP("my-mcp-server", auth=auth)

@mcp.tool()
def whoami() -> dict:
    """Get the authenticated user's access token."""
    token = get_access_token()
    return token.model_dump() if token else {"error": "No access token"}

# Run with streamable HTTP
if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=8000)
```

To run this example server with North auth:

```bash
uv run --env-file .env python main.py --auth north
```

## Troubleshooting

### Dex not reachable

Ensure the Dex container is running:

```bash
docker compose ps
docker compose logs dex
```

### CORS errors in Inspector

The server is configured with CORS middleware to allow requests from any origin. If you still see CORS errors, ensure you're connecting to `http://localhost:5885/mcp` (not `127.0.0.1`).

### Authentication fails

1. Verify Dex is running and accessible at `http://localhost:5886/dex/.well-known/openid-configuration`
2. Check that the MCP server is running on port 5885
3. Ensure you're using the correct test credentials
