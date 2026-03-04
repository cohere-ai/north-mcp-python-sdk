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


def create_x_north_headers(email: str = "test@company.com") -> dict[str, str]:
    """Helper to create valid X-North headers."""
    user_id_token = jwt.encode(payload={"email": email}, key="does-not-matter")
    connector_tokens_json = json.dumps(
        {"google": "token123", "slack": "token456"}
    )
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
async def test_x_north_headers_success():
    """Test successful X-North authentication with all headers."""
    backend = NorthAuthBackend(server_secret="server_secret")
    headers = create_x_north_headers("test@company.com")
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "test@company.com"
    assert user.access_token.claims["connector_access_tokens"] == {
        "google": "token123",
        "slack": "token456",
    }


@pytest.mark.asyncio
async def test_x_north_headers_invalid_auth():
    """Test X-North authentication failures (wrong secret, bad tokens, missing email)."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # Wrong server secret
    headers = create_x_north_headers()
    headers["X-North-Server-Secret"] = "wrong_secret"
    conn = create_mock_connection(headers)

    with pytest.raises(AuthenticationError, match="access denied"):
        await backend.authenticate(conn)

    # Invalid connector tokens - should succeed but with empty connector tokens
    # (code logs a warning but doesn't raise an error for invalid format)
    headers = create_x_north_headers()
    headers["X-North-Connector-Tokens"] = "invalid_base64!@#"
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    # Invalid tokens are silently ignored, resulting in empty dict
    assert user.access_token.claims["connector_access_tokens"] == {}

    # JWT missing email - should succeed but with no email (legacy behavior)
    invalid_jwt = jwt.encode(payload={"name": "test"}, key="test")
    headers = create_x_north_headers()
    headers["X-North-ID-Token"] = invalid_jwt
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert (
        user.access_token.claims["email"] is None
    )  # email should be None when missing from token


@pytest.mark.asyncio
async def test_x_north_takes_precedence_over_bearer():
    """Test X-North headers take precedence over Authorization Bearer."""
    from north_mcp_python_sdk.auth import AuthHeaderTokens

    backend = NorthAuthBackend(server_secret="server_secret")

    # Create conflicting tokens
    legacy_token = jwt.encode(
        payload={"email": "legacy@company.com"}, key="test"
    )
    legacy_header = AuthHeaderTokens(
        server_secret="server_secret",
        user_id_token=legacy_token,
        connector_access_tokens={"legacy": "legacy_token"},
    )
    legacy_b64 = base64.b64encode(
        json.dumps(legacy_header.model_dump()).encode()
    ).decode()

    # X-North should win
    headers = {
        **create_x_north_headers("xnorth@company.com"),
        "Authorization": f"Bearer {legacy_b64}",
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    # Should use X-North headers
    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "xnorth@company.com"
    assert "google" in user.access_token.claims["connector_access_tokens"]


@pytest.mark.asyncio
async def test_legacy_bearer_fallback():
    """Test legacy Authorization Bearer works when no X-North headers."""
    from north_mcp_python_sdk.auth import AuthHeaderTokens

    backend = NorthAuthBackend(server_secret="server_secret")

    user_token = jwt.encode(
        payload={"email": "legacy@company.com"}, key="test"
    )
    legacy_header = AuthHeaderTokens(
        server_secret="server_secret",
        user_id_token=user_token,
        connector_access_tokens={"legacy": "legacy_token"},
    )
    legacy_b64 = base64.b64encode(
        json.dumps(legacy_header.model_dump()).encode()
    ).decode()

    headers = {"Authorization": f"Bearer {legacy_b64}"}
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "legacy@company.com"
    assert user.access_token.claims["connector_access_tokens"] == {
        "legacy": "legacy_token"
    }


@pytest.mark.asyncio
async def test_minimal_x_north_headers():
    """Test X-North with minimal headers (just server secret)."""
    backend = NorthAuthBackend(server_secret="server_secret")

    headers = {"X-North-Server-Secret": "server_secret"}
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] is None
    assert user.access_token.claims["connector_access_tokens"] == {}


@pytest.mark.asyncio
async def test_x_north_user_email_header_fallback():
    """Test X-North-User-Email header as fallback when no email in ID token."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # ID token without email claim
    user_id_token = jwt.encode(payload={"name": "Test User"}, key="test")
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
        "X-North-User-Email": "fallback@company.com",
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "fallback@company.com"


