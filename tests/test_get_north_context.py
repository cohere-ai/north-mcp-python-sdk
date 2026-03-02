"""
Tests for get_north_context() function.

This function extracts context values from X-North-Context-* headers.
"""

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from starlette.requests import Request
from starlette.responses import JSONResponse

from north_mcp_python_sdk import NorthMCPServer, get_north_context


def create_server_with_context_endpoint() -> NorthMCPServer:
    """Create a test server with an endpoint that returns context."""
    server = NorthMCPServer("ContextTestServer")

    @server.custom_route("/get-context", methods=["GET"])
    async def get_context_route(request: Request) -> JSONResponse:
        """Endpoint that returns the North context."""
        context = get_north_context()
        return JSONResponse({"context": context})

    @server.tool()
    def get_context_tool() -> dict:
        """Tool that returns the North context."""
        return get_north_context()

    return server


@pytest_asyncio.fixture
async def test_client():
    """Create test client for context testing."""
    server = create_server_with_context_endpoint()
    app = server.http_app(transport="streamable-http")
    async with LifespanManager(app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app),
            base_url="http://test",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_get_north_context_no_headers(test_client: httpx.AsyncClient):
    """Test get_north_context returns empty dict when no context headers."""
    response = await test_client.get("/get-context")
    assert response.status_code == 200
    data = response.json()
    assert data["context"] == {}


@pytest.mark.asyncio
async def test_get_north_context_single_header(test_client: httpx.AsyncClient):
    """Test get_north_context with a single context header.

    Note: HTTP headers are normalized to lowercase by ASGI servers,
    so the context key will be lowercase.
    """
    headers = {"X-North-Context-UserId": "user-123"}
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    assert data["context"] == {"userid": "user-123"}


@pytest.mark.asyncio
async def test_get_north_context_multiple_headers(
    test_client: httpx.AsyncClient,
):
    """Test get_north_context with multiple context headers.

    Note: HTTP headers are normalized to lowercase by ASGI servers.
    """
    headers = {
        "X-North-Context-UserId": "user-123",
        "X-North-Context-TenantId": "tenant-456",
        "X-North-Context-SessionId": "session-789",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    assert data["context"] == {
        "userid": "user-123",
        "tenantid": "tenant-456",
        "sessionid": "session-789",
    }


@pytest.mark.asyncio
async def test_get_north_context_case_insensitive_prefix(
    test_client: httpx.AsyncClient,
):
    """Test get_north_context handles case-insensitive header names."""
    headers = {
        "x-north-context-lowercase": "value1",
        "X-NORTH-CONTEXT-UPPERCASE": "value2",
        "X-North-Context-MixedCase": "value3",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # All should be extracted regardless of case
    assert len(data["context"]) == 3


@pytest.mark.asyncio
async def test_get_north_context_ignores_non_context_headers(
    test_client: httpx.AsyncClient,
):
    """Test get_north_context ignores headers without the context prefix."""
    headers = {
        "X-North-Context-Valid": "included",
        "X-North-ID-Token": "not-included",
        "X-North-Server-Secret": "not-included",
        "Authorization": "Bearer not-included",
        "Content-Type": "application/json",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    assert data["context"] == {"valid": "included"}


@pytest.mark.asyncio
async def test_get_north_context_preserves_value_content(
    test_client: httpx.AsyncClient,
):
    """Test get_north_context preserves special characters in values.

    Note: HTTP headers must be ASCII-encodable, so Unicode values
    are not supported directly (would need to be base64 encoded).
    """
    headers = {
        "X-North-Context-Special": "value with spaces",
        "X-North-Context-Json": '{"key": "value"}',
        "X-North-Context-Numbers": "12345",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    assert data["context"]["special"] == "value with spaces"
    assert data["context"]["json"] == '{"key": "value"}'
    assert data["context"]["numbers"] == "12345"


@pytest.mark.asyncio
async def test_get_north_context_empty_value(test_client: httpx.AsyncClient):
    """Test get_north_context handles empty header values."""
    headers = {
        "X-North-Context-Empty": "",
        "X-North-Context-NonEmpty": "value",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    assert data["context"]["empty"] == ""
    assert data["context"]["nonempty"] == "value"


@pytest.mark.asyncio
async def test_get_north_context_key_extraction(
    test_client: httpx.AsyncClient,
):
    """Test that context keys are extracted correctly after the prefix.

    Note: HTTP headers are normalized to lowercase by ASGI servers.
    """
    headers = {
        "X-North-Context-": "empty-key",  # Edge case: empty key
        "X-North-Context-A": "single-char-key",
        "X-North-Context-Key-With-Dashes": "dashed-key",
        "X-North-Context-key_with_underscores": "underscored-key",
    }
    response = await test_client.get("/get-context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Headers are lowercased by ASGI
    # Empty key after prefix becomes empty string key
    assert "" in data["context"]
    assert data["context"]["a"] == "single-char-key"
    assert data["context"]["key-with-dashes"] == "dashed-key"
    assert data["context"]["key_with_underscores"] == "underscored-key"
