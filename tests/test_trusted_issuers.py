import json
import pytest
from base64 import b64encode
import jwt
import httpx
import pytest_asyncio

from north_mcp_python_sdk import NorthMCPServer
from north_mcp_python_sdk.auth import AuthHeaderTokens


class TestTrustedIssuers:
    """Test cases for trusted issuer verification functionality."""

    @pytest_asyncio.fixture(scope="module")
    async def server_with_trusted_issuers(self):
        """Server fixture configured with trusted issuers."""
        server = NorthMCPServer(
            name="test-server",
            trusted_issuers=["https://example.okta.com"],
            debug=True
        )
        return server

    @pytest_asyncio.fixture(scope="module") 
    async def test_client_with_trusted_issuers(self, server_with_trusted_issuers):
        """Test client for server with trusted issuers."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server_with_trusted_issuers.streamable_http_app()),
            base_url="https://mcptest.com"
        ) as client:
            yield client

    @staticmethod
    def create_test_token(payload: dict, headers: dict = None) -> str:
        """Helper to create test JWT tokens."""
        return jwt.encode(
            payload=payload,
            key="test-secret",
            algorithm="HS256",
            headers=headers or {"kid": "test-key-id"}
        )

    @staticmethod
    def create_auth_header(user_id_token: str = None) -> str:
        """Helper to create base64 encoded auth header."""
        if user_id_token is None:
            user_id_token = TestTrustedIssuers.create_test_token({
                "email": "test@example.com", 
                "iss": "https://example.okta.com"
            })
        
        header = AuthHeaderTokens(
            server_secret=None,
            user_id_token=user_id_token,
            connector_access_tokens={"slack": "test-token"}
        )
        header_json = json.dumps(header.model_dump())
        return b64encode(header_json.encode()).decode()

    def test_server_initialization_with_trusted_issuers(self):
        """Test that server initializes correctly with trusted_issuers parameter."""
        trusted_issuers = ["https://cohere.okta.com", "http://localhost:5556/dex"]
        server = NorthMCPServer(name="test-server", trusted_issuers=trusted_issuers)
        assert server._trusted_issuers == trusted_issuers

    def test_server_initialization_without_trusted_issuers(self):
        """Test that server initializes correctly without trusted_issuers parameter."""
        server = NorthMCPServer(name="test-server")
        assert server._trusted_issuers is None

    @pytest.mark.asyncio
    async def test_no_trusted_issuers_skips_verification(self):
        """Test that signature verification is skipped when no trusted issuers are configured."""
        server = NorthMCPServer(name="test-server")  # No trusted_issuers
        
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.streamable_http_app()),
            base_url="https://mcptest.com"
        ) as client:
            token = TestTrustedIssuers.create_test_token({
                "email": "test@example.com", 
                "iss": "https://untrusted.example.com"
            })
            auth_header = TestTrustedIssuers.create_auth_header(user_id_token=token)
            
            result = await client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {auth_header}"},
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            )
            
            assert 200 <= result.status_code <= 307

    @pytest.mark.asyncio
    async def test_untrusted_issuer_rejected(self, test_client_with_trusted_issuers):
        """Test that tokens from untrusted issuers are rejected."""
        token = TestTrustedIssuers.create_test_token({
            "email": "test@example.com",
            "iss": "https://untrusted.example.com"  # Not in trusted list
        })
        auth_header = TestTrustedIssuers.create_auth_header(user_id_token=token)
        
        result = await test_client_with_trusted_issuers.post(
            "/mcp",
            headers={"Authorization": f"Bearer {auth_header}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        
        assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_issuer_claim(self, test_client_with_trusted_issuers):
        """Test that tokens without issuer claim are rejected."""
        token = TestTrustedIssuers.create_test_token({"email": "test@example.com"})  # No 'iss' claim
        auth_header = TestTrustedIssuers.create_auth_header(user_id_token=token)
        
        result = await test_client_with_trusted_issuers.post(
            "/mcp",
            headers={"Authorization": f"Bearer {auth_header}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        
        assert result.status_code == 401

    @pytest.mark.asyncio 
    async def test_missing_kid_header(self, test_client_with_trusted_issuers):
        """Test that tokens without 'kid' header are rejected."""
        token = jwt.encode(
            payload={"email": "test@example.com", "iss": "https://example.okta.com"},
            key="test-secret",
            algorithm="HS256",
            headers={}  # No 'kid' header
        )
        auth_header = TestTrustedIssuers.create_auth_header(user_id_token=token)
        
        result = await test_client_with_trusted_issuers.post(
            "/mcp",
            headers={"Authorization": f"Bearer {auth_header}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        
        assert result.status_code == 401
