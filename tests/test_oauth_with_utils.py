"""
Example tests showing how to use the new OAuth testing utilities.

This demonstrates the simplified testing patterns using create_oauth_client
and the token creation helpers.
"""

import pytest
import pytest_asyncio
from tests.test_utils import (
    create_oauth_jwt_token,
    create_oauth_bearer_token,
    quick_oauth_bearer,
    quick_oauth_token
)


@pytest.mark.asyncio
async def test_jwt_oauth_simple(create_oauth_client):
    """Test JWT OAuth with simplified client creation."""
    # Create JWT-based OAuth client
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="my-jwt-secret"
    )
    
    # Create OAuth token
    token = create_oauth_bearer_token(
        user_email="jwt-user@example.com",
        jwt_secret="my-jwt-secret",
        connector_tokens={"github": "github-token-123"}
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "jwt-user@example.com"
        assert "github" in data["connectors"]


@pytest.mark.asyncio
async def test_custom_oauth_simple(create_oauth_client):
    """Test custom OAuth validator with simplified setup."""
    
    async def my_validator(token: str):
        """Custom OAuth validator."""
        if token == "special-oauth-token":
            return {
                "email": "special@example.com",
                "connector_access_tokens": {"special": "special-123"}
            }
        return None
    
    # Create custom OAuth client
    client = await create_oauth_client(
        auth_type="custom",
        validator=my_validator
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": "Bearer special-oauth-token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "special@example.com"
        assert "special" in data["connectors"]


@pytest.mark.asyncio
async def test_multi_auth_providers(create_multi_auth_client):
    """Test multiple authentication providers working together."""
    
    client = await create_multi_auth_client([
        {"type": "oauth", "jwt_secret": "oauth-secret"},
        {"type": "bearer", "server_secret": "bearer-secret"},
        {"type": "api_key", "valid_keys": ["api-key-123"]}
    ])
    
    async with client:
        # Test OAuth authentication
        oauth_token = quick_oauth_bearer(email="oauth@example.com", secret="oauth-secret")
        response = await client.get("/auth-test", headers={
            "Authorization": oauth_token
        })
        assert response.status_code == 200
        assert response.json()["email"] == "oauth@example.com"
        
        # Test Bearer token authentication  
        from tests.test_utils import quick_bearer_token
        bearer_token = quick_bearer_token(email="bearer@example.com", secret="bearer-secret")
        response = await client.get("/auth-test", headers={
            "Authorization": bearer_token
        })
        assert response.status_code == 200
        assert response.json()["email"] == "bearer@example.com"
        
        # Test API key authentication
        response = await client.get("/auth-test", headers={
            "X-API-Key": "api-key-123"
        })
        assert response.status_code == 200
        assert response.json()["authenticated"] == True


@pytest.mark.asyncio
async def test_oauth_mcp_endpoint(create_oauth_client):
    """Test OAuth authentication on MCP protocol endpoints."""
    
    client = await create_oauth_client(auth_type="jwt", jwt_secret="test-secret")
    
    # Create valid OAuth token using matching secret
    token = quick_oauth_bearer(secret="test-secret")
    
    async with client:
        response = await client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }, headers={
            "Authorization": token
        })
        
        # Should not be 401 (authentication successful)
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_oauth_invalid_token(create_oauth_client):
    """Test OAuth with invalid token."""
    
    client = await create_oauth_client(auth_type="jwt", jwt_secret="correct-secret")
    
    # Create token with wrong secret
    invalid_token = create_oauth_bearer_token(
        user_email="user@example.com",
        jwt_secret="wrong-secret"  # Wrong secret!
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": invalid_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == False


@pytest.mark.asyncio
async def test_oauth_custom_claims(create_oauth_client):
    """Test OAuth with custom JWT claims."""
    
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="custom-secret",
        email_claim="user_email"  # Use different claim for email
    )
    
    # Create token with custom claims using matching secret
    token = create_oauth_bearer_token(
        jwt_secret="custom-secret",
        additional_claims={
            "user_email": "custom@example.com",  # Email in custom claim
            "role": "admin",
            "permissions": ["read", "write"]
        }
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "custom@example.com"


@pytest.mark.asyncio
async def test_oauth_no_connectors(create_oauth_client):
    """Test OAuth token without connector tokens."""
    
    client = await create_oauth_client(auth_type="jwt", jwt_secret="minimal-secret")
    
    # Create token without connector tokens using matching secret
    token = create_oauth_bearer_token(
        user_email="minimal@example.com",
        jwt_secret="minimal-secret",
        connector_tokens={}  # No connectors
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "minimal@example.com"
        assert data["connectors"] == []


def test_quick_token_helpers():
    """Test the quick token creation helpers."""
    
    # Test quick OAuth token (raw JWT)
    jwt_token = quick_oauth_token(email="test@example.com")
    assert isinstance(jwt_token, str)
    assert jwt_token.count('.') == 2  # JWT has 3 parts separated by dots
    
    # Test quick OAuth Bearer token
    bearer_token = quick_oauth_bearer(email="test@example.com")
    assert bearer_token.startswith("Bearer ")
    assert bearer_token.count('.') == 2  # Should contain JWT
    
    # Test custom secrets
    token1 = quick_oauth_token(secret="secret1")
    token2 = quick_oauth_token(secret="secret2")
    assert token1 != token2  # Different secrets = different tokens