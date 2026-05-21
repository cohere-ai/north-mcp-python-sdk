"""
Tests for utility functions in the north_mcp_python_sdk package.
"""

import os
from unittest.mock import patch


from north_mcp_python_sdk import is_debug_mode, is_verbose_mode


class TestIsDebugMode:
    """Tests for is_debug_mode() function."""

    def test_debug_mode_true_values(self):
        """Test that various 'true' values enable debug mode."""
        true_values = [
            "true",
            "True",
            "TRUE",
            "1",
            "yes",
            "Yes",
            "YES",
            "on",
            "On",
            "ON",
        ]

        for value in true_values:
            with patch.dict(os.environ, {"DEBUG": value}):
                assert is_debug_mode() is True, (
                    f"DEBUG={value} should enable debug mode"
                )

    def test_debug_mode_false_values(self):
        """Test that other values disable debug mode."""
        false_values = [
            "false",
            "False",
            "FALSE",
            "0",
            "no",
            "No",
            "NO",
            "off",
            "Off",
            "OFF",
            "",
            "random",
            "debug",
        ]

        for value in false_values:
            with patch.dict(os.environ, {"DEBUG": value}):
                assert is_debug_mode() is False, (
                    f"DEBUG={value} should disable debug mode"
                )

    def test_debug_mode_unset(self):
        """Test that unset DEBUG env var disables debug mode."""
        env = os.environ.copy()
        env.pop("DEBUG", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_debug_mode() is False

    def test_debug_mode_whitespace(self):
        """Test that whitespace around values is handled correctly."""
        # The current implementation doesn't strip whitespace,
        # so " true" would be false
        with patch.dict(os.environ, {"DEBUG": " true"}):
            # This will be False because " true".lower() != "true"
            assert is_debug_mode() is False

        with patch.dict(os.environ, {"DEBUG": "true "}):
            # This will be False because "true ".lower() != "true"
            assert is_debug_mode() is False


class TestIsVerboseMode:
    """Tests for is_verbose_mode() function."""

    def test_verbose_mode_true_values(self):
        for value in ("true", "1", "yes", "on"):
            with patch.dict(os.environ, {"VERBOSE": value}):
                assert is_verbose_mode() is True

    def test_verbose_mode_false_when_unset(self):
        env = os.environ.copy()
        env.pop("VERBOSE", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_verbose_mode() is False


class TestNorthMCPServerVerboseMode:
    """Tests for NorthMCPServer verbose mode initialization."""

    def test_server_verbose_mode_from_env(self):
        from north_mcp_python_sdk import NorthMCPServer

        with patch.dict(os.environ, {"VERBOSE": "true"}):
            server = NorthMCPServer(name="test")
            assert server._verbose is True

    def test_server_verbose_mode_explicit_override(self):
        from north_mcp_python_sdk import NorthMCPServer

        with patch.dict(os.environ, {"VERBOSE": "true"}):
            server = NorthMCPServer(name="test", verbose=False)
            assert server._verbose is False

    def test_server_verbose_mode_default(self):
        from north_mcp_python_sdk import NorthMCPServer

        env = os.environ.copy()
        env.pop("VERBOSE", None)
        with patch.dict(os.environ, env, clear=True):
            server = NorthMCPServer(name="test")
            assert server._verbose is False


class TestNorthMCPServerDebugMode:
    """Tests for NorthMCPServer debug mode initialization."""

    def test_server_debug_mode_from_env(self):
        """Test that server picks up debug mode from environment."""
        from north_mcp_python_sdk import NorthMCPServer

        with patch.dict(os.environ, {"DEBUG": "true"}):
            server = NorthMCPServer(name="test")
            assert server._debug is True

    def test_server_debug_mode_explicit_true(self):
        """Test that explicit debug=True overrides environment."""
        from north_mcp_python_sdk import NorthMCPServer

        with patch.dict(os.environ, {"DEBUG": "false"}):
            server = NorthMCPServer(name="test", debug=True)
            assert server._debug is True

    def test_server_debug_mode_explicit_false(self):
        """Test that explicit debug=False overrides environment."""
        from north_mcp_python_sdk import NorthMCPServer

        with patch.dict(os.environ, {"DEBUG": "true"}):
            server = NorthMCPServer(name="test", debug=False)
            assert server._debug is False

    def test_server_debug_mode_default(self):
        """Test that debug defaults to False when env is not set."""
        from north_mcp_python_sdk import NorthMCPServer

        env = os.environ.copy()
        env.pop("DEBUG", None)
        with patch.dict(os.environ, env, clear=True):
            server = NorthMCPServer(name="test")
            assert server._debug is False


class TestPackageExports:
    """Tests for package __all__ exports."""

    def test_all_exports_importable(self):
        """Test that all items in __all__ can be imported."""
        from north_mcp_python_sdk import __all__

        expected_exports = [
            "NorthMCPServer",
            "NorthTokenVerifier",
            "TraceContextFormatter",
            "get_north_context",
            "get_tracer",
            "is_debug_mode",
            "is_verbose_mode",
            "traced_span",
        ]

        assert set(__all__) == set(expected_exports)

    def test_north_mcp_server_import(self):
        """Test that NorthMCPServer can be imported."""
        from north_mcp_python_sdk import NorthMCPServer

        assert NorthMCPServer is not None

    def test_north_token_verifier_import(self):
        """Test that NorthTokenVerifier can be imported."""
        from north_mcp_python_sdk import NorthTokenVerifier

        assert NorthTokenVerifier is not None

    def test_get_north_context_import(self):
        """Test that get_north_context can be imported."""
        from north_mcp_python_sdk import get_north_context

        assert get_north_context is not None

    def test_is_debug_mode_import(self):
        """Test that is_debug_mode can be imported."""
        from north_mcp_python_sdk import is_debug_mode

        assert is_debug_mode is not None

    def test_is_verbose_mode_import(self):
        """Test that is_verbose_mode can be imported."""
        from north_mcp_python_sdk import is_verbose_mode

        assert is_verbose_mode is not None


class TestAuthModuleExports:
    """Tests for auth module exports."""

    def test_auth_models_importable(self):
        """Test that auth models can be imported."""
        from north_mcp_python_sdk.auth import (
            AuthHeaderTokens,
            AuthenticatedNorthUser,
            AuthenticatedNorthUserClaims,
        )

        assert AuthHeaderTokens is not None
        assert AuthenticatedNorthUser is not None
        assert AuthenticatedNorthUserClaims is not None

    def test_auth_backend_importable(self):
        """Test that auth backend classes can be imported."""
        from north_mcp_python_sdk.auth import (
            NorthAuthBackend,
            NorthAuthenticationMiddleware,
            NorthTokenVerifier,
        )

        assert NorthAuthBackend is not None
        assert NorthAuthenticationMiddleware is not None
        assert NorthTokenVerifier is not None

    def test_auth_functions_importable(self):
        """Test that auth functions can be imported."""
        from north_mcp_python_sdk.auth import (
            get_authenticated_user,
            get_north_context,
            on_auth_error,
        )

        assert get_authenticated_user is not None
        assert get_north_context is not None
        assert on_auth_error is not None


class TestAuthenticatedNorthUser:
    """Tests for AuthenticatedNorthUser class."""

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUser

        user = AuthenticatedNorthUser(
            connector_access_tokens={"google": "token123"},
            email="test@example.com",
        )

        assert user.connector_access_tokens == {"google": "token123"}
        assert user.email == "test@example.com"

    def test_init_with_no_email(self):
        """Test initialization without email."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUser

        user = AuthenticatedNorthUser(
            connector_access_tokens={"slack": "token456"},
        )

        assert user.connector_access_tokens == {"slack": "token456"}
        assert user.email is None

    def test_init_with_empty_connectors(self):
        """Test initialization with empty connector tokens."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUser

        user = AuthenticatedNorthUser(
            connector_access_tokens={},
            email="test@example.com",
        )

        assert user.connector_access_tokens == {}
        assert user.email == "test@example.com"


class TestAuthenticatedNorthUserClaims:
    """Tests for AuthenticatedNorthUserClaims Pydantic model."""

    def test_model_validation(self):
        """Test that the model validates correctly."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUserClaims

        claims = AuthenticatedNorthUserClaims(
            connector_access_tokens={"google": "token"},
            email="test@example.com",
        )

        assert claims.connector_access_tokens == {"google": "token"}
        assert claims.email == "test@example.com"

    def test_model_dump(self):
        """Test that the model can be dumped to dict."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUserClaims

        claims = AuthenticatedNorthUserClaims(
            connector_access_tokens={"slack": "token123"},
            email="user@test.com",
        )

        dumped = claims.model_dump()
        assert dumped == {
            "connector_access_tokens": {"slack": "token123"},
            "email": "user@test.com",
        }

    def test_model_with_none_email(self):
        """Test model with None email."""
        from north_mcp_python_sdk.auth import AuthenticatedNorthUserClaims

        claims = AuthenticatedNorthUserClaims(
            connector_access_tokens={},
            email=None,
        )

        assert claims.email is None


class TestAuthHeaderTokens:
    """Tests for AuthHeaderTokens Pydantic model."""

    def test_model_validation(self):
        """Test that the model validates correctly."""
        from north_mcp_python_sdk.auth import AuthHeaderTokens

        tokens = AuthHeaderTokens(
            server_secret="secret123",
            user_id_token="jwt.token.here",
            connector_access_tokens={"google": "token"},
        )

        assert tokens.server_secret == "secret123"
        assert tokens.user_id_token == "jwt.token.here"
        assert tokens.connector_access_tokens == {"google": "token"}

    def test_model_with_none_values(self):
        """Test model with None values for optional fields."""
        from north_mcp_python_sdk.auth import AuthHeaderTokens

        tokens = AuthHeaderTokens(
            server_secret=None,
            user_id_token=None,
            connector_access_tokens={},
        )

        assert tokens.server_secret is None
        assert tokens.user_id_token is None
        assert tokens.connector_access_tokens == {}

    def test_default_connector_tokens(self):
        """Test that connector_access_tokens defaults to empty dict."""
        from north_mcp_python_sdk.auth import AuthHeaderTokens

        tokens = AuthHeaderTokens(
            server_secret=None,
            user_id_token=None,
        )

        assert tokens.connector_access_tokens == {}
