"""
Test utilities for North MCP Python SDK authentication testing.

This module provides helper functions to create different types of authentication
tokens and clients for testing purposes.
"""

import json
import base64
import jwt
import httpx
import pytest_asyncio
from typing import Dict, Optional, Any, Callable
from starlette.requests import Request
from starlette.responses import JSONResponse

from north_mcp_python_sdk import NorthMCPServer, OAuthAuthProvider, BearerTokenAuthProvider, APIKeyAuthProvider
from north_mcp_python_sdk.auth import get_authenticated_user_optional


def create_bearer_token(
    user_email: str = "test@bearer.com",
    server_secret: str = "test-secret",
    connector_tokens: Optional[Dict[str, str]] = None
) -> str:
    """
    Create a Bearer token in the standard format.
    
    Args:
        user_email: Email for the user
        server_secret: Server secret for validation
        connector_tokens: Dictionary of connector access tokens
        
    Returns:
        Bearer token string with "Bearer " prefix
    """
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


def create_north_auth_token(
    user_email: str = "test@north.com",
    server_secret: str = "test-secret",
    connector_tokens: Optional[Dict[str, str]] = None
) -> str:
    """
    Create an auth token in North's current format (raw base64, no Bearer prefix).
    
    Args:
        user_email: Email for the user
        server_secret: Server secret for validation
        connector_tokens: Dictionary of connector access tokens
        
    Returns:
        Raw base64 token string (North's current format)
    """
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


def create_oauth_jwt_token(
    user_email: str = "test@oauth.com",
    connector_tokens: Optional[Dict[str, str]] = None,
    jwt_secret: str = "oauth-secret",
    jwt_algorithm: str = "HS256",
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create an OAuth JWT token for testing.
    
    Args:
        user_email: Email for the user
        connector_tokens: Dictionary of connector access tokens
        jwt_secret: Secret used to sign the JWT
        jwt_algorithm: Algorithm used to sign the JWT
        additional_claims: Additional claims to include in the JWT
        
    Returns:
        JWT token string (without Bearer prefix)
    """
    if connector_tokens is None:
        connector_tokens = {"oauth-connector": "oauth-token-123"}
    
    payload = {
        "email": user_email,
        "sub": user_email,
        "iat": 1234567890,
        "exp": 9999999999,  # Far future
        "connector_access_tokens": connector_tokens
    }
    
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)


def create_oauth_bearer_token(
    user_email: str = "test@oauth.com",
    connector_tokens: Optional[Dict[str, str]] = None,
    jwt_secret: str = "oauth-secret",
    jwt_algorithm: str = "HS256",
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create an OAuth Bearer token for testing.
    
    Args:
        user_email: Email for the user
        connector_tokens: Dictionary of connector access tokens
        jwt_secret: Secret used to sign the JWT
        jwt_algorithm: Algorithm used to sign the JWT
        additional_claims: Additional claims to include in the JWT
        
    Returns:
        Bearer token string with "Bearer " prefix
    """
    jwt_token = create_oauth_jwt_token(
        user_email=user_email,
        connector_tokens=connector_tokens,
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_algorithm,
        additional_claims=additional_claims
    )
    return f"Bearer {jwt_token}"


@pytest_asyncio.fixture
async def create_oauth_client():
    """
    Factory function to create OAuth test clients with different configurations.
    
    Usage:
        async def test_example(create_oauth_client):
            # JWT-based OAuth client
            client = await create_oauth_client(
                auth_type="jwt",
                jwt_secret="test-secret"
            )
            
            # Custom validator OAuth client  
            client = await create_oauth_client(
                auth_type="custom",
                validator=my_custom_validator
            )
            
            # Introspection-based OAuth client
            client = await create_oauth_client(
                auth_type="introspection",
                introspection_endpoint="https://oauth.example.com/introspect",
                client_id="test-client",
                client_secret="test-secret"
            )
    """
    
    async def _create_client(
        auth_type: str = "jwt",
        server_name: str = "OAuth Test Server",
        # JWT options
        jwt_secret: Optional[str] = None,
        jwt_algorithm: str = "HS256",
        # Introspection options
        introspection_endpoint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        # Custom validator option
        validator: Optional[Callable] = None,
        # General options
        email_claim: str = "email",
        debug: bool = True,
        # Additional auth providers
        additional_providers: Optional[list] = None
    ):
        """Create an OAuth test client with specified configuration."""
        
        # Create the appropriate OAuth provider based on auth_type
        if auth_type == "jwt":
            if jwt_secret is None:
                jwt_secret = "test-oauth-secret"
            
            oauth_provider = OAuthAuthProvider(
                jwt_secret=jwt_secret,
                jwt_algorithm=jwt_algorithm,
                email_claim=email_claim,
                debug=debug
            )
            
        elif auth_type == "introspection":
            if not all([introspection_endpoint, client_id, client_secret]):
                raise ValueError("Introspection auth requires introspection_endpoint, client_id, and client_secret")
            
            oauth_provider = OAuthAuthProvider(
                introspection_endpoint=introspection_endpoint,
                client_id=client_id,
                client_secret=client_secret,
                email_claim=email_claim,
                debug=debug
            )
            
        elif auth_type == "custom":
            if validator is None:
                # Default custom validator for testing
                async def default_validator(token: str) -> Optional[Dict[str, Any]]:
                    if token == "valid-oauth-token":
                        return {
                            "email": "oauth@example.com",
                            "connector_access_tokens": {"test": "token123"}
                        }
                    elif token.startswith("test-token-"):
                        user_id = token.split("-")[-1]
                        return {
                            "email": f"test-user-{user_id}@example.com",
                            "connector_access_tokens": {}
                        }
                    return None
                validator = default_validator
            
            oauth_provider = OAuthAuthProvider(
                custom_validator=validator,
                email_claim=email_claim,
                debug=debug
            )
            
        else:
            raise ValueError(f"Unknown auth_type: {auth_type}. Use 'jwt', 'introspection', or 'custom'")
        
        # Build provider list
        providers = [oauth_provider]
        if additional_providers:
            providers.extend(additional_providers)
        
        # Create server
        server = NorthMCPServer(
            name=server_name,
            auth_providers=providers,
            debug=debug
        )
        
        # Add standard test routes
        @server.custom_route("/auth-test", methods=["GET"])
        async def auth_test(request: Request) -> JSONResponse:
            """Standard auth test endpoint."""
            user = get_authenticated_user_optional()
            if user:
                return JSONResponse({
                    "authenticated": True,
                    "email": user.email,
                    "connectors": list(user.connector_access_tokens.keys())
                })
            else:
                return JSONResponse({"authenticated": False})
        
        @server.custom_route("/health", methods=["GET"])
        async def health(request: Request) -> JSONResponse:
            """Health check endpoint (no auth required)."""
            return JSONResponse({"status": "healthy"})
        
        # Create and return test client
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.streamable_http_app()),
            base_url="http://test"
        )
    
    return _create_client


