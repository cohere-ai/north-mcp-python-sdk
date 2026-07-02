import json
from base64 import b64encode

import httpx
import jwt
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import AuthHeaderTokens


@pytest.fixture
def app() -> NorthMCPServer:
    return NorthMCPServer()


@pytest.fixture
def app_no_health() -> NorthMCPServer:
    return NorthMCPServer(health_check=False)


@pytest_asyncio.fixture
async def test_client(app: NorthMCPServer):
    asgi_app = app.http_app(transport="streamable-http")
    async with LifespanManager(asgi_app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="https://mcptest.com",
        ) as client:
            yield client


@pytest.fixture
def app_with_auth() -> NorthMCPServer:
    return NorthMCPServer(trusted_issuers=["https://example.okta.com"])


def test_server_secret_kwarg_raises_targeted_error():
    with pytest.raises(
        TypeError, match="server_secret is no longer supported"
    ):
        NorthMCPServer(server_secret="stale-secret")


@pytest_asyncio.fixture
async def auth_test_client(app_with_auth: NorthMCPServer):
    asgi_app = app_with_auth.http_app(transport="streamable-http")
    async with LifespanManager(asgi_app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="https://mcptest.com",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_missing_auth_header(auth_test_client: httpx.AsyncClient):
    result = await auth_test_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_invalid_auth_header(auth_test_client: httpx.AsyncClient):
    result = await auth_test_client.post(
        "/mcp",
        headers={"Authorization": "Bearer Invalid"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_returns_unauthorized(
    auth_test_client: httpx.AsyncClient,
):
    result = await auth_test_client.post(
        "/mcp",
        headers={"Authorization": ""},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_invalid_base64_auth_header(
    auth_test_client: httpx.AsyncClient,
):
    result = await auth_test_client.post(
        "/mcp",
        headers={"Authorization": "invalid_base64"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_trusted_issuer_requires_auth_headers():
    server = NorthMCPServer(trusted_issuers=["https://example.okta.com"])
    asgi_app = server.http_app(transport="streamable-http")

    async with LifespanManager(asgi_app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="https://mcptest.com",
        ) as client:
            result = await client.get(
                "/mcp",
            )

            assert result.status_code == 401, result.text


@pytest.mark.asyncio
async def test_invalid_trusted_issuer_token():
    server = NorthMCPServer(trusted_issuers=["https://example.okta.com"])
    asgi_app = server.http_app(transport="streamable-http")

    async with LifespanManager(asgi_app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="https://mcptest.com",
        ) as client:
            user_id_token = jwt.encode(
                payload={
                    "email": "test@company.com",
                    "iss": "https://untrusted.example.com",
                },
                key="does-not-matter",
            )
            header = AuthHeaderTokens(
                user_id_token=user_id_token,
                connector_access_tokens={"google": "abc"},
            )
            header_as_json = json.dumps(header.model_dump())
            header_as_b64 = b64encode(header_as_json.encode()).decode()

            result = await client.get(
                "/mcp",
                headers={"Authorization": f"Bearer {header_as_b64}"},
            )
            assert result.status_code == 401, result.text


@pytest.mark.asyncio
async def test_missing_email_in_user_id_token(test_client: httpx.AsyncClient):
    user_id_token = jwt.encode(payload={}, key="does-not-matter")
    header = AuthHeaderTokens(
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()

    result = await test_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {header_as_b64}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert result.status_code != 401


@pytest.mark.asyncio
async def test_valid_auth_header(
    app: NorthMCPServer, test_client: httpx.AsyncClient
):
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="does-not-matter"
    )
    header = AuthHeaderTokens(
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()

    result = await test_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {header_as_b64}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )

    assert result.status_code != 401


@pytest.mark.asyncio
async def test_valid_auth_header_no_bearer(
    app: NorthMCPServer, test_client: httpx.AsyncClient
):
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="does-not-matter"
    )
    header = AuthHeaderTokens(
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()

    result = await test_client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {header_as_b64}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )

    assert result.status_code != 401


@pytest_asyncio.fixture
async def no_health_test_client(app_no_health: NorthMCPServer):
    asgi_app = app_no_health.http_app(transport="streamable-http")
    async with LifespanManager(asgi_app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="https://mcptest.com",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_health_check_enabled_by_default(test_client: httpx.AsyncClient):
    """Built-in /health endpoint is available when health_check defaults to True."""
    result = await test_client.get("/health")
    assert result.status_code == 200
    assert result.text == "OK"


@pytest.mark.asyncio
async def test_health_check_disabled(no_health_test_client: httpx.AsyncClient):
    """/health endpoint returns 404 when health_check=False."""
    result = await no_health_test_client.get("/health")
    assert result.status_code == 404
