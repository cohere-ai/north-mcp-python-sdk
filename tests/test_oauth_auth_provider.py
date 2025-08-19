"""
Tests for OAuthAuthProvider.
"""

import json
import pytest
import pytest_asyncio
import httpx
import jwt
from unittest.mock import AsyncMock, patch
from starlette.requests import Request
from starlette.responses import JSONResponse

from north_mcp_python_sdk import NorthMCPServer, OAuthAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user_optional


def create_jwt_token(email: str, secret: str = "test-secret") -> str:
    """Create a test JWT token."""
    payload = {
        "email": email,
        "sub": email,
        "iat": 1234567890,
        "exp": 9999999999  # Far future
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def mock_custom_validator(token: str) -> dict:
    """Mock custom validator for testing."""
    if token == "valid-custom-token":
        return {
            "email": "custom@example.com",
            "connector_access_tokens": {"custom": "token123"}
        }
    elif token == "no-email-token":
        return {"sub": "user123"}  # Missing email
    else:
        return None


@pytest_asyncio.fixture
async def oauth_jwt_client():
    """Create test client with JWT OAuth authentication."""
    server = NorthMCPServer(
        "OAuth JWT Test Server",
        auth_providers=[
            OAuthAuthProvider(
                jwt_secret="test-secret",
                jwt_algorithm="HS256",
                debug=True
            )
        ]
    )
    
    @server.custom_route("/auth-test", methods=["GET"])
    async def auth_test(request: Request) -> JSONResponse:
        user = get_authenticated_user_optional()
        if user:
            return JSONResponse({
                "authenticated": True,
                "email": user.email,
                "connectors": list(user.connector_access_tokens.keys())
            })
        else:
            return JSONResponse({"authenticated": False})
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()),
        base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture  
async def oauth_custom_client():
    """Create test client with custom OAuth authentication."""
    server = NorthMCPServer(
        "OAuth Custom Test Server",
        auth_providers=[
            OAuthAuthProvider(
                custom_validator=mock_custom_validator,
                debug=True
            )
        ]
    )
    
    @server.custom_route("/auth-test", methods=["GET"])
    async def auth_test(request: Request) -> JSONResponse:
        user = get_authenticated_user_optional()
        if user:
            return JSONResponse({
                "authenticated": True,
                "email": user.email,
                "connectors": list(user.connector_access_tokens.keys())
            })
        else:
            return JSONResponse({"authenticated": False})
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_jwt_oauth_authentication_success(oauth_jwt_client):
    """Test successful JWT OAuth authentication."""
    token = create_jwt_token("jwt-user@example.com")
    
    response = await oauth_jwt_client.get("/auth-test", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert data["email"] == "jwt-user@example.com"


@pytest.mark.asyncio
async def test_jwt_oauth_invalid_token(oauth_jwt_client):
    """Test JWT OAuth with invalid token."""
    response = await oauth_jwt_client.get("/auth-test", headers={
        "Authorization": "Bearer invalid-jwt-token"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_jwt_oauth_wrong_secret(oauth_jwt_client):
    """Test JWT OAuth with token signed by wrong secret."""
    token = create_jwt_token("user@example.com", secret="wrong-secret")
    
    response = await oauth_jwt_client.get("/auth-test", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_jwt_oauth_mcp_endpoint(oauth_jwt_client):
    """Test JWT OAuth on MCP protocol endpoint."""
    token = create_jwt_token("mcp-user@example.com")
    
    response = await oauth_jwt_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers={
        "Authorization": f"Bearer {token}"
    })
    
    # Should not be 401 (authentication successful)
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_custom_oauth_authentication_success(oauth_custom_client):
    """Test successful custom OAuth authentication."""
    response = await oauth_custom_client.get("/auth-test", headers={
        "Authorization": "Bearer valid-custom-token"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == True
    assert data["email"] == "custom@example.com"
    assert "custom" in data["connectors"]


@pytest.mark.asyncio
async def test_custom_oauth_invalid_token(oauth_custom_client):
    """Test custom OAuth with invalid token."""
    response = await oauth_custom_client.get("/auth-test", headers={
        "Authorization": "Bearer invalid-custom-token"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_custom_oauth_missing_email(oauth_custom_client):
    """Test custom OAuth with token missing email."""
    response = await oauth_custom_client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }, headers={
        "Authorization": "Bearer no-email-token"
    })
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_no_bearer_token():
    """Test OAuth provider with non-Bearer authorization."""
    server = NorthMCPServer(
        "OAuth Test",
        auth_providers=[OAuthAuthProvider(custom_validator=mock_custom_validator)]
    )
    
    @server.custom_route("/test", methods=["GET"])
    async def test_route(request: Request) -> JSONResponse:
        user = get_authenticated_user_optional()
        return JSONResponse({"authenticated": user is not None})
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()),
        base_url="http://test"
    ) as client:
        # Test with non-Bearer auth header
        response = await client.get("/test", headers={
            "Authorization": "Basic dXNlcjpwYXNz"  # Basic auth, not Bearer
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_oauth_introspection_initialization():
    """Test OAuth introspection provider initialization."""
    # Test that introspection provider can be created with required params
    provider = OAuthAuthProvider(
        introspection_endpoint="https://oauth.example.com/introspect",
        client_id="test-client",
        client_secret="test-secret"
    )
    
    assert provider.introspection_endpoint == "https://oauth.example.com/introspect"
    assert provider.client_id == "test-client"
    assert provider.client_secret == "test-secret"
    assert provider.get_scheme() == "OAuth"


@pytest.mark.asyncio 
async def test_oauth_multiple_validation_methods():
    """Test OAuth provider with multiple validation methods uses correct priority."""
    async def mock_validator(token):
        return {"email": "custom@example.com"}
    
    # Custom validator should have highest priority
    provider = OAuthAuthProvider(
        jwt_secret="test-secret",
        custom_validator=mock_validator,
        introspection_endpoint="https://example.com"
    )
    
    # Mock connection
    from starlette.requests import HTTPConnection
    
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer test-token")]
    }
    conn = HTTPConnection(scope)
    
    result = await provider.authenticate(conn)
    
    # Should use custom validator (highest priority) 
    assert result is not None
    assert result.email == "custom@example.com"


def test_oauth_provider_initialization_errors():
    """Test OAuth provider initialization with invalid parameters."""
    # Should raise error when no validation method provided
    with pytest.raises(ValueError, match="Must provide either jwt_secret, introspection_endpoint, or custom_validator"):
        OAuthAuthProvider()
    
    # Should work with any one validation method
    provider1 = OAuthAuthProvider(jwt_secret="test")
    assert provider1.jwt_secret == "test"
    
    provider2 = OAuthAuthProvider(introspection_endpoint="https://example.com")
    assert provider2.introspection_endpoint == "https://example.com"
    
    provider3 = OAuthAuthProvider(custom_validator=lambda x: None)
    assert provider3.custom_validator is not None


@pytest.mark.asyncio
async def test_oauth_provider_scheme():
    """Test OAuth provider scheme identification."""
    provider = OAuthAuthProvider(jwt_secret="test")
    assert provider.get_scheme() == "OAuth"