@pytest_asyncio.fixture
async def create_multi_auth_client():
    """
    Factory function to create test clients with multiple authentication providers.
    
    Usage:
        async def test_example(create_multi_auth_client):
            client = await create_multi_auth_client([
                {"type": "oauth", "jwt_secret": "oauth-secret"},
                {"type": "bearer", "server_secret": "bearer-secret"},
                {"type": "api_key", "valid_keys": ["key1", "key2"]}
            ])
    """
    
    async def _create_client(
        auth_configs: list,
        server_name: str = "Multi-Auth Test Server",
        debug: bool = True
    ):
        """Create a multi-auth test client."""
        providers = []
        
        for config in auth_configs:
            auth_type = config.get("type")
            
            if auth_type == "oauth":
                provider = OAuthAuthProvider(
                    jwt_secret=config.get("jwt_secret", "test-secret"),
                    jwt_algorithm=config.get("jwt_algorithm", "HS256"),
                    email_claim=config.get("email_claim", "email"),
                    debug=debug
                )
            elif auth_type == "bearer":
                provider = BearerTokenAuthProvider(
                    server_secret=config.get("server_secret", "test-secret"),
                    debug=debug
                )
            elif auth_type == "api_key":
                provider = APIKeyAuthProvider(
                    valid_keys=config.get("valid_keys", ["test-key"]),
                    debug=debug
                )
            else:
                raise ValueError(f"Unknown auth type: {auth_type}")
            
            providers.append(provider)
        
        server = NorthMCPServer(
            name=server_name,
            auth_providers=providers,
            debug=debug
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
        
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.streamable_http_app()),
            base_url="http://test"
        )
    
    return _create_client


# Convenience functions for quick token creation
def quick_oauth_token(email: str = "test@oauth.com", secret: str = "test-secret") -> str:
    """Quick OAuth JWT token creation for simple tests."""
    return create_oauth_jwt_token(user_email=email, jwt_secret=secret)


def quick_oauth_bearer(email: str = "test@oauth.com", secret: str = "test-secret") -> str:
    """Quick OAuth Bearer token creation for simple tests."""
    return create_oauth_bearer_token(user_email=email, jwt_secret=secret)


def quick_bearer_token(email: str = "test@bearer.com", secret: str = "test-secret") -> str:
    """Quick Bearer token creation for simple tests."""
    return create_bearer_token(user_email=email, server_secret=secret)


def quick_north_token(email: str = "test@north.com", secret: str = "test-secret") -> str:
    """Quick North token creation for simple tests."""
    return create_north_auth_token(user_email=email, server_secret=secret)