"""
Tests for deprecation warnings in the auth module.

These tests verify that deprecated features emit proper warnings.
"""

import base64
import json
import warnings

import jwt
import pytest

from north_mcp_python_sdk.auth import NorthAuthBackend


def create_mock_connection(headers: dict[str, str]):
    """Create a mock HTTPConnection with headers."""
    from unittest.mock import Mock

    mock_conn = Mock()
    mock_conn.headers = headers
    mock_conn.client = Mock()
    mock_conn.client.host = "127.0.0.1"
    mock_conn.client.port = 12345
    return mock_conn


class TestServerSecretDeprecation:
    """Tests for X-North-Server-Secret deprecation warnings."""

    @pytest.mark.asyncio
    async def test_server_secret_header_emits_deprecation_warning(self):
        """Test that X-North-Server-Secret header emits deprecation warning."""
        backend = NorthAuthBackend(server_secret="server_secret")

        user_id_token = jwt.encode(
            payload={"email": "test@company.com"}, key="test"
        )
        headers = {
            "X-North-ID-Token": user_id_token,
            "X-North-Server-Secret": "server_secret",
        }
        conn = create_mock_connection(headers)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await backend.authenticate(conn)

            # Check that a deprecation warning was issued
            deprecation_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1

            # Check the warning message
            warning_messages = [str(dw.message) for dw in deprecation_warnings]
            assert any(
                "X-North-Server-Secret is deprecated" in msg
                for msg in warning_messages
            )

    @pytest.mark.asyncio
    async def test_no_server_secret_no_deprecation_warning(self):
        """Test that no warning when server secret is not used."""
        backend = NorthAuthBackend()

        user_id_token = jwt.encode(
            payload={"email": "test@company.com"}, key="test"
        )
        headers = {"X-North-ID-Token": user_id_token}
        conn = create_mock_connection(headers)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await backend.authenticate(conn)

            # Filter for server secret deprecation warnings specifically
            server_secret_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
                and "X-North-Server-Secret" in str(warning.message)
            ]
            assert len(server_secret_warnings) == 0


class TestConnectorTokensDeprecation:
    """Tests for X-North-Connector-Tokens deprecation warnings."""

    @pytest.mark.asyncio
    async def test_connector_tokens_header_emits_deprecation_warning(self):
        """Test that X-North-Connector-Tokens header emits deprecation warning."""
        backend = NorthAuthBackend()

        user_id_token = jwt.encode(
            payload={"email": "test@company.com"}, key="test"
        )
        connector_tokens = {"google": "token123"}
        connector_tokens_b64 = (
            base64.urlsafe_b64encode(json.dumps(connector_tokens).encode())
            .decode()
            .rstrip("=")
        )

        headers = {
            "X-North-ID-Token": user_id_token,
            "X-North-Connector-Tokens": connector_tokens_b64,
        }
        conn = create_mock_connection(headers)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await backend.authenticate(conn)

            # Check for connector tokens deprecation warning
            deprecation_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1

            warning_messages = [str(dw.message) for dw in deprecation_warnings]
            assert any(
                "X-North-Connector-Tokens is deprecated" in msg
                for msg in warning_messages
            )

    @pytest.mark.asyncio
    async def test_no_connector_tokens_no_deprecation_warning(self):
        """Test that no warning when connector tokens are not used."""
        backend = NorthAuthBackend()

        user_id_token = jwt.encode(
            payload={"email": "test@company.com"}, key="test"
        )
        headers = {"X-North-ID-Token": user_id_token}
        conn = create_mock_connection(headers)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await backend.authenticate(conn)

            # Filter for connector tokens deprecation warnings specifically
            connector_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
                and "X-North-Connector-Tokens" in str(warning.message)
            ]
            assert len(connector_warnings) == 0


class TestLegacyBearerDeprecation:
    """Tests for legacy Bearer token auth deprecation behavior."""

    @pytest.mark.asyncio
    async def test_legacy_bearer_with_server_secret(self):
        """Test that legacy bearer with server secret emits deprecation warning."""
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

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await backend.authenticate(conn)

            # Legacy bearer with server_secret should trigger the deprecation
            # warning from _validate_server_secret
            deprecation_warnings = [
                warning
                for warning in w
                if issubclass(warning.category, DeprecationWarning)
                and "X-North-Server-Secret" in str(warning.message)
            ]
            assert len(deprecation_warnings) >= 1


class TestGetAuthenticatedUserDeprecation:
    """Tests for get_authenticated_user deprecation."""

    def test_get_authenticated_user_is_deprecated(self):
        """Test that get_authenticated_user function is marked deprecated."""
        from north_mcp_python_sdk.auth import get_authenticated_user
        import inspect

        # Check if the function has deprecation decorator
        # This is indicated by checking the function's __wrapped__ attribute
        # or by looking at the source
        source = inspect.getsource(get_authenticated_user)
        assert "@deprecated" in source or "deprecated" in source.lower()
