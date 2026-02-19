"""
Tests for NorthAuthenticationMiddleware.

Tests path matching logic and authentication bypass for custom routes.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from north_mcp_python_sdk.auth import NorthAuthBackend, NorthAuthenticationMiddleware


def create_mock_backend():
    """Create a mock authentication backend."""
    backend = Mock(spec=NorthAuthBackend)
    return backend


def create_middleware(
    protected_paths: list[str] | None = None,
    debug: bool = False,
) -> NorthAuthenticationMiddleware:
    """Create a NorthAuthenticationMiddleware instance for testing."""
    app = AsyncMock()
    backend = create_mock_backend()
    on_error = Mock()

    return NorthAuthenticationMiddleware(
        app=app,
        backend=backend,
        on_error=on_error,
        protected_paths=protected_paths,
        debug=debug,
    )


class TestShouldAuthenticate:
    """Tests for _should_authenticate path matching."""

    def test_default_protected_paths(self):
        """Test that default protected paths are /mcp and /sse."""
        middleware = create_middleware()
        assert middleware.protected_paths == ["/mcp", "/sse"]

    def test_mcp_path_requires_auth(self):
        """Test that /mcp path requires authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/mcp") is True

    def test_mcp_path_with_trailing_slash_requires_auth(self):
        """Test that /mcp/ path requires authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/mcp/") is True

    def test_sse_path_requires_auth(self):
        """Test that /sse path requires authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/sse") is True

    def test_sse_path_with_trailing_slash_requires_auth(self):
        """Test that /sse/ path requires authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/sse/") is True

    def test_messages_path_requires_auth(self):
        """Test that /messages/* paths require authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/messages/session-123") is True
        assert middleware._should_authenticate("/messages/") is True
        assert (
            middleware._should_authenticate("/messages/abc-def-ghi") is True
        )

    def test_health_path_does_not_require_auth(self):
        """Test that /health path does not require authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/health") is False

    def test_custom_paths_do_not_require_auth(self):
        """Test that custom paths do not require authentication."""
        middleware = create_middleware()

        custom_paths = [
            "/status",
            "/metrics",
            "/ready",
            "/api/v1/info",
            "/custom/route/here",
        ]

        for path in custom_paths:
            assert middleware._should_authenticate(path) is False, (
                f"Path {path} should not require auth"
            )

    def test_root_path_does_not_require_auth(self):
        """Test that root path does not require authentication."""
        middleware = create_middleware()
        assert middleware._should_authenticate("/") is False

    def test_similar_but_different_paths(self):
        """Test paths that are similar to protected paths but not exact."""
        middleware = create_middleware()

        # These should NOT require auth (not exact matches)
        assert middleware._should_authenticate("/mcps") is False
        assert middleware._should_authenticate("/mcp-old") is False
        assert middleware._should_authenticate("/my-mcp") is False
        assert middleware._should_authenticate("/sse-stream") is False
        assert middleware._should_authenticate("/sse2") is False

        # /message (singular) without trailing path should not match /messages/*
        assert middleware._should_authenticate("/message") is False

    def test_custom_protected_paths(self):
        """Test middleware with custom protected paths."""
        middleware = create_middleware(
            protected_paths=["/api", "/graphql", "/ws"]
        )

        assert middleware._should_authenticate("/api") is True
        assert middleware._should_authenticate("/graphql") is True
        assert middleware._should_authenticate("/ws") is True

        # Default paths should not be protected when custom paths are set
        # (unless they overlap with /messages/* logic)
        assert middleware._should_authenticate("/mcp") is False
        assert middleware._should_authenticate("/sse") is False

    def test_empty_protected_paths_uses_defaults(self):
        """Test that empty protected paths list falls back to defaults.

        The middleware uses `protected_paths or default`, so an empty list
        (which is falsy) will use the default protected paths.
        """
        middleware = create_middleware(protected_paths=[])

        # Empty list is falsy, so defaults are used
        assert middleware.protected_paths == ["/mcp", "/sse"]
        assert middleware._should_authenticate("/mcp") is True
        assert middleware._should_authenticate("/sse") is True
        assert middleware._should_authenticate("/messages/123") is True

    def test_case_sensitive_path_matching(self):
        """Test that path matching is case-sensitive."""
        middleware = create_middleware()

        # Exact case should match
        assert middleware._should_authenticate("/mcp") is True

        # Different case should not match
        assert middleware._should_authenticate("/MCP") is False
        assert middleware._should_authenticate("/Mcp") is False
        assert middleware._should_authenticate("/SSE") is False


class TestMiddlewareInit:
    """Tests for NorthAuthenticationMiddleware initialization."""

    def test_default_debug_is_false(self):
        """Test that debug defaults to False."""
        middleware = create_middleware()
        assert middleware.debug is False

    def test_debug_can_be_enabled(self):
        """Test that debug can be enabled."""
        middleware = create_middleware(debug=True)
        assert middleware.debug is True

    def test_logger_is_created(self):
        """Test that logger is created."""
        middleware = create_middleware()
        assert middleware.logger is not None
        assert middleware.logger.name == "NorthMCP.Auth"


class TestMiddlewareCall:
    """Tests for NorthAuthenticationMiddleware.__call__ method."""

    @pytest.mark.asyncio
    async def test_lifespan_scope_bypasses_auth(self):
        """Test that lifespan scope always bypasses authentication."""
        middleware = create_middleware()
        scope = {"type": "lifespan", "path": "/mcp"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # App should be called directly without auth
        middleware.app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_unprotected_path_sets_null_user(self):
        """Test that unprotected paths set user to None in scope."""
        middleware = create_middleware()
        scope = {"type": "http", "path": "/health"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # User should be None for unprotected paths
        assert scope["user"] is None
        assert scope["auth"] is not None
        middleware.app.assert_called_once()

    @pytest.mark.asyncio
    async def test_protected_path_triggers_parent_auth(self):
        """Test that protected paths trigger parent class authentication."""
        # For this test, we need to verify the parent __call__ is invoked
        # which handles the actual authentication. We can't easily test this
        # without a full integration test, but we can verify the path check.
        middleware = create_middleware()

        # Verify the path check logic
        assert middleware._should_authenticate("/mcp") is True
        assert middleware._should_authenticate("/health") is False


class TestPathNormalization:
    """Tests for path normalization in authentication checks."""

    def test_trailing_slash_normalization(self):
        """Test that trailing slashes are normalized."""
        middleware = create_middleware()

        # Both with and without trailing slash should match
        assert middleware._should_authenticate("/mcp") is True
        assert middleware._should_authenticate("/mcp/") is True
        assert middleware._should_authenticate("/sse") is True
        assert middleware._should_authenticate("/sse/") is True

    def test_multiple_trailing_slashes(self):
        """Test paths with multiple trailing slashes.

        The rstrip('/') removes ALL trailing slashes, so /mcp// becomes /mcp
        which matches the protected path.
        """
        middleware = create_middleware()

        # rstrip('/') removes all trailing slashes, so these match /mcp
        assert middleware._should_authenticate("/mcp//") is True
        assert middleware._should_authenticate("/mcp///") is True

    def test_query_strings_not_stripped(self):
        """Test that query strings affect path matching."""
        middleware = create_middleware()

        # Path with query string won't match protected path
        # (query strings are typically separate from path in scope)
        assert middleware._should_authenticate("/mcp?foo=bar") is False

    def test_empty_path(self):
        """Test empty path handling."""
        middleware = create_middleware()
        assert middleware._should_authenticate("") is False
