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
