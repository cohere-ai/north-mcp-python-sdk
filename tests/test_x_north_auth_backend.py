import base64
import json
from unittest.mock import Mock

import jwt
import pytest

from north_mcp_python_sdk.auth import (
    AuthContextMiddleware,
    AuthenticatedNorthUser,
    NorthAuthBackend,
)
from north_mcp_python_sdk.north_context import (
    DEFAULT_USER_ID_TOKEN_HEADER,
    NORTH_CONTEXT_SCOPE_KEY,
    get_north_request_context,
)
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

    credentials, user = await backend.authenticate(conn)

    assert isinstance(user, AuthenticatedNorthUser)
    assert user.user_id_token == headers[DEFAULT_USER_ID_TOKEN_HEADER]
    assert user.email == "test@company.com"
    assert user.connector_access_tokens == {
        "google": "token123",
        "slack": "token456",
    }
    assert conn.scope[NORTH_CONTEXT_SCOPE_KEY] == user.north_context


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

    # Invalid connector tokens
    headers = create_x_north_headers()
    headers["X-North-Connector-Tokens"] = "invalid_base64!@#"
    conn = create_mock_connection(headers)

    with pytest.raises(
        AuthenticationError, match="invalid connector tokens format"
    ):
        await backend.authenticate(conn)

    # JWT missing email - should succeed but with no email (legacy behavior)
    invalid_jwt = jwt.encode(payload={"name": "test"}, key="test")
    headers = create_x_north_headers()
    headers["X-North-ID-Token"] = invalid_jwt
    conn = create_mock_connection(headers)

    credentials, user = await backend.authenticate(conn)
    assert isinstance(user, AuthenticatedNorthUser)
    assert user.email is None  # email should be None when missing from token


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

    credentials, user = await backend.authenticate(conn)

    # Should use X-North headers
    assert user.user_id_token == headers[DEFAULT_USER_ID_TOKEN_HEADER]
    assert user.email == "xnorth@company.com"
    assert "google" in user.connector_access_tokens
    assert conn.scope[NORTH_CONTEXT_SCOPE_KEY] == user.north_context


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

    credentials, user = await backend.authenticate(conn)

    assert user.email == "legacy@company.com"
    assert user.connector_access_tokens == {"legacy": "legacy_token"}
    assert user.user_id_token == user_token
    assert conn.scope[NORTH_CONTEXT_SCOPE_KEY] == user.north_context


@pytest.mark.asyncio
async def test_minimal_x_north_headers():
    """Test X-North with minimal headers (just server secret)."""
    backend = NorthAuthBackend(server_secret="server_secret")

    headers = {"X-North-Server-Secret": "server_secret"}
    conn = create_mock_connection(headers)

    credentials, user = await backend.authenticate(conn)

    assert isinstance(user, AuthenticatedNorthUser)
    assert user.email is None
    assert user.connector_access_tokens == {}
    assert user.user_id_token is None
    assert conn.scope[NORTH_CONTEXT_SCOPE_KEY] == user.north_context


@pytest.mark.asyncio
async def test_auth_context_middleware_shares_request_context():
    """Auth context middleware should expose the shared request context."""

    recorded_context = None

    async def app(scope, receive, send):
        nonlocal recorded_context
        recorded_context = get_north_request_context()
        assert scope["state"]["north_context"] == recorded_context

    middleware = AuthContextMiddleware(app)
    scope = {
        "type": "http",
        "user": AuthenticatedNorthUser(
            connector_access_tokens={"google": "token123"},
            email="user@company.com",
            user_id_token="id-token",
        ),
        "state": {},
    }

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        pass

    await middleware(scope, receive, send)

    assert recorded_context is not None
    assert recorded_context.connector_tokens == {"google": "token123"}
    assert recorded_context.user_id_token == "id-token"
    # Context should reset after the middleware call.
    assert get_north_request_context().connector_tokens == {}
