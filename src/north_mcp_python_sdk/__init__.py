import logging
import os
from typing import Any, List, Optional

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware

from .auth import (
    AuthContextMiddleware, 
    NorthAuthBackend, 
    NorthAuthenticationMiddleware, 
    on_auth_error, 
    get_authenticated_user_optional,
    AuthProvider,
    BearerTokenAuthProvider,
    APIKeyAuthProvider,
    OAuthAuthProvider,
)


def is_debug_mode() -> bool:
    """Check if debug mode should be enabled based on environment variable."""
    return os.getenv('DEBUG', '').lower() in ('true', '1', 'yes', 'on')


class NorthMCPServer(FastMCP):
    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        auth_providers: Optional[List[AuthProvider]] = None,
        auth_server_provider: OAuthAuthorizationServerProvider[Any, Any, Any]
        | None = None,
        debug: bool | None = None,
        **settings: Any,
    ):
        """
        Initialize North MCP Server with modular authentication.
        
        Args:
            name: Server name
            instructions: Server instructions
            server_secret: Legacy server secret (for backward compatibility)
            auth_providers: List of authentication providers to use. If None, defaults to BearerTokenAuthProvider
            auth_server_provider: OAuth server provider (legacy)
            debug: Enable debug mode
            **settings: Additional settings
        """
        super().__init__(name, instructions, auth_server_provider, **settings)
        self._server_secret = server_secret
        self._auth_providers = auth_providers
        
        # Auto-enable debug mode from environment variable if not explicitly set
        if debug is None:
            self._debug = is_debug_mode()
        else:
            self._debug = debug
        
        # Configure logging for debug mode
        if self._debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.debug("Debug mode enabled for North MCP Server")
        else:
            self._logger = logging.getLogger(f"NorthMCP.{name or 'Server'}")
            self._logger.setLevel(logging.INFO)

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        app = super().sse_app(mount_path=mount_path)
        middleware = [
            Middleware(
                NorthAuthenticationMiddleware,
                backend=NorthAuthBackend(
                    providers=self._auth_providers, 
                    server_secret=self._server_secret, 
                    debug=self._debug
                ),
                on_error=on_auth_error,
                debug=self._debug,
            ),
            Middleware(AuthContextMiddleware, debug=self._debug),
        ]
        app.user_middleware.extend(middleware)
        return app

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        middleware = [
            Middleware(
                NorthAuthenticationMiddleware,
                backend=NorthAuthBackend(
                    providers=self._auth_providers, 
                    server_secret=self._server_secret, 
                    debug=self._debug
                ),
                on_error=on_auth_error,
                debug=self._debug,
            ),
            Middleware(AuthContextMiddleware, debug=self._debug),
        ]
        app.user_middleware.extend(middleware)
        return app


# Convenience exports
__all__ = [
    "NorthMCPServer",
    "get_authenticated_user_optional",
    "is_debug_mode",
    "AuthProvider",
    "BearerTokenAuthProvider", 
    "APIKeyAuthProvider",
    "OAuthAuthProvider",
]