@pytest.mark.asyncio
async def test_x_north_user_email_header_not_override_token_email():
    """Test that ID token email takes precedence over X-North-User-Email."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # ID token with email claim
    user_id_token = jwt.encode(
        payload={"email": "token@company.com"}, key="test"
    )
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
        "X-North-User-Email": "header@company.com",
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    # Token email should take precedence
    assert user.access_token.claims["email"] == "token@company.com"


@pytest.mark.asyncio
async def test_x_north_user_email_with_server_secret_only():
    """Test X-North-User-Email with only server secret (no ID token)."""
    backend = NorthAuthBackend(server_secret="server_secret")

    headers = {
        "X-North-Server-Secret": "server_secret",
        "X-North-User-Email": "email@company.com",
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "email@company.com"


@pytest.mark.asyncio
async def test_x_north_empty_headers_treated_as_absent():
    """Test that empty X-North headers are treated as absent."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # Empty strings should be treated as if the header is not present
    headers = {
        "X-North-ID-Token": "",
        "X-North-Server-Secret": "server_secret",
    }
    conn = create_mock_connection(headers)

    # Should still succeed with just server secret since ID-Token is empty
    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)



@pytest.mark.asyncio
async def test_no_auth_headers_present():
    """Test error when no authentication headers are provided at all."""
    backend = NorthAuthBackend()

    headers = {}
    conn = create_mock_connection(headers)

    with pytest.raises(AuthenticationError, match="invalid authorization"):
        await backend.authenticate(conn)


@pytest.mark.asyncio
async def test_x_north_id_token_only():
    """Test X-North with only ID token (no server secret)."""
    backend = NorthAuthBackend()  # No server secret configured

    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="test"
    )
    headers = {"X-North-ID-Token": user_id_token}
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    assert isinstance(user, AuthenticatedUser)
    assert user.access_token.claims["email"] == "test@company.com"


@pytest.mark.asyncio
async def test_connector_tokens_non_string_values_filtered():
    """Test that connector tokens with non-string values are filtered out."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # Create connector tokens with mixed types
    connector_tokens = {
        "valid_string": "token123",
        "invalid_number": 12345,  # Should be filtered
        "invalid_bool": True,  # Should be filtered
        "invalid_null": None,  # Should be filtered
        "another_valid": "token456",
    }
    connector_tokens_json = json.dumps(connector_tokens)
    connector_tokens_b64 = (
        base64.urlsafe_b64encode(connector_tokens_json.encode())
        .decode()
        .rstrip("=")
    )

    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="test"
    )
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
        "X-North-Connector-Tokens": connector_tokens_b64,
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    # Only string:string pairs should be included
    assert user.access_token.claims["connector_access_tokens"] == {
        "valid_string": "token123",
        "another_valid": "token456",
    }


@pytest.mark.asyncio
async def test_connector_tokens_non_dict_ignored():
    """Test that connector tokens that aren't objects are ignored."""
    backend = NorthAuthBackend(server_secret="server_secret")

    # Array instead of object
    connector_tokens_json = json.dumps(["token1", "token2"])
    connector_tokens_b64 = (
        base64.urlsafe_b64encode(connector_tokens_json.encode())
        .decode()
        .rstrip("=")
    )

    user_id_token = jwt.encode(
        payload={"email": "test@company.com"}, key="test"
    )
    headers = {
        "X-North-ID-Token": user_id_token,
        "X-North-Server-Secret": "server_secret",
        "X-North-Connector-Tokens": connector_tokens_b64,
    }
    conn = create_mock_connection(headers)

    auth_response = await backend.authenticate(conn)
    if auth_response is None:
        raise ValueError("Authentication response is None")
    _, user = auth_response

    # Non-dict values result in empty connector tokens
    assert user.access_token.claims["connector_access_tokens"] == {}


