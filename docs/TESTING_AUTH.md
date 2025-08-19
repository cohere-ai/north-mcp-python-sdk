# Testing Authentication Providers

This guide shows how to test different authentication providers using the built-in testing utilities.

## Quick Start

```python
import pytest
from tests.test_utils import (
    quick_oauth_bearer,
    quick_bearer_token,
    quick_north_token,
    create_oauth_client,
    create_multi_auth_client
)

@pytest.mark.asyncio
async def test_my_oauth_server(create_oauth_client):
    # Create OAuth server with JWT validation
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="my-secret"
    )
    
    # Create matching OAuth token
    token = quick_oauth_bearer(
        email="user@example.com",
        secret="my-secret"
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        assert response.json()["authenticated"] == True
```

## Token Creation Helpers

### Quick Helpers (for simple tests)

```python
# OAuth tokens
oauth_token = quick_oauth_bearer(email="user@oauth.com", secret="oauth-secret")
oauth_jwt = quick_oauth_token(email="user@oauth.com", secret="oauth-secret")

# Bearer tokens (North format)
bearer_token = quick_bearer_token(email="user@bearer.com", secret="bearer-secret")

# North tokens (raw base64)
north_token = quick_north_token(email="user@north.com", secret="north-secret")
```

### Detailed Token Creation

```python
from tests.test_utils import (
    create_oauth_bearer_token,
    create_bearer_token,
    create_north_auth_token
)

# OAuth token with custom claims
oauth_token = create_oauth_bearer_token(
    user_email="admin@example.com",
    jwt_secret="oauth-secret",
    connector_tokens={"github": "gh-token", "slack": "sl-token"},
    additional_claims={
        "role": "admin",
        "permissions": ["read", "write"],
        "org_id": "org-123"
    }
)

# Standard Bearer token
bearer_token = create_bearer_token(
    user_email="user@standard.com",
    server_secret="server-secret",
    connector_tokens={"gdrive": "drive-token"}
)

# North compatibility token
north_token = create_north_auth_token(
    user_email="user@north.com",
    server_secret="north-secret",
    connector_tokens={"google": "google-token", "slack": "slack-token"}
)
```

## OAuth Client Testing

### JWT-Based OAuth

```python
@pytest.mark.asyncio
async def test_jwt_oauth(create_oauth_client):
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="my-jwt-secret",
        jwt_algorithm="HS256",  # or RS256, etc.
        email_claim="email"     # JWT claim containing user email
    )
    
    token = create_oauth_bearer_token(
        user_email="jwt-user@example.com",
        jwt_secret="my-jwt-secret"
    )
    
    async with client:
        # Test custom route (optional auth)
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        assert response.json()["email"] == "jwt-user@example.com"
        
        # Test MCP endpoint (required auth)
        response = await client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
        }, headers={"Authorization": token})
        assert response.status_code != 401
```

### Custom OAuth Validator

```python
@pytest.mark.asyncio
async def test_custom_oauth(create_oauth_client):
    async def my_oauth_validator(token: str):
        # Your custom OAuth validation logic
        if token == "valid-company-token":
            return {
                "email": "employee@company.com",
                "connector_access_tokens": {"jira": "jira-token"}
            }
        return None
    
    client = await create_oauth_client(
        auth_type="custom",
        validator=my_oauth_validator
    )
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": "Bearer valid-company-token"
        })
        assert response.json()["email"] == "employee@company.com"
```

### OAuth Introspection

```python
@pytest.mark.asyncio
async def test_oauth_introspection(create_oauth_client):
    client = await create_oauth_client(
        auth_type="introspection",
        introspection_endpoint="https://oauth.company.com/introspect",
        client_id="mcp-server",
        client_secret="client-secret",
        email_claim="sub"  # or "email", depending on your OAuth server
    )
    
    # Test with a token that your OAuth server would validate
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": "Bearer real-oauth-access-token"
        })
        # This would make a real call to your introspection endpoint
```

## Multi-Provider Testing

```python
@pytest.mark.asyncio
async def test_multiple_auth_methods(create_multi_auth_client):
    client = await create_multi_auth_client([
        # Try OAuth first
        {"type": "oauth", "jwt_secret": "oauth-secret"},
        # Fallback to Bearer tokens
        {"type": "bearer", "server_secret": "bearer-secret"},
        # API keys as last resort
        {"type": "api_key", "valid_keys": ["api-key-123"]}
    ])
    
    async with client:
        # Test OAuth (highest priority)
        oauth_token = quick_oauth_bearer(secret="oauth-secret")
        response = await client.get("/auth-test", headers={
            "Authorization": oauth_token
        })
        assert response.json()["authenticated"] == True
        
        # Test Bearer token fallback
        bearer_token = quick_bearer_token(secret="bearer-secret")
        response = await client.get("/auth-test", headers={
            "Authorization": bearer_token
        })
        assert response.json()["authenticated"] == True
        
        # Test API key fallback
        response = await client.get("/auth-test", headers={
            "X-API-Key": "api-key-123"
        })
        assert response.json()["authenticated"] == True
```

## Testing Auth Failures

```python
@pytest.mark.asyncio
async def test_auth_failures(create_oauth_client):
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="correct-secret"
    )
    
    async with client:
        # Test invalid token (wrong secret)
        invalid_token = create_oauth_bearer_token(
            jwt_secret="wrong-secret"
        )
        response = await client.get("/auth-test", headers={
            "Authorization": invalid_token
        })
        assert response.json()["authenticated"] == False
        
        # Test MCP endpoint with invalid auth (should be 401)
        response = await client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
        }, headers={"Authorization": invalid_token})
        assert response.status_code == 401
        
        # Test no auth header
        response = await client.get("/auth-test")
        assert response.json()["authenticated"] == False
```

## Standard Test Routes

All test clients created with `create_oauth_client` and `create_multi_auth_client` include these standard routes:

- **`/auth-test`** (GET) - Custom route with optional auth, returns authentication status
- **`/health`** (GET) - Health check route (no auth required)
- **`/mcp`** (POST) - MCP protocol endpoint (auth required)

The `/auth-test` endpoint returns:
```json
{
  "authenticated": true,
  "email": "user@example.com",
  "connectors": ["github", "slack"]
}
```

## Best Practices

1. **Use matching secrets**: Always ensure your token creation uses the same secret as your client configuration
2. **Test both success and failure cases**: Test valid tokens, invalid tokens, and missing tokens
3. **Test different routes**: Test both custom routes (optional auth) and MCP endpoints (required auth)
4. **Use realistic data**: Use realistic email addresses and connector names in your tests
5. **Test multi-provider scenarios**: Ensure fallback authentication works as expected

## Integration with Existing Tests

You can import these utilities into any test file:

```python
from tests.test_utils import quick_oauth_bearer, create_oauth_client

# Use in existing test patterns
def test_my_existing_feature():
    token = quick_oauth_bearer()
    # ... rest of your test
```

These utilities are designed to be a drop-in replacement for manual token creation, making your authentication tests much more readable and maintainable.