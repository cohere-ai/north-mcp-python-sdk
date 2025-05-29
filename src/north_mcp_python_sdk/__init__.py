from typing import Any

from mcp.server.auth.provider import OAuthAuthorizationServerProvider
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

from .auth import AuthContextMiddleware, NorthAuthBackend, on_auth_error


class NorthMCPServer(FastMCP):
    def __init__(
        self,
        name: str | None = None,
        instructions: str | None = None,
        server_secret: str | None = None,
        auth_server_provider: OAuthAuthorizationServerProvider[Any, Any, Any]
        | None = None,
        **settings: Any,
    ):
        super().__init__(name, instructions, auth_server_provider, **settings)
        self._server_secret = server_secret

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
                backend=NorthAuthBackend(self._server_secret),
                on_error=on_auth_error,
            ),
            Middleware(AuthContextMiddleware),
        ]
        app.user_middleware.extend(middleware)
