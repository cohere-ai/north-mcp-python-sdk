"""
Comparison showing how OAuth testing utilities simplify test code.

This file demonstrates the difference between manual token creation
and using the new testing utilities.
"""

import jwt
import json
import base64
import httpx
from north_mcp_python_sdk import NorthMCPServer, OAuthAuthProvider


# =============================================================================
# BEFORE: Manual OAuth Testing (verbose and error-prone)
# =============================================================================

async def test_oauth_manual_way():
    """Example of testing OAuth authentication the manual way."""
    
    # 1. Manually create OAuth provider
    oauth_provider = OAuthAuthProvider(
        jwt_secret="test-oauth-secret",
        jwt_algorithm="HS256",
        debug=True
    )
    
    # 2. Manually create server
    server = NorthMCPServer(
        name="Manual OAuth Test",
        auth_providers=[oauth_provider],
        debug=True
    )
    
    # 3. Manually add test routes
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from north_mcp_python_sdk.auth import get_authenticated_user_optional
    
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
    
    # 4. Manually create JWT token
    payload = {
        "email": "manual-user@example.com",
        "sub": "manual-user@example.com",
        "iat": 1234567890,
        "exp": 9999999999,
        "connector_access_tokens": {"github": "github-token-123"}
    }
    jwt_token = jwt.encode(payload, "test-oauth-secret", algorithm="HS256")
    bearer_token = f"Bearer {jwt_token}"
    
    # 5. Manually create HTTP client
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.streamable_http_app()),
        base_url="http://test"
    ) as client:
        
        response = await client.get("/auth-test", headers={
            "Authorization": bearer_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "manual-user@example.com"
        assert "github" in data["connectors"]


# =============================================================================
# AFTER: Using OAuth Testing Utilities (clean and simple)
# =============================================================================

async def test_oauth_with_utilities(create_oauth_client):
    """Example of testing OAuth authentication with utilities."""
    from tests.test_utils import create_oauth_bearer_token
    
    # 1. Create OAuth client in one line
    client = await create_oauth_client(
        auth_type="jwt",
        jwt_secret="test-oauth-secret"
    )
    
    # 2. Create token in one line  
    token = create_oauth_bearer_token(
        user_email="utility-user@example.com",
        jwt_secret="test-oauth-secret",
        connector_tokens={"github": "github-token-123"}
    )
    
    # 3. Test (client already has auth-test route)
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] == True
        assert data["email"] == "utility-user@example.com"
        assert "github" in data["connectors"]


# =============================================================================
# Even simpler with quick helpers
# =============================================================================

async def test_oauth_super_simple(create_oauth_client):
    """Ultra-simple OAuth testing with quick helpers."""
    from tests.test_utils import quick_oauth_bearer
    
    # Create everything with minimal code
    client = await create_oauth_client(auth_type="jwt", jwt_secret="secret")
    token = quick_oauth_bearer(email="simple@example.com", secret="secret")
    
    async with client:
        response = await client.get("/auth-test", headers={
            "Authorization": token
        })
        
        assert response.status_code == 200
        assert response.json()["authenticated"] == True


# =============================================================================
# Multi-provider testing comparison
# =============================================================================

async def test_multi_auth_manual():
    """Manual multi-provider setup (lots of boilerplate)."""
    from north_mcp_python_sdk import BearerTokenAuthProvider, APIKeyAuthProvider
    
    # Manually create each provider
    oauth_provider = OAuthAuthProvider(jwt_secret="oauth-secret", debug=True)
    bearer_provider = BearerTokenAuthProvider(server_secret="bearer-secret", debug=True)
    api_provider = APIKeyAuthProvider(valid_keys=["api-key-123"], debug=True)
    
    # Manually create server
    server = NorthMCPServer(
        name="Multi Auth Test",
        auth_providers=[oauth_provider, bearer_provider, api_provider],
        debug=True
    )
    
    # ... lots more manual setup code ...


async def test_multi_auth_with_utilities(create_multi_auth_client):
    """Multi-provider setup with utilities (one function call)."""
    from tests.test_utils import quick_oauth_bearer, quick_bearer_token
    
    # Create multi-auth client in one line
    client = await create_multi_auth_client([
        {"type": "oauth", "jwt_secret": "oauth-secret"},
        {"type": "bearer", "server_secret": "bearer-secret"},
        {"type": "api_key", "valid_keys": ["api-key-123"]}
    ])
    
    async with client:
        # Test OAuth
        oauth_token = quick_oauth_bearer(secret="oauth-secret")
        response = await client.get("/auth-test", headers={"Authorization": oauth_token})
        assert response.json()["authenticated"] == True
        
        # Test Bearer
        bearer_token = quick_bearer_token(secret="bearer-secret")
        response = await client.get("/auth-test", headers={"Authorization": bearer_token})
        assert response.json()["authenticated"] == True
        
        # Test API Key
        response = await client.get("/auth-test", headers={"X-API-Key": "api-key-123"})
        assert response.json()["authenticated"] == True


if __name__ == "__main__":
    print("🧪 OAuth Testing Utilities Comparison")
    print("\nBEFORE: Manual testing required ~50 lines of boilerplate code")
    print("AFTER:  Utility-based testing requires ~10 lines of code")
    print("\nKey benefits:")
    print("✅ Less boilerplate code")
    print("✅ Consistent token formats")
    print("✅ Built-in test routes")
    print("✅ Easy multi-provider testing")
    print("✅ Reduced test maintenance")
    print("✅ Fewer authentication-related test bugs")