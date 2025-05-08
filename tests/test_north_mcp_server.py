import json
from base64 import b64encode

import httpx
import jwt
import pytest
import pytest_asyncio

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import AuthHeaderTokens


@pytest.fixture
def app() -> NorthMCPServer:
    return NorthMCPServer()


@pytest_asyncio.fixture
async def test_client(app: NorthMCPServer):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.sse_app()), base_url="https://mcptest.com"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_missing_auth_header(test_client: httpx.AsyncClient):
    result = await test_client.post("/messages/")

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_invalid_auth_header(test_client: httpx.AsyncClient):
    result = await test_client.post("/messages/", headers={"Authorization": "Invalid"})

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_missing_token(test_client: httpx.AsyncClient):
    result = await test_client.post("/messages/", headers={"Authorization": "Bearer "})

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_valid_auth_header(app: NorthMCPServer, test_client: httpx.AsyncClient):
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="does-not-matter"
    )
    header = AuthHeaderTokens(
        server_secret="server_secret",
        user_id_token=user_id_token,
        connector_access_tokens={"google": "abc"},
    )
    header_as_json = json.dumps(header.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()

    result = await test_client.post(
        "/messages/",
        headers={"Authorization": f"Bearer {header_as_b64}"},
        json={"method": "initialize"},
        params={"session_id": "65cc6ee7899c40d08b1f369403a7f450"},
    )

    assert result.status_code != 401
