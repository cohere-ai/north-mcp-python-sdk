import base64
import json
from unittest.mock import Mock

import jwt
import pytest

from north_mcp_python_sdk.auth import NorthAuthBackend, AuthenticatedNorthUser
from north_mcp_python_sdk.north_context import NORTH_CONTEXT_SCOPE_KEY
from starlette.authentication import AuthenticationError


def create_mock_connection(headers: dict[str, str]) -> Mock:
    """Create a mock HTTPConnection with headers."""
    mock_conn = Mock()
    mock_conn.headers = headers
    mock_conn.client = Mock()
    mock_conn.client.host = "127.0.0.1"
    mock_conn.client.port = 12345
    mock_conn.scope = {"type": "http", "state": {}}
    return mock_conn


def create_x_north_headers_with_issuer(
    email: str = "test@company.com", issuer: str = "https://example.okta.com"
) -> dict[str, str]:
    """Helper to create X-North headers with specific issuer."""
    user_id_token = jwt.encode(
        payload={"email": email, "iss": issuer},
        key="does-not-matter",
        headers={"kid": "test-key-id"},
    )
    connector_tokens_json = json.dumps({"google": "token123"})
    connector_tokens_b64 = (
        base64.urlsafe_b64encode(connector_tokens_json.encode())
        .decode()
        .rstrip("=")
    )

    return {
        "X-North-ID-Token": user_id_token,
        "X-North-Connector-Tokens": connector_tokens_b64,
        "X-North-Server-Secret": "server_secret",
    }


@pytest.mark.asyncio
async def test_x_north_headers_without_trusted_issuers():
    """Test X-North headers work normally when no trusted issuers configured."""
    backend = NorthAuthBackend(
        server_secret="server_secret",
        trusted_issuers=None,  # No signature verification
    )

    # Token from any issuer should work
    headers = create_x_north_headers_with_issuer(
        email="test@company.com", issuer="https://untrusted.example.com"
    )
    conn = create_mock_connection(headers)

    credentials, user = await backend.authenticate(conn)

    assert isinstance(user, AuthenticatedNorthUser)
    assert user.email == "test@company.com"
    assert conn.scope[NORTH_CONTEXT_SCOPE_KEY] == user.north_context


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_missing_issuer():
    """Test X-North headers reject tokens missing issuer when trusted issuers configured."""
    backend = NorthAuthBackend(
        server_secret="server_secret",
        trusted_issuers=["https://example.okta.com"],
    )

    # Token without issuer claim
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"},  # No 'iss' claim
        key="does-not-matter",
    )
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
    }
    conn = create_mock_connection(headers)

    with pytest.raises(
        AuthenticationError, match="invalid user id token: token missing issuer"
    ):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_untrusted_issuer():
    """Test X-North headers reject tokens from untrusted issuers."""
    backend = NorthAuthBackend(
        server_secret="server_secret",
        trusted_issuers=["https://example.okta.com"],  # Only trust this issuer
    )

    # Token from untrusted issuer
    headers = create_x_north_headers_with_issuer(
        email="test@company.com",
        issuer="https://malicious.example.com",  # Not in trusted list
    )
    conn = create_mock_connection(headers)

    with pytest.raises(
        AuthenticationError, match="invalid user id token: untrusted issuer"
    ):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_missing_kid():
    """Test X-North headers reject tokens missing key ID when trusted issuers configured."""
    backend = NorthAuthBackend(
        server_secret="server_secret",
        trusted_issuers=["https://example.okta.com"],
    )

    # Token without 'kid' header
    user_id_token = jwt.encode(
        payload={
            "email": "test@company.com",
            "iss": "https://example.okta.com",
        },
        key="does-not-matter",
        headers={},  # No 'kid' header
    )
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
    }
    conn = create_mock_connection(headers)

    with pytest.raises(
        AuthenticationError,
        match="invalid user id token: token missing key identifier",
    ):
        await backend.authenticate(conn)
