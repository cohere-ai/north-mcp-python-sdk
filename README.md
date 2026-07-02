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
* You can validate North user identity with ID tokens and optionally restrict
  accepted identity providers with `trusted_issuers` for production.
* You can access the user's OAuth token to interact with third-party services on their behalf.
* You can access the user's identity (from the identity provider used with North).
* **Debug mode** for detailed authentication logging and troubleshooting.
* **OpenTelemetry helpers** for custom spans, log/trace correlation, and privacy-aware error recording (built on [FastMCP telemetry](https://gofastmcp.com/servers/telemetry)).
* **Built-in health check** endpoint for Kubernetes liveness probes (enabled by default).

## Health Check

`NorthMCPServer` includes a built-in `/health` endpoint that responds to `GET` requests with a `200 OK` plain-text response. This is useful for Kubernetes liveness/readiness probes and load balancer health checks. The endpoint bypasses authentication, so no tokens are needed.

It is enabled by default. To disable it:

```python
mcp = NorthMCPServer(name="Demo", health_check=False)
```

## Examples

This repository contains example servers that you can use as a quickstart. You can find them in the [examples directory](https://github.com/cohere-ai/north-mcp-python-sdk/tree/main/examples).

Examples cover authentication, tool metadata for the North UI, debug mode, and OpenTelemetry (`examples/telemetry-demo/`).


## Authentication

This SDK offers several strategies for authenticating users and authorizing their requests.


#### I only want North to be able to send requests to my server

North sends an `X-North-ID-Token` with requests. For production, configure
`trusted_issuers` so your server verifies that token was issued by an expected
identity provider. For local development or lower-risk setups, this setting is
optional and tokens are decoded without signature verification.

```python
mcp = NorthMCPServer(
    name="Demo",
    port=5222,
    trusted_issuers=["https://your-idp.example.com"],
)
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
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Successfully parsed auth tokens. Has user_id_token: True, Connector count: 2
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Available connectors: ['google', 'slack']
2024-01-15 10:30:45 - NorthMCP.Auth - DEBUG - Successfully decoded user ID token. Email: user@example.com
2024-01-15 10:30:45 - NorthMCP.AuthContext - DEBUG - Setting authenticated user in context: email=user@example.com, connectors=['google', 'slack']
```

### Debug Mode Examples

See `examples/server_with_debug.py` for a runnable example.

### Security Note

Debug mode logs sensitive information including request headers and token metadata. **Never enable debug mode in production environments** as it may expose authentication details in logs.

## OpenTelemetry

FastMCP 3 emits a span for each tool call when a `TracerProvider` is configured. The North SDK adds helpers on top of that; it does **not** install exporters or configure where traces are sent — `opentelemetry-sdk` and OTLP exporters are not bundled dependencies. Servers run fine without a `TracerProvider`; traces become no-ops until you add one.

### What the SDK provides

| Helper | Purpose |
|--------|---------|
| `TelemetryConfig` | Opt-in config object for the telemetry integration (sensitive-data policy, log/trace correlation) |
| `mcp.telemetry.traced_span` | Custom spans nested under FastMCP tool spans, driven by the server's `TelemetryConfig`. Use this when you have `mcp` in scope. |
| `traced_span` (module-level) | Same context manager, but auto-resolves the active server's config via `fastmcp.server.dependencies.get_server`. Use this from tool bodies that don't hold an `mcp` reference. |
| `get_telemetry_config()` | Returns the active `NorthMCPServer`'s `TelemetryConfig` (or a private "off" config when there's no active North server). Lets tools branch on `record_sensitive_data` without an `mcp` reference. |
| `Depends` | Re-export of FastMCP's `Depends` factory. Combine with `get_telemetry_config` for FastAPI-style parameter injection: `telemetry: TelemetryConfig = Depends(get_telemetry_config)`. |
| `get_tracer` | Re-export of FastMCP's tracer (`fastmcp` instrumentation name) |
| `TraceContextFormatter` | Appends `trace_id` / `span_id` to log lines on the `NorthMCP.{name}` logger when a span is active |

### Setup

1. **Register a `TracerProvider` and exporters in `main` before importing `NorthMCPServer`** (FastMCP reads the global provider at import time). Use your own setup or standard OTel env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, etc.).
2. **Pass a `TelemetryConfig` to `NorthMCPServer`** — this is the opt-in signal. When `log_trace_context` is enabled (the default for an opted-in config), trace/span IDs are appended automatically to `NorthMCP.*` log lines.
3. **Inject the config into tools with `Depends(get_telemetry_config)`** and call `telemetry.traced_span(...)` for custom spans. See the helper table for `mcp.telemetry` and bare-import alternatives.

```python
def configure_tracing() -> None:
    # Install opentelemetry-sdk + exporters in your server project.
    # See examples/telemetry-demo/main.py for a minimal OTLP gRPC example.
    ...

def main() -> None:
    configure_tracing()

    from north_mcp_python_sdk import (
        Depends,
        NorthMCPServer,
        TelemetryConfig,
        get_telemetry_config,
    )

    mcp = NorthMCPServer(
        "Search",
        telemetry=TelemetryConfig(
            record_sensitive_data=False,
            log_trace_context=True,
        ),
    )

    @mcp.tool()
    async def search(
        query: str,
        telemetry: TelemetryConfig = Depends(get_telemetry_config),
    ) -> list[dict]:
        # FastMCP injects the active server's TelemetryConfig as `telemetry`
        # before the tool body runs. No reference to `mcp` is needed, and
        # `telemetry.traced_span` honours `record_sensitive_data` for
        # exception details.
        with telemetry.traced_span(
            "search.provider_call",
            attributes={"search.query_length": len(query)},
        ) as span:
            if telemetry.record_sensitive_data:
                span.add_event("search.query", {"query": query})

            results = await provider.search(query)
            span.set_attribute("search.result_count", len(results))
            return results
```

`Depends(...)` in a default trips ruff's `B008` and basedpyright's `reportCallInDefaultInitializer`. Whitelist `Depends` as configured in this repo's `pyproject.toml`; this is the same approach FastAPI projects use.

Full walkthrough: [`examples/telemetry-demo/main.py`](examples/telemetry-demo/main.py). For broader auto-instrumentation (HTTP, logging, etc.), use the [`opentelemetry-instrument`](https://opentelemetry.io/docs/zero-code/python/) CLI per [FastMCP telemetry docs](https://gofastmcp.com/servers/telemetry).

### `TelemetryConfig` options

| Option | Default (when opted in) | Description |
|--------|-------------------------|-------------|
| `record_sensitive_data` | `False` | When `True`, `traced_span` records full exception messages on spans and tools may attach sensitive payloads (query text, IDs, etc.) as span events. Off by default for safety; opt in explicitly in code only. |
| `log_trace_context` | `True` | When `True`, the SDK attaches a formatter that appends `trace_id` / `span_id` to log lines on the `NorthMCP.*` logger while a span is active. |

If you leave `telemetry=None`, the SDK uses an internal "telemetry not opted in" config: both flags `False`, no formatter is attached to the `NorthMCP.*` logger, and `traced_span` records only the exception type name on error. Neither flag has an environment-variable fallback. FastMCP's own tool/resource/prompt spans are unaffected — they still appear whenever a `TracerProvider` is configured.

```python
mcp = NorthMCPServer(
    name="Demo",
    telemetry=TelemetryConfig(record_sensitive_data=True),
)
```

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
