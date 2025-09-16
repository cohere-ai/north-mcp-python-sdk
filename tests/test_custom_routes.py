"""
Test script to verify that custom routes work without authentication
while MCP routes still require authentication using North's default
smart authentication middleware.
"""

import json
import base64
import pytest
import pytest_asyncio
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import get_authenticated_user


def create_test_server() -> NorthMCPServer:
    """Create a test server with custom routes and MCP tools."""
    mcp = NorthMCPServer("TestServer", server_secret="test-secret")

    @mcp.tool()
    def test_tool(message: str) -> str:
        """A test tool that requires authentication."""
        try:
            user = get_authenticated_user()
        except Exception:
            user = None
        if user:
            return f"Authenticated tool call: {message} (user: {user.email})"
        else:
            return f"Unauthenticated tool call: {message}"

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        """Health check - should work without auth."""
        return PlainTextResponse("OK")

    @mcp.custom_route("/status", methods=["GET"])
    async def status_check(request: Request) -> JSONResponse:
        """Status check - should work without auth."""
        return JSONResponse({
            "status": "running",
            "server": "TestServer",
            "authenticated": False
        })

    @mcp.custom_route("/auth-info", methods=["GET"])
    async def auth_info(request: Request) -> JSONResponse:
        """Show authentication info - works with or without auth."""
        try:
            user = get_authenticated_user()
        except Exception:
            user = None
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


def create_auth_header() -> str:
    """Create a valid authentication header for testing."""
    auth_data = {
        "server_secret": "test-secret",
        "user_id_token": None,
        "connector_access_tokens": {}
    }
    
    encoded = base64.b64encode(json.dumps(auth_data).encode()).decode()
    return f"Bearer {encoded}"


@pytest_asyncio.fixture
async def test_client():
    """Create test client for custom routes testing."""
    server = create_test_server()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()), 
        base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def sse_test_client():
    """Create test client for SSE routes testing."""
    server = create_test_server()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.sse_app()), 
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_custom_routes_without_auth(test_client):
    """Test that custom routes work without authentication."""
    # Test health endpoint
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.text == "OK"
    
    # Test status endpoint
    response = await test_client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["authenticated"] == False
    
    # Test auth-info endpoint without auth
    response = await test_client.get("/auth-info")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_mcp_routes_require_auth(test_client):
    """Test that MCP routes require authentication."""
    # Test MCP endpoint without auth (should fail)
    response = await test_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert response.status_code == 401
    
    response = await test_client.post("/mcp/", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    })
    assert response.status_code == 401
    
    # Test MCP endpoint with auth (should work)
    headers = {"Authorization": create_auth_header()}
    response = await test_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers=headers)
    # Should not be 401 (might be other errors but not auth)
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_sse_routes_require_auth(sse_test_client):
    """Test that SSE routes require authentication."""
    # Test SSE endpoint without auth (should fail)
    response = await sse_test_client.get("/sse")
    assert response.status_code == 401
    
    # For SSE endpoint with auth, we just verify it doesn't return 401
    # Note: SSE endpoints are streaming and will hang on successful auth,
    # so we test auth validation only by checking invalid auth still returns 401
    headers = {"Authorization": "Bearer invalid"}
    response = await sse_test_client.get("/sse", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_messages_routes_require_auth(sse_test_client):
    """Test that /messages/* routes require authentication."""
    response = await sse_test_client.post("/messages/test-session-id", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "test",
        "params": {}
    })
    assert response.status_code == 401
    
    headers = {"Authorization": "Bearer invalid"}
    response = await sse_test_client.post("/messages/test-session-id", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "test", 
        "params": {}
    }, headers=headers)
    assert response.status_code == 401
    
    test_paths = [
        "/messages/",
        "/messages/abc-123",
        "/messages/session-uuid-here"
    ]
    
    for path in test_paths:
        response = await sse_test_client.post(path, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "test",
            "params": {}
        })
        assert response.status_code == 401, f"Path {path} should require auth but returned {response.status_code}"


@pytest.mark.asyncio
async def test_custom_routes_with_optional_auth(test_client):
    """Test that custom routes can optionally use auth info."""
    # Test auth-info endpoint with auth
    headers = {"Authorization": create_auth_header()}
    response = await test_client.get("/auth-info", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Note: will be False because we don't have a valid user_id_token in our test
    # but the important thing is that it doesn't return 401
    assert response.status_code == 200
