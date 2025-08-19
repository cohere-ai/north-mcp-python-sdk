"""
Test backward compatibility with North's current MCP client format.
"""

import json
import base64
import pytest
import pytest_asyncio
import httpx
import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from north_mcp_python_sdk import NorthMCPServer, BearerTokenAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user_optional


def create_north_compatible_server() -> NorthMCPServer:
    """Create a server compatible with North's current auth format."""
    mcp = NorthMCPServer(
        "NorthCompatibleServer", 
        server_secret="test-secret"
    )

    @mcp.custom_route("/auth-info", methods=["GET"])
    async def auth_info(request: Request) -> JSONResponse:
        """Show authentication info to test North compatibility."""
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


def create_north_auth_token(
    user_email: str = "test@north.com",
    server_secret: str = "test-secret",
    connector_tokens: dict = None
) -> str:
    """Create an auth token in North's current format."""
    if connector_tokens is None:
        connector_tokens = {"google": "google-token-123", "slack": "slack-token-456"}
    
    # Create user_id_token (JWT from OIDC provider)
    user_id_token = jwt.encode({"email": user_email}, key="test-key")
    
    # Create North's current token format
    north_token = {
        "user_id_token": user_id_token,
        "auth_token": "dex-access-token-123",  # North's dex token
        "connector_access_tokens": connector_tokens,
        "server_secret": server_secret
    }
    
    # Encode as North does (raw base64, no Bearer prefix)
    json_bytes = json.dumps(north_token).encode()
    return base64.b64encode(json_bytes).decode()


def create_standard_bearer_token(
    user_email: str = "test@standard.com", 
    server_secret: str = "test-secret",
    connector_tokens: dict = None
) -> str:
    """Create a standard Bearer token format."""
    if connector_tokens is None:
        connector_tokens = {"gdrive": "drive-token-789"}
    
    user_id_token = jwt.encode({"email": user_email}, key="test-key")
    
    # Standard format (what our original tests used)
    standard_token = {
        "user_id_token": user_id_token,
        "connector_access_tokens": connector_tokens,
        "server_secret": server_secret
    }
    
    json_bytes = json.dumps(standard_token).encode()
    base64_token = base64.b64encode(json_bytes).decode()
    
    # Return with Bearer prefix
    return f"Bearer {base64_token}"


@pytest_asyncio.fixture
async def north_compatible_client():
    """Create test client for North compatibility testing."""
    server = create_north_compatible_server()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()), 
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_north_current_format_auth(north_compatible_client):
    """Test that North's current direct base64 format works."""
    # Create token in North's current format (no Bearer prefix)
    north_token = create_north_auth_token()
    
    # Test custom route with North's format
    response = await north_compatible_client.get("/auth-info", headers={
        "Authorization": north_token,  # Direct base64, no "Bearer " prefix
        "X-North-User-ID": "user123",
        "X-North-Conversation-ID": "conv456"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert data["email"] == "test@north.com"
    assert "google" in data["connectors"]
    assert "slack" in data["connectors"]


@pytest.mark.asyncio
async def test_standard_bearer_format_still_works(north_compatible_client):
    """Test that standard Bearer format still works for backward compatibility."""
    # Create standard Bearer token
    bearer_token = create_standard_bearer_token()
    
    response = await north_compatible_client.get("/auth-info", headers={
        "Authorization": bearer_token  # "Bearer <base64>" format
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert data["email"] == "test@standard.com"
    assert "gdrive" in data["connectors"]


@pytest.mark.asyncio 
async def test_north_format_mcp_endpoint(north_compatible_client):
    """Test that North format works with MCP protocol endpoints."""
    north_token = create_north_auth_token()
    
    # Test MCP endpoint (should require auth)
    response = await north_compatible_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize", 
        "params": {}
    }, headers={
        "Authorization": north_token,
        "X-North-User-ID": "user123"
    })
    
    # Should not be 401 (authentication successful)
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_server_secret_validation_north_format(north_compatible_client):
    """Test server secret validation with North format."""
    # Test with wrong server secret
    wrong_secret_token = create_north_auth_token(server_secret="wrong-secret")
    
    response = await north_compatible_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers={
        "Authorization": wrong_secret_token
    })
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_malformed_base64_handling(north_compatible_client):
    """Test handling of malformed base64 tokens."""
    # Test completely invalid base64
    response = await north_compatible_client.get("/auth-info", headers={
        "Authorization": "not-base64-at-all!"
    })
    assert response.status_code == 200  # Custom route, should work without auth
    data = response.json()
    assert data["authenticated"] == False
    
    # Test invalid base64 on MCP endpoint
    response = await north_compatible_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers={
        "Authorization": "invalid-token"
    })
    assert response.status_code == 401  # Should be rejected


@pytest.mark.asyncio
async def test_mixed_auth_methods(north_compatible_client):
    """Test that multiple auth methods work together."""
    # This tests our multi-provider setup
    # First try with North format
    north_token = create_north_auth_token()
    response = await north_compatible_client.get("/auth-info", headers={
        "Authorization": north_token
    })
    assert response.status_code == 200
    assert response.json()["authenticated"] == True
    
    # Then try with Bearer format  
    bearer_token = create_standard_bearer_token()
    response = await north_compatible_client.get("/auth-info", headers={
        "Authorization": bearer_token
    })
    assert response.status_code == 200
    assert response.json()["authenticated"] == True