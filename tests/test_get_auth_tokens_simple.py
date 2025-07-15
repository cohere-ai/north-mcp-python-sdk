import json
from base64 import b64encode
from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt
import pytest
import pytest_asyncio

from north_mcp_python_sdk import NorthMCPServer, get_auth_tokens
from north_mcp_python_sdk.auth import AuthHeaderTokens, get_authenticated_user


@pytest.fixture
def app() -> NorthMCPServer:
    return NorthMCPServer()


@pytest_asyncio.fixture
async def test_client(app: NorthMCPServer):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.sse_app()), base_url="https://mcptest.com"
    ) as client:
        yield client


def test_get_auth_tokens_no_context():
    """Test that get_auth_tokens raises an error when called outside of request context"""
    with pytest.raises(Exception) as exc_info:
        get_auth_tokens()
    
    assert "auth tokens not found in context" in str(exc_info.value)


def test_get_auth_tokens_return_type():
    """Test that get_auth_tokens has the correct return type annotation"""
    import inspect
    sig = inspect.signature(get_auth_tokens)
    assert sig.return_annotation == AuthHeaderTokens


@pytest.mark.asyncio
async def test_auth_middleware_sets_tokens_in_context():
    """Test that our auth middleware correctly sets tokens in the context"""
    from north_mcp_python_sdk.auth import AuthContextMiddleware, auth_tokens_context_var
    
    # Create mock app and request
    mock_app = AsyncMock()
    mock_scope = {
        "type": "http",
        "user": MagicMock(),
        "auth_tokens": AuthHeaderTokens(
            server_secret="test_secret",
            user_id_token="test_token",
            connector_access_tokens={"google": "google_token"}
        )
    }
    
    # Mock the user to be the correct type
    from north_mcp_python_sdk.auth import AuthenticatedNorthUser
    mock_user = AuthenticatedNorthUser(
        connector_access_tokens={"google": "google_token"},
        email="test@example.com"
    )
    mock_scope["user"] = mock_user
    
    middleware = AuthContextMiddleware(mock_app)
    
    # Track if the context was set correctly
    context_value = None
    
    async def capture_context(*args, **kwargs):
        nonlocal context_value
        context_value = auth_tokens_context_var.get()
    
    mock_app.side_effect = capture_context
    
    # Call the middleware
    await middleware(mock_scope, AsyncMock(), AsyncMock())
    
    # Verify the context was set
    assert context_value is not None
    assert context_value.server_secret == "test_secret"
    assert context_value.user_id_token == "test_token"
    assert context_value.connector_access_tokens == {"google": "google_token"}


def test_auth_backend_token_storage_concept():
    """Test that the auth backend has the concept of storing tokens in scope"""
    from north_mcp_python_sdk.auth import NorthAuthBackend
    
    # Verify that the authenticate method exists and can be called
    backend = NorthAuthBackend()
    assert hasattr(backend, 'authenticate')
    
    # Verify that AuthHeaderTokens can be created and serialized
    auth_tokens = AuthHeaderTokens(
        server_secret="test_secret",
        user_id_token="test_token",
        connector_access_tokens={"slack": "slack_token"}
    )
    
    # Test that the tokens can be serialized for storage
    token_dict = auth_tokens.model_dump()
    assert token_dict["server_secret"] == "test_secret"
    assert token_dict["user_id_token"] == "test_token"
    assert token_dict["connector_access_tokens"] == {"slack": "slack_token"}
    
    # Test that tokens can be recreated from dict
    recreated = AuthHeaderTokens.model_validate(token_dict)
    assert recreated.server_secret == "test_secret"
    assert recreated.user_id_token == "test_token"
    assert recreated.connector_access_tokens == {"slack": "slack_token"}


@pytest.mark.asyncio
async def test_full_auth_flow_with_real_request():
    """Test the full auth flow with a real HTTP request"""
    app = NorthMCPServer()
    
    # Create valid auth tokens
    user_id_token = jwt.encode(
        payload={"email": "integration@example.com"}, key="test-key"
    )
    
    auth_tokens = AuthHeaderTokens(
        server_secret="integration_secret",
        user_id_token=user_id_token,
        connector_access_tokens={"github": "github_token", "notion": "notion_token"}
    )
    
    header_as_json = json.dumps(auth_tokens.model_dump())
    header_as_b64 = b64encode(header_as_json.encode()).decode()
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app.sse_app()), base_url="https://mcptest.com"
    ) as client:
        # Make a simple request that should be authenticated
        result = await client.get(
            "/health",
            headers={"Authorization": f"Bearer {header_as_b64}"}
        )
        
        # The request should not fail with auth error (even if the endpoint doesn't exist)
        # A 401 would indicate auth failure, 404 would indicate auth success but missing endpoint
        assert result.status_code != 401


def test_auth_header_tokens_model():
    """Test the AuthHeaderTokens model works correctly"""
    # Test with all fields
    tokens = AuthHeaderTokens(
        server_secret="my_secret",
        user_id_token="my_token",
        connector_access_tokens={"google": "google_token", "slack": "slack_token"}
    )
    
    assert tokens.server_secret == "my_secret"
    assert tokens.user_id_token == "my_token"
    assert tokens.connector_access_tokens == {"google": "google_token", "slack": "slack_token"}
    
    # Test with minimal fields
    minimal_tokens = AuthHeaderTokens(
        server_secret=None,
        user_id_token=None,
        connector_access_tokens={}
    )
    
    assert minimal_tokens.server_secret is None
    assert minimal_tokens.user_id_token is None
    assert minimal_tokens.connector_access_tokens == {}
    
    # Test serialization/deserialization
    json_data = tokens.model_dump()
    recreated = AuthHeaderTokens.model_validate(json_data)
    
    assert recreated.server_secret == tokens.server_secret
    assert recreated.user_id_token == tokens.user_id_token
    assert recreated.connector_access_tokens == tokens.connector_access_tokens


def test_import_get_auth_tokens():
    """Test that get_auth_tokens can be imported from the main module"""
    from north_mcp_python_sdk import get_auth_tokens
    
    # Function should exist and be callable
    assert callable(get_auth_tokens)
    
    # Should have correct signature
    import inspect
    sig = inspect.signature(get_auth_tokens)
    assert len(sig.parameters) == 0
    assert sig.return_annotation == AuthHeaderTokens


def test_get_auth_tokens_and_get_authenticated_user_similar_behavior():
    """Test that get_auth_tokens behaves similarly to get_authenticated_user when no context"""
    # Both should raise an exception when called outside request context
    with pytest.raises(Exception) as auth_tokens_exc:
        get_auth_tokens()
    
    with pytest.raises(Exception) as auth_user_exc:
        get_authenticated_user()
    
    # Both should indicate missing context
    assert "not found in context" in str(auth_tokens_exc.value)
    assert "not found in context" in str(auth_user_exc.value)
