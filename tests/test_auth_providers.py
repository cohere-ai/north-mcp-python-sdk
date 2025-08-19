"""
Tests for modular authentication providers.
"""

import pytest
import pytest_asyncio
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer, BearerTokenAuthProvider, APIKeyAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user_optional


def create_api_key_server() -> NorthMCPServer:
    """Create a test server with API key authentication."""
    mcp = NorthMCPServer(
        "APIKeyTestServer", 
        auth_providers=[
            APIKeyAuthProvider(valid_keys=["test-key-123", "another-key-456"])
        ]
    )

    @mcp.tool()
    def test_tool(message: str) -> str:
        """A test tool that requires authentication."""
        user = get_authenticated_user_optional()
        if user:
            return f"Tool called by: {user.email}"
        else:
            return "Tool called without auth"

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check - should work without auth."""
        return PlainTextResponse("OK")

    @mcp.custom_route("/auth-info", methods=["GET"])
    async def auth_info(request: Request) -> JSONResponse:
        """Show authentication info."""
        user = get_authenticated_user_optional()
        if user:
            return JSONResponse({
                "authenticated": True,
                "email": user.email,
                "connectors": list(user.connector_access_tokens.keys())
            })
        else:
            return JSONResponse({
                "authenticated": False,
                "message": "No authentication provided"
            })

    return mcp


def create_multi_auth_server() -> NorthMCPServer:
    """Create a test server with multiple authentication methods."""
    mcp = NorthMCPServer(
        "MultiAuthTestServer",
        auth_providers=[
            BearerTokenAuthProvider(server_secret="test-secret"),
            APIKeyAuthProvider(valid_keys=["api-key-123"])
        ]
    )

    @mcp.custom_route("/auth-test", methods=["GET"])
    async def auth_test(request: Request) -> JSONResponse:
        """Test which auth method was used."""
        user = get_authenticated_user_optional()
        if user:
            return JSONResponse({
                "authenticated": True,
                "email": user.email,
                "has_connectors": bool(user.connector_access_tokens)
            })
        else:
            return JSONResponse({"authenticated": False})

    return mcp


@pytest_asyncio.fixture
async def api_key_client():
    """Create test client for API key server."""
    server = create_api_key_server()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()), 
        base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def multi_auth_client():
    """Create test client for multi-auth server."""
    server = create_multi_auth_server()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()), 
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_api_key_auth_via_header(api_key_client):
    """Test API key authentication via X-API-Key header."""
    # Test with valid API key
    response = await api_key_client.get("/auth-info", headers={"X-API-Key": "test-key-123"})
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert "api-key-user-" in data["email"]
    
    # Test with invalid API key - custom routes should still return 200 but show unauthenticated
    response = await api_key_client.get("/auth-info", headers={"X-API-Key": "invalid-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_api_key_auth_via_bearer(api_key_client):
    """Test API key authentication via Authorization Bearer header."""
    # Test with valid API key
    response = await api_key_client.get("/auth-info", headers={"Authorization": "Bearer test-key-123"})
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    
    # Test with invalid API key - custom routes should still return 200 but show unauthenticated  
    response = await api_key_client.get("/auth-info", headers={"Authorization": "Bearer invalid-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_api_key_mcp_endpoint_auth(api_key_client):
    """Test that MCP endpoints require API key authentication."""
    # Test without auth
    response = await api_key_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert response.status_code == 401
    
    # Test with valid API key
    response = await api_key_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers={"X-API-Key": "test-key-123"})
    assert response.status_code != 401  # Should not be unauthorized


@pytest.mark.asyncio
async def test_custom_routes_bypass_auth(api_key_client):
    """Test that custom routes don't require authentication."""
    response = await api_key_client.get("/health")
    assert response.status_code == 200
    assert response.text == "OK"
    
    response = await api_key_client.get("/auth-info")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_multiple_auth_providers_bearer_token(multi_auth_client):
    """Test that Bearer token authentication works in multi-auth setup."""
    import json
    import base64
    from north_mcp_python_sdk.auth import AuthHeaderTokens
    import jwt
    
    # Create a valid Bearer token
    user_id_token = jwt.encode({"email": "test@example.com"}, key="test")
    header = AuthHeaderTokens(
        server_secret="test-secret",
        user_id_token=user_id_token,
        connector_access_tokens={"google": "token123"}
    )
    header_json = json.dumps(header.model_dump())
    header_b64 = base64.b64encode(header_json.encode()).decode()
    
    response = await multi_auth_client.get("/auth-test", headers={
        "Authorization": f"Bearer {header_b64}"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert data["email"] == "test@example.com"
    assert data["has_connectors"] == True  # Bearer tokens have connectors


@pytest.mark.asyncio
async def test_multiple_auth_providers_api_key(multi_auth_client):
    """Test that API key authentication works in multi-auth setup."""
    response = await multi_auth_client.get("/auth-test", headers={
        "X-API-Key": "api-key-123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert "api-key-user-" in data["email"]
    assert data["has_connectors"] == False  # API keys don't have connectors


@pytest.mark.asyncio
async def test_multiple_auth_providers_fallback(multi_auth_client):
    """Test that authentication falls back to next provider when first fails."""
    # This should fail Bearer token auth but succeed with API key
    response = await multi_auth_client.get("/auth-test", headers={
        "Authorization": "Bearer api-key-123"  # This will be tried as Bearer token first, then as API key
    })
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True


@pytest.mark.asyncio
async def test_no_auth_providers_failure(multi_auth_client):
    """Test that requests fail when no valid authentication is provided."""
    response = await multi_auth_client.get("/auth-test")
    assert response.status_code == 200  # Custom route, no auth required
    data = response.json()
    assert data["authenticated"] == False
    
    # But MCP endpoint should require auth
    response = await multi_auth_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert response.status_code == 401