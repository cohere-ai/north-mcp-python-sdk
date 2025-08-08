import logging
import os
from typing import Any

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from .auth import (
    AuthContextMiddleware,
    HeadersContextMiddleware,
    NorthAuthBackend,
    on_auth_error,
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
        auth_server_provider: OAuthAuthorizationServerProvider[Any, Any, Any]
        | None = None,
        debug: bool | None = None,
        **settings: Any,
    ):
        super().__init__(name, instructions, auth_server_provider, **settings)
        self._server_secret = server_secret
        
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
        self._add_middleware(app)
        return app

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        self._add_middleware(app)
        return app

    def _add_middleware(self, app: Starlette) -> None:
        middleware = [
            Middleware(
                AuthenticationMiddleware,
                backend=NorthAuthBackend(self._server_secret, debug=self._debug),
                on_error=on_auth_error,
            ),
            Middleware(AuthContextMiddleware, debug=self._debug),
            Middleware(HeadersContextMiddleware, debug=self._debug),
        ]
        app.user_middleware.extend(middleware)
