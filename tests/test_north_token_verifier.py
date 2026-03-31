"""
Tests for NorthTokenVerifier class.

NorthTokenVerifier is a FastMCP AuthProvider that wraps NorthAuthBackend
and provides authentication middleware for MCP servers.
"""

import base64
import json

import httpx
import jwt
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastmcp import FastMCP
from starlette.authentication import AuthenticationError

from north_mcp_python_sdk.auth import (
    NorthAuthBackend,
    NorthAuthenticationMiddleware,
    NorthTokenVerifier,
    on_auth_error,
)


class TestNorthTokenVerifierInit:
    """Test NorthTokenVerifier initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        verifier = NorthTokenVerifier()

        assert verifier.trusted_issuers is None
        assert verifier.server_secret is None
        assert verifier.debug is False
        assert isinstance(verifier.backend, NorthAuthBackend)

    def test_init_with_trusted_issuers(self):
        """Test initialization with trusted issuers."""
        issuers = ["https://auth.example.com", "https://auth2.example.com"]
        verifier = NorthTokenVerifier(trusted_issuers=issuers)

        assert verifier.trusted_issuers == issuers
        assert verifier.backend._trusted_issuers == issuers

    def test_init_with_server_secret(self):
        """Test initialization with server secret."""
        verifier = NorthTokenVerifier(server_secret="my-secret")

        assert verifier.server_secret == "my-secret"
        assert verifier.backend._server_secret == "my-secret"

    def test_init_with_debug_enabled(self):
        """Test initialization with debug mode enabled."""
        verifier = NorthTokenVerifier(debug=True)

        assert verifier.debug is True
        assert verifier.backend.debug is True

    def test_init_with_all_options(self):
        """Test initialization with all options specified."""
        verifier = NorthTokenVerifier(
            trusted_issuers=["https://auth.example.com"],
            server_secret="secret-123",
            debug=True,
        )

        assert verifier.trusted_issuers == ["https://auth.example.com"]
        assert verifier.server_secret == "secret-123"
        assert verifier.debug is True


class TestNorthTokenVerifierMiddleware:
    """Test NorthTokenVerifier middleware generation."""

    def test_get_middleware_returns_list(self):
        """Test that get_middleware returns a list of middleware."""
        verifier = NorthTokenVerifier()
        middleware = verifier.get_middleware()

        assert isinstance(middleware, list)
        assert len(middleware) == 1

    def test_middleware_uses_north_authentication_middleware(self):
        """Test that the middleware uses NorthAuthenticationMiddleware."""
        verifier = NorthTokenVerifier()
        middleware = verifier.get_middleware()

        # The middleware should be configured with NorthAuthenticationMiddleware
        assert middleware[0].cls == NorthAuthenticationMiddleware

    def test_middleware_passes_backend(self):
        """Test that the middleware is configured with the correct backend."""
        verifier = NorthTokenVerifier(server_secret="test-secret")
        middleware = verifier.get_middleware()

        # Check middleware kwargs contain the backend
        assert "backend" in middleware[0].kwargs
        assert middleware[0].kwargs["backend"] is verifier.backend

    def test_middleware_passes_debug_flag(self):
        """Test that the middleware receives the debug flag."""
        verifier = NorthTokenVerifier(debug=True)
        middleware = verifier.get_middleware()

        assert "debug" in middleware[0].kwargs
        assert middleware[0].kwargs["debug"] is True


class TestNorthTokenVerifierVerifyToken:
    """Test NorthTokenVerifier.verify_token method."""

    @pytest.mark.asyncio
    async def test_verify_token_raises_error(self):
        """Test that verify_token raises AuthenticationError.

        NorthTokenVerifier doesn't use FastMCP's token verification flow;
        it uses middleware instead. The verify_token method should raise.
        """
        verifier = NorthTokenVerifier()

        with pytest.raises(
            AuthenticationError, match="Could not verify token"
        ):
            await verifier.verify_token("any-token")


class TestNorthTokenVerifierIntegration:
    """Integration tests for NorthTokenVerifier with FastMCP."""

    @staticmethod
    def create_auth_header(
        server_secret: str | None = None,
        email: str = "test@example.com",
    ) -> str:
        """Create a valid authentication header."""
        user_id_token = jwt.encode(payload={"email": email}, key="test-secret")
        auth_data = {
            "server_secret": server_secret,
            "user_id_token": user_id_token,
            "connector_access_tokens": {},
        }
        encoded = base64.b64encode(json.dumps(auth_data).encode()).decode()
        return f"Bearer {encoded}"

    @pytest_asyncio.fixture
    async def fastmcp_with_north_auth(self):
        """Create FastMCP server with NorthTokenVerifier."""
        auth = NorthTokenVerifier()
        mcp = FastMCP("test-server", auth=auth)

        @mcp.tool()
        def echo(message: str) -> str:
            return f"Echo: {message}"

        app = mcp.http_app(transport="streamable-http")
        async with LifespanManager(app) as manager:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=manager.app),
                base_url="http://test",
            ) as client:
                yield client

    @pytest_asyncio.fixture
    async def fastmcp_with_secret(self):
        """Create FastMCP server with NorthTokenVerifier and server secret."""
        auth = NorthTokenVerifier(server_secret="test-secret")
        mcp = FastMCP("test-server", auth=auth)

        @mcp.tool()
        def echo(message: str) -> str:
            return f"Echo: {message}"

        app = mcp.http_app(transport="streamable-http")
        async with LifespanManager(app) as manager:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=manager.app),
                base_url="http://test",
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_mcp_route_allows_requests_without_auth_by_default(
        self, fastmcp_with_north_auth
    ):
        """Test that MCP routes do not require auth when no auth is configured."""
        response = await fastmcp_with_north_auth.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_mcp_route_with_valid_auth(self, fastmcp_with_north_auth):
        """Test that MCP routes work with valid authentication."""
        auth_header = self.create_auth_header()
        response = await fastmcp_with_north_auth.post(
            "/mcp",
            headers={"Authorization": auth_header},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_server_secret_validation(self, fastmcp_with_secret):
        """Test that server secret is validated."""
        # Without secret - should fail
        auth_header = self.create_auth_header(server_secret=None)
        response = await fastmcp_with_secret.post(
            "/mcp",
            headers={"Authorization": auth_header},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_server_secret_auth_requires_headers(
        self, fastmcp_with_secret
    ):
        """Test that MCP routes require auth when server secret auth is configured."""
        response = await fastmcp_with_secret.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )
        assert response.status_code == 401

        # With wrong secret - should fail
        auth_header = self.create_auth_header(server_secret="wrong-secret")
        response = await fastmcp_with_secret.post(
            "/mcp",
            headers={"Authorization": auth_header},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )
        assert response.status_code == 401

        # With correct secret - should work
        auth_header = self.create_auth_header(server_secret="test-secret")
        response = await fastmcp_with_secret.post(
            "/mcp",
            headers={"Authorization": auth_header},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        assert response.status_code != 401


class TestOnAuthError:
    """Test the on_auth_error helper function."""

    def test_on_auth_error_returns_json_response(self):
        """Test that on_auth_error returns a JSONResponse."""
        from unittest.mock import Mock

        mock_conn = Mock()
        error = AuthenticationError("test error message")

        response = on_auth_error(mock_conn, error)

        assert response.status_code == 401
        # Decode the body to check content
        body = json.loads(response.body.decode())
        assert body == {"error": "test error message"}

    def test_on_auth_error_with_different_messages(self):
        """Test on_auth_error with various error messages."""
        from unittest.mock import Mock

        mock_conn = Mock()

        test_messages = [
            "access denied",
            "invalid token",
            "no authentication headers present",
            "Token missing issuer",
        ]

        for message in test_messages:
            error = AuthenticationError(message)
            response = on_auth_error(mock_conn, error)
            body = json.loads(response.body.decode())
            assert body["error"] == message
