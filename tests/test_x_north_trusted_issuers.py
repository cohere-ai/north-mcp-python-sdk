import base64
import json
from unittest.mock import Mock

import jwt
import pytest

from north_mcp_python_sdk.auth import NorthAuthBackend
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from starlette.authentication import AuthenticationError


def create_mock_connection(headers: dict[str, str]) -> Mock:
    """Create a mock HTTPConnection with headers."""
    mock_conn = Mock()
    mock_conn.headers = headers
    mock_conn.client = Mock()
    mock_conn.client.host = "127.0.0.1"
    mock_conn.client.port = 12345
    return mock_conn


def create_x_north_headers_with_issuer(
    email: str = "test@company.com",
    issuer: str = "https://example.okta.com",
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

    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Connector-Tokens": connector_tokens_b64,
    }
    return headers


@pytest.mark.asyncio
async def test_x_north_headers_without_trusted_issuers():
    """Test X-North headers work normally when no trusted issuers configured."""
    backend = NorthAuthBackend(
        trusted_issuers=None,  # No signature verification
    )

    # Token from any issuer should work
    headers = create_x_north_headers_with_issuer(
        email="test@company.com", issuer="https://untrusted.example.com"
    )
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "test@company.com"


@pytest.mark.asyncio
async def test_auth_without_configuration_allows_missing_headers():
    backend = NorthAuthBackend()
    conn = create_mock_connection({})

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.token == ""
    assert user.access_token.claims["email"] is None


@pytest.mark.asyncio
async def test_auth_without_configuration_still_parses_x_north_headers():
    backend = NorthAuthBackend()
    headers = create_x_north_headers_with_issuer(
        email="test@company.com",
        issuer="https://untrusted.example.com",
    )
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "test@company.com"
    assert user.access_token.claims["connector_access_tokens"] == {
        "google": "token123"
    }


@pytest.mark.asyncio
async def test_trusted_issuers_require_auth_headers():
    backend = NorthAuthBackend(
        trusted_issuers=["https://example.okta.com"],
    )
    conn = create_mock_connection({})

    with pytest.raises(
        AuthenticationError, match="invalid authorization header"
    ):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_trusted_issuers_reject_email_header_without_id_token():
    backend = NorthAuthBackend(
        trusted_issuers=["https://example.okta.com"],
    )
    conn = create_mock_connection(
        {"X-North-User-Email": "fallback@company.com"}
    )

    with pytest.raises(
        AuthenticationError, match="invalid authorization header"
    ):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_trusted_issuers_reject_connector_tokens_without_id_token():
    backend = NorthAuthBackend(
        trusted_issuers=["https://example.okta.com"],
    )
    connector_tokens_json = json.dumps({"github": "token123"})
    connector_tokens_b64 = (
        base64.urlsafe_b64encode(connector_tokens_json.encode())
        .decode()
        .rstrip("=")
    )
    conn = create_mock_connection(
        {
            "X-North-Connector-Tokens": connector_tokens_b64,
            "X-North-User-Email": "fallback@company.com",
        }
    )

    with pytest.raises(
        AuthenticationError, match="no authentication headers present"
    ):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_missing_issuer():
    """Test X-North headers reject tokens missing issuer when trusted issuers configured."""
    backend = NorthAuthBackend(
        trusted_issuers=["https://example.okta.com"],
    )

    # Token without issuer claim
    user_id_token = jwt.encode(
        payload={"email": "test@company.com"},  # No 'iss' claim
        key="does-not-matter",
    )
    headers = {
        "X-North-ID-Token": user_id_token,
    }
    conn = create_mock_connection(headers)

    with pytest.raises(AuthenticationError, match="Token missing issuer"):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_untrusted_issuer():
    """Test X-North headers reject tokens from untrusted issuers."""
    backend = NorthAuthBackend(
        trusted_issuers=["https://example.okta.com"],  # Only trust this issuer
    )

    # Token from untrusted issuer
    headers = create_x_north_headers_with_issuer(
        email="test@company.com",
        issuer="https://malicious.example.com",  # Not in trusted list
    )
    conn = create_mock_connection(headers)

    with pytest.raises(AuthenticationError, match="Untrusted issuer"):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_headers_trusted_issuers_missing_kid():
    """Test X-North headers reject tokens missing key ID when trusted issuers configured."""
    backend = NorthAuthBackend(
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
    }
    conn = create_mock_connection(headers)

    with pytest.raises(
        AuthenticationError, match="Token missing key identifier"
    ):
        await backend.authenticate(conn)
